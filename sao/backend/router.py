import httpx
import litellm

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


class Router:
    def __init__(self):
        self.system_prompt = "You are Sao, a lightweight AI chat assistant for solo developers. Provide clear, concise answers without fluff."

    def list_available_models(self, provider):
        if provider == "OpenAI":
            return self._fetch_openai_models()
        elif provider == "Anthropic":
            return self._fetch_anthropic_models()
        elif provider == "Google":
            return self._fetch_google_models()
        elif provider == "GitHub":
            return self._fetch_github_copilot_models()
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    def _fetch_openai_models(self):
        try:
            models = litellm.get_valid_models(
                check_provider_endpoint=True,
                custom_llm_provider="openai",
            )
            result = []
            for m in models:
                if not isinstance(m, str) or "/" in m:
                    continue
                lower = m.lower()
                if not any(lower.startswith(p) for p in _OPENAI_CHAT_PREFIXES):
                    continue
                if any(excl in lower for excl in _OPENAI_EXCLUDE):
                    continue
                result.append(m)
            return sorted(set(result))
        except Exception:
            return self._static_fallback("OpenAI")

    def _fetch_anthropic_models(self):
        try:
            models = litellm.get_valid_models(
                check_provider_endpoint=True,
                custom_llm_provider="anthropic",
            )
            return sorted(set(m for m in models if isinstance(m, str)))
        except Exception:
            return self._static_fallback("Anthropic")

    def _fetch_google_models(self):
        try:
            models = litellm.get_valid_models(
                check_provider_endpoint=True,
                custom_llm_provider="gemini",
            )
            result = []
            for m in models:
                if not isinstance(m, str):
                    continue
                # Normalise prefix — keep only gemini generative models
                display = m[len("gemini/"):] if m.startswith("gemini/") else m
                if display.startswith("gemini-"):
                    result.append(display)
            return sorted(set(result))
        except Exception:
            return self._static_fallback("Google")

    def _fetch_github_copilot_models(self):
        try:
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

            return sorted(set(result)) if result else self._static_fallback("GitHub")
        except Exception:
            return self._static_fallback("GitHub")

    def _static_fallback(self, provider):
        config = self._get_provider_config(provider)
        prefix = config["prefix"]
        raw = litellm.models_by_provider.get(config["provider_key"], [])
        result = []
        for m in raw:
            if isinstance(m, str):
                display = m[len(prefix):] if prefix and m.startswith(prefix) else m
                result.append(display)
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

    async def generate_response_stream(self, model_id, messages, tools=None):
        try:
            # Prepend system prompt if not present
            if not messages or messages[0].get("role") != "system":
                messages.insert(0, {"role": "system", "content": self.system_prompt})

            litellm_model = self.normalize_model_id(model_id)

            kwargs = {
                "model": litellm_model,
                "messages": messages,
                "stream": True,
            }
            if tools:
                kwargs["tools"] = tools

            response = await litellm.acompletion(**kwargs)

            async for chunk in response:
                yield chunk

        except Exception as e:
            yield {"error": str(e)}
