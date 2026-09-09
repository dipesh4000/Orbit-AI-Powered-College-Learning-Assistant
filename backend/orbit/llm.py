import json
import httpx
from .config import settings


class ModelUnavailable(RuntimeError):
    pass


class Model:
    async def complete(self, messages, tools=None):
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
                response = await client.post(endpoint, headers=headers, json=body)
                response.raise_for_status()
                result = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            # Never relay provider response bodies, headers, or secrets to the browser.
            raise ModelUnavailable(
                "The model provider is unavailable or rejected the configuration. Please check the local settings and retry."
            ) from exc
        if settings.llm_provider == "anthropic":
            return {
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
            "role": "assistant",
            "content": message.get("content") or "",
            "tool_calls": message.get("tool_calls", []),
        }
