import time

import numpy as np
import pymupdf
import pytest
from fastapi.testclient import TestClient
from orbit import database as db
from orbit import papers
from orbit.embeddings import EmbeddingUnavailable
from orbit.main import app
from sqlalchemy import select
from test_personal import environment as environment  # noqa: PLC0414
from test_personal import register


@pytest.fixture(autouse=True)
def embeddings(monkeypatch):
    def encode(texts, **kwargs):
        vectors = np.zeros((len(texts), 384), dtype="float32")
        vectors[:, 0] = 1
        return vectors

    monkeypatch.setattr(papers.embedder, "encode", encode)


def subject(client):
    return client.post(
        "/api/subjects", json={"name": "Databases", "code": "DB", "semester": "3"}
    ).json()["id"]


def upload(client, sid, data=None, filename="exam.pdf"):
    if data is None:
        with pymupdf.open() as doc:
            page = doc.new_page()
            page.insert_text(
                (50, 60),
                "DATABASE SYSTEMS - 2025\n1. Explain SQL joins. [5 marks]\n2. Describe normalization. [10 marks]",
            )
            data = doc.tobytes()
    return client.post(
        "/api/papers",
        data={"subject_id": sid, "year": 2025, "topics": "SQL,Normalization"},
        files={"file": (filename, data)},
    )


def review(client, q, **changes):
    body = {
        k: q[k] for k in ("content", "topic", "marks", "page", "confirmed", "revision")
    }
    return client.put(f"/api/paper-questions/{q['id']}", json={**body, **changes})


def test_pdf_review_search_privacy_and_cascade(environment):
    with TestClient(app) as alice, TestClient(app) as bob:
        register(alice, "paper-alice@example.com")
        register(bob, "paper-bob@example.com")
        sid = subject(alice)
        assert upload(bob, sid).status_code == 404
        response = upload(alice, sid)
        assert response.status_code == 202, response.text
        pid = response.json()["id"]
        detail = alice.get(f"/api/papers/{pid}").json()
        assert detail["status"] == "needs review"
        assert len(detail["questions"]) == 2
        assert detail["questions"][0]["marks"] == 5
        assert "source" not in detail
        assert alice.get(f"/api/papers/{pid}/source").content.startswith(b"%PDF")
        assert bob.get("/api/papers").json() == []
        for suffix in ("", "/source"):
            assert bob.get(f"/api/papers/{pid}{suffix}").status_code == 404
        for suffix in ("retry", "reindex", "questions"):
            assert bob.post(f"/api/papers/{pid}/{suffix}").status_code == 404
        query = {"query": "SQL", "mode": "keyword"}
        assert alice.post("/api/papers/search", json=query).json() == []
        first, second = detail["questions"]
        assert review(bob, first, confirmed=True).status_code == 404
        assert review(alice, first, topic="invented topic").status_code == 422
        assert (
            review(
                alice,
                first,
                content="1. Explain SQL inner and outer joins.",
                confirmed=True,
            ).status_code
            == 200
        )
        assert review(alice, first, confirmed=True).status_code == 409
        assert (
            review(
                alice, second, marks=8, topic="Normalization", confirmed=True
            ).status_code
            == 200
        )
        assert alice.get(f"/api/papers/{pid}").json()["status"] == "ready"
        assert len(alice.post("/api/papers/search", json=query).json()) == 1
        assert bob.post("/api/papers/search", json=query).json() == []
        assert (
            alice.post(
                "/api/papers/search", json={**query, "subject_id": 999}
            ).status_code
            == 404
        )
        assert alice.delete(f"/api/subjects/{sid}").status_code == 409
        assert alice.post(f"/api/papers/{pid}/reindex").status_code == 200
        assert (
            len(
                alice.post(
                    "/api/papers/search", json={**query, "mode": "semantic"}
                ).json()
            )
            == 2
        )
        assert (
            bob.post("/api/papers/search", json={**query, "mode": "semantic"}).json()
            == []
        )
        assert bob.delete(f"/api/paper-questions/{first['id']}").status_code == 404
        assert alice.post(f"/api/papers/{pid}/questions").status_code == 201
        assert alice.get(f"/api/papers/{pid}").json()["status"] == "needs review"
        assert bob.delete(f"/api/papers/{pid}").status_code == 404
        assert alice.delete(f"/api/papers/{pid}").status_code == 200
        assert alice.post("/api/papers/search", json=query).json() == []
        with environment.connect() as conn:
            assert conn.execute(select(db.paper_questions)).all() == []


def test_embedding_failure_preserves_review_and_model_changes_exclude_old_vectors(
    environment, monkeypatch
):
    with TestClient(app) as client:
        register(client, "embedding@example.com")
        pid = upload(client, subject(client)).json()["id"]
        q = client.get(f"/api/papers/{pid}").json()["questions"][0]
        review(client, q, confirmed=True)
        monkeypatch.setattr(papers, "signature", lambda: "different model")
        assert (
            client.post(
                "/api/papers/search", json={"query": "SQL", "mode": "semantic"}
            ).json()
            == []
        )

        def fail(*args, **kwargs):
            raise EmbeddingUnavailable("Provider unavailable")

        monkeypatch.setattr(papers.embedder, "encode", fail)
        assert client.post(f"/api/papers/{pid}/reindex").status_code == 503
        assert len(client.post("/api/papers/search", json={"query": "SQL"}).json()) == 1
        second = upload(client, client.get("/api/subjects").json()[0]["id"]).json()[
            "id"
        ]
        detail = client.get(f"/api/papers/{second}").json()
        assert detail["status"] == "needs review"
        assert "Semantic indexing is unavailable" in detail["error"]
        assert len(detail["questions"]) == 2


def test_failed_upload_retry_stale_worker_and_validation(environment):
    with TestClient(app) as client:
        register(client, "retry@example.com")
        sid = subject(client)
        for data, filename, status in [
            (b"", "x.pdf", 413),
            (b"abc", "x.exe", 422),
            (b"a" * (papers.MAX_BYTES + 1), "x.txt", 413),
        ]:
            assert upload(client, sid, data, filename).status_code == status
        pid = upload(client, sid, b"invalid pdf").json()["id"]
        assert client.get(f"/api/papers/{pid}").json()["status"] == "failed"
        assert client.post(f"/api/papers/{pid}/retry").status_code == 202
        oid = client.get("/api/session").json()["owner_id"]
        key, lease = papers.create(
            oid, environment, "paper.txt", b"1. Explain SQL joins.", sid, 2025, "SQL"
        )
        assert client.post(f"/api/papers/{key}/retry").status_code == 409
        with environment.begin() as conn:
            conn.execute(
                db.papers.update()
                .where(db.papers.c.id == key)
                .values(started_at=time.time() - 700)
            )
        assert client.get("/api/papers").json()[0]["retryable"]
        assert client.post(f"/api/papers/{key}/retry").status_code == 202
        papers.process(oid, environment, key, lease)
        assert len(client.get(f"/api/papers/{key}").json()["questions"]) == 1
        client.delete(f"/api/papers/{key}")
        papers.process(oid, environment, key, lease)
        assert client.get(f"/api/papers/{key}").status_code == 404


def test_ocr_failure_is_actionable_and_headers_do_not_become_questions(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("missing tessdata")

    monkeypatch.setattr(pymupdf.Page, "get_textpage_ocr", fail)
    with pymupdf.open() as doc:
        doc.new_page()
        with pytest.raises(ValueError, match="needs OCR"):
            papers.extract(doc.tobytes(), "scan.pdf")
    result = papers.split_questions(
        [(1, "Exam instructions\n1. Explain SQL. [4]\n2. Describe joins. (6 marks)")],
        ["SQL"],
    )
    assert len(result) == 2
    assert result[0]["marks"] == 4
    assert result[1]["marks"] == 6
