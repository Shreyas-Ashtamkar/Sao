# Sao
![Sao Logo](./assets/logo.png)

**A lightweight, minimalist AI chat agent for solo developers.**

---

## What is Sao?
Sao is a locally-hosted desktop application designed for solo developers. It provides a bloat-free Graphical User Interface (GUI) to interact with large language models (LLMs) and execute local tools via the Model Context Protocol (MCP). 

Built with speed and minimalism in mind, Sao offers you a powerful assistant experience without the heavy footprint of enterprise IDEs or multi-agent orchestration platforms.

## Key Features
- **Modern UI**: Built on **PyQt6** for a native, fast, and responsive desktop experience.
- **High-Performance Architecture**: Decoupled GUI and Python backend, communicating locally via **gRPC** and **FlatBuffers** to ensure the interface never freezes, even under heavy generation loads.
- **LLM Hot-Switching**: Instantly switch between OpenAI, Anthropic, Ollama, and GitHub Copilot natively using **LiteLLM**.
- **Model Context Protocol (MCP)**: Bundled with the **WebFetch MCP**, enabling your LLM to seamlessly browse and fetch web contents.
- **Local Privacy**: All conversation histories and metadata are saved to a local **SQLite** database. No telemetry, no cloud syncing.
- **Single-Session Focus**: Hardcoded system prompt keeping the assistant strictly focused on your immediate tasks without context bleed from older sessions.

## Getting Started
*(Setup instructions and documentation will be added here as the project matures.)*
