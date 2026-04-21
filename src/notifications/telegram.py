"""Telegram Bot notifications with interactive trade approval buttons.

Sends trading signal alerts via Telegram Bot API with inline keyboards
for Approve / Ignore / Auto-Sell actions. Polls for user callback responses.

Setup (2 minutes):
1. Open Telegram, search for @BotFather
2. Send /newbot, follow prompts -> get BOT_TOKEN
3. Create a group/channel or message your bot directly
4. Get your chat_id: visit https://api.telegram.org/bot<TOKEN>/getUpdates
   after sending a message to the bot
5. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any, Callable, Dict, List, Optional

import httpx
import structlog

from src.models import AutoSellTrigger, ExitSignal, ScoredSignal, TradeAction

logger = structlog.get_logger(__name__)

TELEGRAM_TOKEN_ENV = "TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID_ENV = "TELEGRAM_CHAT_ID"
TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}"


class TelegramNotifier:
    """Send trading notifications via Telegram Bot API with interactive buttons."""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        timeout: float = 10.0,
    ) -> None:
        self._token = bot_token or os.getenv(TELEGRAM_TOKEN_ENV, "")
        self._chat_id = chat_id or os.getenv(TELEGRAM_CHAT_ID_ENV, "")
        self._timeout = timeout
        self._last_update_id: int = 0
        self._callback_handler: Optional[Callable] = None
        self._polling_thread: Optional[threading.Thread] = None
        self._polling_active: bool = False

    @property
    def is_configured(self) -> bool:
        return bool(self._token and self._chat_id)

    # ---- Signal Notifications ----

    def send_signal_for_approval(self, signal: ScoredSignal, signal_id: str) -> Optional[int]:
        """Send a trading signal with Approve/Ignore/Auto-Sell inline buttons.

        Returns the Telegram message_id for callback routing, or None on failure.
        """
        if not self.is_configured:
            logger.warning("telegram_not_configured")
            return None

        text = self._format_signal_approval(signal)

        # Inline keyboard — primary action is BUY/SELL with auto-sell trigger
        action_label = signal.direction.value  # BUY or SELL
        keyboard = {
            "inline_keyboard": [
                [
                    {
                        "text": f"{action_label} & Auto-Sell",
                        "callback_data": f"auto_sell:{signal_id}",
                    },
                    {
                        "text": f"Manual {action_label}",
                        "callback_data": f"approve:{signal_id}",
                    },
                ],
                [
                    {"text": "Ignore", "callback_data": f"ignore:{signal_id}"},
                ],
            ]
        }

        message_id = self._send_with_keyboard(text, keyboard)
        return message_id

    def send_signal(self, signal: ScoredSignal) -> bool:
        """Send a trading signal as a formatted message (no buttons)."""
        if not self.is_configured:
            return False
        text = self._format_signal(signal)
        return self._send(text)

    def send_trade_executed(self, signal: ScoredSignal, fill_price: float, quantity: int, auto_sell: bool = False) -> bool:
        """Notify user that a trade was executed."""
        if not self.is_configured:
            return False

        esc = self._escape_md
        direction_emoji = "\U0001f7e2" if signal.direction.value == "BUY" else "\U0001f534"
        auto_tag = " \\| \U0001f916 *Auto\\-Sell ENABLED*" if auto_sell else ""

        lines = [
            f"{direction_emoji} *TRADE EXECUTED*{auto_tag}",
            "",
            f"*{esc(signal.direction.value)} {esc(signal.symbol)}*",
            f"Price: {esc(f'{fill_price:.2f}')} \\| Qty: {esc(str(quantity))}",
            f"Strategy: {esc(signal.strategy_name)}",
        ]

        if auto_sell:
            ret = signal.expected_return_pct
            ret_str = f" \\({esc(f'{ret:+.1f}%')}\\)" if ret is not None else ""
            target_str = esc(f'{signal.target_price:.2f}') if signal.target_price else "Calculated"
            lines.extend([
                "",
                "\U0001f916 *Auto\\-Sell active:*",
                f"  Target: \u20b9{target_str}{ret_str}",
                f"  Stop: \u20b9{esc(f'{signal.stop_loss:.2f}')}",
                f"  \u23f0 {esc(signal.display_horizon)}",
                "\U0001f6e1 *GTT protection on exchange*",
            ])

        return self._send("\n".join(lines))

    def send_auto_sell_exit(
        self,
        symbol: str,
        exit_signal: ExitSignal,
        exit_price: float,
        pnl: float,
        entry_price: float,
        quantity: int,
    ) -> bool:
        """Notify user of an automatic position exit."""
        if not self.is_configured:
            return False

        esc = self._escape_md
        pnl_emoji = "\U0001f7e2" if pnl >= 0 else "\U0001f534"
        urgency_emoji = {"HIGH": "\U0001f6a8", "MEDIUM": "\u26a0\ufe0f", "LOW": "\u2139\ufe0f"}.get(exit_signal.urgency, "\u26a0\ufe0f")

        pnl_pct = (pnl / (entry_price * quantity)) * 100 if entry_price * quantity > 0 else 0
        pnl_str = f"{pnl:+,.2f}"
        pnl_pct_str = f"{pnl_pct:+.1f}%"

        # Distinguish GTT-triggered vs software-triggered exits
        is_gtt = exit_signal.reason.value.startswith("gtt_")
        header = "\U0001f6e1 *GTT TRIGGERED*" if is_gtt else f"{urgency_emoji} *AUTO\\-SELL EXECUTED*"
        method = "Exchange \\(GTT\\)" if is_gtt else "Software monitor"

        lines = [
            header,
            "",
            f"*{esc(symbol)}* position closed automatically",
            f"*Via:* {method}",
            "",
            f"*Reason:* {esc(exit_signal.reason.value.replace('_', ' ').title())}",
            f"*Details:* {esc(exit_signal.message)}",
            f"*Urgency:* {esc(exit_signal.urgency)}",
            "",
            f"{pnl_emoji} *PnL:* {esc(pnl_str)} \\({esc(pnl_pct_str)}\\)",
            f"*Entry:* {esc(f'{entry_price:.2f}')} \\| *Exit:* {esc(f'{exit_price:.2f}')}",
            f"*Quantity:* {esc(str(quantity))}",
        ]

        return self._send("\n".join(lines))

    def send_exit_reminder(
        self,
        symbol: str,
        reason: str,
        urgency: str,
        current_price: float,
        entry_price: float,
        suggestion: str,
    ) -> bool:
        """Send an exit reminder for manually-managed positions."""
        if not self.is_configured:
            return False

        esc = self._escape_md
        pnl_pct = (current_price - entry_price) / entry_price * 100
        pnl_emoji = "\U0001f7e2" if pnl_pct >= 0 else "\U0001f534"
        urgency_emoji = {"HIGH": "\U0001f6a8", "MEDIUM": "\u26a0\ufe0f", "LOW": "\u2139\ufe0f"}.get(urgency, "\u26a0\ufe0f")

        lines = [
            f"{urgency_emoji} *EXIT REMINDER*",
            "",
            f"*{esc(symbol)}* \\| {pnl_emoji} {esc(f'{pnl_pct:+.1f}%')}",
            f"*Reason:* {esc(reason)}",
            f"*Current:* {esc(f'{current_price:.2f}')} \\| *Entry:* {esc(f'{entry_price:.2f}')}",
            "",
            f"*Suggested action:* {esc(suggestion)}",
        ]

        return self._send("\n".join(lines))

    def send_daily_summary(self, summary: Dict[str, Any]) -> bool:
        """Send end-of-day summary."""
        if not self.is_configured:
            return False
        text = self._format_daily_summary(summary)
        return self._send(text)

    def send_alert(self, message: str) -> bool:
        """Send a plain text alert (kill switch, errors, etc.)."""
        if not self.is_configured:
            return False
        return self._send(f"\u26a0\ufe0f *ALERT*\n{self._escape_md(message)}")

    def send_plain(self, text: str) -> Optional[int]:
        """Send a plain-text (no Markdown escaping) message; return the message_id."""
        if not self.is_configured:
            return None
        url = f"{TELEGRAM_API_BASE.format(token=self._token)}/sendMessage"
        try:
            resp = httpx.post(
                url,
                json={
                    "chat_id": self._chat_id,
                    "text": text,
                    "disable_web_page_preview": True,
                },
                timeout=self._timeout,
            )
            data = resp.json()
            if resp.status_code == 200 and data.get("ok"):
                return int(data["result"]["message_id"])
            logger.warning("telegram_send_plain_failed", description=data.get("description", ""))
        except httpx.HTTPError as e:
            logger.error("telegram_http_error", error=str(e))
        return None

    def process_updates_once(
        self,
        offset: int,
        handler: Optional[Callable[[str, str], None]] = None,
    ) -> int:
        """One-shot getUpdates (short poll). Returns the next offset to persist.

        Designed for cloud Routines: called every run instead of a long-lived
        daemon. `handler(action, signal_id)` is invoked for every
        callback_query parsed the same way as `_poll_callbacks`.
        """
        if not self.is_configured:
            return offset
        url = f"{TELEGRAM_API_BASE.format(token=self._token)}/getUpdates"
        try:
            resp = httpx.get(
                url,
                params={"offset": offset, "timeout": 0, "allowed_updates": ["callback_query"]},
                timeout=10.0,
            )
            data = resp.json()
        except httpx.HTTPError as e:
            logger.error("telegram_poll_once_http_error", error=str(e))
            return offset

        if not data.get("ok"):
            return offset

        next_offset = offset
        self._callback_handler = handler
        for update in data.get("result", []):
            update_id = update.get("update_id", 0)
            next_offset = max(next_offset, update_id + 1)
            cb = update.get("callback_query")
            if cb:
                self._handle_callback(cb)
        return next_offset

    def update_signal_message(self, message_id: int, action: TradeAction, symbol: str) -> bool:
        """Update the original signal message to show the user's action."""
        if not self.is_configured or not message_id:
            return False

        action_text = {
            TradeAction.APPROVE: "\u2705 Manual Trade Placed",
            TradeAction.IGNORE: "\u274c Ignored",
            TradeAction.AUTO_SELL: "\U0001f916 Bought with Auto-Sell",
        }.get(action, str(action))

        try:
            url = f"{TELEGRAM_API_BASE.format(token=self._token)}/editMessageReplyMarkup"
            # Remove buttons after action
            payload = {
                "chat_id": self._chat_id,
                "message_id": message_id,
                "reply_markup": {"inline_keyboard": []},
            }
            httpx.post(url, json=payload, timeout=self._timeout)

            # Send confirmation
            self._send(f"*{self._escape_md(symbol)}*: {self._escape_md(action_text)}")
            return True
        except Exception as e:
            logger.error("telegram_update_message_error", error=str(e))
            return False

    # ---- Memory Update Approval ----

    def send_memory_update_for_approval(
        self,
        pending_id: int,
        headline: str,
        summary: str,
        has_mistakes: bool,
        has_learnings: bool,
        has_strategy: bool,
    ) -> Optional[int]:
        """Send a memory-update draft with Approve & Commit / Reject buttons.

        Returns the Telegram message_id for later editing.
        """
        if not self.is_configured:
            logger.warning("telegram_not_configured")
            return None

        esc = self._escape_md
        flags = []
        if has_mistakes:
            flags.append("MISTAKES\\.md")
        if has_learnings:
            flags.append("LEARNINGS\\.md")
        if has_strategy:
            flags.append("TRADING\\-STRATEGY\\.md")
        flag_line = " \\+ ".join(flags) if flags else "no files"

        # Telegram message limit: 4096 chars. Truncate summary aggressively.
        summary_excerpt = summary[:1500] + ("..." if len(summary) > 1500 else "")

        lines = [
            "\U0001f9e0 *Memory Update Proposed*",
            "",
            f"*{esc(headline)}*",
            "",
            f"*Would update:* {flag_line}",
            "",
            "*Preview:*",
            f"```\n{summary_excerpt}\n```",
            "",
            "\u2b07\ufe0f *Approve to commit these diffs to memory/\\*\\.md*",
        ]

        keyboard = {
            "inline_keyboard": [
                [
                    {
                        "text": "\u2705 Approve & Commit",
                        "callback_data": f"memory_update:{pending_id}:approve",
                    },
                    {
                        "text": "\u274c Reject",
                        "callback_data": f"memory_update:{pending_id}:reject",
                    },
                ]
            ]
        }
        # Use plain Markdown (not V2) for code fence rendering with minimal escapes.
        text = "\n".join(lines)
        return self._send_with_keyboard(text, keyboard)

    def update_memory_message(self, message_id: int, new_status: str) -> bool:
        """Edit a memory-update message to reflect approved / rejected / expired status."""
        if not self.is_configured or not message_id:
            return False

        try:
            url = f"{TELEGRAM_API_BASE.format(token=self._token)}/editMessageReplyMarkup"
            httpx.post(
                url,
                json={
                    "chat_id": self._chat_id,
                    "message_id": message_id,
                    "reply_markup": {"inline_keyboard": []},
                },
                timeout=self._timeout,
            )
            self._send(f"\U0001f9e0 *Memory update:* {self._escape_md(new_status)}")
            return True
        except Exception as e:
            logger.error("telegram_update_memory_error", error=str(e))
            return False

    # ---- Callback Polling ----

    def start_callback_polling(self, handler: Callable[[str, str], None]) -> None:
        """Start polling for inline keyboard callback responses.

        Args:
            handler: Callback function(action, signal_id) called when user taps a button.
                     action is one of: "approve", "ignore", "auto_sell"
        """
        if self._polling_active:
            return

        self._callback_handler = handler
        self._polling_active = True
        self._polling_thread = threading.Thread(
            target=self._poll_callbacks, daemon=True, name="telegram-callbacks"
        )
        self._polling_thread.start()
        logger.info("telegram_callback_polling_started")

    def stop_callback_polling(self) -> None:
        """Stop polling for callbacks."""
        self._polling_active = False
        if self._polling_thread:
            self._polling_thread.join(timeout=5)
        logger.info("telegram_callback_polling_stopped")

    def _poll_callbacks(self) -> None:
        """Long-poll Telegram for callback query updates."""
        url = f"{TELEGRAM_API_BASE.format(token=self._token)}/getUpdates"

        while self._polling_active:
            try:
                params = {
                    "offset": self._last_update_id + 1,
                    "timeout": 30,  # Long poll (30 seconds)
                    "allowed_updates": ["callback_query"],
                }

                response = httpx.get(url, params=params, timeout=35)
                data = response.json()

                if not data.get("ok"):
                    time.sleep(2)
                    continue

                for update in data.get("result", []):
                    update_id = update.get("update_id", 0)
                    self._last_update_id = max(self._last_update_id, update_id)

                    callback = update.get("callback_query")
                    if callback:
                        self._handle_callback(callback)

            except httpx.TimeoutException:
                continue  # Normal for long polling
            except Exception as e:
                logger.error("telegram_poll_error", error=str(e))
                time.sleep(5)

    def _handle_callback(self, callback: Dict[str, Any]) -> None:
        """Process a callback query from an inline keyboard button press."""
        callback_id = callback.get("id", "")
        callback_data = callback.get("data", "")

        # Answer the callback to remove loading state on button
        self._answer_callback(callback_id)

        if ":" not in callback_data:
            return

        action, signal_id = callback_data.split(":", 1)

        logger.info(
            "telegram_callback_received",
            action=action,
            signal_id=signal_id,
        )

        if self._callback_handler:
            try:
                self._callback_handler(action, signal_id)
            except Exception as e:
                logger.error("telegram_callback_handler_error", error=str(e))

    def _answer_callback(self, callback_id: str) -> None:
        """Acknowledge a callback query to remove loading indicator."""
        try:
            url = f"{TELEGRAM_API_BASE.format(token=self._token)}/answerCallbackQuery"
            httpx.post(url, json={"callback_query_id": callback_id}, timeout=5)
        except Exception:
            pass

    # ---- Core Send Methods ----

    def _send(self, text: str, parse_mode: str = "MarkdownV2") -> bool:
        """Send a message via Telegram Bot API."""
        url = f"{TELEGRAM_API_BASE.format(token=self._token)}/sendMessage"
        payload = {
            "chat_id": self._chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }

        try:
            response = httpx.post(url, json=payload, timeout=self._timeout)
            data = response.json()

            if response.status_code == 200 and data.get("ok"):
                logger.info("telegram_sent", chat_id=self._chat_id)
                return True
            else:
                logger.warning(
                    "telegram_send_failed",
                    status=response.status_code,
                    description=data.get("description", ""),
                )
                return False
        except httpx.HTTPError as e:
            logger.error("telegram_http_error", error=str(e))
            return False

    def _send_with_keyboard(self, text: str, keyboard: Dict[str, Any]) -> Optional[int]:
        """Send a message with inline keyboard buttons. Returns message_id."""
        url = f"{TELEGRAM_API_BASE.format(token=self._token)}/sendMessage"
        payload = {
            "chat_id": self._chat_id,
            "text": text,
            "parse_mode": "MarkdownV2",
            "reply_markup": keyboard,
        }

        try:
            response = httpx.post(url, json=payload, timeout=self._timeout)
            data = response.json()

            if response.status_code == 200 and data.get("ok"):
                message_id = data.get("result", {}).get("message_id")
                logger.info("telegram_sent_with_keyboard", message_id=message_id)
                return message_id
            else:
                logger.warning(
                    "telegram_keyboard_send_failed",
                    status=response.status_code,
                    description=data.get("description", ""),
                )
                return None
        except httpx.HTTPError as e:
            logger.error("telegram_http_error", error=str(e))
            return None

    # ---- Formatting ----

    @staticmethod
    def _escape_md(text: str) -> str:
        """Escape special characters for Telegram MarkdownV2."""
        special = r"_[]()~`>#+-=|{}.!"
        for char in special:
            text = text.replace(char, f"\\{char}")
        return text

    @classmethod
    def _format_signal_approval(cls, signal: ScoredSignal) -> str:
        """Format signal as clean, action-oriented approval notification."""
        esc = cls._escape_md
        direction_emoji = "\U0001f7e2" if signal.direction.value == "BUY" else "\U0001f534"

        lines = [
            f"{direction_emoji} *Stock:* {esc(signal.symbol)}",
            f"*Recommendation:* {esc(signal.direction.value)}",
            "",
        ]

        # Price levels and expected return
        lines.append(f"*Entry:* \u20b9{esc(f'{signal.entry_price:.2f}')}")
        if signal.target_price:
            lines.append(f"*Target:* \u20b9{esc(f'{signal.target_price:.2f}')}")
        lines.append(f"*Stop Loss:* \u20b9{esc(f'{signal.stop_loss:.2f}')}")

        ret = signal.expected_return_pct
        if ret is not None:
            lines.append(f"*Expected Return:* {esc(f'{ret:+.1f}%')}")
        lines.append("")

        # Horizon
        lines.append(f"\u23f0 *Horizon:* {esc(signal.display_horizon)}")
        lines.append("")

        # Rationale — combine summary, drivers, and risks
        rationale_parts = []
        if signal.summary:
            rationale_parts.append(signal.summary)
        if signal.key_drivers:
            rationale_parts.append(", ".join(signal.key_drivers[:3]))
        rationale_text = ". ".join(rationale_parts) if rationale_parts else "AI analysis pending"
        if signal.risks:
            rationale_text += f". Risk: {', '.join(signal.risks[:2])}"

        lines.append("\U0001f4a1 *Rationale:*")
        lines.append(f"_{esc(rationale_text)}_")
        lines.append("")

        lines.append("\u2b07\ufe0f *Choose an action:*")

        return "\n".join(lines)

    @classmethod
    def _format_signal(cls, signal: ScoredSignal) -> str:
        """Format signal as Telegram message with MarkdownV2 (no buttons)."""
        esc = cls._escape_md
        direction_emoji = "\U0001f7e2" if signal.direction.value == "BUY" else "\U0001f534"
        strength_map = {"STRONG": "\u2b50\u2b50\u2b50", "MODERATE": "\u2b50\u2b50", "WEAK": "\u2b50"}

        header = f"{direction_emoji} *{esc(signal.direction.value)} {esc(signal.symbol)}*"

        lines = [
            header,
            "",
            f"*Strategy:* {esc(signal.strategy_name)}",
            f"*Sentiment:* {esc(signal.sentiment.value)} \\| *Strength:* {strength_map.get(signal.strength.value, chr(0x2B50))}",
            f"*Confidence:* {esc(f'{signal.confidence:.2f}')} \\| *Score:* {esc(f'{signal.final_score:.2f}')}",
        ]

        if signal.target_price:
            lines.append(
                f"*Entry:* \u20b9{esc(f'{signal.entry_price:.2f}')} \\| "
                f"*Stop:* \u20b9{esc(f'{signal.stop_loss:.2f}')} \\| "
                f"*Target:* \u20b9{esc(f'{signal.target_price:.2f}')}"
            )
        else:
            lines.append(
                f"*Entry:* \u20b9{esc(f'{signal.entry_price:.2f}')} \\| "
                f"*Stop:* \u20b9{esc(f'{signal.stop_loss:.2f}')}"
            )

        if signal.key_drivers:
            drivers = ", ".join(signal.key_drivers[:3])
            lines.append(f"*Drivers:* {esc(drivers)}")

        if signal.risks:
            risks = ", ".join(signal.risks[:2])
            lines.append(f"*Risks:* {esc(risks)}")

        if signal.summary:
            lines.append(f"\n_{esc(signal.summary)}_")

        if signal.regime:
            lines.append(f"*Regime:* {esc(signal.regime.value)}")

        return "\n".join(lines)

    @classmethod
    def _format_daily_summary(cls, summary: Dict[str, Any]) -> str:
        esc = cls._escape_md
        win_rate = summary.get("win_rate", 0)
        realized_pnl = summary.get("realized_pnl", 0)
        capital_deployed = summary.get("capital_deployed", 0)
        win_rate_str = f"{win_rate:.1%}"
        pnl_str = f"{realized_pnl:.2f}"
        capital_str = f"{capital_deployed:.2f}"
        lines = [
            "\U0001f4ca *Daily Summary*",
            "",
            f"*Trades:* {esc(str(summary.get('total_trades', 0)))}",
            f"*Win Rate:* {esc(win_rate_str)}",
            f"*PnL:* \u20b9{esc(pnl_str)}",
            f"*Open Positions:* {esc(str(summary.get('open_positions', 0)))}",
            f"*Capital Deployed:* \u20b9{esc(capital_str)}",
        ]
        if summary.get("regime"):
            lines.append(f"*Regime:* {esc(str(summary['regime']))}")
        return "\n".join(lines)
