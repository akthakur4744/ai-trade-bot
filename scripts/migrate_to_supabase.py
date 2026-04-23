"""One-shot migration: run Alembic schema on both Supabase DBs.

Usage (from project root, with venv active):
    python scripts/migrate_to_supabase.py

Set env vars first:
    export DATABASE_URL_PAPER="postgresql://postgres:<pw>@db.mgarzpkoxgicdacujhny.supabase.co:5432/postgres"
    export DATABASE_URL_LIVE="postgresql://postgres:<pw>@db.xagungelhyaqwokamayo.supabase.co:5432/postgres"
"""
from __future__ import annotations

import os
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError


def _run_alembic(url: str, mode: str) -> bool:
    """Run alembic upgrade head against the given URL."""
    from alembic.config import Config
    from alembic import command

    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "src/storage/migrations")
    # Override the URL directly — avoids env var encoding issues
    cfg.set_section_option("alembic", "sqlalchemy.url", url)

    import os as _os
    _os.environ["EXECUTION_MODE"] = mode

    # Monkey-patch the URL resolution in env.py to use our URL
    _os.environ["DATABASE_URL"] = url

    try:
        command.upgrade(cfg, "head")
        return True
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def test_connection(url: str, label: str) -> bool:
    print(f"\n[{label}] Testing connection...")
    try:
        engine = create_engine(url, connect_args={"connect_timeout": 10})
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()")).scalar()
            print(f"  OK — {result[:40]}...")
        engine.dispose()
        return True
    except OperationalError as e:
        print(f"  FAILED — {str(e).splitlines()[0]}")
        return False


def run_migrations(url: str, label: str) -> bool:
    print(f"\n[{label}] Running Alembic migrations...")
    os.environ["DATABASE_URL"] = url
    mode = "live" if "live" in label.lower() else "paper"
    os.environ["EXECUTION_MODE"] = mode

    from alembic.config import Config
    from alembic import command

    cfg = Config("alembic.ini")
    try:
        command.upgrade(cfg, "head")
        print(f"  OK — schema applied")
        return True
    except Exception as e:
        msg = str(e).splitlines()[0]
        if "already exists" in msg or "DuplicateTable" in msg:
            print(f"  OK — tables already exist (skipped)")
            return True
        print(f"  ERROR — {msg}")
        return False


def main() -> int:
    paper_url = os.getenv("DATABASE_URL_PAPER")
    live_url = os.getenv("DATABASE_URL_LIVE")

    if not paper_url or not live_url:
        print("ERROR: Set DATABASE_URL_PAPER and DATABASE_URL_LIVE env vars first.")
        print()
        print("  export DATABASE_URL_PAPER='postgresql://postgres:<pw>@db.mgarzpkoxgicdacujhny.supabase.co:5432/postgres'")
        print("  export DATABASE_URL_LIVE='postgresql://postgres:<pw>@db.xagungelhyaqwokamayo.supabase.co:5432/postgres'")
        return 1

    ok = True
    for url, label in [(paper_url, "PAPER"), (live_url, "LIVE")]:
        if not test_connection(url, label):
            ok = False
            continue
        if not run_migrations(url, label):
            ok = False

    if ok:
        print("\nDone. Both Supabase DBs have the full schema.")
        print("Next: update DATABASE_URL_PAPER / DATABASE_URL_LIVE in your .env and Fly.io / CF Worker secrets.")
    else:
        print("\nOne or more steps failed. Check errors above.")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
