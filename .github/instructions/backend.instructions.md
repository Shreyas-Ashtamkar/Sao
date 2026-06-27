---
description: "Use when editing backend routing, LiteLLM integration, SQLite persistence, or MCP tool execution in sao/backend."
applyTo: "sao/backend/**/*.py"
---
# Backend Guidelines

- Keep the hardcoded system prompt and single-session behavior intact.
- Normalize model IDs in the router without duplicating provider logic in the frontend.
- Preserve streaming responses end to end through the gRPC service.
- Keep persistence local to SQLite and avoid introducing cloud sync or telemetry.
- Scope tool execution to MCP only; do not add arbitrary shell execution paths.
- If backend behavior changes, check the call path from [sao/backend/server.py](sao/backend/server.py) through [sao/backend/router.py](sao/backend/router.py) and [sao/backend/database.py](sao/backend/database.py).
