"""Databases moved forward by Alembic, for tests that then run the app on them."""
from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import command
from sqlalchemy import create_engine, text

from tests.word_support import TEST_SECTION

if TYPE_CHECKING:
    from alembic.config import Config

HEAD = "head"


def upgrade_to_head_with_sections(cfg: Config, url: str) -> None:
    """The later migrations, then a section on every phrase the earlier ones left
    without one."""
    command.upgrade(cfg, HEAD)
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE phrases SET earned_section = :s WHERE earned_section IS NULL"),
                {"s": TEST_SECTION},
            )
    finally:
        engine.dispose()
