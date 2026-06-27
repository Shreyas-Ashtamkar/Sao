---
description: "Use when editing FlatBuffers schema, gRPC IPC, or generated bindings between the frontend and backend."
applyTo: "ipc/**/*.fbs, sao/ipc/**/*.py"
---
# IPC Guidelines

- Treat [ipc/sao.fbs](../../ipc/sao.fbs) as the schema source of truth.
- Keep request and response schema changes in sync with generated bindings under [sao/ipc/](../../sao/ipc/).
- Regenerate bindings with [bin/flatc](../../bin/flatc) when the schema changes.
- Preserve compatibility across the frontend client and backend servicer when changing message fields or enums.
