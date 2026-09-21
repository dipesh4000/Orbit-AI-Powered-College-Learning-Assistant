import pytest
from fastapi.testclient import TestClient
from orbit import auth, sessions
from orbit import database as db
from orbit.config import settings
from orbit.main import app, services, session_engine
from orbit.services import Services
from sqlalchemy import create_engine, select
from sqlalchemy.pool import StaticPool


@pytest.fixture
def environment(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    db.metadata.create_all(engine)
    monkeypatch.setattr(settings, "demo_enabled", False)
    app.dependency_overrides[auth.engine] = lambda: engine
    app.dependency_overrides[session_engine] = lambda: engine
    app.dependency_overrides[services] = lambda: Services(engine)
    yield engine
    app.dependency_overrides.clear()
    engine.dispose()


def register(client, email):
    response = client.post(
        "/api/auth/register",
        json={"email": email, "name": "Student", "password": "long secure password"},
    )
    assert response.status_code == 201, response.text
    assert "HttpOnly" in response.headers["set-cookie"]
    return response


def test_two_accounts_and_subject_isolation(environment):
    with TestClient(app) as alice, TestClient(app) as bob:
        register(alice, "alice@example.com")
        register(bob, "bob@example.com")
        subject = alice.post(
            "/api/subjects",
            json={"name": "Databases", "code": "CS301", "semester": "3"},
        )
        assert subject.status_code == 201
        key = subject.json()["id"]
        assert len(alice.get("/api/subjects").json()) == 1
        assert bob.get("/api/subjects").json() == []
        assert bob.get(f"/api/subjects/{key}").status_code == 404
        assert alice.get(f"/api/subjects/{key}").status_code == 200
        forged = alice.post(
            "/api/subjects",
            json={"name": "X", "code": "X", "semester": "3", "owner_id": 2},
        )
        assert forged.status_code == 422
        token = alice.cookies.get("orbit_session")
        assert alice.delete("/api/session").status_code == 200
        alice.cookies.set("orbit_session", token)
        assert alice.get("/api/subjects").status_code == 401
        alice.cookies.clear()
        assert (
            alice.post(
                "/api/auth/login",
                json={"email": "ALICE@example.com", "password": "long secure password"},
            ).status_code
            == 200
        )
        assert len(alice.get("/api/subjects").json()) == 1
        assert alice.get("/api/session").json()["email"] == "alice@example.com"
        assert bob.get("/api/session").json()["email"] == "bob@example.com"


def test_demo_flag_and_boundaries(environment, monkeypatch):
    with TestClient(app) as client:
        assert client.get("/api/health").json()["demo"] is False
        assert client.get("/api/students").status_code == 404
        assert client.post("/api/login", json={"user_id": "demo"}).status_code == 404
        register(client, "alice@example.com")
        monkeypatch.setattr(settings, "demo_enabled", True)
        # Every legacy route guarded by current_session rejects personal identity.
        from orbit.main import current_session

        for route in app.routes:
            if not hasattr(route, "dependant") or not any(
                d.call is current_session for d in route.dependant.dependencies
            ):
                continue
            path = (
                route.path.replace("{course_id}", "x")
                .replace("{assessment_id}", "x")
                .replace("{conversation_id}", "x")
            )
            for method in route.methods:
                response = client.request(method, path, json={})
                assert response.status_code == 403, (method, path, response.text)
        token = sessions.create(
            environment, {"user_id": "demo", "label": "Demo", "rationale": "Demo"}
        )
        client.cookies.clear()
        client.cookies.set("orbit_session", token)
        assert client.get("/api/subjects").status_code == 403
        monkeypatch.setattr(settings, "demo_enabled", False)
        assert client.get("/api/session").status_code == 404


def test_credentials_rotation_expiry_and_validation(environment, monkeypatch):
    with TestClient(app) as client:
        register(client, "alice@example.com")
        old = client.cookies.get("orbit_session")
        assert (
            client.post(
                "/api/auth/register",
                json={
                    "email": "ALICE@example.com",
                    "name": "Other",
                    "password": "long secure password",
                },
            ).status_code
            == 409
        )
        for email in ("alice@example.com", "missing@example.com"):
            response = client.post(
                "/api/auth/login", json={"email": email, "password": "wrong"}
            )
            assert response.status_code == 401
            assert response.json()["detail"] == "Email or password is incorrect."
        assert (
            client.post(
                "/api/auth/login",
                json={"email": "alice@example.com", "password": "long secure password"},
            ).status_code
            == 200
        )
        with environment.connect() as conn:
            assert (
                conn.scalar(
                    select(db.sessions.c.token_hash).where(
                        db.sessions.c.token_hash == sessions.token_hash(old)
                    )
                )
                is None
            )
        monkeypatch.setattr(sessions, "time", lambda: 99999999999)
        assert client.get("/api/session").status_code == 401
        assert client.get("/api/subjects").status_code == 401
        for bad in ("forged", old):
            client.cookies.clear()
            client.cookies.set("orbit_session", bad)
            assert client.get("/api/subjects").status_code == 401


def test_origin_and_subject_validation(environment):
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/auth/login",
                headers={"Origin": "https://evil.example"},
                json={"email": "a@b", "password": "bad"},
            ).status_code
            == 403
        )
        register(client, "a@b.com")
        assert (
            client.post(
                "/api/subjects", json={"name": " ", "code": "x", "semester": "1"}
            ).status_code
            == 422
        )
        body = {"name": "Math", "code": "M1", "semester": "1"}
        assert client.post("/api/subjects", json=body).status_code == 201
        assert client.post("/api/subjects", json=body).status_code == 409
