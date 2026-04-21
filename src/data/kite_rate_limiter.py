"""Cross-trigger rate limiter for Kite API calls — backed by Neon.

Kite quotas (per API key, enforced server-side):
  - 3 req/s historical
  - 10 req/s other endpoints

When multiple cloud Routines (signal-scan, telegram-poll, strategy-backtest)
share one API key, the per-process rate limit in `kite_client.py` is
insufficient. This module implements a token-bucket in `app_state` so any
concurrent trigger respects the global quota.

Usage:
    with kite_rate_limit(db, kind="historical"):
        kite.historical_data(...)
"""
from __future__ import annotations

import json
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterator

from sqlalchemy.orm import Session

from src.storage.models import AppState


@dataclass(frozen=True)
class Bucket:
    key: str
    capacity: int  # tokens
    refill_per_sec: float  # tokens/sec


BUCKETS = {
    "historical": Bucket(key="kite_bucket_historical", capacity=3, refill_per_sec=3.0),
    "default":    Bucket(key="kite_bucket_default",    capacity=10, refill_per_sec=10.0),
}


def _load(s: Session, bucket: Bucket) -> tuple[float, float]:
    row = s.query(AppState).filter_by(key=bucket.key).first()
    if not row:
        return (float(bucket.capacity), time.monotonic())
    try:
        d = json.loads(row.value)
        return (float(d["tokens"]), float(d["updated"]))
    except (ValueError, KeyError, json.JSONDecodeError):
        return (float(bucket.capacity), time.monotonic())


def _save(s: Session, bucket: Bucket, tokens: float, updated: float) -> None:
    val = json.dumps({"tokens": tokens, "updated": updated})
    row = s.query(AppState).filter_by(key=bucket.key).first()
    if row:
        row.value = val
    else:
        s.add(AppState(key=bucket.key, value=val))
    s.commit()


@contextmanager
def kite_rate_limit(db, kind: str = "default") -> Iterator[None]:
    """Block until a token is available, then consume one.

    Correctness caveats:
      - This is *optimistic* — two concurrent triggers could both read and
        both consume without seeing each other. Acceptable because Kite
        itself enforces the true quota server-side; this is advisory.
      - For strict cross-trigger coordination, add a SELECT ... FOR UPDATE
        around _load/_save (Postgres-only; SQLite will serialize via WAL).
    """
    bucket = BUCKETS.get(kind, BUCKETS["default"])
    while True:
        with db.get_session() as s:
            tokens, updated = _load(s, bucket)
            now = time.monotonic()
            tokens = min(bucket.capacity, tokens + (now - updated) * bucket.refill_per_sec)
            if tokens >= 1.0:
                _save(s, bucket, tokens - 1.0, now)
                break
            # Not enough tokens — wait roughly until one refills.
            wait = (1.0 - tokens) / bucket.refill_per_sec
        time.sleep(max(0.05, wait))
    try:
        yield
    finally:
        pass
