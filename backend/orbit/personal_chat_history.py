"""One durable main conversation per owner, with optimistic concurrent-write checks."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from . import database as db


def load(owner_id, engine):
    with engine.connect() as conn:
        row = (
            conn.execute(
                select(db.personal_chats).where(
                    db.personal_chats.c.owner_id == owner_id
                )
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None


def restore(owner_id, engine, state):
    row = load(owner_id, engine)
    if row:
        state["history"] = row["history"]
        state["transcript"] = row["transcript"]
    return row["version"] if row else None


def save(owner_id, engine, state, version):
    values = {
        "history": state.get("history", [])[-20:],
        "transcript": state.get("transcript", [])[-200:],
        "version": (version or 0) + 1,
    }
    try:
        with engine.begin() as conn:
            if version is None:
                conn.execute(
                    db.personal_chats.insert().values(owner_id=owner_id, **values)
                )
            else:
                updated = conn.execute(
                    db.personal_chats.update()
                    .where(
                        db.personal_chats.c.owner_id == owner_id,
                        db.personal_chats.c.version == version,
                    )
                    .values(**values)
                )
                if not updated.rowcount:
                    raise HTTPException(
                        409,
                        "Your chat changed in another window. Reload the conversation before sending again.",
                    )
    except IntegrityError as exc:
        raise HTTPException(
            409,
            "Your chat changed in another window. Reload the conversation before sending again.",
        ) from exc
