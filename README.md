<div align="center">
  <img src="assets/logo.png" alt="Sao Logo" width="200" height="200" />
  <h1>Sao</h1>
  <p><b>A lightweight, minimalist AI chat agent for solo developers.</b></p>
</div>

---

## What is Sao?
Sao is a locally-hosted desktop application designed for solo developers. It provides a bloat-free Graphical User Interface (GUI) to interact with large language models (LLMs) and execute local tools via the Model Context Protocol (MCP). 

Built with speed and minimalism in mind, Sao offers you a powerful assistant experience without the heavy footprint of enterprise IDEs or multi-agent orchestration platforms.

## Key Features
- **Modern UI**: Built on **PyQt6** for a native, fast, and responsive desktop experience.
- **High-Performance Architecture**: Decoupled GUI and Python backend, communicating locally via **gRPC** and **FlatBuffers** to ensure the interface never freezes, even under heavy generation loads.
- **LLM Hot-Switching**: Instantly switch between OpenAI, Anthropic, Ollama, and GitHub Copilot natively using **LiteLLM**.
- **Model Context Protocol (MCP)**: Connects explicitly configured local MCP servers, enabling the LLM to use their exposed tools.
- **Local Privacy**: All conversation histories and metadata are saved to a local **SQLite** database. No telemetry, no cloud syncing.
- **Single-Session Focus**: Hardcoded system prompt keeping the assistant strictly focused on your immediate tasks without context bleed from older sessions.

## Getting Started

Install dependencies with `python -m pip install -r requirements.txt`, then run `python main.py`.

### MCP configuration

Configure local stdio MCP servers in `~/.sao/mcp_servers.json` before starting Sao. Server
commands, arguments, environment variables, and working directories remain local; Sao does not
provide hidden or cloud-synced server defaults.

```json
{
  "servers": {
    "webfetch": {
      "command": "npx",
      "args": ["-y", "@example/webfetch-mcp"],
      "cwd": "/path/to/working-directory"
    }
  }
}
```

Tools are presented to models as `<server>__<tool>`, and execution is limited to the configured
server that exposes each tool.
