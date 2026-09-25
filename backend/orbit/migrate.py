"""Compatibility entry point for schema upgrades."""

from .core.migrate import upgrade

if __name__ == "__main__":
    from .core.database import get_engine

    upgrade(get_engine())
    print("Personal workspace schema is up to date.")
