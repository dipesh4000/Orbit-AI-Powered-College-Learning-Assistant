"""Provider failures must recover within a bound and never expose response bodies."""

import asyncio

import httpx
import pytest
from orbit.config import settings
from orbit.llm import Model, ModelUnavailable


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "openai-compatible")
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_model", "test-model")
    monkeypatch.setattr(settings, "llm_base_url", "https://model.invalid/v1")


def mock_provider(monkeypatch, statuses, retry_after="1"):
    calls, waits = [], []

    def respond(request):
        status = statuses[min(len(calls), len(statuses) - 1)]
        calls.append(request)
        payload = (
            {"choices": [{"message": {"content": "OK"}}]}
            if status == 200
            else {"error": "PRIVATE PROVIDER DETAILS"}
        )
        return httpx.Response(
            status, json=payload, headers={"retry-after": retry_after}
        )

    client_type = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: client_type(transport=httpx.MockTransport(respond), **kwargs),
    )

    async def sleep(delay):
        waits.append(delay)

    monkeypatch.setattr("orbit.llm.asyncio.sleep", sleep)
    return calls, waits


def test_rate_limit_recovers(monkeypatch, provider):
    calls, waits = mock_provider(monkeypatch, [429, 200])
    result = asyncio.run(Model().complete([{"role": "user", "content": "Hello"}]))
    assert result["content"] == "OK"
    assert len(calls) == 2
    assert waits == [1]


def test_rate_limit_is_bounded(monkeypatch, provider):
    calls, waits = mock_provider(monkeypatch, [429])
    with pytest.raises(ModelUnavailable, match="rate limit") as error:
        asyncio.run(Model().complete([]))
    assert len(calls) == 3
    assert len(waits) == 2
    assert "PRIVATE" not in str(error.value)


def test_long_quota_reset_does_not_block(monkeypatch, provider):
    calls, waits = mock_provider(monkeypatch, [429], retry_after="3600")
    with pytest.raises(ModelUnavailable, match="rate limit"):
        asyncio.run(Model().complete([]))
    assert len(calls) == 1
    assert waits == []


def test_invalid_key_is_not_retried_or_exposed(monkeypatch, provider):
    calls, waits = mock_provider(monkeypatch, [401])
    with pytest.raises(ModelUnavailable, match="LLM_API_KEY") as error:
        asyncio.run(Model().complete([]))
    assert len(calls) == 1
    assert waits == []
    assert "PRIVATE" not in str(error.value)
