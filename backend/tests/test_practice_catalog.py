import json

from orbit import rag
from orbit.rag import Retriever


def test_practice_catalog_topic_skips_embedding_load(tmp_path, monkeypatch):
    folder = tmp_path / "data/rag"
    folder.mkdir(parents=True)
    chunk = {
        "id": "c1",
        "topic": "Collections",
        "course_ids": ["python"],
        "text": "Tuples are immutable.",
    }
    (folder / "chunks.json").write_text(json.dumps({"chunks": [chunk]}))
    monkeypatch.setattr(rag, "ROOT", tmp_path)
    retriever = Retriever()
    monkeypatch.setattr(
        retriever,
        "search",
        lambda *args: (_ for _ in ()).throw(AssertionError("Must use catalog")),
    )
    assert retriever.practice_sources("Collections", "python") == [chunk]
    assert retriever.model is None


def test_practice_catalog_does_not_cross_courses(tmp_path, monkeypatch):
    folder = tmp_path / "data/rag"
    folder.mkdir(parents=True)
    (folder / "chunks.json").write_text(
        json.dumps(
            {"chunks": [{"id": "c1", "topic": "Collections", "course_ids": ["python"]}]}
        )
    )
    monkeypatch.setattr(rag, "ROOT", tmp_path)
    retriever = Retriever()
    calls = []
    monkeypatch.setattr(retriever, "search", lambda *args: calls.append(args) or [])
    assert retriever.practice_sources("Collections", "java") == []
    assert calls == [("Collections", "java", 5)]
