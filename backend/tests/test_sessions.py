"""Session state must survive worker restarts and independent DB connections."""

import asyncio

import pytest
from fastapi import HTTPException
from orbit import database as db
from orbit import sessions
from sqlalchemy import create_engine, select


@pytest.fixture
def workers(tmp_path):
    url = "sqlite:///" + (tmp_path / "sessions.db").as_posix()
    engines = [create_engine(url), create_engine(url)]
    yield engines
    for engine in engines:
        engine.dispose()
    sessions.prepare.cache_clear()


def test_session_and_chat_state_survive_worker_restart(workers):
    first, second = workers
    token = sessions.create(first, {"user_id": "student-a", "label": "Student A"})
    first.dispose()
    state = sessions.load(second, token)

    async def update():
        async with state["lock"]:
            state["history"] = [{"role": "user", "content": "Hello"}]
            state["transcript"] = state["history"][:]
            state["conversation_id"] = "saved-chat"

    asyncio.run(update())
    restored = sessions.load(first, token)
    assert restored["user_id"] == "student-a"
    assert restored["history"] == state["history"]
    assert restored["transcript"] == state["transcript"]
    assert restored["conversation_id"] == "saved-chat"
    with first.connect() as conn:
        assert conn.scalar(select(db.sessions.c.token_hash)) != token


def test_logout_and_profile_switch_revoke_on_every_worker(workers):
    first, second = workers
    old = sessions.create(first, {"user_id": "student-a"})
    new = sessions.create(second, {"user_id": "student-b"}, old)
    with pytest.raises(HTTPException) as exc:
        sessions.load(first, old)
    assert exc.value.status_code == 401
    assert sessions.load(first, new)["user_id"] == "student-b"
    sessions.revoke(first, new)
    with pytest.raises(HTTPException) as exc:
        sessions.load(second, new)
    assert exc.value.status_code == 401


def test_expired_and_forged_cookies_are_rejected(workers, monkeypatch):
    first, second = workers
    monkeypatch.setattr(sessions, "time", lambda: 1000)
    token = sessions.create(first, {"user_id": "student-a"})
    for invalid in (None, "forged-token", token + "tampered"):
        with pytest.raises(HTTPException) as exc:
            sessions.load(second, invalid)
        assert exc.value.status_code == 401
    monkeypatch.setattr(sessions, "time", lambda: 1000 + sessions.MAX_AGE)
    with pytest.raises(HTTPException) as exc:
        sessions.load(second, token)
    assert exc.value.status_code == 401


def test_failed_turn_rolls_back_and_next_writer_reloads_latest_state(workers):
    first, second = workers
    token = sessions.create(first, {"user_id": "student-a"})
    a, b = sessions.load(first, token), sessions.load(second, token)

    async def update():
        with pytest.raises(ValueError):
            async with a["lock"]:
                a["conversation_id"] = "failed"
                raise ValueError("Provider failed")
        assert "conversation_id" not in sessions.load(second, token)
        async with a["lock"]:
            a["conversation_id"] = "latest"
        async with b["lock"]:
            assert b["conversation_id"] == "latest"
            b.pop("conversation_id")
            b["history"].clear()
            b["transcript"].clear()

    asyncio.run(update())
    assert "conversation_id" not in sessions.load(first, token)
