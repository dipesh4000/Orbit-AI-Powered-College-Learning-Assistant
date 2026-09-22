import asyncio
import time
from datetime import UTC, datetime

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from orbit import coding
from orbit import database as db
from orbit.main import app
from orbit.personal_tools import PersonalRegistry
from sqlalchemy import select
from test_personal import environment as environment  # noqa: PLC0414
from test_personal import register


def profile():
    stamp = str(
        int(
            datetime.now(UTC)
            .replace(hour=0, minute=0, second=0, microsecond=0)
            .timestamp()
        )
    )
    return {
        "status": {"success": True},
        "data": {
            "userDetails": {"email": "private@example.invalid"},
            "codolioCardDetails": {"totalQuestionsSolved": 42, "totalActiveDays": 0},
            "githubProfileDetails": {
                "totalContributions": 80,
                "commitCounts": 61,
                "pushRequestsCount": 3,
                "developmentActivity": {stamp: 4, "bad": 9},
                "languageDistributions": {"Python": 75, "Java": 25},
            },
            "codolioDevelopmentCardDetails": {"totalContribution": 99},
        },
    }


def test_normalizer_preserves_unknown_zero_and_metric_provenance():
    result = coding.normalize(profile(), time.time())
    assert result["solved"] == 42
    assert result["active_days"] == 0
    assert result["stars"] is None
    assert result["contributions"] == 80  # Not the other card's incompatible total.
    assert result["pull_requests"] == 3
    assert len(result["activity"]) == 1
    assert result["languages"][0]["percent"] == 75
    assert "email" not in str(result)


@pytest.mark.parametrize(
    "raw",
    [
        {},
        {"status": {"success": False}, "data": {}},
        {"status": {"success": True}, "data": {}},
        {
            "status": {"success": True},
            "data": {"codolioCardDetails": {"totalQuestionsSolved": True}},
        },
    ],
)
def test_bad_provider_payload_is_not_a_zero_snapshot(raw):
    with pytest.raises(ValueError):
        coding.normalize(raw, time.time())


def test_saved_snapshot_failure_isolation_and_disconnect(environment, monkeypatch):
    calls = []

    async def fetch(handle):
        calls.append(handle)
        return profile()

    monkeypatch.setattr(coding, "fetch_profile", fetch)
    with TestClient(app) as alice, TestClient(app) as bob:
        register(alice, "alice@example.com")
        register(bob, "bob@example.com")
        assert (
            alice.post("/api/coding/connection", json={"handle": "alice"}).status_code
            == 201
        )
        assert alice.post("/api/coding/refresh").status_code == 202
        saved = alice.get("/api/coding").json()
        assert saved["latest"]["codolio"]["normalized"]["solved"] == 42
        assert "private@example.invalid" not in str(saved)
        assert "raw" not in saved["latest"]["codolio"]
        assert calls == ["alice"]
        assert alice.get("/api/coding").json() == saved
        assert calls == ["alice"]  # Loading never calls the provider.
        assert bob.get("/api/coding").json()["latest"]["codolio"] is None
        assert bob.post("/api/coding/refresh").status_code == 404
        bob.delete("/api/coding/connection")

        async def failure(handle):
            raise httpx.ReadTimeout("not exposed")

        monkeypatch.setattr(coding, "fetch_profile", failure)
        alice.post("/api/coding/refresh")
        failed = alice.get("/api/coding").json()
        assert failed["connection"]["error"]
        assert failed["latest"] == saved["latest"]
        assert len(failed["history"]["codolio"]) == 1
        alice.post("/api/coding/manual", json={"solved": 0})
        result = alice.delete("/api/coding/connection").json()
        assert result["connection"] is None
        assert result["latest"]["codolio"] is None
        assert result["latest"]["manual"]["normalized"]["solved"] == 0


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"solved": -1},
        {"solved": 1.5},
        {"solved": True},
        {"solved": 1, "owner_id": 2},
    ],
)
def test_manual_validation(environment, body):
    with TestClient(app) as client:
        register(client, "a@example.com")
        assert client.post("/api/coding/manual", json=body).status_code == 422
        assert client.get("/api/coding").json()["latest"]["manual"] is None


def test_manual_history_and_assistant_are_owner_scoped(environment):
    with TestClient(app) as alice, TestClient(app) as bob:
        register(alice, "a@example.com")
        register(bob, "b@example.com")
        for solved in [0, 5]:
            assert (
                alice.post("/api/coding/manual", json={"solved": solved}).status_code
                == 201
            )
        result = alice.get("/api/coding").json()
        assert len(result["history"]["manual"]) == 2
        assert result["latest"]["manual"]["normalized"]["stars"] is None
        with environment.connect() as conn:
            bob_id = conn.scalar(
                select(db.owners.c.id).where(db.owners.c.email == "b@example.com")
            )
        tool, _ = asyncio.run(
            PersonalRegistry(environment).execute("get_coding_snapshot", {}, bob_id)
        )
        assert tool["latest"]["manual"] is None
        bob.delete("/api/coding/manual")
        assert alice.get("/api/coding").json()["latest"]["manual"]
        assert alice.delete("/api/coding/manual").json()["latest"]["manual"] is None


def test_leases_block_overlap_and_disconnected_fetch_cannot_restore(environment):
    with TestClient(app) as client:
        owner = register(client, "a@example.com").json()["owner_id"]
        coding.connect(owner, environment, coding.ConnectionInput(handle="one"))
        handle, lease = coding.claim(owner, environment)
        with pytest.raises(HTTPException) as error:
            coding.claim(owner, environment)
        assert error.value.status_code == 409
        coding.remove(owner, environment, "codolio")
        coding.connect(owner, environment, coding.ConnectionInput(handle="two"))
        coding.finish(
            owner,
            environment,
            handle,
            lease,
            profile(),
            coding.normalize(profile(), time.time()),
            None,
        )
        packet = coding.packet(owner, environment)
        assert packet["connection"]["handle"] == "two"
        assert packet["latest"]["codolio"] is None
        _, lease2 = coding.claim(owner, environment)
        with environment.begin() as conn:
            conn.execute(
                db.coding_connections.update().values(attempted_at=time.time() - 70)
            )
        _, lease3 = coding.claim(owner, environment)
        assert lease2 != lease3


@pytest.mark.parametrize(
    "handle", ["https://evil.example", "../x", "a?x=y", "a/b", "a b"]
)
def test_handle_never_accepts_url(environment, handle):
    with TestClient(app) as client:
        register(client, "a@example.com")
        assert (
            client.post("/api/coding/connection", json={"handle": handle}).status_code
            == 422
        )


def test_provider_transport_is_fixed_and_failure_not_saved(monkeypatch):
    client_type = httpx.AsyncClient

    def respond(request):
        assert request.url.host == "api.codolio.com"
        assert request.url.params["userKey"] == "sample"
        return httpx.Response(200, json=profile())

    monkeypatch.setattr(
        coding.httpx,
        "AsyncClient",
        lambda **kwargs: client_type(transport=httpx.MockTransport(respond), **kwargs),
    )
    assert asyncio.run(coding.fetch_profile("sample"))["status"]["success"] is True


def test_refresh_has_total_deadline_and_releases_lease(environment, monkeypatch):
    async def slow(handle):
        await asyncio.sleep(10)

    monkeypatch.setattr(coding, "fetch_profile", slow)
    monkeypatch.setattr(coding, "FETCH_TIMEOUT", 0.01)
    with TestClient(app) as client:
        register(client, "timeout@example.com")
        client.post("/api/coding/connection", json={"handle": "slow"})
        assert client.post("/api/coding/refresh").status_code == 202
        result = client.get("/api/coding").json()
        assert result["connection"]["error"]
        assert not result["connection"]["refreshing"]
        assert result["latest"]["codolio"] is None
