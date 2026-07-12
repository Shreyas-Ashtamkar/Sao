import json
import os
from pathlib import Path
from dotenv import set_key, unset_key, dotenv_values

PROJECT_ROOT = Path(__file__).parent.parent
LAST_STATE_FILE = PROJECT_ROOT / ".last_state"
ENV_FILE = PROJECT_ROOT / ".env"

DEFAULT_BASES = {
    "OpenAI": "https://api.openai.com/v1",
    "Anthropic": "https://api.anthropic.com/v1",
    "Google": "https://generativelanguage.googleapis.com/v1beta/openai", # Using litellm default mapping or standard.
    "GitHub": ""
}

def load_last_state():
    default_state = {
        "active_provider": "OpenAI",
        "providers": {}
    }
    if LAST_STATE_FILE.exists():
        try:
            with open(LAST_STATE_FILE, "r") as f:
                data = json.load(f)
                if "providers" not in data:
                    provider = data.get("provider", "OpenAI")
                    default_state["active_provider"] = provider
                    default_state["providers"][provider] = {
                        "model": data.get("model", ""),
                        "config_mode": data.get("config_mode", "Default")
                    }
                    return default_state
                return data
        except Exception:
            pass
    return default_state

def save_last_state(provider, model=None, config_mode=None):
    state = load_last_state()
    if provider:
        state["active_provider"] = provider
        if provider not in state["providers"]:
            state["providers"][provider] = {"model": "", "config_mode": "Default"}
            
    if model is not None:
        state["providers"][provider]["model"] = model
    if config_mode is not None:
        state["providers"][provider]["config_mode"] = config_mode
        
    with open(LAST_STATE_FILE, "w") as f:
        json.dump(state, f)

def get_env_credentials(provider):
    env_vals = dotenv_values(ENV_FILE)
    if provider == "OpenAI":
        return env_vals.get("OPENAI_API_BASE", ""), env_vals.get("OPENAI_API_KEY", "")
    elif provider == "Anthropic":
        return env_vals.get("ANTHROPIC_API_BASE", ""), env_vals.get("ANTHROPIC_API_KEY", "")
    elif provider == "Google":
        return env_vals.get("GEMINI_API_BASE", ""), env_vals.get("GEMINI_API_KEY", "")
    return "", ""

def set_env_credentials(provider, api_base, api_key):
    if not ENV_FILE.exists():
        ENV_FILE.touch()
        
    env_path = str(ENV_FILE)
    def update_key(key, val):
        if val:
            set_key(env_path, key, val)
        else:
            unset_key(env_path, key)
            
    if provider == "OpenAI":
        update_key("OPENAI_API_BASE", api_base)
        update_key("OPENAI_API_KEY", api_key)
    elif provider == "Anthropic":
        update_key("ANTHROPIC_API_BASE", api_base)
        update_key("ANTHROPIC_API_KEY", api_key)
    elif provider == "Google":
        update_key("GEMINI_API_BASE", api_base)
        update_key("GEMINI_API_KEY", api_key)
