import asyncio
import json
from time import perf_counter

import httpx

from . import telemetry
from .config import settings


class ModelUnavailable(RuntimeError):
    pass


class Model:
    async def complete(self, messages, tools=None):
        started, failed, usage = perf_counter(), True, {}
        try:
            result = await self._complete(messages, tools)
            usage = result.pop("usage", {})
            failed = False
            return result
        finally:
            telemetry.record(
                "model",
                settings.llm_provider,
                (perf_counter() - started) * 1000,
                error=failed,
                input_tokens=usage.get("input_tokens", usage.get("prompt_tokens", 0)),
                output_tokens=usage.get(
                    "output_tokens", usage.get("completion_tokens", 0)
                ),
            )

    async def _complete(self, messages, tools=None):
        if not settings.llm_api_key or not settings.llm_model:
            raise ModelUnavailable(
                "Configure LLM_API_KEY and LLM_MODEL in backend/.env to enable AI responses."
            )
        if settings.llm_provider == "anthropic":
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
                "model": settings.llm_model,
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
                "x-api-key": settings.llm_api_key,
                "anthropic-version": "2023-06-01",
            }
            endpoint = settings.llm_base_url.rstrip("/") + "/messages"
        elif settings.llm_provider == "openai-compatible":
            body = {
                "model": settings.llm_model,
                "messages": messages,
                "temperature": 0.2,
                "max_tokens": 6000,
            }
            if tools:
                body["tools"] = tools
            headers = {"Authorization": "Bearer " + settings.llm_api_key}
            endpoint = settings.llm_base_url.rstrip("/") + "/chat/completions"
        else:
            raise ModelUnavailable(
                "Unsupported LLM_PROVIDER; choose anthropic or openai-compatible."
            )
        try:
            async with httpx.AsyncClient(timeout=45) as client:
                for attempt in range(3):
                    attempt_started = perf_counter()
                    response = await client.post(endpoint, headers=headers, json=body)
                    telemetry.record(
                        "provider_http",
                        settings.llm_provider,
                        (perf_counter() - attempt_started) * 1000,
                        error=response.status_code >= 400,
                        status=response.status_code,
                        attempt=attempt + 1,
                    )
                    if response.status_code != 429 or attempt == 2:
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
                message = "The model provider rejected access. Check LLM_API_KEY and model permissions in backend/.env."
            else:
                message = "The model provider rejected the request. Check the configured model and retry."
            raise ModelUnavailable(message) from exc
        except (httpx.HTTPError, ValueError) as exc:
            # Never relay provider response bodies, headers, or secrets to the browser.
            raise ModelUnavailable(
                "The model provider is unavailable or rejected the configuration. Please check the local settings and retry."
            ) from exc
        if settings.llm_provider == "anthropic":
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
        return {
            "usage": result.get("usage", {}),
            "role": "assistant",
            "content": message.get("content") or "",
            "tool_calls": message.get("tool_calls", []),
        }
