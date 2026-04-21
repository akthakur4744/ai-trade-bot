"""Kite session token store — backed by `app_state` in Neon.

The daily login flow writes `kite_access_token` + `kite_session_expires_at`
after the Cloudflare Worker receives the Zerodha redirect. All cloud routines
read the token from here at startup; they exit 0 with an alert if stale.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.storage.models import AppState

ACCESS_TOKEN_KEY = "kite_access_token"
EXPIRES_AT_KEY = "kite_session_expires_at"
LOGIN_MESSAGE_ID_KEY = "kite_login_message_id"


@dataclass
class KiteSession:
    access_token: str
    expires_at: datetime  # UTC

    def is_active(self, now: Optional[datetime] = None) -> bool:
        now = now or datetime.now(timezone.utc)
        return now < self.expires_at


def _get(session: Session, key: str) -> Optional[str]:
    row = session.query(AppState).filter_by(key=key).first()
    return row.value if row else None


def _set(session: Session, key: str, value: str) -> None:
    row = session.query(AppState).filter_by(key=key).first()
    if row:
        row.value = value
    else:
        session.add(AppState(key=key, value=value))


def get_active_session(session: Session) -> Optional[KiteSession]:
    """Return the stored Kite session if it's still valid; else None."""
    token = _get(session, ACCESS_TOKEN_KEY)
    exp_raw = _get(session, EXPIRES_AT_KEY)
    if not token or not exp_raw:
        return None
    try:
        exp = datetime.fromisoformat(exp_raw)
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    ks = KiteSession(access_token=token, expires_at=exp)
    return ks if ks.is_active() else None


def store_session(session: Session, access_token: str, expires_at: datetime) -> None:
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    _set(session, ACCESS_TOKEN_KEY, access_token)
    _set(session, EXPIRES_AT_KEY, expires_at.isoformat())
    session.commit()


def clear_session(session: Session) -> None:
    for k in (ACCESS_TOKEN_KEY, EXPIRES_AT_KEY):
        row = session.query(AppState).filter_by(key=k).first()
        if row:
            session.delete(row)
    session.commit()


def set_login_message_id(session: Session, message_id: int) -> None:
    _set(session, LOGIN_MESSAGE_ID_KEY, json.dumps({"id": message_id, "ts": datetime.now(timezone.utc).isoformat()}))
    session.commit()


def get_login_message_id(session: Session) -> Optional[int]:
    raw = _get(session, LOGIN_MESSAGE_ID_KEY)
    if not raw:
        return None
    try:
        return int(json.loads(raw)["id"])
    except (ValueError, KeyError, json.JSONDecodeError):
        return None
