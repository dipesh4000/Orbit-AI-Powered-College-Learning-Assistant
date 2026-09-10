"""Shared, revocable sessions for serverless workers; cookies contain only a token."""

import hashlib
import secrets
from functools import lru_cache
from time import time

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError
from starlette.concurrency import run_in_threadpool

from . import database as db

MAX_AGE = 8 * 3600


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


@lru_cache(maxsize=16)
def prepare(engine):
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            # Serialize first-use DDL when several cold workers start together.
            conn.execute(text("SELECT pg_advisory_xact_lock(734821906)"))
        db.sessions.create(conn, checkfirst=True)


def create(engine, student, previous_token=None):
    prepare(engine)
    token = secrets.token_urlsafe(32)
    with engine.begin() as conn:
        conn.execute(db.sessions.delete().where(db.sessions.c.expires_at <= time()))
        if previous_token:
            conn.execute(
                db.sessions.delete().where(
                    db.sessions.c.token_hash == token_hash(previous_token)
                )
            )
        conn.execute(
            db.sessions.insert().values(
                token_hash=token_hash(token),
                expires_at=time() + MAX_AGE,
                data={**dict(student), "history": [], "transcript": []},
            )
        )
    return token


def revoke(engine, token):
    if not token:
        return
    prepare(engine)
    with engine.begin() as conn:
        conn.execute(
            db.sessions.delete().where(db.sessions.c.token_hash == token_hash(token))
        )


def query(token):
    return select(db.sessions.c.data).where(
        db.sessions.c.token_hash == token_hash(token),
        db.sessions.c.expires_at > time(),
    )


def load(engine, token):
    if not token:
        raise HTTPException(401, "Choose a student to begin.")
    prepare(engine)
    with engine.connect() as conn:
        data = conn.execute(query(token)).scalar_one_or_none()
    if data is None:
        raise HTTPException(401, "Choose a student to begin.")
    data["lock"] = SessionLock(engine, token, data)
    return data


class SessionLock:
    """Lock the database row across workers and save state before responding.

    PostgreSQL releases this transaction lock even if a worker crashes. NOWAIT
    rejects simultaneous writes instead of silently overwriting a chat turn.
    """

    def __init__(self, engine, token, data):
        self.engine, self.token, self.data = engine, token, data
        self.connection = None

    def locked(self):
        return self.connection is not None

    def acquire(self):
        conn = self.engine.connect()
        try:
            fresh = conn.execute(
                query(self.token).with_for_update(nowait=True)
            ).scalar_one_or_none()
            if fresh is None:
                raise HTTPException(401, "Choose a student to begin.")
            self.data.clear()
            self.data.update(fresh)
            self.data["lock"] = self
            self.connection = conn
        except BaseException as exc:
            conn.close()
            if (
                isinstance(exc, OperationalError)
                and getattr(exc.orig, "sqlstate", None) == "55P03"
            ):
                raise HTTPException(
                    429, "Wait for your current request to finish."
                ) from exc
            raise

    def release(self, success):
        conn = self.connection
        try:
            if success:
                conn.execute(
                    db.sessions.update()
                    .where(db.sessions.c.token_hash == token_hash(self.token))
                    .values(data={k: v for k, v in self.data.items() if k != "lock"})
                )
                conn.commit()
        finally:
            conn.close()
            self.connection = None

    async def __aenter__(self):
        await run_in_threadpool(self.acquire)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await run_in_threadpool(self.release, exc_type is None)
