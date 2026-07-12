import streamlit as st
import uuid
from sao.frontend.client import SaoClient
from sao.config import load_last_state, save_last_state, get_env_credentials, set_env_credentials

st.set_page_config(page_title="Sao - Minimalist AI", page_icon="🤖", layout="centered")

from sao.config import DEFAULT_BASES

# --- Session State Initialization ---
if "client" not in st.session_state:
    st.session_state.client = SaoClient()
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "provider" not in st.session_state:
    state = load_last_state()
    st.session_state.provider = state.get("active_provider") or "OpenAI"
    provider_state = state.get("providers", {}).get(st.session_state.provider, {})
    st.session_state.last_model = provider_state.get("model", "")
    st.session_state.config_mode = provider_state.get("config_mode", "Default")

# --- Sidebar: Settings & Hot-Switching ---
with st.sidebar:
    st.title("Settings")
    provider = st.selectbox("Provider", ["OpenAI", "Anthropic", "GitHub", "Google"], 
                            index=["OpenAI", "Anthropic", "GitHub", "Google"].index(st.session_state.provider))
    
    if provider != st.session_state.provider:
        # Load the new provider's last saved state
        state = load_last_state()
        provider_state = state.get("providers", {}).get(provider, {})
        
        st.session_state.provider = provider
        st.session_state.config_mode = provider_state.get("config_mode", "Default")
        st.session_state.last_model = provider_state.get("model", "")
        save_last_state(provider)
        st.rerun()
        
    env_api_base, env_api_key = get_env_credentials(st.session_state.provider)
    
    active_api_base = DEFAULT_BASES.get(st.session_state.provider, "") if st.session_state.config_mode == "Default" else env_api_base
    active_api_key = env_api_key

    # Fetch models for the selected provider
    try:
        models = st.session_state.client.list_models(st.session_state.provider, active_api_base, active_api_key)
        if not models:
            st.warning(f"No models found for {st.session_state.provider}. Check your credentials.")
    except Exception as e:
        st.error(f"Error fetching models: {e}")
        models = []

    default_index = 0
    if st.session_state.last_model in models:
        default_index = models.index(st.session_state.last_model)
        
    model_id = st.selectbox("Model", models, index=default_index)
    if model_id and model_id != st.session_state.last_model:
        st.session_state.last_model = model_id
        save_last_state(st.session_state.provider, model_id, st.session_state.config_mode)

    if st.session_state.provider != "GitHub":
        with st.expander("Configs", expanded=False):
            config_mode = st.radio("Configuration Mode", ["Default", "Custom"], index=0 if st.session_state.config_mode == "Default" else 1)
            
            if config_mode != st.session_state.config_mode:
                st.session_state.config_mode = config_mode
                save_last_state(st.session_state.provider, model_id, config_mode)
                st.rerun()

            if config_mode == "Default":
                st.text_input("API Base", value=DEFAULT_BASES.get(st.session_state.provider, ""), disabled=True)
                new_key = st.text_input("API Key (Mandatory)", value=env_api_key, type="password")
                if new_key != env_api_key:
                    set_env_credentials(st.session_state.provider, env_api_base, new_key)
                    st.rerun()
            else:
                new_base = st.text_input("API Base (Mandatory)", value=env_api_base)
                new_key = st.text_input("API Key (Optional)", value=env_api_key, type="password")
                if new_base != env_api_base or new_key != env_api_key:
                    set_env_credentials(st.session_state.provider, new_base, new_key)
                    st.rerun()

# --- Main Chat UI ---
st.title("Sao")

# Render history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Input area
if prompt := st.chat_input("Message Sao..."):
    if st.session_state.provider != "GitHub":
        if st.session_state.config_mode == "Default" and not active_api_key:
            st.error(f"API Key is mandatory for {st.session_state.provider} in Default configuration. Please enter it in the Configs section.")
            st.stop()
        if st.session_state.config_mode == "Custom" and not active_api_base:
            st.error(f"API Base URL is mandatory for {st.session_state.provider} in Custom configuration. Please enter it in the Configs section.")
            st.stop()
            
    if not model_id:
        st.error("Please select a model first.")
        st.stop()
        
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Stream response from backend
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        try:
            # We use a generator to stream chunks from the gRPC client to the Streamlit UI
            api_base, api_key = get_env_credentials(st.session_state.provider)
            
            stream = st.session_state.client.send_chat_stream(
                st.session_state.session_id, 
                model_id, 
                st.session_state.messages, 
                provider=st.session_state.provider,
                api_base=api_base,
                api_key=api_key
            )
            
            for chunk, is_final in stream:
                if chunk:
                    full_response += chunk
                    message_placeholder.markdown(full_response + "▌")
                if is_final:
                    break
            
            message_placeholder.markdown(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            
        except Exception as e:
            st.error(f"Error communicating with backend: {e}")
