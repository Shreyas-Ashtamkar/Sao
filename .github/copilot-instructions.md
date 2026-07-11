# Sao Copilot Instructions

## Source of truth
- Product requirements: `docs/sao_srs.md`
- Project overview: `README.md`
- Dependency lock: `requirements.txt`
- Agent-specific constraints: `AGENTS.md`

## Run and validation commands
- Install dependencies: `pip install -r requirements.txt`
- Run app (frontend + backend): `python main.py`
- Validate Python syntax for touched modules: `python -m compileall sao/backend sao/frontend sao/ipc`
- Focused validation for a few changed files: `python -m compileall path/to/file.py`
- There is currently no repository-defined lint or automated test command.

## Architecture (big picture)
- `main.py` starts the backend in a separate process and runs the PyQt6 frontend in the main thread.
- Frontend/UI owner: `sao/frontend/app.py`
  - UI state, model selector, settings dialog, and streaming updates.
- Frontend transport owner: `sao/frontend/client.py`
  - gRPC calls and FlatBuffers serialization/deserialization.
- Backend service owner: `sao/backend/server.py`
  - gRPC servicer, stream chunking, list-models endpoint, and DB writes.
- Backend routing owner: `sao/backend/router.py`
  - Provider/model normalization and LiteLLM calls.
- Persistence owner: `sao/backend/database.py`
  - SQLite schema and message/provider-model caching.
- MCP integration owner: `sao/backend/mcp_manager.py`
  - Tool schema loading and tool execution path.
- IPC schema source of truth: `ipc/sao.fbs`
  - Generated artifacts live under `sao/ipc/`.

## Repo-specific conventions
- Keep the UI responsive: no blocking/network-heavy work on the UI thread; use signals, worker threads, or background tasks.
- Worker threads emit data only. Create dialogs, open Settings, and call application lifecycle APIs from GUI-thread slots.
- Keep model ID normalization in backend router logic, not duplicated in frontend logic.
- For chat requests, carry the selected provider through IPC so the backend can normalize and validate the model ID with provider context.
- Treat cached models as usable after a provider refresh failure; when no models are available, disable chat rather than sending an empty model ID. Declare whether credentials are frontend- or backend-owned, and keep settings aligned with that owner.
- Preserve single-session behavior and the hardcoded system prompt semantics from the SRS.
- Keep persistence local to SQLite; do not add telemetry/cloud-sync behavior.
- Scope tool execution through MCP only; do not introduce arbitrary shell execution in backend paths.

## GitHub workflow behavior
- Perform GitHub operations only when explicitly requested by the user (for example: commit, push, create PR, merge PR, rebase).
- When explicitly requested, execute directly without asking confirmation questions.
- Use non-interactive `gh`/`git` command flows and report concrete outputs (commit SHA, PR number/link, merge commit).

## PR review behavior
- For PR review requests, scope investigation to the PR diff first (`gh pr view --json files`, `gh pr diff`, targeted file reads).
- Avoid broad branch archaeology unless the PR diff indicates cross-branch context is needed.

## Plan vs implementation rule
- If the user asks to **plan** a fix, return the plan only.
- Start implementation only after explicit user approval to proceed.

## IPC and streaming checklist
- When changing `ipc/sao.fbs`, regenerate Python FlatBuffers/gRPC bindings with `bin/flatc`.
- Keep schema, generated code, frontend client parsing, and backend servicer handlers in sync.
- Verify the generated bindings imported at runtime; do not manually copy generated code between artifact locations.
- For chat/list-model changes, verify the end-to-end path:
  - `sao/frontend/client.py` -> `sao/ipc/*` -> `sao/backend/server.py` -> `sao/backend/router.py`/`sao/backend/database.py`.

## MCP server configuration guidance
- `README.md` positions WebFetch MCP as bundled; `docs/sao_srs.md` requires MCP servers to be loaded from local configuration at startup.
- Current implementation status: `sao/backend/mcp_manager.py` is still a placeholder; treat it as the single owner for MCP connection and execution wiring.
- Keep MCP server configuration local and explicit (no cloud sync, no hidden fallback server list).
- Load MCP tool schemas before chat requests need them, and pass only those schemas through router calls.
- Keep execution strictly inside MCP (`execute_tool` path); do not add direct shell-command execution paths in backend logic.
