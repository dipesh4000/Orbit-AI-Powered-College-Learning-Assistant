"""Provider failures must recover within a bound and never expose response bodies."""

import asyncio

import httpx
import pytest
from orbit.config import settings
from orbit.llm import Model, ModelUnavailable


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setattr(settings, "nvidia_api_key", "")
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


@pytest.mark.parametrize("status", [401, 402, 403, 429, 500, 503])
def test_nvidia_fallback_is_immediate_and_keeps_history(monkeypatch, provider, status):
    import json

    monkeypatch.setattr(settings, "nvidia_api_key", "nvidia-test-key")
    calls, waits = mock_provider(monkeypatch, [status, 200])
    messages = [
        {"role": "user", "content": "My progress?"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {"name": "progress", "arguments": "{}"},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call-1", "content": '{"progress": 55}'},
    ]
    tools = [
        {
            "type": "function",
            "function": {"name": "progress", "parameters": {"type": "object"}},
        }
    ]
    model = Model()
    assert asyncio.run(model.complete(messages, tools))["content"] == "OK"
    assert len(calls) == 2
    assert waits == []
    payload = json.loads(calls[1].content)
    assert payload["messages"] == messages
    assert payload["tools"] == tools
    assert payload["model"] == settings.nvidia_model
    assert payload["stream"] is False
    assert payload["chat_template_kwargs"] == {"enable_thinking": False}
    assert calls[1].headers["authorization"] == "Bearer nvidia-test-key"
    assert calls[1].url.host == "integrate.api.nvidia.com"
    asyncio.run(model.complete(messages))
    assert len(calls) == 3
    assert calls[-1].url.host == "integrate.api.nvidia.com"
    model._primary_retry_at = 0
    asyncio.run(model.complete(messages))
    assert calls[-1].url.host == "model.invalid"


def test_primary_success_does_not_use_fallback(monkeypatch, provider):
    monkeypatch.setattr(settings, "nvidia_api_key", "nvidia-test-key")
    calls, _ = mock_provider(monkeypatch, [200])
    asyncio.run(Model().complete([]))
    assert len(calls) == 1
    assert calls[0].url.host == "model.invalid"


def test_nvidia_works_without_primary(monkeypatch, provider):
    monkeypatch.setattr(settings, "nvidia_api_key", "nvidia-test-key")
    monkeypatch.setattr(settings, "llm_api_key", "")
    calls, _ = mock_provider(monkeypatch, [200])
    assert asyncio.run(Model().complete([]))["content"] == "OK"
    assert len(calls) == 1
    assert calls[0].url.host == "integrate.api.nvidia.com"


def test_both_providers_fail_safely(monkeypatch, provider):
    monkeypatch.setattr(settings, "nvidia_api_key", "nvidia-test-key")
    calls, waits = mock_provider(monkeypatch, [429])
    with pytest.raises(ModelUnavailable) as error:
        asyncio.run(Model().complete([]))
    assert len(calls) == 2
    assert waits == []
    assert "PRIVATE" not in str(error.value)


@pytest.mark.parametrize("failure", ["timeout", "invalid", "empty"])
def test_unusable_primary_response_falls_back(monkeypatch, provider, failure):
    monkeypatch.setattr(settings, "nvidia_api_key", "nvidia-test-key")
    calls = []
    tool_call = {
        "id": "call-1",
        "type": "function",
        "function": {"name": "progress", "arguments": "{}"},
    }

    def respond(request):
        calls.append(request)
        if len(calls) == 1:
            if failure == "timeout":
                raise httpx.ReadTimeout("PRIVATE", request=request)
            if failure == "invalid":
                return httpx.Response(200, json={})
            return httpx.Response(
                200, json={"choices": [{"message": {"content": None}}]}
            )
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": None, "tool_calls": [tool_call]}}]
            },
        )

    client_type = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: client_type(transport=httpx.MockTransport(respond), **kwargs),
    )
    result = asyncio.run(Model().complete([]))
    assert result["tool_calls"] == [tool_call]
    assert len(calls) == 2


def test_total_timeout_falls_back(monkeypatch, provider):
    monkeypatch.setattr(settings, "nvidia_api_key", "nvidia-test-key")
    monkeypatch.setattr(settings, "llm_timeout_seconds", 0.01)
    model = Model()
    providers = []

    async def complete(messages, tools, **config):
        providers.append(config["provider"])
        if config["provider"] != "nvidia":
            await asyncio.sleep(1)
        return {"content": "OK", "tool_calls": []}

    monkeypatch.setattr(model, "_complete", complete)
    assert asyncio.run(model.complete([]))["content"] == "OK"
    assert providers == ["openai-compatible", "nvidia"]
