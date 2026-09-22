import asyncio
from datetime import date

import pytest
from fastapi.testclient import TestClient
from orbit import database as db
from orbit import demo, insights, papers, personal
from orbit.main import app
from orbit.personal_tools import PersonalRegistry
from sqlalchemy import select
from test_personal import environment as environment  # noqa: PLC0414
from test_personal import register


def seeded(environment):
    return demo.seed(environment)["id"]


def test_demo_reference_totals_and_labels(environment):
    oid = seeded(environment)
    workspace = personal.workspace(oid, environment)
    assert workspace["counts"] == {"subjects": 42, "assessments": 44, "hackathons": 1}
    final = [r for r in workspace["assessments"] if r["kind"] == "final"]
    assert len(final) == 42
    assert sum(r["score"] for r in final) == 3295
    assert all(r["max_score"] == 100 and r["weak_topics"] == [] for r in final)
    subject = next(s for s in workspace["subjects"] if s["code"] == "CIC-210")
    result = next(r for r in final if r["subject_id"] == subject["id"])
    assert result["score"] == 85 and result["assessed_on"] == date(2026, 6, 29)
    assert "Illustrative" in workspace["hackathons"][0]["name"]
    assert len(papers.listing(oid, environment)) == 2
    with pytest.raises(RuntimeError, match="empty database"):
        demo.seed(environment)


def test_frequency_comparison_and_tool_owner_binding(environment):
    oid = seeded(environment)
    subjects = personal.list_subjects(oid, environment)
    sid = next(s["id"] for s in subjects if s["code"] == "CIC-210")
    topics = insights.topic_frequency(oid, environment, sid)
    assert {t["topic"]: t["question_count"] for t in topics} == {"Joins": 2, "Normalization": 2, "SQL": 2}
    assert all(t["paper_count"] == 2 for t in topics)
    pairs = insights.compare_assessments(oid, environment, sid)
    quiz = next(p for p in pairs if p["kind"] == "quiz")
    final = next(p for p in pairs if p["kind"] == "final")
    assert quiz["change_percentage_points"] == 20
    assert final["previous"] is None and "Insufficient evidence" in final["note"]
    registry = PersonalRegistry(environment)
    async def tools():
        found, _ = await registry.execute("search_pyq", {"query": "Joins", "subject_id": sid}, oid)
        assert len(found) == 2 and found[0]["evidence_id"].startswith("question-")
        with pytest.raises(ValueError):
            await registry.execute("search_pyq", {"query": "Joins", "owner_id": oid+1}, oid)
        missing, _ = await registry.execute("get_topic_frequency", {"subject_id": sid}, oid+1)
        assert missing == {"error": "Subject not found."}
        empty, _ = await registry.execute("search_pyq", {"query": "Joins"}, oid+1)
        assert empty == []
    asyncio.run(tools())


def test_comparison_refuses_ambiguous_dates_and_mixed_scales(environment):
    oid = seeded(environment)
    sid = next(s["id"] for s in personal.list_subjects(oid, environment) if s["code"] == "CIC-210")
    latest = next(r for r in personal.list_records(oid, environment, "assessments", sid) if r["kind"] == "quiz")
    personal.save_record(oid, environment, "assessments", personal.AssessmentInput(subject_id=sid, title="Another quiz", score=9, max_score=10, kind="quiz", assessed_on=latest["assessed_on"]))
    pair = next(r for r in insights.compare_assessments(oid, environment, sid) if r["kind"] == "quiz")
    assert pair["previous"] is None and "unambiguous" in pair["note"]
    personal.save_record(oid, environment, "assessments", personal.AssessmentInput(subject_id=sid, title="New scale", score=18, max_score=20, kind="quiz", assessed_on=latest["assessed_on"]))
    pair = next(r for r in insights.compare_assessments(oid, environment, sid) if r["max_score"] == 20)
    assert pair["previous"] is None


def test_decisions_deduplicate_and_deleted_or_unconfirmed_evidence_is_stale(environment, monkeypatch):
    oid = seeded(environment)
    monkeypatch.setattr(app.state, "demo_owner_id", oid, raising=False)
    with TestClient(app) as alice, TestClient(app) as bob:
        assert alice.post("/api/auth/demo").status_code == 200
        register(bob, "isolated-phase4@example.com")
        rows = alice.get("/api/personal/suggestions").json()
        row = rows[0]
        assert bob.get("/api/personal/suggestions").json() == []
        assert bob.put(f"/api/personal/suggestions/{row['id']}", json={"state":"accepted"}).status_code == 404
        for ref in row["evidence"]:
            assert bob.get(f"/api/personal/evidence/{ref['kind']}/{ref['id']}").status_code == 404
        assert alice.put(f"/api/personal/suggestions/{row['id']}", json={"state":"dismissed"}).status_code == 200
        assert alice.post("/api/personal/suggestions/refresh").json()[0]["state"] == "dismissed"
        assert len(alice.post("/api/personal/suggestions/refresh").json()) == len(rows)
        answer = alice.post("/api/personal/chat", json={"message":"SQL test Friday, two hours"}).json()
        assert "not re-propose" in answer["answer"]
        question = next(r for r in row["evidence"] if r["kind"] == "question")
        with environment.begin() as conn:
            conn.execute(db.paper_questions.update().where(db.paper_questions.c.id == question["id"]).values(confirmed=False))
        assert alice.get("/api/personal/suggestions").json()[0]["stale"]
        newer = alice.post("/api/personal/suggestions/refresh").json()[0]
        assert newer["id"] != row["id"]
        assert alice.put(f"/api/personal/suggestions/{newer['id']}", json={"state":"accepted"}).status_code == 200
        assert alice.get("/api/personal/suggestions").json()[0]["state"] == "accepted"
        assert alice.get(f"/api/personal/evidence/question/{question['id']}").status_code == 404


def test_changed_mark_blocks_acceptance_and_preserves_decision(environment):
    oid = seeded(environment)
    row = insights.listing(oid, environment)[0]
    mark = next(r for r in row["evidence"] if r["kind"] == "assessment")
    with environment.begin() as conn:
        conn.execute(db.personal_assessments.update().where(db.personal_assessments.c.id == mark["id"]).values(score=9))
    assert insights.listing(oid, environment)[0]["stale"]
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:
        insights.decide(oid, environment, row["id"], "accepted")
    assert error.value.status_code == 409
    refreshed = insights.refresh(oid, environment)
    assert len(refreshed) == 2
    insights.decide(oid, environment, refreshed[0]["id"], "accepted")
    assert insights.refresh(oid, environment)[0]["state"] == "accepted"


def test_demo_endpoint_off_by_default_and_assistant_is_grounded(environment, monkeypatch):
    with TestClient(app) as client:
        assert client.post("/api/auth/demo").status_code == 404
        oid = seeded(environment)
        monkeypatch.setattr(app.state, "demo_owner_id", oid, raising=False)
        response = client.post("/api/auth/demo")
        assert response.status_code == 200 and response.json()["demo_account"]
        assert client.get("/api/session").json()["demo_account"]
        answer = client.post("/api/personal/chat", json={"message":"SQL test Friday, two hours"})
        assert answer.status_code == 200, answer.text
        body = answer.json()
        assert body["demo"] and "120-minute" in body["answer"]
        assert "8/10" in body["answer"] and "authored examples" in body["answer"]
        assert {r["kind"] for r in body["sources"]} >= {"assessment", "question"}
        assert client.get("/api/personal/chat").json()["history"][-1]["sources"] == body["sources"]
        for prompt, expected in [("Show coding activity", "136"), ("Show project work", "demo"), ("Show my DBMS marks", "85/100"), ("Compare my DBMS results", "+20 percentage points")]:
            result = client.post("/api/personal/chat", json={"message": prompt})
            assert result.status_code == 200 and expected in result.json()["answer"]
        with environment.connect() as conn:
            assert conn.scalar(select(db.suggestions.c.state).limit(1)) == "proposed"
