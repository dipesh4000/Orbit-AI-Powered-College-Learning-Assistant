"""Multi-session personal chat history. Each owner can have many named sessions."""

from time import time

from fastapi import HTTPException
from sqlalchemy import select

from . import database as db

MAX_SESSIONS = 50
MAX_HISTORY = 20
MAX_TRANSCRIPT = 200


def list_sessions(owner_id, engine):
    with engine.connect() as conn:
        rows = conn.execute(
            select(
                db.personal_chat_sessions.c.id,
                db.personal_chat_sessions.c.title,
                db.personal_chat_sessions.c.created_at,
                db.personal_chat_sessions.c.updated_at,
            )
            .where(db.personal_chat_sessions.c.owner_id == owner_id)
            .order_by(db.personal_chat_sessions.c.updated_at.desc())
        ).mappings()
        return [dict(r) for r in rows]


def load(owner_id, engine, session_id):
    with engine.connect() as conn:
        row = conn.execute(
            select(db.personal_chat_sessions).where(
                db.personal_chat_sessions.c.owner_id == owner_id,
                db.personal_chat_sessions.c.id == session_id,
            )
        ).mappings().first()
    if row is None:
        raise HTTPException(404, "Chat session not found.")
    return dict(row)


def create(owner_id, engine):
    now = time()
    with engine.begin() as conn:
        # Enforce cap: remove oldest beyond limit
        ids = [
            r[0]
            for r in conn.execute(
                select(db.personal_chat_sessions.c.id)
                .where(db.personal_chat_sessions.c.owner_id == owner_id)
                .order_by(db.personal_chat_sessions.c.updated_at.desc())
            )
        ]
        if len(ids) >= MAX_SESSIONS:
            for old_id in ids[MAX_SESSIONS - 1:]:
                conn.execute(
                    db.personal_chat_sessions.delete().where(
                        db.personal_chat_sessions.c.id == old_id,
                        db.personal_chat_sessions.c.owner_id == owner_id,
                    )
                )
        key = conn.execute(
            db.personal_chat_sessions.insert().values(
                owner_id=owner_id,
                title="New chat",
                history=[],
                transcript=[],
                created_at=now,
                updated_at=now,
            )
        ).inserted_primary_key[0]
    return {"id": key, "title": "New chat", "created_at": now, "updated_at": now}


def restore(owner_id, engine, state, session_id):
    """Load a session into the in-memory state dict. Returns the session row."""
    row = load(owner_id, engine, session_id)
    state["history"] = list(row["history"])
    state["transcript"] = list(row["transcript"])
    return row


def save(owner_id, engine, state, session_id):
    history = state.get("history", [])[-MAX_HISTORY:]
    transcript = state.get("transcript", [])[-MAX_TRANSCRIPT:]
    # Auto-title from first user message
    title = "New chat"
    for m in transcript:
        if m.get("role") == "user":
            title = m["content"][:80]
            break
    now = time()
    with engine.begin() as conn:
        conn.execute(
            db.personal_chat_sessions.update()
            .where(
                db.personal_chat_sessions.c.id == session_id,
                db.personal_chat_sessions.c.owner_id == owner_id,
            )
            .values(history=history, transcript=transcript, title=title, updated_at=now)
        )


def delete(owner_id, engine, session_id):
    with engine.begin() as conn:
        result = conn.execute(
            db.personal_chat_sessions.delete().where(
                db.personal_chat_sessions.c.id == session_id,
                db.personal_chat_sessions.c.owner_id == owner_id,
            )
        )
    if not result.rowcount:
        raise HTTPException(404, "Chat session not found.")
    return {"ok": True}
