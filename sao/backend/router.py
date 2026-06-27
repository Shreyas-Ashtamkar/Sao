import litellm

class Router:
    def __init__(self):
        self.system_prompt = "You are Sao, a lightweight AI chat assistant for solo developers. Provide clear, concise answers without fluff."

    async def generate_response_stream(self, model_id, messages, tools=None):
        try:
            # Prepend system prompt if not present
            if not messages or messages[0].get("role") != "system":
                messages.insert(0, {"role": "system", "content": self.system_prompt})

            # Map friendly model IDs to litellm-compliant IDs
            model_map = {
                "github_copilot": "github_copilot/gpt-4o",
                "claude-3-5-sonnet-20240620": "anthropic/claude-3-5-sonnet-20240620",
                "claude-3-opus-20240229": "anthropic/claude-3-opus-20240229",
                "claude-3-haiku-20240307": "anthropic/claude-3-haiku-20240307",
                "gemini-1.5-pro": "gemini/gemini-1.5-pro",
                "gemini-1.5-flash": "gemini/gemini-1.5-flash"
            }
            litellm_model = model_map.get(model_id, model_id)

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
