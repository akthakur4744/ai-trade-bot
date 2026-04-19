"""Tests for notification modules — Telegram and WhatsApp."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.models import (
    ConfidenceBreakdown,
    Direction,
    MarketRegime,
    ScoredSignal,
    Sentiment,
    Strength,
)
from src.notifications.telegram import TelegramNotifier
from src.notifications.whatsapp import WhatsAppNotifier


def _make_signal() -> ScoredSignal:
    return ScoredSignal(
        symbol="RELIANCE",
        direction=Direction.BUY,
        sentiment=Sentiment.BULLISH,
        confidence=0.78,
        strength=Strength.STRONG,
        final_score=0.82,
        confidence_breakdown=ConfidenceBreakdown(
            news_strength=0.7,
            signal_alignment=0.8,
            market_confirmation=0.9,
        ),
        strategy_name="momentum",
        key_drivers=["Earnings beat", "Volume spike"],
        risks=["Global headwinds"],
        summary="Strong momentum play on RELIANCE",
        entry_price=2500.0,
        stop_loss=2450.0,
        target_price=2600.0,
        regime=MarketRegime.BULL,
    )


# ---- Telegram Tests ----


class TestTelegramNotifier:
    def test_not_configured(self):
        notifier = TelegramNotifier(bot_token="", chat_id="")
        assert not notifier.is_configured
        assert notifier.send_signal(_make_signal()) is False

    def test_is_configured(self):
        notifier = TelegramNotifier(bot_token="123:ABC", chat_id="456")
        assert notifier.is_configured

    def test_partially_configured(self):
        notifier = TelegramNotifier(bot_token="123:ABC", chat_id="")
        assert not notifier.is_configured

    def test_escape_md(self):
        text = TelegramNotifier._escape_md("hello_world [test] (1.5)")
        assert "\\_" in text
        assert "\\[" in text
        assert "\\(" in text

    def test_format_signal_buy(self):
        text = TelegramNotifier._format_signal(_make_signal())
        assert "BUY" in text
        assert "RELIANCE" in text
        assert "momentum" in text
        assert "2500" in text
        assert "2450" in text
        assert "2600" in text

    def test_format_signal_sell(self):
        signal = _make_signal().model_copy(update={"direction": Direction.SELL})
        text = TelegramNotifier._format_signal(signal)
        assert "SELL" in text
        assert "🔴" in text

    def test_format_signal_no_target(self):
        signal = _make_signal().model_copy(update={"target_price": None})
        text = TelegramNotifier._format_signal(signal)
        assert "Target" not in text

    def test_format_signal_with_regime(self):
        text = TelegramNotifier._format_signal(_make_signal())
        assert "bull" in text

    def test_format_daily_summary(self):
        summary = {
            "total_trades": 3,
            "win_rate": 0.667,
            "realized_pnl": 1500.50,
            "open_positions": 1,
            "capital_deployed": 8000.0,
            "regime": "bull",
        }
        text = TelegramNotifier._format_daily_summary(summary)
        assert "3" in text
        assert "1500" in text
        assert "bull" in text

    @patch("src.notifications.telegram.httpx.post")
    def test_send_success(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"ok": True, "result": {}}),
        )
        notifier = TelegramNotifier(bot_token="123:ABC", chat_id="456")
        assert notifier.send_signal(_make_signal()) is True
        mock_post.assert_called_once()

    @patch("src.notifications.telegram.httpx.post")
    def test_send_failure(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=400,
            json=MagicMock(return_value={"ok": False, "description": "Bad Request"}),
        )
        notifier = TelegramNotifier(bot_token="123:ABC", chat_id="456")
        assert notifier.send_signal(_make_signal()) is False

    @patch("src.notifications.telegram.httpx.post")
    def test_send_alert(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"ok": True}),
        )
        notifier = TelegramNotifier(bot_token="123:ABC", chat_id="456")
        assert notifier.send_alert("Kill switch activated") is True

    @patch("src.notifications.telegram.httpx.post")
    def test_send_daily_summary(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"ok": True}),
        )
        notifier = TelegramNotifier(bot_token="123:ABC", chat_id="456")
        summary = {"total_trades": 5, "win_rate": 0.6, "realized_pnl": 2000.0, "open_positions": 2, "capital_deployed": 15000.0}
        assert notifier.send_daily_summary(summary) is True

    def test_format_signal_approval(self):
        text = TelegramNotifier._format_signal_approval(_make_signal())
        assert "Stock" in text
        assert "BUY" in text
        assert "RELIANCE" in text
        assert "2500" in text
        assert "Rationale" in text
        assert "Risk" in text
        assert "action" in text.lower()

    @patch("src.notifications.telegram.httpx.post")
    def test_send_signal_for_approval(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"ok": True, "result": {"message_id": 42}}),
        )
        notifier = TelegramNotifier(bot_token="123:ABC", chat_id="456")
        msg_id = notifier.send_signal_for_approval(_make_signal(), "test-id-1")
        assert msg_id == 42
        # Verify the keyboard was included in the payload
        call_kwargs = mock_post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert "reply_markup" in payload
        assert "inline_keyboard" in payload["reply_markup"]

    @patch("src.notifications.telegram.httpx.post")
    def test_send_trade_executed(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"ok": True}),
        )
        notifier = TelegramNotifier(bot_token="123:ABC", chat_id="456")
        result = notifier.send_trade_executed(
            _make_signal(), fill_price=2502.50, quantity=4, auto_sell=True
        )
        assert result is True

    @patch("src.notifications.telegram.httpx.post")
    def test_send_auto_sell_exit(self, mock_post):
        from src.models import ExitReason, ExitSignal
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"ok": True}),
        )
        notifier = TelegramNotifier(bot_token="123:ABC", chat_id="456")
        exit_signal = ExitSignal(
            symbol="RELIANCE",
            reason=ExitReason.TARGET,
            urgency="LOW",
            message="Target hit at 2600",
        )
        result = notifier.send_auto_sell_exit(
            symbol="RELIANCE",
            exit_signal=exit_signal,
            exit_price=2600.0,
            pnl=400.0,
            entry_price=2500.0,
            quantity=4,
        )
        assert result is True


# ---- WhatsApp Tests ----


class TestWhatsAppNotifier:
    def test_not_configured(self):
        notifier = WhatsAppNotifier()
        assert not notifier.is_configured
        assert notifier.send_signal(_make_signal()) is False

    def test_is_configured(self):
        notifier = WhatsAppNotifier(
            account_sid="AC123",
            auth_token="token",
            from_number="whatsapp:+14155238886",
            to_number="whatsapp:+919999999999",
        )
        assert notifier.is_configured

    def test_format_signal(self):
        text = WhatsAppNotifier._format_signal(_make_signal())
        assert "BUY" in text
        assert "RELIANCE" in text
        assert "2500" in text
        assert "momentum" in text

    def test_format_daily_summary(self):
        summary = {"total_trades": 2, "win_rate": 0.5, "realized_pnl": 500.0, "open_positions": 0}
        text = WhatsAppNotifier._format_daily_summary(summary)
        assert "500" in text

    @patch("src.notifications.whatsapp.httpx.post")
    def test_send_success(self, mock_post):
        mock_post.return_value = MagicMock(status_code=201)
        notifier = WhatsAppNotifier(
            account_sid="AC123",
            auth_token="token",
            from_number="whatsapp:+14155238886",
            to_number="whatsapp:+919999999999",
        )
        assert notifier.send_signal(_make_signal()) is True

    @patch("src.notifications.whatsapp.httpx.post")
    def test_send_failure(self, mock_post):
        mock_post.return_value = MagicMock(status_code=400, text="Bad Request")
        notifier = WhatsAppNotifier(
            account_sid="AC123",
            auth_token="token",
            from_number="whatsapp:+14155238886",
            to_number="whatsapp:+919999999999",
        )
        assert notifier.send_signal(_make_signal()) is False
