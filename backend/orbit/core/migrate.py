"""Explicit schema upgrade, also used by disposable integration databases."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text


def upgrade(engine):
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    with engine.begin() as connection:
        if engine.dialect.name == "postgresql":
            connection.execute(text("SELECT pg_advisory_xact_lock(734821907)"))
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


if __name__ == "__main__":
    from .database import get_engine

    upgrade(get_engine())
    print("Personal workspace schema is up to date.")
