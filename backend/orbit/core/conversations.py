"""Persistent conversations, always scoped to the selected student."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select

from . import database as db


def listing(engine, user_id):
    db.conversations.create(engine, checkfirst=True)
    with engine.connect() as conn:
        return [
            dict(row)
            for row in conn.execute(
                select(
                    db.conversations.c.id,
                    db.conversations.c.title,
                    db.conversations.c.updated_at,
                )
                .where(db.conversations.c.user_id == user_id)
                .order_by(db.conversations.c.updated_at.desc())
                .limit(50)
            ).mappings()
        ]


def load(engine, user_id, conversation_id):
    db.conversations.create(engine, checkfirst=True)
    with engine.connect() as conn:
        row = (
            conn.execute(
                select(db.conversations).where(
                    db.conversations.c.id == conversation_id,
                    db.conversations.c.user_id == user_id,
                )
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None


def save(engine, session):
    db.conversations.create(engine, checkfirst=True)
    conversation_id = session.get("conversation_id") or str(uuid4())
    messages = session.get("transcript", session["history"])[-200:]
    values = {"messages": messages, "updated_at": datetime.now(UTC).isoformat()}
    with engine.begin() as conn:
        if session.get("conversation_id"):
            result = conn.execute(
                db.conversations.update()
                .where(
                    db.conversations.c.id == conversation_id,
                    db.conversations.c.user_id == session["user_id"],
                )
                .values(**values)
            )
            if result.rowcount != 1:
                raise ValueError("Conversation is unavailable for this student.")
        else:
            conn.execute(
                db.conversations.insert().values(
                    id=conversation_id,
                    user_id=session["user_id"],
                    title=messages[0]["content"][:80],
                    **values,
                )
            )
    session["conversation_id"] = conversation_id
    return conversation_id
