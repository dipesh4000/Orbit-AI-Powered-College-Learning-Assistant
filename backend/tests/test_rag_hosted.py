import json

import httpx
import pytest
from orbit import rag
from orbit.config import settings
from orbit.embeddings import EmbeddingUnavailable


@pytest.fixture
def hosted_index(tmp_path, monkeypatch):
    monkeypatch.setattr(rag, "ROOT", tmp_path)
    monkeypatch.setattr(settings, "hf_token", "fake-token")
    monkeypatch.setattr(settings, "hf_embedding_url", "")
    monkeypatch.setattr(settings, "embedding_dimensions", 3)
    monkeypatch.setattr(settings, "rag_threshold", 0.6)
    folder = tmp_path / "data/rag"
    folder.mkdir(parents=True)
    chunks = [
        {
            "id": "sql",
            "source": "SQL",
            "text": "Normalization",
            "topic": "SQL",
            "course_ids": ["c1"],
        },
        {
            "id": "python",
            "source": "Python",
            "text": "Tuples",
            "topic": "Python",
            "course_ids": ["c2"],
        },
    ]
    (folder / "chunks.json").write_text(
        json.dumps(
            {"model": "old-model", "chunks": chunks, "catalog": {"c1": {}, "c2": {}}}
        )
    )
    calls = []

    def respond(request):
        inputs = json.loads(request.content)["inputs"]
        calls.append(inputs)
        vectors = []
        for text in inputs:
            vectors.append(
                [1, 0, 0]
                if "SQL" in text
                else [0, 1, 0]
                if "Python" in text
                else [0, 0, 1]
            )
        return httpx.Response(200, json=vectors)

    client_type = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: client_type(transport=httpx.MockTransport(respond), **kwargs),
    )
    rag.build_index(from_existing=True)
    return folder, calls


def test_build_and_search_use_same_api_and_preserve_sources(hosted_index):
    folder, calls = hosted_index
    retriever = rag.Retriever()
    result = retriever.search("SQL")
    assert result[0]["id"] == "sql"
    assert result[0]["source"] == "SQL"
    assert result[0]["similarity"] == 1
    assert len(calls) == 2
    assert calls[0] == ["SQL. Normalization", "Python. Tuples"]
    assert calls[1] == [settings.embedding_query_prefix + "SQL"]
    assert rag.index_ready()
    manifest = json.loads((folder / "chunks.json").read_text())
    assert manifest["embedding"]["normalize"] is True
    assert manifest["model"] == settings.embedding_model


def test_cache_avoids_duplicate_api_calls(hosted_index):
    _, calls = hosted_index
    retriever = rag.Retriever()
    assert retriever.search("SQL") == retriever.search("SQL")
    assert len(calls) == 2


def test_threshold_and_course_filter(hosted_index):
    retriever = rag.Retriever()
    assert retriever.search("unrelated") == []
    assert retriever.search("SQL", course_id="c2") == []
    assert retriever.search("SQL", course_id="c1")[0]["id"] == "sql"


@pytest.mark.parametrize(
    "setting,value",
    [
        ("embedding_model", "other/model"),
        ("embedding_dimensions", 4),
        ("embedding_query_prefix", "different: "),
        ("hf_embedding_url", "https://other.endpoints.huggingface.cloud"),
    ],
)
def test_rejects_incompatible_index_before_api_call(
    hosted_index, monkeypatch, setting, value
):
    _, calls = hosted_index
    monkeypatch.setattr(settings, setting, value)
    assert not rag.index_ready()
    with pytest.raises(EmbeddingUnavailable, match="outdated or incompatible"):
        rag.Retriever().search("SQL")
    assert len(calls) == 1


def test_detects_corrupted_index(hosted_index):
    folder, _ = hosted_index
    (folder / "index.faiss").write_bytes(b"corrupt")
    assert not rag.index_ready()
    with pytest.raises(EmbeddingUnavailable, match="incompatible"):
        rag.Retriever().search("SQL")


def test_legacy_index_requires_explicit_migration(hosted_index):
    folder, calls = hosted_index
    manifest = json.loads((folder / "chunks.json").read_text())
    del manifest["embedding"]
    (folder / "chunks.json").write_text(json.dumps(manifest))
    assert not rag.index_ready()
    with pytest.raises(EmbeddingUnavailable, match="from-existing"):
        rag.Retriever().search("SQL")
    assert len(calls) == 1


def test_failed_reindex_preserves_current_artifacts(hosted_index, monkeypatch):
    folder, _ = hosted_index
    before = {p.name: p.read_bytes() for p in folder.iterdir()}
    monkeypatch.setattr(settings, "hf_token", "")
    with pytest.raises(EmbeddingUnavailable, match="HF_TOKEN"):
        rag.build_index(from_existing=True)
    assert before == {p.name: p.read_bytes() for p in folder.iterdir()}


def test_new_materials_use_api_too(hosted_index, monkeypatch):
    folder, calls = hosted_index
    chunks = [{"id": "new", "source": "SQL", "text": "New text", "course_ids": ["c1"]}]
    monkeypatch.setattr(rag, "source_chunks", lambda: (chunks, {"c1": {}}))
    rag.build_index()
    assert calls[-1] == ["SQL. New text"]
    assert json.loads((folder / "chunks.json").read_text())["chunks"] == chunks


def test_embedding_error_has_safe_api_response():
    from fastapi.testclient import TestClient
    from orbit.main import app, services

    def unavailable():
        raise EmbeddingUnavailable(
            "Hugging Face embeddings are unavailable. Please retry."
        )

    previous = dict(app.dependency_overrides)
    app.dependency_overrides[services] = unavailable
    try:
        with TestClient(app) as client:
            response = client.get("/api/students")
        assert response.status_code == 503
        assert response.json()["detail"].startswith("Hugging Face")
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
