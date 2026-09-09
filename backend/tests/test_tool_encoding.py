import asyncio
import json

from orbit.orchestrator import encode_tool_result


def test_unbacked_model_answer_uses_fixed_missing_information(monkeypatch, tmp_path):
    from orbit import orchestrator
    from orbit.rag import INSUFFICIENT

    class UnbackedModel:
        async def complete(self, messages, tools):
            return {"content": "An unsupported factual claim", "tool_calls": []}

    monkeypatch.setattr(orchestrator, "ROOT", tmp_path)
    result = asyncio.run(
        orchestrator.chat(
            "What is the secret campus parking policy?",
            {"user_id": "student", "history": []},
            None,
            UnbackedModel(),
        )
    )
    assert result["answer"] == INSUFFICIENT
    assert result["sources"] == []


def test_table_encoding_preserves_nulls_duplicates_and_shared_assumptions():
    rows = [
        {"course_id": "a", "score": None, "basis": "Demo scale", "pending": [1]},
        {"course_id": "b", "score": 0, "basis": "Demo scale", "pending": [2]},
        {"course_id": "b", "score": 0, "basis": "Demo scale", "pending": [2]},
    ]
    encoded = json.loads(encode_tool_result(rows))
    restored = [
        {**encoded["shared"], **dict(zip(encoded["columns"], row))}
        for row in encoded["rows"]
    ]
    assert restored == rows


def test_heterogeneous_results_remain_unchanged():
    for result in [[], [{"a": 1}], [{"a": 1}, {"b": 2}], {"eligible": False}]:
        assert json.loads(encode_tool_result(result)) == result


def test_repeated_tool_metadata_is_encoded_once():
    rows = [{"id": i, "basis": "Repeated assumption " * 30} for i in range(48)]
    assert len(encode_tool_result(rows)) < len(json.dumps(rows)) / 10
