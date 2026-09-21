import asyncio
import json

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from orbit import auth, github, personal
from orbit import database as db
from orbit.main import app
from orbit.migrate import upgrade
from orbit.personal_tools import PersonalRegistry
from pydantic import ValidationError
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.exc import IntegrityError
from test_personal import environment as environment  # noqa: PLC0414
from test_personal import register


def subject(client, **changes):
    result = client.post(
        "/api/subjects", json={"name": "SQL", "code": "DB", "semester": "3", **changes}
    )
    assert result.status_code == 201
    return result.json()["id"]


def mark(key, **changes):
    return {
        "subject_id": key,
        "title": "SQL quiz",
        "score": 12,
        "max_score": 20,
        "assessed_on": "2026-01-10",
        "kind": "quiz",
        "weak_topics": ["joins"],
        **changes,
    }


def hackathon(**changes):
    return {
        "name": "Build Day",
        "event_date": "2026-01-11",
        "role": "Developer",
        "project": "Orbit",
        **changes,
    }


def test_record_crud_and_cross_owner_rejection(environment):
    with TestClient(app) as alice, TestClient(app) as bob:
        register(alice, "alice@example.com")
        register(bob, "bob@example.com")
        a, b = subject(alice), subject(bob)
        assert alice.post("/api/assessments", json=mark(b)).status_code == 404
        for resource, body in [("assessments", mark(a)), ("hackathons", hackathon())]:
            result = alice.post(f"/api/{resource}", json=body)
            assert result.status_code == 201, result.text
            key = result.json()["id"]
            assert bob.get(f"/api/{resource}").json() == []
            assert bob.get(f"/api/{resource}/{key}").status_code == 404
            assert bob.put(f"/api/{resource}/{key}", json=body).status_code == 404
            assert bob.delete(f"/api/{resource}/{key}").status_code == 404
            assert (
                alice.put(
                    f"/api/{resource}/{key}", json={**body, "owner_id": 2}
                ).status_code
                == 422
            )
            if resource == "assessments":
                assert alice.delete(f"/api/subjects/{a}").status_code == 409
                body["score"] = 16
            else:
                body["reflection"] = "Learned to collaborate"
            assert alice.put(f"/api/{resource}/{key}", json=body).status_code == 200
            assert alice.delete(f"/api/{resource}/{key}").status_code == 200
            assert alice.get(f"/api/{resource}/{key}").status_code == 404
        changed = {"name": "Databases", "code": "DB", "semester": "4"}
        assert bob.put(f"/api/subjects/{a}", json=changed).status_code == 404
        assert bob.delete(f"/api/subjects/{a}").status_code == 404
        assert alice.put(f"/api/subjects/{a}", json=changed).status_code == 200
        assert alice.delete(f"/api/subjects/{a}").status_code == 200


@pytest.mark.parametrize(
    "changes",
    [
        {"score": -1},
        {"score": 21},
        {"max_score": 0},
        {"assessed_on": "2099-01-01"},
        {"kind": "exam"},
        {"title": " "},
        {"weak_topics": [""]},
    ],
)
def test_mark_validation(environment, changes):
    with TestClient(app) as client:
        register(client, "a@b.com")
        key = subject(client)
        assert (
            client.post("/api/assessments", json=mark(key, **changes)).status_code
            == 422
        )
        assert client.get("/api/assessments").json() == []


def test_nonfinite_and_unsafe_links():
    for score in [float("nan"), float("inf")]:
        with pytest.raises(ValidationError):
            personal.AssessmentInput(**mark(1, score=score))
    with pytest.raises(ValidationError):
        personal.HackathonInput(**hackathon(repo_url="javascript:alert(1)"))


HEADER = "subject_code,title,score,max_score,assessed_on,kind,weak_topics\n"


def test_csv_is_atomic_and_reports_rows(environment):
    with TestClient(app) as client:
        register(client, "a@b.com")
        subject(client)
        valid = "DB,Quiz,8,10,2026-01-11,quiz,joins;sql\n"
        bad = "DB,Wrong,12,10,2026-01-12,quiz,\n"
        result = client.post(
            "/api/assessments/import", json={"content": HEADER + valid + bad}
        )
        assert result.status_code == 422
        assert result.json()["detail"]["errors"][0]["row"] == 3
        assert client.get("/api/assessments").json() == []
        result = client.post(
            "/api/assessments/import", json={"content": "\ufeff" + HEADER + valid}
        )
        assert result.json() == {"imported": 1}
        assert client.get("/api/assessments").json()[0]["weak_topics"] == [
            "joins",
            "sql",
        ]
        subject(client, semester="4")
        assert (
            client.post(
                "/api/assessments/import", json={"content": HEADER + valid}
            ).status_code
            == 422
        )
        content = HEADER.rstrip() + ",semester\n" + valid.rstrip() + ",4\n"
        assert client.post(
            "/api/assessments/import", json={"content": content}
        ).json() == {"imported": 1}
        assert (
            client.post(
                "/api/assessments/import", json={"content": HEADER + 'DB,"unterminated'}
            ).status_code
            == 422
        )


def test_malformed_header_and_repo_url(environment):
    with TestClient(app) as client:
        register(client, "header@example.com")
        assert (
            client.post(
                "/api/assessments/import", json={"content": '"broken header'}
            ).status_code
            == 422
        )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(github.preview_repo("https://[invalid"))
    assert exc.value.status_code == 422


def test_summary_only_compares_same_type_scale_and_earlier_dates(environment):
    with TestClient(app) as client:
        register(client, "a@b.com")
        key = subject(client)
        for body in [
            mark(key),
            mark(key, score=18, assessed_on="2026-01-12"),
            mark(key, kind="final", score=90, max_score=100, assessed_on="2026-01-11"),
        ]:
            assert client.post("/api/assessments", json=body).status_code == 201
        packet = client.get("/api/personal/workspace").json()
        assert packet["counts"] == {"subjects": 1, "assessments": 3, "hackathons": 0}
        assert packet["subjects"][0]["change"] == 30
        assert packet["subjects"][0]["latest"]["score"] == 18


def test_migration_preserves_phase0_and_enforces_parent_ownership(tmp_path):
    engine = create_engine("sqlite:///" + (tmp_path / "migration.db").as_posix())

    @event.listens_for(engine, "connect")
    def enable_fk(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE workspace_owners (id INTEGER PRIMARY KEY, email VARCHAR(254) NOT NULL UNIQUE, name VARCHAR(100) NOT NULL, password_hash TEXT NOT NULL)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE personal_subjects (id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL REFERENCES workspace_owners(id), name VARCHAR(100) NOT NULL, code VARCHAR(40) NOT NULL, semester VARCHAR(40) NOT NULL, UNIQUE(owner_id, code, semester))"
            )
        )
        conn.execute(
            db.owners.insert(),
            [
                {"id": 1, "email": "a@b", "name": "A", "password_hash": "untouched"},
                {"id": 2, "email": "b@b", "name": "B", "password_hash": "untouched"},
            ],
        )
        conn.execute(
            db.subjects.insert().values(
                id=1, owner_id=1, name="SQL", code="DB", semester="3"
            )
        )
    upgrade(engine)
    upgrade(engine)
    with engine.connect() as conn:
        assert (
            conn.scalar(select(db.owners.c.password_hash).where(db.owners.c.id == 1))
            == "untouched"
        )
        assert conn.scalar(select(db.subjects.c.name)) == "SQL"
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "0002"
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            db.personal_assessments.insert().values(
                owner_id=2, **personal.AssessmentInput(**mark(1)).model_dump()
            )
        )
    engine.dispose()


def test_personal_chat_reads_saved_records_and_rejects_identity_arguments(
    environment, monkeypatch
):
    class Model:
        async def complete(self, messages, tools):
            assert {t["function"]["name"] for t in tools} == {
                "get_subjects",
                "get_assessments",
                "get_hackathons",
            }
            if messages[-1]["role"] != "tool":
                return {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "1",
                            "type": "function",
                            "function": {"name": "get_assessments", "arguments": "{}"},
                        }
                    ],
                }
            records = json.loads(messages[-1]["content"])
            assert records[0]["title"] == "SQL quiz"
            assert len(records) == 1
            return {
                "role": "assistant",
                "content": "SQL quiz: 12/20 on 2026-01-10 (record #1).",
                "tool_calls": [],
            }

    monkeypatch.setattr(auth, "personal_model", Model())
    with TestClient(app) as client:
        register(client, "a@b.com")
        key = subject(client)
        client.post("/api/assessments", json=mark(key))
        result = client.post(
            "/api/personal/chat", json={"message": "What did I score in SQL?"}
        )
        assert result.status_code == 200, result.text
        assert "12/20" in result.json()["answer"]
        assert len(client.get("/api/personal/chat").json()["history"]) == 2
    with pytest.raises(ValidationError):
        asyncio.run(
            PersonalRegistry(environment).execute("get_assessments", {"owner_id": 2}, 1)
        )


def test_github_preview_and_language_failure(monkeypatch):
    real_client = httpx.AsyncClient

    def response(request):
        if request.url.path.endswith("/languages"):
            return httpx.Response(403, json={"message": "rate limited"})
        return httpx.Response(
            200, json={"name": "orbit", "description": "Learning workspace"}
        )

    monkeypatch.setattr(
        github.httpx,
        "AsyncClient",
        lambda **kw: real_client(transport=httpx.MockTransport(response), **kw),
    )
    result = asyncio.run(github.preview_repo("https://github.com/example/orbit"))
    assert result["project"] == "orbit"
    assert result["technologies"] is None
    with pytest.raises(HTTPException) as exc:
        asyncio.run(github.preview_repo("https://github.com.evil.example/a/b"))
    assert exc.value.status_code == 422


def test_put_origin_guard(environment):
    with TestClient(app) as client:
        register(client, "a@b.com")
        key = subject(client)
        assert (
            client.put(
                f"/api/subjects/{key}",
                json={},
                headers={"Origin": "https://evil.example"},
            ).status_code
            == 403
        )
