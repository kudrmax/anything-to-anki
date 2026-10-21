from __future__ import annotations

import sys
from pathlib import Path

from alembic import context
from sqlalchemy import pool

# Make the backend package importable when running `alembic` CLI from backend/
# alembic/ is now inside the package: backend/src/backend/alembic/
# parents[2] = backend/src/
_src = Path(__file__).parents[2]
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from backend.infrastructure.persistence import models  # noqa: E402,F401 — registers all ORM models
from backend.infrastructure.persistence.database import (  # noqa: E402
    Base,
    create_app_engine,
    default_db_url,
)

target_metadata = Base.metadata

config = context.config

# Set URL dynamically so alembic.ini doesn't need a hardcoded path
if not config.get_main_option("sqlalchemy.url", None):
    config.set_main_option("sqlalchemy.url", default_db_url())


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = config.get_main_option("sqlalchemy.url")
    assert url is not None
    connectable = create_app_engine(url, poolclass=pool.NullPool, foreign_keys=False)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
