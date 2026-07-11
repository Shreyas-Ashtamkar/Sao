import httpx
import litellm
import json
import asyncio
from dataclasses import dataclass

from litellm.llms.github_copilot.authenticator import Authenticator as _CopilotAuthenticator
from litellm.llms.github_copilot.common_utils import (
    GITHUB_COPILOT_API_BASE as _COPILOT_API_BASE,
    get_copilot_default_headers as _get_copilot_headers,
)

PROVIDER_CONFIG = {
    "OpenAI": {
        "provider_key": "openai",
        "prefix": "",
    },
    "Anthropic": {
        "provider_key": "anthropic",
        "prefix": "anthropic/",
    },
    "GitHub": {
        "provider_key": "github_copilot",
        "prefix": "github_copilot/",
    },
    "Google": {
        "provider_key": "gemini",
        "prefix": "gemini/",
    },
}

# OpenAI chat model filter constants
_OPENAI_CHAT_PREFIXES = ("gpt-", "o1", "o3", "o4", "chatgpt-")
_OPENAI_EXCLUDE = (
    "dall-e", "whisper", "tts", "embedding", "moderation",
    "babbage", "davinci", "curie", "ada", "image", "realtime",
)
_MAX_TOOL_CONTINUATIONS = 8
_COMPLETION_TIMEOUT_SECONDS = 120


@dataclass(frozen=True)
class ModelDiscoveryResult:
    models: list[str]
    is_live: bool


class Router:
    def __init__(self):
        self.system_prompt = "You are Sao, a lightweight AI chat assistant for solo developers. Provide clear, concise answers without fluff."

    def list_available_models(self, provider):
        fetchers = {
            "OpenAI": self._fetch_openai_models,
            "Anthropic": self._fetch_anthropic_models,
            "Google": self._fetch_google_models,
            "GitHub": self._fetch_github_copilot_models,
        }
        try:
            models = fetchers[provider]()
        except KeyError as exc:
            raise ValueError(f"Unsupported provider: {provider}") from exc
        except Exception:
            return ModelDiscoveryResult([], is_live=False)

        return ModelDiscoveryResult(models, is_live=bool(models))

    def _fetch_openai_models(self):
        models = litellm.get_valid_models(
            check_provider_endpoint=True,
            custom_llm_provider="openai",
        )
        return self._filter_openai_models(models)

    def _fetch_anthropic_models(self):
        models = litellm.get_valid_models(
            check_provider_endpoint=True,
            custom_llm_provider="anthropic",
        )
        return sorted(set(m for m in models if isinstance(m, str)))

    def _fetch_google_models(self):
        models = litellm.get_valid_models(
            check_provider_endpoint=True,
            custom_llm_provider="gemini",
        )
        result = []
        for model in models:
            if not isinstance(model, str):
                continue
            display = model[len("gemini/"):] if model.startswith("gemini/") else model
            if display.startswith("gemini-"):
                result.append(display)
        return sorted(set(result))

    def _fetch_github_copilot_models(self):
        auth = _CopilotAuthenticator()
        api_key = auth.get_api_key()
        api_base = (auth.get_api_base() or _COPILOT_API_BASE).rstrip("/")
        headers = _get_copilot_headers(api_key)

        with httpx.Client(timeout=15) as client:
            response = client.get(f"{api_base}/models", headers=headers)
            response.raise_for_status()
            data = response.json()

        result = []
        for entry in data.get("data", []):
            caps = entry.get("capabilities", {})
            if caps.get("type") == "chat":
                model_id = entry.get("id", "")
                if model_id:
                    if model_id.startswith("github_copilot/"):
                        model_id = model_id[len("github_copilot/"):]
                    result.append(model_id)

        return sorted(set(result))

    def get_static_models(self, provider):
        config = self._get_provider_config(provider)
        prefix = config["prefix"]
        raw = litellm.models_by_provider.get(config["provider_key"], [])
        result = [
            model[len(prefix):] if prefix and model.startswith(prefix) else model
            for model in raw
            if isinstance(model, str)
        ]
        if provider == "OpenAI":
            result = self._filter_openai_models(result)
        elif provider == "Google":
            result = [model for model in result if model.startswith("gemini-")]
        return sorted(set(result))

    def _filter_openai_models(self, models):
        result = []
        for model in models:
            if not isinstance(model, str) or "/" in model:
                continue
            lower = model.lower()
            if not any(lower.startswith(prefix) for prefix in _OPENAI_CHAT_PREFIXES):
                continue
            if any(exclusion in lower for exclusion in _OPENAI_EXCLUDE):
                continue
            result.append(model)
        return sorted(set(result))

    def normalize_model_id(self, model_id, provider=None):
        if not model_id:
            raise ValueError("model_id is required")

        if model_id.startswith("github/"):
            return f"github_copilot/{model_id.split('/', 1)[1]}"

        if provider:
            config = self._get_provider_config(provider)
            prefix = config["prefix"]
            if prefix and not model_id.startswith(prefix):
                return f"{prefix}{model_id}"
            return model_id

        return model_id

    def _get_provider_config(self, provider):
        if provider not in PROVIDER_CONFIG:
            raise ValueError(f"Unsupported provider: {provider}")
        return PROVIDER_CONFIG[provider]

    def _normalize_provider_models(self, provider, models):
        config = self._get_provider_config(provider)
        prefix = config["prefix"]
        normalized = []

        for model in models:
            if not isinstance(model, str):
                continue
            display_model = model
            if prefix and display_model.startswith(prefix):
                display_model = display_model[len(prefix):]
            normalized.append(display_model)

        return sorted(set(normalized))

    async def generate_response_stream(self, model_id, messages, tools=None, provider=None, tool_executor=None):
        try:
            # Prepend system prompt if not present
            if not messages or messages[0].get("role") != "system":
                messages.insert(0, {"role": "system", "content": self.system_prompt})

            litellm_model = self.normalize_model_id(model_id, provider=provider)

            kwargs = {
                "model": litellm_model,
                "messages": messages,
                "stream": True,
            }
            if tools:
                kwargs["tools"] = tools

            for _ in range(_MAX_TOOL_CONTINUATIONS):
                response = await asyncio.wait_for(
                    litellm.acompletion(**kwargs),
                    timeout=_COMPLETION_TIMEOUT_SECONDS,
                )
                tool_calls = {}
                assistant_content = ""

                async with asyncio.timeout(_COMPLETION_TIMEOUT_SECONDS):
                    async for chunk in response:
                        content = self._get_chunk_content(chunk)
                        if content:
                            assistant_content += content
                        self._collect_tool_calls(chunk, tool_calls)
                        yield chunk

                if not tool_calls:
                    break
                if tool_executor is None:
                    raise RuntimeError("Model requested MCP tools but no tool executor is configured")
                if _ == _MAX_TOOL_CONTINUATIONS - 1:
                    raise RuntimeError(
                        f"Model exceeded the maximum of {_MAX_TOOL_CONTINUATIONS} tool continuations"
                    )

                completed_calls = [
                    {
                        "id": call["id"],
                        "type": "function",
                        "function": {
                            "name": call["name"],
                            "arguments": call["arguments"],
                        },
                    }
                    for _, call in sorted(tool_calls.items())
                ]
                messages.append(
                    {
                        "role": "assistant",
                        "content": assistant_content or None,
                        "tool_calls": completed_calls,
                    }
                )
                for call in completed_calls:
                    try:
                        arguments = json.loads(call["function"]["arguments"] or "{}")
                    except json.JSONDecodeError as exc:
                        raise ValueError(
                            f"Invalid arguments for MCP tool {call['function']['name']}"
                        ) from exc
                    if not isinstance(arguments, dict):
                        raise ValueError(
                            f"Arguments for MCP tool {call['function']['name']} must be an object"
                        )
                    tool_result = await tool_executor(call["function"]["name"], arguments)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call["id"],
                            "content": tool_result,
                        }
                    )
        except Exception as e:
            yield {"error": str(e)}

    @staticmethod
    def _get_chunk_content(chunk):
        if isinstance(chunk, dict):
            choices = chunk.get("choices", [])
            if choices:
                return choices[0].get("delta", {}).get("content") or ""
            return ""

        choices = getattr(chunk, "choices", [])
        if choices:
            return getattr(choices[0].delta, "content", None) or ""
        return ""

    @staticmethod
    def _collect_tool_calls(chunk, tool_calls):
        if isinstance(chunk, dict):
            choices = chunk.get("choices", [])
            delta = choices[0].get("delta", {}) if choices else {}
            calls = delta.get("tool_calls", [])
        else:
            choices = getattr(chunk, "choices", [])
            delta = choices[0].delta if choices else None
            calls = getattr(delta, "tool_calls", []) if delta else []

        for call in calls or []:
            if isinstance(call, dict):
                index = call.get("index", 0)
                call_id = call.get("id")
                function = call.get("function", {})
                name = function.get("name")
                arguments = function.get("arguments", "")
            else:
                index = getattr(call, "index", 0)
                call_id = getattr(call, "id", None)
                function = getattr(call, "function", None)
                name = getattr(function, "name", None) if function else None
                arguments = getattr(function, "arguments", "") if function else ""

            tool_call = tool_calls.setdefault(
                index,
                {"id": call_id or "", "name": name or "", "arguments": ""},
            )
            if call_id:
                tool_call["id"] = call_id
            if name:
                tool_call["name"] = name
            if arguments:
                tool_call["arguments"] += arguments
