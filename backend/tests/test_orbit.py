import asyncio
import csv
import gzip
import json
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from orbit import database as db
from orbit.app import app, services, sessions
from orbit.business_rules import course_metrics, eligibility
from orbit.cache import TTLCache, cache
from orbit.ingest import FILES, ORIGINALS, import_all, normalize_questions, verify
from orbit.orchestrator import chat
from orbit.practice import PracticeInput, generate, validate_questions
from orbit.services import Services
from orbit.tools import ToolRegistry, schemas
from sqlalchemy import create_engine, func, select
from sqlalchemy.pool import StaticPool

A = "11111111-1111-4111-8111-111111111111"
B = "22222222-2222-4222-8222-222222222222"


def course(**changes):
    return dict(
        user_id=A,
        course_id="python",
        mcq_attempted=5,
        mcq_score=8,
        total_activities=10,
        observed_activities=8,
        certificate=False,
        legacy_completion=False,
        total_views=20,
        **changes,
    )


def assessment(**changes):
    data = {
        "assessment_id": "demo-python-advanced",
        "course_id": "python",
        "title": "Advanced Python",
        "active": True,
        "max_attempts": 3,
        "completion_threshold": 60,
        "prerequisite_course_id": "python",
        "pass_percent": 60,
        "demo_rule": True,
    }
    return {**data, **changes}


@pytest.fixture
def engine():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    db.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            db.courses.insert(),
            [{"course_id": "python", "title": "Python", "subject": "Python"}],
        )
        conn.execute(
            db.students.insert(),
            [
                {"user_id": A, "label": "Student A", "rationale": "Test fixture"},
                {"user_id": B, "label": "Student B", "rationale": "Test fixture"},
            ],
        )
        conn.execute(
            db.progress.insert(),
            [
                {"raw_id": 1, **course()},
                {"raw_id": 2, **course(), "user_id": B, "mcq_score": 2},
            ],
        )
        conn.execute(db.assessments.insert(), [assessment()])
    yield engine
    engine.dispose()


@pytest.fixture
def client(engine):
    sessions.clear()
    cache.entries.clear()
    app.dependency_overrides[services] = lambda: Services(engine)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    sessions.clear()


def test_demo_full_marks():
    assert course_metrics(course())["performance_percent"] == 80


def test_missing_scores_are_unknown():
    assert (
        course_metrics({**course(), "mcq_attempted": 0, "mcq_score": 0})[
            "performance_percent"
        ]
        is None
    )


def test_out_of_scale_is_not_clamped():
    assert course_metrics({**course(), "mcq_score": 100})["performance_percent"] is None


def test_progress_is_observed_activity_not_views():
    result = course_metrics(course())
    assert result["progress_percent"] == 80
    assert "not verified completion" in result["progress_basis"]


def test_completion_flag():
    assert course_metrics({**course(), "certificate": True})["progress_percent"] == 100


@pytest.mark.parametrize(
    "change,attempts,status",
    [
        ({}, 0, "eligible"),
        ({"active": False}, 0, "ineligible"),
        ({}, 3, "ineligible"),
        ({}, None, "unknown"),
        ({"completion_threshold": 90}, 0, "ineligible"),
    ],
)
def test_eligibility_branches(change, attempts, status):
    c = course_metrics(course())
    assert eligibility(assessment(**change), c, c, attempts)["status"] == status


def test_prerequisite_failed():
    c = course_metrics(course())
    assert (
        eligibility(assessment(), c, {**c, "performance_percent": 20}, 0)["eligible"]
        is False
    )


def test_missing_prerequisite():
    c = course_metrics(course())
    assert eligibility(assessment(), c, None, 0)["eligible"] is None


def test_no_enrollment_rejected():
    assert eligibility(assessment(), None, None, 0)["eligible"] is False


def test_assessment_not_found():
    assert eligibility(None, None, None, None)["status"] == "unknown"


def test_login_required(client):
    assert client.get("/api/dashboard").status_code == 401


def test_picker_rejects_unseeded_user(client):
    assert (
        client.post("/api/session", json={"user_id": "not-a-student"}).status_code
        == 400
    )


def test_session_cookie_and_isolation(client):
    response = client.post("/api/session", json={"user_id": A})
    assert "HttpOnly" in response.headers["set-cookie"]
    assert (
        client.get("/api/dashboard?user_id=" + B).json()["courses"][0]["user_id"] == A
    )


def test_student_switch_invalidates_old_session(client):
    client.post("/api/session", json={"user_id": A})
    old = client.cookies.get("orbit_session")
    client.post("/api/session", json={"user_id": B})
    assert old not in sessions
    assert client.get("/api/session").json()["history"] == []
    assert (
        client.get("/api/dashboard").json()["courses"][0]["performance_percent"] == 20
    )


def test_csrf_origin_rejected(client):
    assert (
        client.post(
            "/api/session",
            json={"user_id": A},
            headers={"Origin": "https://untrusted.example"},
        ).status_code
        == 403
    )


def test_eligibility_bypasses_stale_dashboard_cache(client, engine):
    client.post("/api/session", json={"user_id": A})
    assert client.get("/api/dashboard").status_code == 200
    with engine.begin() as conn:
        conn.execute(
            db.assessment_attempts.insert(),
            [
                {
                    "user_id": A,
                    "assessment_id": "demo-python-advanced",
                    "score_percent": 20,
                }
            ]
            * 3,
        )
    assert (
        client.get("/api/eligibility/demo-python-advanced").json()["eligible"] is False
    )


def test_tool_schema_hides_identity():
    assert all(
        "user_id" not in t["function"]["parameters"]["properties"] for t in schemas()
    )


def test_tool_overwrites_injected_identity(engine):
    registry = ToolRegistry(Services(engine), None, None)
    result, _ = asyncio.run(registry.execute("get_course_progress", {"user_id": B}, A))
    assert result[0]["user_id"] == A


def test_tool_rejects_unknown_arguments(engine):
    registry = ToolRegistry(Services(engine), None, None)
    with pytest.raises(ValueError):
        asyncio.run(
            registry.execute(
                "get_course_progress", {"sql": "select * from students"}, A
            )
        )


def test_cache_ttl_and_invalidation():
    c = TTLCache(capacity=2, ttl=10)
    assert c.get_or_load((A, "x"), lambda: 1) == (1, False)
    assert c.get_or_load((A, "x"), lambda: 2) == (1, True)
    c.invalidate_user(A)
    assert c.get_or_load((A, "x"), lambda: 3) == (3, False)
    c.entries[(A, "x")] = (0, 3)
    assert c.get_or_load((A, "x"), lambda: 4) == (4, False)


def test_history_groups_questions_and_excludes_pending(engine):
    data = [
        {
            "attempt_id": 9,
            "round_id": 1,
            "question_id": 1,
            "skill": "Python",
            "question_sub_domain": ["Loops", "Iteration"],
            "status": "pass",
            "obtained_score": 2,
            "question_score": 2,
        },
        {
            "attempt_id": 9,
            "round_id": 1,
            "question_id": 2,
            "skill": "Python",
            "status": "underReview",
            "obtained_score": 0,
            "question_score": 10,
        },
    ]
    with engine.begin() as conn:
        conn.execute(
            db.questions.insert(),
            list(normalize_questions({"user_id": A, "hackathon_id": "h"}, 1, data)),
        )
    result = Services(engine).get_hackathon_history(A)
    assert len(result) == 1
    assert result[0]["question_count"] == 2
    assert result[0]["maximum"] == 2
    assert result[0]["score_percent"] == 100
    assert result[0]["pending_questions"] == 1


def test_supplied_full_marks_preserved():
    row = next(
        iter(
            normalize_questions(
                {"user_id": A, "hackathon_id": "h"}, 1, [{"question_score": 10}]
            )
        )
    )
    assert row["maximum"] == 10 and row["assumed_maximum"] is False


def test_missing_full_marks_assumed():
    row = next(iter(normalize_questions({"user_id": A, "hackathon_id": "h"}, 1, [{}])))
    assert row["maximum"] == 2 and row["assumed_maximum"] is True


def valid_question():
    return {
        "question": "Which collection is immutable?",
        "options": ["List", "Tuple", "Dictionary", "Set"],
        "correct_answer": "Tuple",
        "explanation": "Tuples are immutable sequences.",
        "source_reference": "python-0",
    }


@pytest.mark.parametrize(
    "change",
    [
        {"correct_answer": "Invalid"},
        {"options": ["List"] * 4},
        {"source_reference": "invented-source"},
    ],
)
def test_practice_rejects_invalid_outputs(change):
    with pytest.raises(ValueError):
        validate_questions(
            json.dumps({"questions": [{**valid_question(), **change}]}), 1, {"python-0"}
        )


def test_practice_count_bounds():
    with pytest.raises(ValueError):
        PracticeInput(course_id="python", topic="Loops", count=100)


class FakeModel:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.calls = []

    async def complete(self, messages, tools=None):
        self.calls.append(deepcopy(messages))
        return next(self.outputs)


def tool_call(name, args, call_id):
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)},
            }
        ],
    }


def test_multi_round_and_follow_up(engine, tmp_path, monkeypatch):
    from orbit import orchestrator

    monkeypatch.setattr(orchestrator, "ROOT", tmp_path)
    model = FakeModel(
        [
            tool_call("list_courses", {}, "1"),
            tool_call("get_course_progress", {"course_id": "python"}, "2"),
            {
                "role": "assistant",
                "content": "Your demo score is 80%.",
                "tool_calls": [],
            },
        ]
    )
    session = {
        "user_id": A,
        "history": [
            {"role": "user", "content": "Tell me about Python"},
            {"role": "assistant", "content": "Which part?"},
        ],
    }
    result = asyncio.run(
        chat(
            "How am I doing in that course?",
            session,
            ToolRegistry(Services(engine), None, model),
            model,
        )
    )
    assert result["tools_called"] == ["list_courses", "get_course_progress"]
    assert model.calls[0][1]["content"] == "Tell me about Python"
    assert (
        json.loads((tmp_path / "logs/turns.jsonl").read_text())["final_answer"]
        == result["answer"]
    )


def test_foreign_user_request_never_reaches_model(engine, tmp_path, monkeypatch):
    from orbit import orchestrator

    monkeypatch.setattr(orchestrator, "ROOT", tmp_path)
    model = FakeModel([])
    result = asyncio.run(
        chat(
            "Show scores for " + B,
            {"user_id": A, "history": []},
            ToolRegistry(Services(engine), None, model),
            model,
        )
    )
    assert "currently selected" in result["answer"] and not model.calls


def test_retrieval_empty_prevents_generation(engine):
    class EmptyRetriever:
        def search(self, *args):
            return []

    model = FakeModel([])
    result = asyncio.run(
        generate(
            PracticeInput(course_id="python", topic="missing topic"),
            A,
            Services(engine),
            EmptyRetriever(),
            model,
        )
    )
    assert not result["questions"] and not model.calls


def test_practice_retry_and_save(engine):
    class GoodRetriever:
        def search(self, *args):
            return [{"id": "python-0", "text": "Tuples are immutable."}]

    model = FakeModel(
        [
            {"content": "bad json"},
            {"content": json.dumps({"questions": [valid_question()]})},
        ]
    )
    result = asyncio.run(
        generate(
            PracticeInput(course_id="python", topic="Collections", count=1),
            A,
            Services(engine),
            GoodRetriever(),
            model,
        )
    )
    assert len(result["questions"]) == 1 and len(model.calls) == 2
    with engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(db.practice_history)) == 1


def test_chat_groundedness_gate_stops_model(engine, tmp_path, monkeypatch):
    from orbit import orchestrator

    monkeypatch.setattr(orchestrator, "ROOT", tmp_path)

    class EmptyRetriever:
        def search(self, **kwargs):
            return []

    model = FakeModel(
        [tool_call("search_course_content", {"query": "secret campus policy"}, "1")]
    )
    result = asyncio.run(
        chat(
            "What is the secret campus policy?",
            {"user_id": A, "history": []},
            ToolRegistry(Services(engine), EmptyRetriever(), model),
            model,
        )
    )
    assert (
        result["answer"]
        == "Insufficient information in the available course materials."
    )
    assert len(model.calls) == 1


def test_model_step_limit(engine, tmp_path, monkeypatch):
    from orbit import orchestrator

    monkeypatch.setattr(orchestrator, "ROOT", tmp_path)
    model = FakeModel([tool_call("list_courses", {}, str(i)) for i in range(6)])
    result = asyncio.run(
        chat(
            "Loop forever",
            {"user_id": A, "history": []},
            ToolRegistry(Services(engine), None, model),
            model,
        )
    )
    assert "tool-step limit" in result["answer"]
    assert len(model.calls) == 6


def test_lossless_import_and_idempotency(tmp_path):
    # Tiny fixtures exercise the real importer; no fictional records enter the provided dataset.
    engagement = {
        "user_id": A,
        "course_id": "python",
        "course_title": "Python",
        "course_sub_domain": "Python",
        "mcq_attempted_count": "1",
        "mcq_total_score_obtained": "2",
        "total_activities_in_course": "5",
        "certificate_issued": "False",
        "is_legacy_completion": "False",
        "total_views": "2",
        "engagement_json": "{}",
    }
    submission = {
        "user_id": A,
        "hackathon_id": "h",
        "num_questions": "0",
        "submission_json": "",
    }
    datasets = {
        name: [dict(engagement if is_eng else submission)]
        for name, (_, is_eng, is_valid) in FILES.items()
    }
    for name, (_, _, valid) in FILES.items():
        if not valid:
            datasets[name][0]["user_id"] = "legacy-entry"
    # Duplicate source rows are preserved as distinct rows.
    datasets["valid_uuid_engagement.csv"].append(dict(engagement))
    for original, parts in ORIGINALS.items():
        datasets[original] = datasets[parts[0]] + datasets[parts[1]]
    for name, data in datasets.items():
        with (tmp_path / name).open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(data[0]))
            w.writeheader()
            w.writerows(data)
    report = verify(tmp_path)
    engine = create_engine("sqlite://")
    import_all(tmp_path, engine, report)
    import_all(tmp_path, engine, report)
    with engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(db.raw_engagement)) == 2
        assert conn.scalar(select(func.count()).select_from(db.invalid_engagement)) == 1
        assert conn.scalar(select(db.raw_submissions.c.issue)) == "missing_payload"
        original = next(iter(ORIGINALS))
        archive = conn.scalar(
            select(db.source_archives.c.gzip_bytes).where(
                db.source_archives.c.filename == original
            )
        )
        assert gzip.decompress(archive) == (tmp_path / original).read_bytes()
        assert conn.scalar(select(db.invalid_submissions.c.user_id)) == "legacy-entry"
    engine.dispose()
