"""Main entry point — market-hours scheduler loop.

Schedule:
  09:15 IST: Auth with Kite, init all components
  Every 5-15 min during market hours:
    -> Fetch candles for watchlist
    -> Run strategies -> raw signals
    -> Researcher -> Sentinel -> Orchestrator -> Stitch
    -> Filter -> Rank -> Top N
    -> Risk guardrails -> Position sizing -> Execute
    -> Check existing positions for exit conditions
  15:30 IST: Close positions, daily summary, persist metrics

Approval workflow:
  Signal found -> Pending queue -> Telegram notification with buttons
  User taps Approve -> Execute trade (manual exit management)
  User taps Auto-Sell -> Execute trade + AI exit triggers (no human intervention)
  User taps Ignore -> Signal discarded
  Signal expires after 15 min if no action
"""

from __future__ import annotations

import os
import signal
import sys
import uuid
from datetime import datetime, time as dtime
from typing import Any, Dict, List, Optional

import structlog
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.agents.orchestrator import OrchestratorAgent
from src.agents.researcher import ResearcherAgent
from src.agents.sentinel import SentinelAgent
from src.agents.stitch import StitchAgent
from src.config import AppConfig, load_config
from src.data.kite_client import KiteClient
from src.data.macro_data import MacroDataFetcher
from src.data.market_data import MarketDataFetcher
from src.data.news_feed import NewsFeed
from src.execution.auto_exit import AutoExitMonitor
from src.execution.auto_sell import AutoSellManager
from src.execution.order_manager import OrderManager
from src.execution.paper_broker import PaperBroker
from src.feedback.memory_writer import MemoryWriter
from src.feedback.postmortem_agent import PostmortemAgent
from src.feedback.postmortem_pipeline import PostmortemPipeline
from src.models import (
    AutoSellTrigger,
    Direction,
    ExitReason,
    GTTStatus,
    MarketRegime,
    PendingSignal,
    ScoredSignal,
    SignalStatus,
    TradeAction,
)
from src.notifications.telegram import TelegramNotifier
from src.notifications.whatsapp import WhatsAppNotifier
from src.regime.detector import RegimeDetector
from src.risk.kill_switch import KillSwitch
from src.risk.portfolio import Portfolio
from src.scoring.filters import apply_filters
from src.storage.database import Database
from src.strategies.base import Strategy
from src.strategies.bollinger_squeeze import BollingerSqueezeStrategy
from src.strategies.golden_cross import GoldenCrossStrategy
from src.strategies.mean_reversion import MeanReversionStrategy
from src.strategies.momentum import MomentumStrategy
from src.strategies.seasonal import SeasonalStrategy
from src.strategies.vwap_reversion import VWAPReversionStrategy

logger = structlog.get_logger(__name__)


class TradingEngine:
    """Core trading engine that orchestrates the full pipeline.

    Designed to be used by the scheduler during market hours,
    or manually for single-cycle runs.

    Supports two execution modes:
    - Direct: Signals auto-execute (legacy, for fully automated operation)
    - Approval: Signals go to pending queue, user approves via Telegram/Dashboard
    """

    def __init__(self, config: AppConfig, on_event: Optional[Any] = None) -> None:
        """Initialize the trading engine.

        Args:
            config: Application configuration.
            on_event: Optional callback(event_type, data) for UI updates.
                      event_type: "alert", "signal", "trade", "error",
                                  "insight", "pending_signal", "auto_sell"
        """
        self._config = config
        self._on_event = on_event
        self._db = Database(config.database.url)
        self._db.create_tables()

        # Kite Connect — prefer the Neon-backed session (Cloudflare Worker
        # writes the token after the user logs in via Telegram link). Falls
        # back to the local file cache for legacy/offline dev.
        self._kite_client = KiteClient(db=self._db)
        self._kite_client.authenticate()
        self._kite = self._kite_client.kite

        # Data providers
        self._market_data = MarketDataFetcher(
            self._kite, rate_limit_per_sec=config.data.rate_limit_per_sec
        )
        self._macro_data = MacroDataFetcher(self._kite)
        self._news_feed = NewsFeed()

        # Strategies
        self._strategies = self._init_strategies()

        # AI Agents
        self._researcher = ResearcherAgent(config.agents)
        self._sentinel = SentinelAgent(config.agents)
        self._orchestrator = OrchestratorAgent(config.agents, config.scoring)
        self._stitch = StitchAgent(config.scoring)

        # Regime detection
        self._regime_detector = RegimeDetector()
        self._current_regime: Optional[MarketRegime] = None

        # Risk management
        self._portfolio = Portfolio(db=self._db)
        self._kill_switch = KillSwitch(portfolio=self._portfolio, config=config.risk, db=self._db)

        # Execution
        if config.execution.mode == "paper":
            broker = PaperBroker(
                market_data=self._market_data,
                config=config.execution.paper,
            )
        else:
            from src.execution.live_broker import LiveBroker
            broker = LiveBroker(kite=self._kite)

        self._order_manager = OrderManager(
            broker=broker,
            portfolio=self._portfolio,
            kill_switch=self._kill_switch,
            config=config,
            db=self._db,
        )

        self._auto_exit = AutoExitMonitor()

        # Auto-sell manager (dual protection: GTT on exchange + software monitor)
        self._broker = broker
        self._auto_sell = AutoSellManager(
            broker=broker,
            config=config.execution.auto_sell,
            db=self._db,
        )

        # Reconcile GTT state on startup (check if GTTs are still active on exchange)
        self._reconcile_gtt_on_startup()

        # Pending signals queue (approval workflow)
        self._pending_signals: Dict[str, PendingSignal] = {}  # signal_id -> PendingSignal
        self._load_pending_signals()

        # Notifications
        self._telegram = TelegramNotifier()
        self._whatsapp = WhatsAppNotifier()

        # Self-improvement memory pipeline (postmortem → Telegram → memory/*.md)
        self._postmortem_pipeline = PostmortemPipeline(
            agent=PostmortemAgent(config.agents),
            writer=MemoryWriter(),
            telegram=self._telegram,
            db=self._db,
        )

        # Start Telegram callback polling for button responses
        if self._telegram.is_configured:
            self._telegram.start_callback_polling(self._handle_telegram_callback)

        # Watchlist
        self._watchlist = [s.symbol for s in config.watchlist.symbols]
        self._sector_map = {s.symbol: s.sector for s in config.watchlist.symbols}

        # Instrument token cache
        self._instrument_tokens: Dict[str, int] = {}

        logger.info(
            "engine_initialized",
            mode=config.execution.mode,
            watchlist_size=len(self._watchlist),
            strategies=len(self._strategies),
        )

    def _load_pending_signals(self) -> None:
        """Restore pending signals from database on startup."""
        rows = self._db.load_pending_signals()
        for row in rows:
            try:
                signal = ScoredSignal.model_validate_json(row["signal_json"])
                pending = PendingSignal(
                    signal_id=row["signal_id"],
                    signal=signal,
                    created_at=row["created_at"],
                    expiry_minutes=row["expiry_minutes"],
                    telegram_message_id=row.get("telegram_message_id"),
                    status=SignalStatus(row["status"]),
                )
                # Skip if already expired
                if pending.is_expired:
                    pending.status = SignalStatus.EXPIRED
                    self._db.update_pending_signal_status(
                        row["signal_id"], "expired", None
                    )
                    continue

                self._pending_signals[row["signal_id"]] = pending
            except Exception as e:
                logger.warning(
                    "pending_signal_load_error",
                    signal_id=row.get("signal_id"),
                    error=str(e),
                )

        if self._pending_signals:
            logger.info("pending_signals_loaded", count=len(self._pending_signals))

    def _reconcile_gtt_on_startup(self) -> None:
        """Check GTT status on exchange for all active triggers after restart."""
        unprotected = self._auto_sell.reconcile_on_startup()

        for symbol in unprotected:
            position = self._portfolio.get_position(symbol)
            trigger = self._auto_sell.get_trigger(symbol)
            if not position or not trigger:
                continue

            # Re-place GTT for unprotected positions
            if self._auto_sell._should_place_gtt():
                try:
                    ltp_data = self._kite.ltp([f"NSE:{symbol}"])
                    last_price = ltp_data.get(f"NSE:{symbol}", {}).get("last_price", 0)
                    if last_price > 0:
                        result = self._auto_sell._place_gtt_with_retry(
                            trigger, position.quantity, last_price
                        )
                        if result.success:
                            trigger.gtt_trigger_id = result.trigger_id
                            trigger.gtt_status = GTTStatus.ACTIVE
                            trigger.gtt_stop_price = trigger.stop_loss
                            trigger.gtt_last_updated = datetime.utcnow()
                            if self._db:
                                self._db.save_auto_sell_trigger(trigger)
                            logger.info("gtt_re_placed_on_startup", symbol=symbol)
                except Exception as e:
                    logger.error("gtt_startup_replacement_failed", symbol=symbol, error=str(e))

        if unprotected:
            logger.warning("gtt_startup_unprotected", symbols=unprotected)

    def _init_strategies(self) -> List[Strategy]:
        strategies: List[Strategy] = []
        toggle = self._config.strategies
        if toggle.mean_reversion.enabled:
            strategies.append(MeanReversionStrategy())
        if toggle.momentum.enabled:
            strategies.append(MomentumStrategy())
        if toggle.bollinger_squeeze.enabled:
            strategies.append(BollingerSqueezeStrategy())
        if toggle.golden_cross.enabled:
            strategies.append(GoldenCrossStrategy())
        if toggle.vwap_reversion.enabled:
            strategies.append(VWAPReversionStrategy())
        if toggle.seasonal.enabled:
            strategies.append(SeasonalStrategy())
        return strategies

    def run_cycle(self) -> None:
        """Execute one full analysis -> execution cycle."""
        logger.info("cycle_start")
        self._emit("alert", {"message": "Scan cycle starting...", "level": "info"})

        if self._kill_switch.check():
            logger.warning("cycle_blocked_kill_switch")
            self._emit("alert", {"message": "Cycle blocked — kill switch active", "level": "error"})
            return

        try:
            # 0. Expire old pending signals
            self._expire_pending_signals()

            # 0b. Monitor auto-sell positions
            self._monitor_auto_sell_positions()

            # 1. Fetch macro context
            macro = self._macro_data.get_snapshot()
            macro_dict = self._macro_to_dict(macro)

            # Emit macro insight
            nifty_str = f"\u20b9{macro.nifty_price:,.0f}" if macro.nifty_price else "N/A"
            vix_str = f"{macro.india_vix:.1f}" if macro.india_vix else "N/A"
            nifty_chg = f"{macro.nifty_change_pct:+.2f}%" if macro.nifty_change_pct else ""
            self._emit("insight", {
                "type": "macro",
                "title": "Market Context",
                "data": {
                    "nifty": f"{nifty_str} ({nifty_chg})",
                    "vix": vix_str,
                    "direction": macro.market_direction,
                    "risk_off": macro.is_risk_off,
                    "regime": self._current_regime.value if self._current_regime else "unknown",
                },
            })

            # 2. Update regime
            self._update_regime()

            # 3. Fetch news
            news_items = self._news_feed.fetch()

            # Emit news headlines to dashboard
            news_headlines = [
                {"title": item.title, "source": item.source}
                for item in news_items[:10]
            ]
            self._emit("insight", {
                "type": "news",
                "title": f"News Feed ({len(news_items)} headlines)",
                "data": {"headlines": news_headlines},
            })

            # 4. Run Researcher on news
            researcher_output = self._researcher.analyze_news(
                news_items, macro_dict, self._watchlist
            )

            # Emit researcher analysis
            self._emit("insight", {
                "type": "research",
                "title": "AI Research Analysis",
                "data": {
                    "sentiment": researcher_output.get("sentiment", "NEUTRAL"),
                    "news_strength": researcher_output.get("news_strength", 0),
                    "key_drivers": researcher_output.get("key_drivers", []),
                    "urgency": researcher_output.get("urgency", "LOW"),
                    "affected_sectors": researcher_output.get("affected_sectors", []),
                    "summary": researcher_output.get("summary", "No analysis available"),
                    "entities": [
                        {"symbol": e.get("symbol", ""), "sentiment": e.get("sentiment", "")}
                        for e in researcher_output.get("entities", [])[:10]
                    ],
                },
            })

            # 5. Scan strategies across watchlist
            strategy_signals = self._scan_all_strategies()

            # Emit strategy scan results
            self._emit("insight", {
                "type": "strategies",
                "title": f"Strategy Scan ({len(strategy_signals)} raw signals)",
                "data": {
                    "signals": [
                        {
                            "symbol": s.symbol,
                            "direction": s.direction.value,
                            "strategy": s.strategy_name,
                            "entry": s.entry_price,
                        }
                        for s in strategy_signals[:10]
                    ],
                },
            })

            if not strategy_signals:
                logger.info("cycle_no_signals")
                self._emit("alert", {"message": "No strategy signals this cycle", "level": "info"})
                self._check_exits(macro_dict)
                self._send_cycle_report(macro, researcher_output, [], [], [], [], news_items)
                return

            # 6. Run Sentinel
            existing_positions = list(self._portfolio.open_positions.keys())
            sentinel_output = self._sentinel.evaluate(
                researcher_output, macro_dict,
                [self._signal_to_dict(s) for s in strategy_signals],
                existing_positions,
            )

            # Emit sentinel risk assessment
            self._emit("insight", {
                "type": "sentinel",
                "title": "Risk Assessment (Sentinel)",
                "data": {
                    "risk_penalty": sentinel_output.get("risk_penalty", 0),
                    "recommendation": sentinel_output.get("recommendation", "N/A"),
                    "counter_arguments": sentinel_output.get("counter_arguments", []),
                    "conflicting_signals": sentinel_output.get("conflicting_signals", []),
                },
            })

            # 7. Score via Orchestrator
            scored_signals = self._orchestrator.score_signals(
                strategy_signals, researcher_output, sentinel_output,
                macro_dict, self._current_regime,
            )

            # 8. Filter
            passing_signals = []
            filtered_reasons = []
            for sig in scored_signals:
                passed, reasons = apply_filters(
                    sig.confidence, sig.confidence_breakdown, self._config.scoring.filters
                )
                if passed:
                    passing_signals.append(sig)
                else:
                    filtered_reasons.append({"symbol": sig.symbol, "reasons": reasons})
                    logger.info("signal_filtered", symbol=sig.symbol, reasons=reasons)

            # Emit scoring results
            self._emit("insight", {
                "type": "scoring",
                "title": f"Scoring: {len(scored_signals)} scored -> {len(passing_signals)} passed filters",
                "data": {
                    "scored": [
                        {
                            "symbol": s.symbol,
                            "direction": s.direction.value,
                            "confidence": round(s.confidence, 3),
                            "final_score": round(s.final_score, 3),
                            "strategy": s.strategy_name,
                            "summary": s.summary[:100] if s.summary else "",
                        }
                        for s in scored_signals[:10]
                    ],
                    "filtered_out": filtered_reasons[:5],
                },
            })

            # 9. Stitch (consensus + dedup + rank)
            final_signals = self._stitch.finalize(
                passing_signals, self._sector_map
            )

            # 10. Queue signals for user approval (instead of auto-executing)
            for sig in final_signals:
                self._queue_signal_for_approval(sig)

            # 11. Check exits on existing positions
            self._check_exits(macro_dict)

            self._emit("alert", {
                "message": (
                    f"Cycle done: {len(strategy_signals)} raw -> "
                    f"{len(scored_signals)} scored -> {len(passing_signals)} filtered -> "
                    f"{len(final_signals)} awaiting approval"
                ),
                "level": "success",
            })
            logger.info(
                "cycle_complete",
                raw_signals=len(strategy_signals),
                scored=len(scored_signals),
                filtered=len(passing_signals),
                final=len(final_signals),
            )

            # Send Telegram cycle report
            self._send_cycle_report(
                macro, researcher_output, scored_signals, passing_signals, final_signals, filtered_reasons, news_items
            )

        except Exception as e:
            logger.error("cycle_error", error=str(e))
            self._emit("alert", {"message": f"Cycle error: {e}", "level": "error"})
            self._send_alert(f"Cycle error: {e}")

    # ---- Approval Workflow ----

    def _queue_signal_for_approval(self, signal: ScoredSignal) -> None:
        """Add a signal to the pending queue and notify the user."""
        signal_id = str(uuid.uuid4())[:8]

        pending = PendingSignal(
            signal_id=signal_id,
            signal=signal,
        )

        # Send Telegram notification with buttons
        if self._telegram.is_configured:
            message_id = self._telegram.send_signal_for_approval(signal, signal_id)
            pending.telegram_message_id = message_id

        self._pending_signals[signal_id] = pending

        # Persist to database
        self._db.save_pending_signal(pending)

        # Emit to dashboard
        self._emit("pending_signal", {
            "signal_id": signal_id,
            "symbol": signal.symbol,
            "direction": signal.direction.value,
            "strategy": signal.strategy_name,
            "confidence": round(signal.confidence, 3),
            "score": round(signal.final_score, 3),
            "entry": signal.entry_price,
            "stop": signal.stop_loss,
            "target": signal.target_price or 0,
            "sentiment": signal.sentiment.value,
            "strength": signal.strength.value,
            "key_drivers": signal.key_drivers[:3],
            "risks": signal.risks[:2],
            "summary": signal.summary[:150] if signal.summary else "",
            "time_horizon": signal.time_horizon,
            "regime": signal.regime.value if signal.regime else "unknown",
            "created_at": pending.created_at.strftime("%H:%M:%S"),
            "expiry_minutes": pending.expiry_minutes,
        })

        # Also emit as a regular signal for the signals table
        self._emit("signal", {
            "time": datetime.now().strftime("%H:%M:%S"),
            "symbol": signal.symbol,
            "direction": signal.direction.value,
            "strategy": signal.strategy_name,
            "confidence": signal.confidence,
            "score": signal.final_score,
            "entry": signal.entry_price,
            "stop": signal.stop_loss,
            "target": signal.target_price or 0,
        })

        logger.info(
            "signal_queued_for_approval",
            signal_id=signal_id,
            symbol=signal.symbol,
            direction=signal.direction.value,
            confidence=signal.confidence,
        )

    def handle_signal_action(self, signal_id: str, action: str) -> Dict[str, Any]:
        """Process user action on a pending signal.

        Called from Telegram callbacks or dashboard API.
        Returns result dict with status and details.
        """
        pending = self._pending_signals.get(signal_id)
        if not pending:
            return {"status": "error", "message": "Signal not found or expired"}

        if pending.status != SignalStatus.PENDING:
            return {"status": "error", "message": f"Signal already {pending.status.value}"}

        if pending.is_expired:
            pending.status = SignalStatus.EXPIRED
            self._db.update_pending_signal_status(signal_id, "expired", None)
            return {"status": "error", "message": "Signal has expired"}

        action_enum = TradeAction(action)
        pending.action = action_enum
        sig = pending.signal

        # Update Telegram message (remove buttons, show action)
        if self._telegram.is_configured and pending.telegram_message_id:
            self._telegram.update_signal_message(
                pending.telegram_message_id, action_enum, sig.symbol
            )

        if action_enum == TradeAction.APPROVE:
            pending.status = SignalStatus.APPROVED
            self._db.update_pending_signal_status(signal_id, "approved", "approve")
            result = self._execute_approved_signal(sig, auto_sell=False)
            return result

        elif action_enum == TradeAction.AUTO_SELL:
            pending.status = SignalStatus.APPROVED
            self._db.update_pending_signal_status(signal_id, "approved", "auto_sell")
            result = self._execute_approved_signal(sig, auto_sell=True)
            return result

        elif action_enum == TradeAction.IGNORE:
            pending.status = SignalStatus.REJECTED
            self._db.update_pending_signal_status(signal_id, "rejected", "ignore")
            self._emit("alert", {
                "message": f"Signal ignored: {sig.direction.value} {sig.symbol}",
                "level": "info",
            })
            logger.info("signal_ignored", signal_id=signal_id, symbol=sig.symbol)
            return {"status": "ignored", "symbol": sig.symbol}

        return {"status": "error", "message": f"Unknown action: {action}"}

    def _execute_approved_signal(self, signal: ScoredSignal, auto_sell: bool) -> Dict[str, Any]:
        """Execute a user-approved signal."""
        result = self._order_manager.execute_signal(
            signal, capital=self._config.risk.max_capital_deployed
        )

        if not result or not result.success:
            msg = result.message if result else "Order placement failed"
            self._emit("alert", {
                "message": f"Order failed for {signal.symbol}: {msg}",
                "level": "error",
            })
            return {"status": "error", "message": msg}

        # Emit trade event
        self._emit("trade", {
            "time": datetime.now().strftime("%H:%M:%S"),
            "symbol": signal.symbol,
            "direction": signal.direction.value,
            "price": result.fill_price,
            "quantity": result.fill_quantity,
            "strategy": signal.strategy_name,
            "auto_sell": auto_sell,
        })

        auto_sell_tag = " (Auto-Sell)" if auto_sell else ""
        self._emit("alert", {
            "message": (
                f"Trade executed{auto_sell_tag}: {signal.direction.value} {signal.symbol} "
                f"@ \u20b9{result.fill_price:.2f} x{result.fill_quantity}"
            ),
            "level": "success",
        })

        # Setup auto-sell triggers if requested
        trigger = None
        if auto_sell:
            trigger = self._auto_sell.create_trigger(
                signal,
                quantity=result.fill_quantity,
                last_price=result.fill_price,
            )
            self._emit("auto_sell", {
                "action": "created",
                "symbol": signal.symbol,
                "stop_loss": trigger.stop_loss,
                "target": trigger.target_price,
                "trailing_pct": trigger.trailing_stop_pct,
                "max_hold_min": trigger.max_hold_minutes,
                "confidence_floor": trigger.confidence_floor,
                "exit_strategy": trigger.exit_strategy,
                "invalidation": trigger.invalidation_condition,
            })
            logger.info(
                "auto_sell_enabled",
                symbol=signal.symbol,
                stop=trigger.stop_loss,
                target=trigger.target_price,
            )

        # Notify via Telegram
        if self._telegram.is_configured:
            self._telegram.send_trade_executed(
                signal, result.fill_price, result.fill_quantity, auto_sell=auto_sell
            )

        logger.info(
            "trade_executed",
            symbol=signal.symbol,
            direction=signal.direction.value,
            price=result.fill_price,
            quantity=result.fill_quantity,
            auto_sell=auto_sell,
        )

        return {
            "status": "executed",
            "symbol": signal.symbol,
            "price": result.fill_price,
            "quantity": result.fill_quantity,
            "auto_sell": auto_sell,
        }

    def _handle_telegram_callback(self, action: str, signal_id: str) -> None:
        """Handle Telegram inline button callback (runs on polling thread)."""
        logger.info("telegram_action_received", action=action, signal_id=signal_id)

        # Memory-update approval routes: callback_data = "memory_update:<id>:<approve|reject>"
        # The telegram notifier splits on first ":" so action="memory_update", signal_id="<id>:<action>"
        if action == "memory_update":
            try:
                pending_id_str, sub_action = signal_id.split(":", 1)
                pending_id = int(pending_id_str)
            except (ValueError, AttributeError):
                logger.warning("memory_callback_malformed", signal_id=signal_id)
                return
            self._postmortem_pipeline.handle_memory_callback(pending_id, sub_action)
            return

        result = self.handle_signal_action(signal_id, action)
        logger.info("telegram_action_result", signal_id=signal_id, result=result)

    def _expire_pending_signals(self) -> None:
        """Expire old pending signals."""
        expired_ids = []
        for signal_id, pending in self._pending_signals.items():
            if pending.status == SignalStatus.PENDING and pending.is_expired:
                pending.status = SignalStatus.EXPIRED
                expired_ids.append(signal_id)
                self._db.update_pending_signal_status(signal_id, "expired", None)
                logger.info("signal_expired", signal_id=signal_id, symbol=pending.signal.symbol)

                # Notify user about expiry
                if self._telegram.is_configured and pending.telegram_message_id:
                    self._telegram.update_signal_message(
                        pending.telegram_message_id,
                        TradeAction.IGNORE,  # Show as ignored
                        pending.signal.symbol,
                    )
                    self._telegram.send_alert(
                        f"Signal expired: {pending.signal.direction.value} {pending.signal.symbol} "
                        f"(no action taken within {pending.expiry_minutes} min)"
                    )

        if expired_ids:
            self._emit("alert", {
                "message": f"Expired {len(expired_ids)} pending signal(s)",
                "level": "warning",
            })

        # Periodically clean up old non-pending signals from DB
        self._db.cleanup_old_pending_signals()

    # ---- Auto-Sell Monitoring ----

    def tick_auto_sell(self) -> None:
        """Public entrypoint for the Fly.io always-on worker.

        Re-reads the Kite session (handles daily 15:30 IST token rollover)
        and re-loads auto-sell triggers from DB (so newly-approved
        positions created by other processes — e.g. the `telegram_poll`
        routine — get picked up immediately).
        """
        try:
            self._kite_client.authenticate()
        except Exception as e:
            logger.error("auto_sell_tick_reauth_failed", error=str(e))
            return
        self._auto_sell._triggers.clear()
        self._auto_sell._load_from_db()
        self._monitor_auto_sell_positions()

    def _monitor_auto_sell_positions(self) -> None:
        """Check all auto-sell triggers against current market data.

        Dual monitoring:
        1. Check GTT status on Zerodha (exchange-level stop/target)
        2. Check software triggers (trailing stop, time, confidence, structure)
        3. Update GTT stop leg if trailing stop has improved
        """
        active_triggers = self._auto_sell.active_triggers
        if not active_triggers:
            return

        # 1. Check GTT status first — exchange may have already executed
        for symbol, trigger in list(active_triggers.items()):
            if trigger.gtt_trigger_id and trigger.gtt_status.value == "active":
                gtt_exit = self._auto_sell.check_gtt_status(symbol)
                if gtt_exit:
                    # GTT was triggered by exchange — position already closed
                    self._handle_gtt_triggered_exit(gtt_exit, trigger)
                    return  # Re-check active triggers after removal

        # Refresh active triggers (GTT exits may have deactivated some)
        active_triggers = self._auto_sell.active_triggers
        if not active_triggers:
            return

        # 2. Get current prices for all triggered symbols
        prices: Dict[str, float] = {}
        for symbol in active_triggers:
            position = self._portfolio.get_position(symbol)
            if position and position.current_price > 0:
                prices[symbol] = position.current_price
            else:
                # Try to get LTP
                token = self._instrument_tokens.get(symbol)
                if token:
                    try:
                        ltp_data = self._kite.ltp([f"NSE:{symbol}"])
                        price = ltp_data.get(f"NSE:{symbol}", {}).get("last_price", 0)
                        if price > 0:
                            prices[symbol] = price
                    except Exception:
                        pass

        if not prices:
            return

        # 3. Check software triggers (trailing, time, confidence, structure)
        exit_signals = self._auto_sell.check_all(prices=prices)

        for exit_signal in exit_signals:
            self._execute_auto_sell_exit(exit_signal, prices.get(exit_signal.symbol, 0))

        # 4. Update GTT trailing stop if improved
        for symbol, trigger in self._auto_sell.active_triggers.items():
            if symbol not in prices:
                continue
            position = self._portfolio.get_position(symbol)
            if not position:
                continue

            # Calculate current trailing stop level
            if trigger.position_direction == Direction.BUY:
                trailing_stop = trigger.highest_price * (1 - trigger.trailing_stop_pct / 100)
                # Only update GTT if trailing stop is higher than current GTT stop
                if trailing_stop > trigger.gtt_stop_price:
                    self._auto_sell.update_gtt_trailing_stop(
                        symbol, trailing_stop, position.quantity, prices[symbol]
                    )
            else:
                trailing_stop = trigger.lowest_price * (1 + trigger.trailing_stop_pct / 100)
                if trailing_stop < trigger.gtt_stop_price or trigger.gtt_stop_price == 0:
                    self._auto_sell.update_gtt_trailing_stop(
                        symbol, trailing_stop, position.quantity, prices[symbol]
                    )

    def _execute_auto_sell_exit(self, exit_signal: Any, current_price: float) -> None:
        """Execute an auto-sell exit and notify the user."""
        symbol = exit_signal.symbol
        position = self._portfolio.get_position(symbol)
        if not position:
            logger.warning("auto_sell_no_position", symbol=symbol)
            self._auto_sell.deactivate(symbol)
            return

        logger.info(
            "auto_sell_executing",
            symbol=symbol,
            reason=exit_signal.reason.value,
            urgency=exit_signal.urgency,
            current_price=current_price,
        )

        # Execute the exit
        result = self._order_manager.close_position(
            symbol=symbol,
            reason=exit_signal.reason,
            exit_price=current_price if current_price > 0 else None,
        )

        if result and result.success:
            # Calculate PnL
            if position.direction.value == "BUY":
                pnl = (result.fill_price - position.entry_price) * position.quantity
            else:
                pnl = (position.entry_price - result.fill_price) * position.quantity

            # Deactivate trigger
            self._auto_sell.deactivate(symbol)

            # Notify user
            if self._telegram.is_configured:
                self._telegram.send_auto_sell_exit(
                    symbol=symbol,
                    exit_signal=exit_signal,
                    exit_price=result.fill_price,
                    pnl=pnl,
                    entry_price=position.entry_price,
                    quantity=position.quantity,
                )

            # Emit to dashboard
            self._emit("auto_sell", {
                "action": "executed",
                "symbol": symbol,
                "reason": exit_signal.reason.value,
                "urgency": exit_signal.urgency,
                "message": exit_signal.message,
                "exit_price": result.fill_price,
                "entry_price": position.entry_price,
                "pnl": round(pnl, 2),
                "quantity": position.quantity,
            })
            self._emit("alert", {
                "message": (
                    f"Auto-Sell executed: {symbol} @ \u20b9{result.fill_price:.2f} "
                    f"| PnL: \u20b9{pnl:+,.2f} | Reason: {exit_signal.reason.value}"
                ),
                "level": "success" if pnl >= 0 else "warning",
            })

            logger.info(
                "auto_sell_completed",
                symbol=symbol,
                exit_price=result.fill_price,
                pnl=round(pnl, 2),
                reason=exit_signal.reason.value,
            )

            # Trigger self-improvement postmortem (Telegram-gated memory write).
            self._safe_enqueue_postmortem(result.order_id or position.order_id)
        else:
            msg = result.message if result else "Exit order failed"
            logger.error("auto_sell_failed", symbol=symbol, error=msg)
            self._emit("alert", {
                "message": f"Auto-Sell FAILED for {symbol}: {msg}",
                "level": "error",
            })
            # Send alert — user needs to manually intervene
            if self._telegram.is_configured:
                self._telegram.send_alert(
                    f"AUTO-SELL FAILED for {symbol}: {msg}. Please manually exit position!"
                )

    def _handle_gtt_triggered_exit(self, exit_signal: Any, trigger: Any) -> None:
        """Handle a GTT-triggered exit — position was closed by the exchange.

        No need to place an exit order (exchange already did it).
        Just reconcile state, calculate PnL, and notify user.
        """
        symbol = exit_signal.symbol
        position = self._portfolio.get_position(symbol)
        if not position:
            # Position already gone — just clean up trigger
            self._auto_sell.deactivate(symbol)
            return

        # Get actual exit price from GTT status or estimate
        gtt_status = self._broker.get_gtt_status(trigger.gtt_trigger_id)
        exit_price = 0.0
        for order in gtt_status.get("orders", []):
            result = order.get("result", {})
            if result.get("status") == "complete":
                exit_price = result.get("average_price", 0)
                break

        if exit_price <= 0:
            # Fallback: use trigger price
            if exit_signal.reason == ExitReason.GTT_TARGET:
                exit_price = trigger.target_price
            else:
                exit_price = trigger.gtt_stop_price or trigger.stop_loss

        # Calculate PnL
        if position.direction == Direction.BUY:
            pnl = (exit_price - position.entry_price) * position.quantity
        else:
            pnl = (position.entry_price - exit_price) * position.quantity

        # Update portfolio (mark position as closed)
        self._portfolio.close_position(symbol, exit_price, exit_signal.reason.value)

        # Deactivate trigger (GTT already triggered, no need to cancel)
        trigger_obj = self._auto_sell.get_trigger(symbol)
        if trigger_obj:
            trigger_obj.is_active = False
            trigger_obj.gtt_status = GTTStatus.TRIGGERED

        # Persist trade exit to DB
        if self._db:
            self._db.update_trade_exit(
                symbol=symbol,
                exit_price=exit_price,
                exit_reason=exit_signal.reason.value,
                pnl=pnl,
            )

        # Notify user
        if self._telegram.is_configured:
            self._telegram.send_auto_sell_exit(
                symbol=symbol,
                exit_signal=exit_signal,
                exit_price=exit_price,
                pnl=pnl,
                entry_price=position.entry_price,
                quantity=position.quantity,
            )

        self._emit("auto_sell", {
            "action": "gtt_triggered",
            "symbol": symbol,
            "reason": exit_signal.reason.value,
            "exit_price": exit_price,
            "entry_price": position.entry_price,
            "pnl": round(pnl, 2),
            "quantity": position.quantity,
        })
        self._emit("alert", {
            "message": (
                f"GTT Triggered: {symbol} @ \u20b9{exit_price:.2f} "
                f"| PnL: \u20b9{pnl:+,.2f} | {exit_signal.reason.value}"
            ),
            "level": "success" if pnl >= 0 else "warning",
        })

        # Trigger self-improvement postmortem (Telegram-gated memory write).
        self._safe_enqueue_postmortem(position.order_id)

        logger.info(
            "gtt_exit_completed",
            symbol=symbol,
            exit_price=exit_price,
            pnl=round(pnl, 2),
            reason=exit_signal.reason.value,
        )

    # ---- Existing Methods ----

    def _scan_all_strategies(self):
        """Run all enabled strategies across the watchlist."""
        from src.models import StrategySignal

        signals: List[StrategySignal] = []

        for symbol in self._watchlist:
            data = self._fetch_symbol_data(symbol)
            if not data:
                continue

            for strategy in self._strategies:
                try:
                    signal = strategy.scan(symbol, data, {})
                    if signal is not None:
                        signals.append(signal)
                except Exception as e:
                    logger.warning(
                        "strategy_scan_error",
                        strategy=strategy.name,
                        symbol=symbol,
                        error=str(e),
                    )

        logger.info("scan_complete", signals=len(signals), symbols=len(self._watchlist))
        return signals

    def _fetch_symbol_data(self, symbol: str) -> Dict[str, Any]:
        """Fetch multi-timeframe OHLCV data for a symbol."""
        token = self._instrument_tokens.get(symbol)
        if token is None:
            return {}

        data = {}
        for interval in self._config.data.candle_intervals:
            try:
                df = self._market_data.get_historical_data(
                    instrument_token=token,
                    interval=interval,
                    lookback_days=self._config.data.lookback_days,
                )
                if df is not None and len(df) > 0:
                    data[interval] = df
            except Exception as e:
                logger.warning(
                    "data_fetch_error", symbol=symbol, interval=interval, error=str(e)
                )
        return data

    def _check_exits(self, macro_dict: Dict[str, Any]) -> None:
        """Check all open positions for exit conditions.

        For auto-sell positions, the auto_sell manager handles exits.
        For manually-managed positions, check strategy + auto-exit conditions.
        """
        for symbol, position in list(self._portfolio.open_positions.items()):
            # Skip if auto-sell is managing this position
            if self._auto_sell.has_trigger(symbol):
                continue

            data = self._fetch_symbol_data(symbol)
            if not data:
                continue

            # Check strategy-specific exits
            for strategy in self._strategies:
                if strategy.name == position.strategy_name:
                    exit_signal = strategy.check_exit(position, data, {})
                    if exit_signal is not None:
                        logger.info(
                            "exit_triggered",
                            symbol=symbol,
                            reason=exit_signal.reason.value,
                        )
                        self._order_manager.close_position(
                            symbol, exit_signal.reason
                        )

                        # Notify user of exit for manual positions
                        if self._telegram.is_configured:
                            self._telegram.send_exit_reminder(
                                symbol=symbol,
                                reason=exit_signal.reason.value,
                                urgency=exit_signal.urgency,
                                current_price=position.current_price,
                                entry_price=position.entry_price,
                                suggestion=exit_signal.message,
                            )
                        break

            # Check auto-exit conditions (stop-loss, time, confidence decay)
            if self._portfolio.has_position(symbol):
                exit_signal = self._auto_exit.check(position, data, {})
                if exit_signal is not None:
                    logger.info(
                        "auto_exit_triggered",
                        symbol=symbol,
                        reason=exit_signal.reason.value,
                    )
                    self._order_manager.close_position(symbol, exit_signal.reason)

    def _update_regime(self) -> None:
        """Update market regime from recent Nifty data."""
        if not self._regime_detector.is_trained:
            return
        try:
            nifty_token = self._instrument_tokens.get("NIFTY 50")
            if nifty_token:
                nifty_daily = self._market_data.get_historical_data(
                    instrument_token=nifty_token, interval="day", lookback_days=365
                )
                self._current_regime = self._regime_detector.predict(nifty_daily)
        except Exception as e:
            logger.warning("regime_update_error", error=str(e))

    def _safe_enqueue_postmortem(self, order_id: Optional[str]) -> None:
        """Enqueue a postmortem for a just-closed trade. Never raises."""
        if not order_id:
            return
        try:
            self._postmortem_pipeline.enqueue_postmortem_for_closed_trade(order_id)
        except Exception as e:
            logger.error("postmortem_enqueue_error", order_id=order_id, error=str(e))

    def sweep_pending_memory_updates(self) -> None:
        """Scheduled job: expire stale pending memory updates."""
        try:
            self._postmortem_pipeline.sweep_expired()
        except Exception as e:
            logger.error("memory_sweep_error", error=str(e))

    def run_weekly_review(self) -> Optional[int]:
        """Scheduled job (Friday post-close): draft a weekly review for user approval."""
        try:
            from src.feedback.weekly_review_agent import WeeklyReviewAgent

            agent = WeeklyReviewAgent(self._config.agents)
            return agent.run(
                db=self._db,
                telegram=self._telegram,
                writer_pipeline=self._postmortem_pipeline,
            )
        except Exception as e:
            logger.error("weekly_review_error", error=str(e))
            return None

    def send_daily_summary(self) -> None:
        """Send end-of-day performance summary."""
        stats = self._portfolio.get_daily_stats()
        summary = {
            "total_trades": stats.get("trades_today", 0),
            "win_rate": stats.get("win_rate", 0),
            "realized_pnl": self._portfolio.realized_pnl_today,
            "open_positions": self._portfolio.open_position_count,
            "capital_deployed": self._portfolio.deployed_capital,
            "regime": self._current_regime.value if self._current_regime else "unknown",
        }

        if self._telegram.is_configured:
            self._telegram.send_daily_summary(summary)
        if self._whatsapp.is_configured:
            self._whatsapp.send_daily_summary(summary)

        logger.info("daily_summary_sent", **summary)

    def _send_cycle_report(
        self,
        macro: Any,
        researcher_output: Dict[str, Any],
        scored_signals: list,
        passing_signals: list,
        final_signals: list,
        filtered_reasons: list,
        news_items: list,
    ) -> None:
        """Send a comprehensive cycle report to Telegram."""
        if not self._telegram.is_configured:
            return

        now = datetime.now()
        nifty_str = f"\u20b9{macro.nifty_price:,.0f}" if macro.nifty_price else "N/A"
        vix_str = f"{macro.india_vix:.1f}" if macro.india_vix else "N/A"
        nifty_chg = f"{macro.nifty_change_pct:+.2f}%" if macro.nifty_change_pct else ""

        lines = [
            f"\U0001f4ca Scan Report \u2014 {now.strftime('%H:%M IST')}",
            "",
            f"\U0001f3db Market: Nifty {nifty_str} ({nifty_chg}) | VIX: {vix_str}",
            f"\U0001f4c8 Direction: {macro.market_direction}",
        ]

        if self._current_regime:
            lines.append(f"\U0001f504 Regime: {self._current_regime.value.upper()}")
        if macro.is_risk_off:
            lines.append("\u26a0\ufe0f RISK-OFF environment detected")

        # News summary
        sentiment = researcher_output.get("sentiment", "NEUTRAL")
        news_strength = researcher_output.get("news_strength", 0)
        summary = researcher_output.get("summary", "")
        key_drivers = researcher_output.get("key_drivers", [])

        lines.append("")
        lines.append(f"\U0001f4f0 News: {len(news_items)} headlines | Sentiment: {sentiment} ({news_strength:.0%})")

        if summary:
            lines.append(f"\U0001f4a1 {summary}")

        if key_drivers:
            lines.append(f"\U0001f511 Drivers: {', '.join(key_drivers[:3])}")

        # Affected stocks
        entities = researcher_output.get("entities", [])
        if entities:
            stock_mentions = []
            for e in entities[:5]:
                sym = e.get("symbol", "")
                sent = e.get("sentiment", "")
                if sym:
                    emoji = "\U0001f7e2" if sent == "BULLISH" else "\U0001f534" if sent == "BEARISH" else "\u26aa"
                    stock_mentions.append(f"{emoji}{sym}")
            if stock_mentions:
                lines.append(f"\U0001f3f7 Stocks: {' '.join(stock_mentions)}")

        # Signals summary
        lines.append("")
        if scored_signals:
            lines.append(f"\U0001f3af Signals: {len(scored_signals)} scored, {len(passing_signals)} passed filters")
            if passing_signals:
                for sig in passing_signals[:3]:
                    direction = "\U0001f7e2" if sig.direction.value == "BUY" else "\U0001f534"
                    lines.append(
                        f"  {direction} {sig.symbol} ({sig.strategy_name}) \u2014 "
                        f"conf: {sig.confidence:.0%}, score: {sig.final_score:.2f}"
                    )
                    if sig.summary:
                        lines.append(f"     {sig.summary[:80]}")
            if filtered_reasons:
                lines.append("")
                lines.append("\u274c Filtered out:")
                for item in filtered_reasons[:3]:
                    sym = item.get("symbol", "?")
                    reasons = item.get("reasons", [])
                    reason_str = "; ".join(reasons[:2]) if reasons else "unknown reason"
                    lines.append(f"  \u274c {sym}: {reason_str}")
        else:
            lines.append("\U0001f3af No signals scored this cycle")

        if final_signals:
            lines.append("")
            lines.append(f"\u23f3 Awaiting approval: {len(final_signals)} signals")
            for sig in final_signals:
                lines.append(
                    f"  \u2192 {sig.direction.value} {sig.symbol} @ \u20b9{sig.entry_price:.2f}"
                )

        # Auto-sell status
        auto_sell_active = self._auto_sell.active_triggers
        if auto_sell_active:
            lines.append("")
            lines.append(f"\U0001f916 Auto-Sell active: {len(auto_sell_active)} positions")
            for sym in auto_sell_active:
                lines.append(f"  \u2192 {sym}")

        # Portfolio snapshot
        open_count = self._portfolio.open_position_count
        pnl = self._portfolio.realized_pnl_today
        if open_count > 0 or pnl != 0:
            lines.append("")
            lines.append(f"\U0001f4bc Portfolio: {open_count} open | PnL: \u20b9{pnl:+,.2f}")

        # Pending signals count
        pending_count = sum(
            1 for p in self._pending_signals.values() if p.status == SignalStatus.PENDING
        )
        if pending_count > 0:
            lines.append(f"\u23f0 {pending_count} signal(s) awaiting your decision")

        self._telegram.send_alert("\n".join(lines))

    def _emit(self, event_type: str, data: Any = None) -> None:
        """Push event to UI callback if registered."""
        if self._on_event:
            try:
                self._on_event(event_type, data)
            except Exception:
                pass  # Never let callback errors break the engine

    def _send_alert(self, message: str) -> None:
        self._emit("alert", {"message": message, "level": "warning"})
        if self._telegram.is_configured:
            self._telegram.send_alert(message)
        if self._whatsapp.is_configured:
            self._whatsapp.send_alert(message)

    # ---- Properties for external access ----

    @property
    def pending_signals(self) -> Dict[str, PendingSignal]:
        return dict(self._pending_signals)

    @property
    def auto_sell_manager(self) -> AutoSellManager:
        return self._auto_sell

    @staticmethod
    def _macro_to_dict(macro) -> Dict[str, Any]:
        return {
            "nifty_price": macro.nifty_price,
            "nifty_change_pct": macro.nifty_change_pct,
            "india_vix": macro.india_vix,
            "market_direction": macro.market_direction,
            "is_risk_off": macro.is_risk_off,
        }

    @staticmethod
    def _signal_to_dict(signal) -> Dict[str, Any]:
        return {
            "symbol": signal.symbol,
            "direction": signal.direction.value,
            "strategy": signal.strategy_name,
            "confidence_inputs": signal.confidence_inputs.model_dump(),
        }

    def load_instruments(self) -> None:
        """Load Kite instrument tokens for the watchlist."""
        from src.data.kite_client import get_instruments
        try:
            symbol_to_token = get_instruments(self._kite_client.kite, exchange="NSE")
            for symbol in self._watchlist:
                token = symbol_to_token.get(symbol)
                if token is not None:
                    self._instrument_tokens[symbol] = token
            logger.info(
                "instruments_loaded",
                count=len(self._instrument_tokens),
                missing=[s for s in self._watchlist if s not in self._instrument_tokens],
            )
        except Exception as e:
            logger.error("instruments_load_error", error=str(e))

    def shutdown(self) -> None:
        """Clean shutdown — stop Telegram polling, deactivate auto-sell."""
        if self._telegram.is_configured:
            self._telegram.stop_callback_polling()
        logger.info("engine_shutdown")


def main() -> None:
    """Entry point: start the market-hours scheduler."""
    mode = os.getenv("EXECUTION_MODE", "paper")
    config = load_config(mode)

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer()
            if config.logging.level == "DEBUG"
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40}.get(
                config.logging.level, 20
            )
        ),
    )

    engine = TradingEngine(config)

    # Schedule market-hours cycles
    scheduler = BlockingScheduler(timezone=config.market.timezone)

    # Main scan cycle: every N minutes during market hours
    open_h, open_m = map(int, config.market.open_time.split(":"))
    close_h, close_m = map(int, config.market.close_time.split(":"))

    scheduler.add_job(
        engine.run_cycle,
        trigger=IntervalTrigger(
            minutes=config.market.scan_interval_minutes,
            start_date=datetime.now().replace(hour=open_h, minute=open_m + 5, second=0),
        ),
        id="main_cycle",
        name="Market Scan Cycle",
        max_instances=1,
    )

    # Pre-market: load instruments at 09:10
    scheduler.add_job(
        engine.load_instruments,
        trigger=CronTrigger(hour=open_h, minute=max(0, open_m - 5), timezone=config.market.timezone),
        id="load_instruments",
        name="Load Instruments",
    )

    # End-of-day summary at 15:35
    scheduler.add_job(
        engine.send_daily_summary,
        trigger=CronTrigger(hour=close_h, minute=close_m + 5, timezone=config.market.timezone),
        id="daily_summary",
        name="Daily Summary",
    )

    # Weekly review — Friday, 10 min after close
    scheduler.add_job(
        engine.run_weekly_review,
        trigger=CronTrigger(
            day_of_week="fri",
            hour=close_h,
            minute=(close_m + 10) % 60,
            timezone=config.market.timezone,
        ),
        id="weekly_review",
        name="Weekly Review",
    )

    # Sweep expired pending memory updates every 15 minutes (24/7 — not market-hours dependent)
    scheduler.add_job(
        engine.sweep_pending_memory_updates,
        trigger=IntervalTrigger(minutes=15),
        id="memory_update_sweeper",
        name="Memory Update Expiry Sweeper",
        max_instances=1,
    )

    # Graceful shutdown
    def shutdown_handler(signum, frame):
        logger.info("shutting_down")
        engine.shutdown()
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    logger.info(
        "scheduler_started",
        mode=mode,
        interval=config.market.scan_interval_minutes,
        market_hours=f"{config.market.open_time}-{config.market.close_time}",
    )

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        engine.shutdown()
        logger.info("scheduler_stopped")


if __name__ == "__main__":
    main()
