# Sao Agent Guide

## Source Of Truth
- Treat [docs/sao_srs.md](docs/sao_srs.md) as the product requirements source of truth.
- Use [README.md](README.md) for the high-level project summary and [requirements.txt](requirements.txt) for dependencies.

## How To Run
- Launch the app with `python main.py`.
- The backend runs in a separate process and the PyQt6 frontend runs in the main thread.

## Code Boundaries
- [main.py](main.py) only wires startup and shutdown.
- [sao/frontend/app.py](sao/frontend/app.py) owns the UI and must stay responsive.
- [sao/frontend/client.py](sao/frontend/client.py) owns gRPC client calls and FlatBuffers serialization.
- [sao/backend/server.py](sao/backend/server.py) owns the streaming service implementation.
- [sao/backend/router.py](sao/backend/router.py) owns model normalization and LiteLLM routing.
- [sao/backend/database.py](sao/backend/database.py) owns SQLite persistence.
- [sao/backend/mcp_manager.py](sao/backend/mcp_manager.py) owns MCP tool wiring.
- [ipc/sao.fbs](ipc/sao.fbs) is the schema source; generated bindings live in [sao/ipc/](sao/ipc/).

## Conventions And Pitfalls
- Keep long-running work off the UI thread; use Qt signals, worker threads, or background tasks.
- Worker threads emit data only; create dialogs, open Settings, and call application lifecycle APIs from GUI-thread slots.
- Keep FlatBuffers schema changes and generated Python bindings in sync.
- Regenerate IPC artifacts with [bin/flatc](bin/flatc) when the schema changes.
- Verify the generated bindings imported at runtime; do not manually copy generated code between artifact locations.
- Carry the selected provider through chat IPC so the backend performs model-ID normalization and validation with provider context.
- Treat cached models as usable after a provider refresh failure; disable chat when no models are available, and keep credential settings aligned with their declared frontend or backend owner.
- Preserve the hardcoded system prompt and single-session behavior described in the SRS.
- Keep GitHub Copilot routing aligned with LiteLLM-based handling from the SRS.
- Link to existing docs instead of duplicating them in instructions.

## Editing Guidance
- Prefer small, focused changes within the owning layer.
- Avoid crossing frontend/backend boundaries unless the request explicitly requires it.
- If you change chat streaming or IPC, validate the end-to-end path from [sao/frontend/client.py](sao/frontend/client.py) to [sao/backend/server.py](sao/backend/server.py).
# Permission and Authorization Handling
- **Report Permission Denials**: If a command, tool, or service fails with a "Permission denied" or authorization error (e.g., missing GitHub CLI permissions), do not silently fall back to a workaround.
- **Prompt the User for Fixes**: Pause execution, report the exact error message and the required permissions to the user. Allow the user to fix the configuration or authorize the action.
- **Use Workarounds Only as a Last Resort**: Only employ alternative methods or workarounds if the user explicitly declines to fix the permissions or instructs you to find another way.
