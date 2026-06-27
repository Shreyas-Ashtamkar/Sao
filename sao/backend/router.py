import litellm


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

class Router:
    def __init__(self):
        self.system_prompt = "You are Sao, a lightweight AI chat assistant for solo developers. Provide clear, concise answers without fluff."

    def list_available_models(self, provider):
        config = self._get_provider_config(provider)
        models = litellm.get_valid_models(
            check_provider_endpoint=False,
            custom_llm_provider=config["provider_key"],
        )
        return self._normalize_provider_models(provider, models)

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
