"""FastAPI web server — Kite OAuth, engine control, approval workflow, and trading dashboard.

Start with: python -m src.web.app
Opens browser -> login with Zerodha -> engine starts -> dashboard shows live status.

Approval workflow:
  Engine finds signals -> Queued as pending -> Telegram buttons or Dashboard buttons
  User taps Approve / Auto-Sell / Ignore -> Engine executes accordingly
"""

from __future__ import annotations

import os
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

import structlog
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

load_dotenv(override=True)

from src.config import AppConfig, load_config
from src.data.kite_client import KiteClient
from src.models import SignalStatus
from src.notifications.telegram import TelegramNotifier

logger = structlog.get_logger(__name__)

# Paths
WEB_DIR = Path(__file__).parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"

# App state
app = FastAPI(title="Insight-Alpha", version="0.2.0")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


class EngineState:
    """Global engine state shared across requests."""

    def __init__(self) -> None:
        self.config: Optional[AppConfig] = None
        self.kite_client: Optional[KiteClient] = None
        self.engine: Optional[Any] = None  # TradingEngine
        self.engine_thread: Optional[threading.Thread] = None

        # Status tracking
        self.is_authenticated: bool = False
        self.is_running: bool = False
        self.started_at: Optional[datetime] = None
        self.last_cycle: Optional[datetime] = None
        self.total_cycles: int = 0

        # Signal/trade history for dashboard
        self.recent_signals: List[Dict[str, Any]] = []
        self.recent_trades: List[Dict[str, Any]] = []
        self.alerts: List[Dict[str, Any]] = []
        self.latest_insights: Dict[str, Dict[str, Any]] = {}

        # Pending signals (approval workflow)
        self.pending_signals: List[Dict[str, Any]] = []

        # Auto-sell events
        self.auto_sell_events: List[Dict[str, Any]] = []

    def add_signal(self, signal_data: Dict[str, Any]) -> None:
        self.recent_signals.insert(0, signal_data)
        self.recent_signals = self.recent_signals[:50]

    def add_trade(self, trade_data: Dict[str, Any]) -> None:
        self.recent_trades.insert(0, trade_data)
        self.recent_trades = self.recent_trades[:50]

    def set_insight(self, insight_type: str, insight_data: Dict[str, Any]) -> None:
        """Store latest insight by type (overwrites previous of same type)."""
        self.latest_insights[insight_type] = {
            **insight_data,
            "updated_at": datetime.now().strftime("%H:%M:%S"),
        }

    def add_alert(self, message: str, level: str = "info") -> None:
        self.alerts.insert(0, {
            "message": message,
            "level": level,
            "time": datetime.now().strftime("%H:%M:%S"),
        })
        self.alerts = self.alerts[:20]

    def add_pending_signal(self, data: Dict[str, Any]) -> None:
        """Add a pending signal for dashboard display."""
        self.pending_signals.insert(0, {
            **data,
            "status": "pending",
        })
        self.pending_signals = self.pending_signals[:20]

    def update_pending_signal(self, signal_id: str, status: str) -> None:
        """Update a pending signal's status after user action."""
        for ps in self.pending_signals:
            if ps.get("signal_id") == signal_id:
                ps["status"] = status
                break

    def add_auto_sell_event(self, data: Dict[str, Any]) -> None:
        """Track auto-sell events."""
        self.auto_sell_events.insert(0, {
            **data,
            "time": datetime.now().strftime("%H:%M:%S"),
        })
        self.auto_sell_events = self.auto_sell_events[:20]


state = EngineState()


def _handle_engine_event(event_type: str, data: Any) -> None:
    """Route engine events to the dashboard state."""
    if event_type == "alert" and isinstance(data, dict):
        state.add_alert(data.get("message", ""), data.get("level", "info"))
    elif event_type == "signal" and isinstance(data, dict):
        state.add_signal(data)
    elif event_type == "trade" and isinstance(data, dict):
        state.add_trade(data)
    elif event_type == "insight" and isinstance(data, dict):
        state.set_insight(data.get("type", "unknown"), data)
    elif event_type == "pending_signal" and isinstance(data, dict):
        state.add_pending_signal(data)
    elif event_type == "auto_sell" and isinstance(data, dict):
        state.add_auto_sell_event(data)
    elif event_type == "error":
        state.add_alert(str(data), "error")


def _populate_dashboard_from_db(engine: Any) -> None:
    """Repopulate dashboard state from database after engine creation."""
    try:
        db = engine._db

        # Load recent signals
        state.recent_signals = db.load_recent_signals(limit=50)

        # Load recent trades
        state.recent_trades = db.load_recent_trades(limit=50)

        # Load pending signals from engine (already loaded from DB)
        for signal_id, pending in engine.pending_signals.items():
            sig = pending.signal
            state.add_pending_signal({
                "signal_id": signal_id,
                "symbol": sig.symbol,
                "direction": sig.direction.value,
                "strategy": sig.strategy_name,
                "confidence": round(sig.confidence, 3),
                "score": round(sig.final_score, 3),
                "entry": sig.entry_price,
                "stop": sig.stop_loss,
                "target": sig.target_price or 0,
                "sentiment": sig.sentiment.value,
                "strength": sig.strength.value,
                "key_drivers": sig.key_drivers[:3],
                "risks": sig.risks[:2],
                "summary": sig.summary[:150] if sig.summary else "",
                "time_horizon": sig.time_horizon,
                "regime": sig.regime.value if sig.regime else "unknown",
                "created_at": pending.created_at.strftime("%H:%M:%S"),
                "expiry_minutes": pending.expiry_minutes,
            })

        logger.info(
            "dashboard_populated_from_db",
            signals=len(state.recent_signals),
            trades=len(state.recent_trades),
            pending=len(state.pending_signals),
        )
    except Exception as e:
        logger.error("dashboard_populate_error", error=str(e))


# ---- Routes ----


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page."""
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "state": state,
    })


@app.get("/auth/login")
async def kite_login():
    """Redirect to Zerodha login page."""
    try:
        state.kite_client = KiteClient()

        # Check if already authenticated today
        try:
            state.kite_client.authenticate()
            state.is_authenticated = True
            state.add_alert("Already authenticated for today", "success")
            return RedirectResponse(url="/")
        except ValueError:
            pass

        # Redirect to Zerodha
        login_url = state.kite_client.login_url
        logger.info("kite_redirecting", url=login_url)
        return RedirectResponse(url=login_url)
    except Exception as e:
        state.add_alert(f"Auth error: {e}", "error")
        return RedirectResponse(url="/")


@app.get("/auth/callback")
async def kite_callback(request: Request):
    """Handle Zerodha OAuth callback — auto-captures request_token."""
    request_token = request.query_params.get("request_token")
    status = request.query_params.get("status")

    if status != "success" or not request_token:
        state.add_alert("Zerodha login failed or was cancelled", "error")
        return RedirectResponse(url="/")

    try:
        if state.kite_client is None:
            state.kite_client = KiteClient()

        state.kite_client.authenticate(request_token=request_token)
        state.is_authenticated = True
        state.add_alert("Kite authenticated successfully!", "success")

        # Send Telegram notification
        telegram = TelegramNotifier()
        if telegram.is_configured:
            telegram.send_alert("Kite authenticated. Engine ready to start.")

        logger.info("kite_auth_success_web")
        return RedirectResponse(url="/")
    except Exception as e:
        state.add_alert(f"Authentication failed: {e}", "error")
        logger.error("kite_auth_failed_web", error=str(e))
        return RedirectResponse(url="/")


@app.post("/engine/start")
async def start_engine():
    """Start the trading engine in a background thread."""
    if state.is_running:
        return JSONResponse({"status": "already_running"})

    if not state.is_authenticated:
        return JSONResponse({"status": "not_authenticated"}, status_code=400)

    try:
        state.config = load_config(os.getenv("EXECUTION_MODE", "paper"))

        from src.main import TradingEngine
        state.engine = TradingEngine(state.config, on_event=_handle_engine_event)

        # Repopulate dashboard state from DB
        _populate_dashboard_from_db(state.engine)

        # Start engine loop in background thread
        state.engine_thread = threading.Thread(
            target=_run_engine_loop, daemon=True, name="trading-engine"
        )
        state.engine_thread.start()
        state.is_running = True
        state.started_at = datetime.now()
        state.add_alert("Trading engine started!", "success")

        telegram = TelegramNotifier()
        if telegram.is_configured:
            telegram.send_alert("Trading engine started. Scanning market...")

        return JSONResponse({"status": "started"})
    except Exception as e:
        state.add_alert(f"Engine start failed: {e}", "error")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/engine/stop")
async def stop_engine():
    """Stop the trading engine."""
    if not state.is_running:
        return JSONResponse({"status": "not_running"})

    state.is_running = False
    if state.engine:
        state.engine.shutdown()
    state.add_alert("Trading engine stopped", "warning")
    return JSONResponse({"status": "stopped"})


@app.post("/engine/cycle")
async def run_single_cycle():
    """Manually trigger a single scan cycle."""
    if not state.is_authenticated:
        return JSONResponse({"status": "not_authenticated"}, status_code=400)

    if state.engine is None:
        try:
            state.config = load_config(os.getenv("EXECUTION_MODE", "paper"))
            from src.main import TradingEngine
            state.engine = TradingEngine(state.config, on_event=_handle_engine_event)
        except Exception as e:
            return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

    try:
        state.engine.run_cycle()
        state.last_cycle = datetime.now()
        state.total_cycles += 1
        state.add_alert("Manual cycle completed", "success")
        return JSONResponse({"status": "completed"})
    except Exception as e:
        state.add_alert(f"Cycle error: {e}", "error")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


# ---- Signal Approval API ----


@app.post("/api/signals/{signal_id}/action")
async def signal_action(signal_id: str, request: Request):
    """Process user action on a pending signal.

    POST body: {"action": "approve" | "ignore" | "auto_sell"}
    """
    if state.engine is None:
        return JSONResponse({"status": "error", "message": "Engine not running"}, status_code=400)

    try:
        body = await request.json()
        action = body.get("action", "")

        if action not in ("approve", "ignore", "auto_sell"):
            return JSONResponse(
                {"status": "error", "message": f"Invalid action: {action}"},
                status_code=400,
            )

        result = state.engine.handle_signal_action(signal_id, action)

        # Update dashboard state
        status_map = {
            "executed": "approved",
            "ignored": "rejected",
            "error": "error",
        }
        state.update_pending_signal(signal_id, status_map.get(result["status"], result["status"]))

        return JSONResponse(result)
    except Exception as e:
        logger.error("signal_action_error", signal_id=signal_id, error=str(e))
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


# ---- Status / Data APIs ----


@app.get("/api/status")
async def get_status():
    """Engine status for dashboard polling."""
    pending_count = sum(1 for ps in state.pending_signals if ps.get("status") == "pending")
    auto_sell_count = 0
    if state.engine:
        auto_sell_count = len(state.engine.auto_sell_manager.active_triggers)

    return JSONResponse({
        "is_authenticated": state.is_authenticated,
        "is_running": state.is_running,
        "started_at": state.started_at.isoformat() if state.started_at else None,
        "last_cycle": state.last_cycle.isoformat() if state.last_cycle else None,
        "total_cycles": state.total_cycles,
        "mode": os.getenv("EXECUTION_MODE", "paper"),
        "pending_signals": pending_count,
        "auto_sell_active": auto_sell_count,
    })


@app.get("/api/signals")
async def get_signals():
    """Recent signals for dashboard."""
    return JSONResponse(state.recent_signals)


@app.get("/api/trades")
async def get_trades():
    """Recent trades for dashboard."""
    return JSONResponse(state.recent_trades)


@app.get("/api/alerts")
async def get_alerts():
    """Recent alerts for dashboard."""
    return JSONResponse(state.alerts)


@app.get("/api/insights")
async def get_insights():
    """Latest cycle insights for dashboard."""
    return JSONResponse(state.latest_insights)


@app.get("/api/pending")
async def get_pending_signals():
    """Get pending signals awaiting user action."""
    # Filter to only show pending ones, but include recently acted-on for UI feedback
    return JSONResponse(state.pending_signals[:20])


@app.get("/api/auto-sell")
async def get_auto_sell_status():
    """Get auto-sell triggers status and recent events."""
    triggers = []
    if state.engine:
        triggers = state.engine.auto_sell_manager.get_status_summary()

    return JSONResponse({
        "triggers": triggers,
        "events": state.auto_sell_events[:10],
    })


@app.get("/api/portfolio")
async def get_portfolio():
    """Current portfolio state."""
    if state.engine is None:
        return JSONResponse({"positions": [], "pnl": 0, "deployed": 0})

    portfolio = state.engine._portfolio
    positions = []
    for sym, pos in portfolio.open_positions.items():
        auto_sell = state.engine.auto_sell_manager.has_trigger(sym)
        trigger = state.engine.auto_sell_manager.get_trigger(sym) if auto_sell else None

        pos_data = {
            "symbol": pos.symbol,
            "direction": pos.direction.value,
            "quantity": pos.quantity,
            "entry_price": pos.entry_price,
            "current_price": pos.current_price,
            "pnl": round(pos.unrealized_pnl, 2),
            "strategy": pos.strategy_name,
            "auto_sell": auto_sell,
        }

        if trigger:
            pos_data["auto_sell_details"] = {
                "stop_loss": trigger.stop_loss,
                "target": trigger.target_price,
                "trailing_pct": trigger.trailing_stop_pct,
                "max_hold_min": trigger.max_hold_minutes,
                "exit_strategy": trigger.exit_strategy,
            }

        positions.append(pos_data)

    return JSONResponse({
        "positions": positions,
        "realized_pnl": round(portfolio.realized_pnl_today, 2),
        "deployed_capital": round(portfolio.deployed_capital, 2),
        "open_count": portfolio.open_position_count,
    })


# ---- Background Engine Loop ----


def _run_engine_loop() -> None:
    """Run trading engine cycles in background thread."""
    scan_interval = 15 * 60  # 15 minutes in seconds

    while state.is_running:
        try:
            now = datetime.now()
            hour_min = now.hour * 100 + now.minute

            # Only scan during market hours (09:20 to 15:25 IST)
            if 920 <= hour_min <= 1525:
                logger.info("engine_cycle_start")
                state.engine.run_cycle()
                state.last_cycle = datetime.now()
                state.total_cycles += 1
                state.add_alert(
                    f"Scan cycle #{state.total_cycles} completed", "info"
                )
            else:
                logger.info("engine_outside_market_hours", time=str(now.time()))

            # Sleep until next cycle
            for _ in range(scan_interval):
                if not state.is_running:
                    return
                time.sleep(1)

        except Exception as e:
            logger.error("engine_loop_error", error=str(e))
            state.add_alert(f"Engine error: {e}", "error")
            time.sleep(60)  # Back off on error


# ---- Entry Point ----


def main() -> None:
    """Start the web server and open browser."""
    # Update redirect URL in kite to http://127.0.0.1:8000/auth/callback
    port = int(os.getenv("PORT", "8000"))

    print("\n" + "=" * 60)
    print("  Insight-Alpha Trading Dashboard")
    print(f"  http://127.0.0.1:{port}")
    print("=" * 60 + "\n")

    # Auto-open browser
    webbrowser.open(f"http://127.0.0.1:{port}")

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
