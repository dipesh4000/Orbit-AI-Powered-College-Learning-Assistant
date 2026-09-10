import asyncio
import json
from time import monotonic, perf_counter

import httpx

from . import telemetry
from .config import settings


class ModelUnavailable(RuntimeError):
    pass


class Model:
    def __init__(self):
        self._primary_retry_at = 0.0

    async def complete(self, messages, tools=None):
        fallback = bool(settings.nvidia_api_key and settings.nvidia_model)
        primary = bool(settings.llm_api_key and settings.llm_model)
        if primary and (not fallback or monotonic() >= self._primary_retry_at):
            try:
                result = await self._measured_complete(
                    messages,
                    tools,
                    provider=settings.llm_provider,
                    api_key=settings.llm_api_key,
                    model=settings.llm_model,
                    base_url=settings.llm_base_url,
                    retry_rate_limit=not fallback,
                )
                self._primary_retry_at = 0.0
                return result
            except ModelUnavailable:
                if not fallback:
                    raise
                self._primary_retry_at = (
                    monotonic() + settings.llm_fallback_cooldown_seconds
                )
                telemetry.record("model_fallback", "nvidia", 0)
        if fallback:
            return await self._measured_complete(
                messages,
                tools,
                provider="nvidia",
                api_key=settings.nvidia_api_key,
                model=settings.nvidia_model,
                base_url=settings.nvidia_base_url,
                retry_rate_limit=False,
            )
        raise ModelUnavailable(
            "Configure LLM_API_KEY and LLM_MODEL or NVIDIA_API_KEY in backend/.env to enable AI responses."
        )

    async def _measured_complete(self, messages, tools, **config):
        started, failed, usage = perf_counter(), True, {}
        try:
            async with asyncio.timeout(settings.llm_timeout_seconds):
                result = await self._complete(messages, tools, **config)
            raw_usage = result.pop("usage", {})
            if isinstance(raw_usage, dict):
                usage = {
                    key: value
                    for key, value in raw_usage.items()
                    if isinstance(value, (int, float)) and value >= 0
                }
            content, calls = result.get("content"), result.get("tool_calls")
            if not isinstance(content, str) or not isinstance(calls, list):
                raise ModelUnavailable(
                    "The model provider returned an invalid response. Please retry."
                )
            if not content.strip() and not calls:
                raise ModelUnavailable(
                    "The model provider returned an empty response. Please retry."
                )
            failed = False
            return result
        except (
            TimeoutError,
            KeyError,
            IndexError,
            TypeError,
            ValueError,
            AttributeError,
        ) as exc:
            raise ModelUnavailable(
                "The model provider returned an invalid response or timed out. Please retry."
            ) from exc
        finally:
            telemetry.record(
                "model",
                config["provider"],
                (perf_counter() - started) * 1000,
                error=failed,
                input_tokens=usage.get("input_tokens", usage.get("prompt_tokens", 0)),
                output_tokens=usage.get(
                    "output_tokens", usage.get("completion_tokens", 0)
                ),
            )

    async def _complete(
        self,
        messages,
        tools=None,
        *,
        provider,
        api_key,
        model,
        base_url,
        retry_rate_limit,
    ):
        if provider == "anthropic":
            history, system = [], ""
            for message in messages:
                role = message["role"]
                if role == "system":
                    system += message["content"] + "\n"
                    continue
                blocks = []
                if role == "tool":
                    blocks.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": message["tool_call_id"],
                            "content": message["content"],
                        }
                    )
                    role = "user"
                else:
                    if message.get("content"):
                        blocks.append({"type": "text", "text": message["content"]})
                    for call in message.get("tool_calls", []):
                        blocks.append(
                            {
                                "type": "tool_use",
                                "id": call["id"],
                                "name": call["function"]["name"],
                                "input": json.loads(call["function"]["arguments"]),
                            }
                        )
                history.append({"role": role, "content": blocks})
            body = {
                "model": model,
                "max_tokens": 6000,
                "system": system,
                "messages": history,
            }
            if tools:
                body["tools"] = [
                    {
                        "name": t["function"]["name"],
                        "description": t["function"]["description"],
                        "input_schema": t["function"]["parameters"],
                    }
                    for t in tools
                ]
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            }
            endpoint = base_url.rstrip("/") + "/messages"
        elif provider in ("openai-compatible", "nvidia"):
            body = {
                "model": model,
                "messages": messages,
                "temperature": 0.2,
                "stream": False,
                "max_tokens": 6000,
            }
            if provider == "nvidia":
                body["chat_template_kwargs"] = {"enable_thinking": False}
            if tools:
                body["tools"] = tools
            headers = {"Authorization": "Bearer " + api_key}
            endpoint = base_url.rstrip("/") + "/chat/completions"
        else:
            raise ModelUnavailable(
                "Unsupported LLM_PROVIDER; choose anthropic or openai-compatible."
            )
        try:
            async with httpx.AsyncClient(
                timeout=settings.llm_timeout_seconds
            ) as client:
                for attempt in range(3):
                    attempt_started = perf_counter()
                    response = await client.post(endpoint, headers=headers, json=body)
                    telemetry.record(
                        "provider_http",
                        provider,
                        (perf_counter() - attempt_started) * 1000,
                        error=response.status_code >= 400,
                        status=response.status_code,
                        attempt=attempt + 1,
                    )
                    if (
                        response.status_code != 429
                        or attempt == 2
                        or not retry_rate_limit
                    ):
                        break
                    try:
                        delay = float(response.headers.get("retry-after", "5"))
                    except ValueError:
                        delay = 5
                    # Long quota resets require user action; never hold a request indefinitely.
                    if not 0 <= delay <= 15:
                        break
                    await asyncio.sleep(max(1, delay))
                response.raise_for_status()
                result = response.json()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 429:
                message = "The model provider's rate limit was reached. Wait a minute and retry, or ask about one course at a time."
            elif status in (401, 403):
                key_name = "NVIDIA_API_KEY" if provider == "nvidia" else "LLM_API_KEY"
                message = f"The model provider rejected access. Check {key_name} and model permissions in backend/.env."
            else:
                message = "The model provider rejected the request. Check the configured model and retry."
            raise ModelUnavailable(message) from exc
        except (httpx.HTTPError, ValueError) as exc:
            # Never relay provider response bodies, headers, or secrets to the browser.
            raise ModelUnavailable(
                "The model provider is unavailable or rejected the configuration. Please check the local settings and retry."
            ) from exc
        if provider == "anthropic":
            return {
                "usage": result.get("usage", {}),
                "role": "assistant",
                "content": "\n".join(
                    b["text"] for b in result["content"] if b["type"] == "text"
                ),
                "tool_calls": [
                    {
                        "id": b["id"],
                        "type": "function",
                        "function": {
                            "name": b["name"],
                            "arguments": json.dumps(b["input"]),
                        },
                    }
                    for b in result["content"]
                    if b["type"] == "tool_use"
                ],
            }
        message = result["choices"][0]["message"]
        if not message.get("content") and not message.get("tool_calls"):
            raise ModelUnavailable(
                "The model provider returned an empty response. Please retry."
            )
        return {
            "usage": result.get("usage", {}),
            "role": "assistant",
            "content": message.get("content") or "",
            "tool_calls": message.get("tool_calls") or [],
        }
