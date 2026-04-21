from datetime import date, datetime
from zoneinfo import ZoneInfo

from src.utils.market_calendar import (
    IST,
    is_market_open,
    is_trading_day,
    next_market_open,
)


def test_weekend_is_not_trading_day():
    assert not is_trading_day(date(2026, 4, 25))  # Saturday
    assert not is_trading_day(date(2026, 4, 26))  # Sunday


def test_holiday_is_not_trading_day():
    assert not is_trading_day(date(2026, 1, 26))  # Republic Day
    assert not is_trading_day(date(2026, 10, 2))  # Gandhi Jayanti


def test_regular_weekday_is_trading_day():
    assert is_trading_day(date(2026, 4, 21))  # Tue


def test_market_open_mid_session():
    t = datetime(2026, 4, 21, 11, 0, tzinfo=IST)
    assert is_market_open(t)


def test_market_closed_before_open():
    t = datetime(2026, 4, 21, 9, 0, tzinfo=IST)
    assert not is_market_open(t)


def test_market_closed_after_close():
    t = datetime(2026, 4, 21, 15, 31, tzinfo=IST)
    assert not is_market_open(t)


def test_market_closed_on_holiday():
    t = datetime(2026, 1, 26, 11, 0, tzinfo=IST)
    assert not is_market_open(t)


def test_next_market_open_from_weekend():
    fri_evening = datetime(2026, 4, 24, 18, 0, tzinfo=IST)
    nxt = next_market_open(fri_evening)
    assert nxt.date() == date(2026, 4, 27)  # Monday
    assert nxt.hour == 9 and nxt.minute == 15
