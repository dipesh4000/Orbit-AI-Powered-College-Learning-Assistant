import asyncio
import json

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from orbit import auth, gemini, personal_chat_history, projects
from orbit.main import app
from orbit.personal_tools import PersonalRegistry
from test_personal import environment as environment  # noqa: PLC0414
from test_personal import register


def subject(client):
    return client.post(
        "/api/subjects", json={"name": "Databases", "code": "DB", "semester": "3"}
    ).json()["id"]


def test_academic_values_missing_scale_syllabus_and_isolation(environment):
    with TestClient(app) as a, TestClient(app) as b:
        register(a, "academic-a@example.com")
        register(b, "academic-b@example.com")
        assert a.get("/api/academics").json() == {
            "profile": None,
            "semesters": [],
            "syllabi": [],
        }
        sid = subject(a)
        assert (
            a.put(
                "/api/academics/profile",
                json={
                    "program": "CSE",
                    "current_semester": "3",
                    "total_credits": 80,
                    "target_sgpa": 9,
                    "sgpa_scale": 10,
                },
            ).status_code
            == 200
        )
        assert (
            a.post(
                "/api/academics/semesters", json={"semester": "1", "sgpa": 8.2}
            ).status_code
            == 200
        )
        assert (
            a.post(
                "/api/academics/semesters", json={"semester": "2", "sgpa": 11}
            ).status_code
            == 422
        )
        assert (
            a.put("/api/academics/profile", json={"sgpa_scale": 4}).status_code == 422
        )
        assert (
            a.put(
                f"/api/academics/syllabus/{sid}",
                json={"content": "SQL joins and transactions"},
            ).status_code
            == 200
        )
        assert (
            b.put(
                f"/api/academics/syllabus/{sid}", json={"content": "forged"}
            ).status_code
            == 404
        )
        assert b.get("/api/academics").json()["profile"] is None
        row = a.get("/api/academics").json()["semesters"][0]
        assert b.delete(f"/api/academics/semesters/{row['id']}").status_code == 404


def test_import_review_atomic_idempotent_and_lease_safe(environment, monkeypatch):
    draft = {
        "profile": {"program": "CSE", "current_semester": "3", "total_credits": None},
        "subjects": [
            {
                "name": "Databases",
                "code": "DB",
                "semester": "3",
                "syllabus": "SQL and joins",
            }
        ],
        "marks": [
            {
                "subject_code": "DB",
                "semester": "3",
                "title": "Final",
                "score": 81,
                "max_score": 100,
                "assessed_on": None,
                "kind": "final",
            }
        ],
        "semesters": [{"semester": "2", "sgpa": 8.5}],
    }

    async def recognize(*args):
        return draft

    monkeypatch.setattr(gemini, "recognize", recognize)
    with TestClient(app) as a, TestClient(app) as b:
        register(a, "import-a@example.com")
        register(b, "import-b@example.com")
        response = a.post(
            "/api/academics/imports",
            files={"file": ("report.pdf", b"%PDF-fixture", "application/pdf")},
        )
        assert response.status_code == 202
        key = response.json()["id"]
        assert a.get("/api/academics/imports").json()[0]["status"] == "review"
        assert a.get("/api/subjects").json() == []
        assert b.get("/api/academics/imports").json() == []
        assert (
            b.put(f"/api/academics/imports/{key}/confirm", json=draft).status_code
            == 404
        )
        assert (
            a.put(f"/api/academics/imports/{key}/confirm", json=draft).status_code
            == 422
        )
        assert (
            a.get("/api/subjects").json() == []
        )  # Entire failed transaction rolled back.
        draft["marks"][0]["assessed_on"] = "2026-06-01"
        for _ in range(2):
            assert (
                a.put(f"/api/academics/imports/{key}/confirm", json=draft).status_code
                == 200
            )
        assert len(a.get("/api/assessments").json()) == 1
        assert a.get("/api/academics").json()["profile"]["total_credits"] is None
        assert a.delete(f"/api/academics/imports/{key}").status_code == 200
        assert len(a.get("/api/assessments").json()) == 1


def test_recognition_failure_keeps_manual_workspace_usable(environment, monkeypatch):
    async def fail(*args):
        raise HTTPException(503, "No key")

    monkeypatch.setattr(gemini, "recognize", fail)
    with TestClient(app) as client:
        register(client, "failure@example.com")
        key = client.post(
            "/api/academics/imports", files={"file": ("x.png", b"image")}
        ).json()["id"]
        row = client.get("/api/academics/imports").json()[0]
        assert row["status"] == "failed" and row["retryable"]
        assert "source" not in row and "lease" not in row
        assert client.post(f"/api/academics/imports/{key}/retry").status_code == 202
        assert (
            client.post(
                "/api/subjects", json={"name": "Manual", "code": "M", "semester": "1"}
            ).status_code
            == 201
        )


def test_projects_context_caching_write_invalidation_and_ownership(environment):
    with TestClient(app) as a, TestClient(app) as b:
        register(a, "project-a@example.com")
        register(b, "project-b@example.com")
        sid = subject(a)
        assert (
            b.post(
                "/api/projects", json={"name": "Foreign subject", "subject_ids": [sid]}
            ).status_code
            == 404
        )
        project = a.post(
            "/api/projects", json={"name": "SQL learning", "subject_ids": [sid]}
        ).json()
        key = project["id"]
        result = a.post(
            f"/api/projects/{key}/documents",
            files={"file": ("notes.txt", b"SQL SELECT reads rows.", "text/plain")},
        ).json()
        mid = result["materials"][0]["id"]
        oid = project["owner_id"]
        registry = PersonalRegistry(environment)

        async def read(owner=oid):
            return await registry.execute(
                "get_project_context", {"project_id": key, "query": "SQL"}, owner
            )

        first, hit = asyncio.run(read())
        assert not hit and "SELECT" in first["materials"][0]["excerpts"][0]["text"]
        assert asyncio.run(read())[1] is True
        assert (
            a.put(
                f"/api/project-materials/{mid}",
                json={"content": "SQL UPDATE changes rows."},
            ).status_code
            == 200
        )
        current, hit = asyncio.run(read())
        assert not hit and "UPDATE" in current["materials"][0]["excerpts"][0]["text"]
        assert asyncio.run(read(oid + 1))[0] == {"error": "Record not found."}
        assert b.get(f"/api/projects/{key}").status_code == 404
        assert b.get(f"/api/personal/evidence/material/{mid}").status_code == 404
        assert b.delete(f"/api/project-materials/{mid}").status_code == 404
        assert a.delete(f"/api/projects/{key}").status_code == 200
        assert a.get(f"/api/personal/evidence/material/{mid}").status_code == 404
        assert "error" in asyncio.run(read())[0]


def test_main_chat_uses_project_and_survives_logout(environment, monkeypatch):
    class ProjectModel:
        async def complete(self, messages, tools=None):
            assert "selected project ID" in messages[0]["content"]
            if messages[-1]["role"] != "tool":
                return {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "p",
                            "type": "function",
                            "function": {
                                "name": "get_project_context",
                                "arguments": json.dumps(
                                    {"project_id": project["id"], "query": "SELECT"}
                                ),
                            },
                        }
                    ],
                }
            return {
                "role": "assistant",
                "content": "The notes say SELECT reads rows. [material-1]",
            }

    monkeypatch.setattr(auth, "personal_model", ProjectModel())
    with TestClient(app) as client:
        register(client, "durable@example.com")
        project = client.post("/api/projects", json={"name": "SQL"}).json()
        client.post(
            f"/api/projects/{project['id']}/documents",
            files={"file": ("notes.txt", b"SELECT reads rows.")},
        )
        response = client.post(
            "/api/personal/chat",
            json={"message": "Explain the notes", "project_id": project["id"]},
        )
        assert response.status_code == 200, response.text
        assert response.json()["tools_called"] == ["get_project_context"]
        assert client.delete("/api/session").status_code == 200
        assert (
            client.post(
                "/api/auth/login",
                json={
                    "email": "durable@example.com",
                    "password": "long secure password",
                },
            ).status_code
            == 200
        )
        history = client.get("/api/personal/chat").json()["history"]
        assert len(history) == 2 and history[0]["project_id"] == project["id"]
        row = personal_chat_history.load(project["owner_id"], environment)
        with pytest.raises(HTTPException):
            personal_chat_history.save(project["owner_id"], environment, row, 0)


def test_github_import_is_bounded_to_public_api_and_preserves_source(
    environment, monkeypatch
):
    import base64

    async def github(client, path, params=None):
        if path.endswith("/commits"):
            return [{"sha": "a" * 40, "commit": {"tree": {"sha": "b" * 40}}}]
        if "/git/trees/" in path:
            return {
                "tree": [
                    {
                        "path": "README.md",
                        "type": "blob",
                        "mode": "100644",
                        "size": 100,
                        "sha": "c" * 40,
                    },
                    {
                        "path": ".env",
                        "type": "blob",
                        "mode": "100644",
                        "size": 10,
                        "sha": "d" * 40,
                    },
                ]
            }
        if "/git/blobs/" in path:
            assert path.endswith("c" * 40)
            return {
                "content": base64.b64encode(
                    b"# Project\nUse SELECT to read rows."
                ).decode()
            }
        return {"default_branch": "main", "description": "Test repository"}

    monkeypatch.setattr(projects, "github_json", github)
    with TestClient(app) as client:
        register(client, "repo@example.com")
        key = client.post("/api/projects", json={"name": "Code"}).json()["id"]
        assert (
            client.post(
                f"/api/projects/{key}/repository",
                json={"url": "https://127.0.0.1/private"},
            ).status_code
            == 422
        )
        response = client.post(
            f"/api/projects/{key}/repository",
            json={"url": "https://github.com/owner/repo"},
        )
        assert response.status_code == 201, response.text
        material = response.json()["materials"][0]
        assert "README.md" in material["content"] and ".env" not in material["content"]
        assert "bounded repository snapshot" in material["content"]
