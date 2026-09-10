import json

import httpx
import numpy as np
import pytest
from orbit.config import settings
from orbit.embeddings import Embeddings, EmbeddingUnavailable


@pytest.fixture(autouse=True)
def config(monkeypatch):
    monkeypatch.setattr(settings, "hf_token", "private-token")
    monkeypatch.setattr(settings, "hf_embedding_url", "")
    monkeypatch.setattr(settings, "embedding_model", "BAAI/bge-small-en-v1.5")
    monkeypatch.setattr(settings, "embedding_dimensions", 3)


def transport(monkeypatch, payload, status=200):
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(status, json=payload)

    client_type = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: client_type(transport=httpx.MockTransport(respond), **kwargs),
    )
    return calls


def test_query_instruction_payload_and_normalization(monkeypatch):
    calls = transport(monkeypatch, [[3, 4, 0]])
    result = Embeddings().encode(["Explain SQL"], query=True)
    np.testing.assert_allclose(result, [[0.6, 0.8, 0]])
    assert result.dtype == np.float32
    assert (
        str(calls[0].url)
        == "https://router.huggingface.co/hf-inference/models/BAAI/bge-small-en-v1.5"
    )
    assert calls[0].headers["authorization"] == "Bearer private-token"
    assert json.loads(calls[0].content) == {
        "inputs": [settings.embedding_query_prefix + "Explain SQL"],
        "normalize": True,
        "truncate": True,
    }


def test_document_batch_has_no_query_instruction(monkeypatch):
    calls = transport(monkeypatch, [[1, 0, 0], [0, 2, 0]])
    result = Embeddings().encode(["Passage A", "Passage B"])
    assert json.loads(calls[0].content)["inputs"] == ["Passage A", "Passage B"]
    np.testing.assert_allclose(np.linalg.norm(result, axis=1), [1, 1])


def test_dedicated_endpoint(monkeypatch):
    monkeypatch.setattr(
        settings, "hf_embedding_url", "https://example.endpoints.huggingface.cloud"
    )
    calls = transport(monkeypatch, [[1, 0, 0]])
    Embeddings().encode(["text"])
    assert calls[0].url.host == "example.endpoints.huggingface.cloud"


def test_missing_token_never_makes_request(monkeypatch):
    calls = transport(monkeypatch, [])
    monkeypatch.setattr(settings, "hf_token", "")
    with pytest.raises(EmbeddingUnavailable, match="HF_TOKEN"):
        Embeddings().encode(["text"])
    assert not calls


@pytest.mark.parametrize("status", [401, 402, 403, 404, 429, 500, 503])
def test_failures_are_safe_and_not_retried(monkeypatch, status):
    calls = transport(
        monkeypatch, {"error": "PRIVATE SERVER DETAILS private-token"}, status
    )
    with pytest.raises(EmbeddingUnavailable) as exc:
        Embeddings().encode(["text"])
    assert len(calls) == 1
    assert "PRIVATE" not in str(exc.value)
    assert "private-token" not in str(exc.value)


@pytest.mark.parametrize(
    "payload",
    [
        [],
        [0.1, 0.2, 0.3],
        [[1, 2]],
        [[0, 0, 0]],
        [[[1, 2, 3]]],
        [[1, 2, 3], [4, 5, 6]],
        {"error": "PRIVATE"},
        [["bad", 0, 1]],
        [[1e100, 0, 0]],
    ],
)
def test_rejects_invalid_vectors(monkeypatch, payload):
    transport(monkeypatch, payload)
    with pytest.raises(EmbeddingUnavailable, match="invalid embeddings"):
        Embeddings().encode(["text"])


def test_timeout_does_not_leak_provider_details(monkeypatch):
    def respond(request):
        raise httpx.ReadTimeout("private-token", request=request)

    client_type = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: client_type(transport=httpx.MockTransport(respond), **kwargs),
    )
    with pytest.raises(EmbeddingUnavailable, match="timed out") as exc:
        Embeddings().encode(["text"])
    assert "private-token" not in str(exc.value)


def test_token_is_not_in_index_signature():
    assert "private-token" not in json.dumps(Embeddings().signature)
