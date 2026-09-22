import asyncio
import json

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from orbit import auth, demo, insights, personal_practice
from orbit import database as db
from orbit.llm import ModelUnavailable
from orbit.main import app
from orbit.personal_tools import PersonalRegistry
from sqlalchemy import select
from test_personal import environment as environment  # noqa: PLC0414
from test_personal import register


class QuizModel:
    async def complete(self, messages):
        payload = json.loads(messages[1]["content"])
        return {
            "content": json.dumps(
                {
                    "questions": [
                        {
                            "question": "Which topic is explicitly named in the source?",
                            "options": ["SQL", "Geometry", "Chemistry", "Mechanics"],
                            "correct_answer": "SQL",
                            "explanation": "The source explicitly names SQL in the question text.",
                            "source_reference": payload["passages"][0]["id"],
                        }
                    ]
                }
            )
        }


def seed(environment):
    oid = demo.seed(environment)["id"]
    with environment.connect() as conn:
        sid = conn.scalar(
            select(db.subjects.c.id).where(db.subjects.c.code == "CIC-210")
        )
    return oid, personal_practice.Generate(subject_id=sid, topic="SQL", count=1)


def test_private_generation_grading_idempotence_tools_and_followup(environment):
    oid, body = seed(environment)
    row = asyncio.run(personal_practice.generate(oid, environment, body, QuizModel()))
    assert "correct_answer" not in row["questions"][0]
    assert (
        "explanation"
        not in insights.evidence(oid, environment, "practice", row["id"])["data"][
            "questions"
        ][0]
    )
    assert personal_practice.listing(oid + 1, environment) == []
    with pytest.raises(HTTPException) as err:
        personal_practice.submit(
            oid + 1, environment, row["id"], personal_practice.Answers(answers=["SQL"])
        )
    assert err.value.status_code == 404
    with pytest.raises(HTTPException) as err:
        personal_practice.submit(
            oid, environment, row["id"], personal_practice.Answers(answers=["forged"])
        )
    assert err.value.status_code == 422
    answer = personal_practice.Answers(answers=["Geometry"])
    result = personal_practice.submit(oid, environment, row["id"], answer)
    assert result["correct"] == 0 and result["answered_at"]
    assert result["questions"][0]["correct_answer"] == "SQL"
    assert personal_practice.submit(oid, environment, row["id"], answer) == result
    with pytest.raises(HTTPException) as err:
        personal_practice.submit(
            oid, environment, row["id"], personal_practice.Answers(answers=["SQL"])
        )
    assert err.value.status_code == 409
    suggestions = insights.refresh(oid, environment)
    followup = next(s for s in suggestions if s["evidence"][0]["kind"] == "practice")
    assert "0/1" in followup["text"]
    registry = PersonalRegistry(environment)
    result, _ = asyncio.run(registry.execute("get_practice_history", {}, oid))
    assert result[0]["correct"] == 0 and registry.evidence[f"practice-{row['id']}"]
    with pytest.raises(ValueError):
        asyncio.run(registry.execute("get_practice_history", {"owner_id": oid}, oid))
    fresh = asyncio.run(personal_practice.generate(oid, environment, body, QuizModel()))
    personal_practice.submit(
        oid, environment, fresh["id"], personal_practice.Answers(answers=["SQL"])
    )
    assert next(
        s for s in insights.listing(oid, environment) if s["id"] == followup["id"]
    )["stale"]


def test_source_changes_and_deletion_block_old_sets(environment):
    oid, body = seed(environment)
    row = asyncio.run(personal_practice.generate(oid, environment, body, QuizModel()))
    with environment.begin() as conn:
        conn.execute(
            db.paper_questions.update()
            .where(db.paper_questions.c.id == row["sources"][0]["id"])
            .values(confirmed=False)
        )
    with pytest.raises(HTTPException) as err:
        personal_practice.submit(
            oid, environment, row["id"], personal_practice.Answers(answers=["SQL"])
        )
    assert err.value.status_code == 409
    personal_practice.remove(oid, environment, row["id"])
    assert personal_practice.listing(oid, environment) == []


def test_provider_failure_empty_evidence_and_invalid_generation_save_nothing(
    environment,
):
    oid, body = seed(environment)

    class Failed:
        async def complete(self, messages):
            raise ModelUnavailable("Provider unavailable")

    with pytest.raises(ModelUnavailable):
        asyncio.run(personal_practice.generate(oid, environment, body, Failed()))

    class Insufficient:
        async def complete(self, messages):
            return {"content": '{"questions": []}'}

    with pytest.raises(HTTPException) as err:
        asyncio.run(personal_practice.generate(oid, environment, body, Insufficient()))
    assert err.value.status_code == 422

    class Invalid:
        calls = 0

        async def complete(self, messages):
            self.calls += 1
            return {"content": '{"questions": [{}]}'}

    invalid = Invalid()
    with pytest.raises(HTTPException):
        asyncio.run(personal_practice.generate(oid, environment, body, invalid))
    assert invalid.calls == 2
    assert personal_practice.listing(oid, environment) == []


def test_routes_restore_attempts_and_clear_only_owned_chat(environment, monkeypatch):
    oid, body = seed(environment)
    monkeypatch.setattr(app.state, "demo_owner_id", oid, raising=False)
    monkeypatch.setattr(auth, "personal_model", QuizModel())
    with TestClient(app) as alice, TestClient(app) as bob:
        assert alice.post("/api/auth/demo").status_code == 200
        register(bob, "practice-isolation@example.com")
        response = alice.post("/api/personal/practice", json=body.model_dump())
        assert response.status_code == 201, response.text
        key = response.json()["id"]
        assert bob.get("/api/personal/practice").json() == []
        assert (
            bob.post(
                f"/api/personal/practice/{key}/answers", json={"answers": ["SQL"]}
            ).status_code
            == 404
        )
        assert bob.delete(f"/api/personal/practice/{key}").status_code == 404
        assert (
            alice.post(
                f"/api/personal/practice/{key}/answers", json={"answers": ["SQL"]}
            ).json()["correct"]
            == 1
        )
        assert alice.get("/api/personal/practice").json()[0]["correct"] == 1
        assert (
            alice.post(
                "/api/personal/chat", json={"message": "Show practice results"}
            ).status_code
            == 200
        )
        assert alice.get("/api/personal/chat").json()["history"]
        assert bob.delete("/api/personal/chat").status_code == 200
        assert alice.get("/api/personal/chat").json()["history"]
        assert alice.delete("/api/personal/chat").status_code == 200
        assert alice.get("/api/personal/chat").json()["history"] == []
        assert alice.get("/api/personal/practice").json()[0]["correct"] == 1
