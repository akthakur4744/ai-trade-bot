"""NSE trading calendar.

Every remote trigger calls `is_market_open()` as its first step and exits 0
if the market is closed — this avoids burning Kite API calls and Anthropic
tokens on a public holiday.

The holiday list below is the NSE official 2026 equity-segment holidays.
Source: https://www.nseindia.com/resources/exchange-communication-holidays
Update this list in January each year.
"""
from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

# NSE equity segment holidays for 2026. Keep sorted.
NSE_HOLIDAYS_2026: frozenset[date] = frozenset({
    date(2026, 1, 26),   # Republic Day (Mon)
    date(2026, 2, 17),   # Mahashivratri (Tue)
    date(2026, 3, 3),    # Holi (Tue)
    date(2026, 3, 20),   # Eid-ul-Fitr (Fri)
    date(2026, 4, 3),    # Good Friday (Fri)
    date(2026, 4, 14),   # Ambedkar Jayanti (Tue)
    date(2026, 5, 1),    # Maharashtra Day (Fri)
    date(2026, 5, 27),   # Eid-ul-Adha (Wed, tentative)
    date(2026, 8, 15),   # Independence Day (Sat) — non-trading anyway
    date(2026, 8, 26),   # Ganesh Chaturthi (Wed, tentative)
    date(2026, 10, 2),   # Gandhi Jayanti (Fri)
    date(2026, 10, 20),  # Dussehra (Tue)
    date(2026, 11, 9),   # Diwali Laxmi Pujan / Muhurat (Mon — special session only)
    date(2026, 11, 10),  # Diwali Balipratipada (Tue)
    date(2026, 11, 25),  # Guru Nanak Jayanti (Wed)
    date(2026, 12, 25),  # Christmas (Fri)
})

MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)


def is_trading_day(d: date) -> bool:
    """True iff `d` is a weekday and not on the NSE holiday list."""
    if d.weekday() >= 5:  # Sat/Sun
        return False
    return d not in NSE_HOLIDAYS_2026


def is_market_open(now: datetime | None = None) -> bool:
    """True iff `now` (IST) is within the NSE equity-segment session window."""
    now = now or datetime.now(IST)
    if now.tzinfo is None:
        now = now.replace(tzinfo=IST)
    else:
        now = now.astimezone(IST)
    if not is_trading_day(now.date()):
        return False
    return MARKET_OPEN <= now.time() <= MARKET_CLOSE


def next_market_open(after: datetime | None = None) -> datetime:
    """Return the next datetime the market opens, in IST."""
    after = after or datetime.now(IST)
    if after.tzinfo is None:
        after = after.replace(tzinfo=IST)
    else:
        after = after.astimezone(IST)
    candidate = after.replace(hour=MARKET_OPEN.hour, minute=MARKET_OPEN.minute, second=0, microsecond=0)
    if candidate <= after:
        candidate = candidate.replace(day=candidate.day)
    while not is_trading_day(candidate.date()) or candidate <= after:
        # Advance one day at a time, at 09:15 IST.
        from datetime import timedelta
        candidate = (candidate + timedelta(days=1)).replace(
            hour=MARKET_OPEN.hour, minute=MARKET_OPEN.minute, second=0, microsecond=0
        )
    return candidate
