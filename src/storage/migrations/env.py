"""Alembic environment.

URL resolution order:
  1. -x url=... CLI override (e.g. `alembic -x url=postgresql://... upgrade head`)
  2. DATABASE_URL env var
  3. DATABASE_URL_PAPER or DATABASE_URL_LIVE based on EXECUTION_MODE
  4. Fallback SQLite file (offline dev)
"""
from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from src.storage.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _resolve_url() -> str:
    x_args = context.get_x_argument(as_dictionary=True)
    if "url" in x_args:
        return x_args["url"]

    if os.getenv("DATABASE_URL"):
        return os.environ["DATABASE_URL"]

    mode = os.getenv("EXECUTION_MODE", "paper").lower()
    var = "DATABASE_URL_LIVE" if mode == "live" else "DATABASE_URL_PAPER"
    if os.getenv(var):
        return os.environ[var]

    return f"sqlite:///insight_alpha_{mode}.db"


def run_migrations_offline() -> None:
    context.configure(
        url=_resolve_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    cfg = config.get_section(config.config_ini_section) or {}
    cfg["sqlalchemy.url"] = _resolve_url()
    connectable = engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
