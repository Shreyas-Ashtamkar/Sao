---
description: "Use when editing PyQt6 frontend code, UI threading, model selection, or chat rendering in sao/frontend."
applyTo: "sao/frontend/**/*.py"
---
# Frontend Guidelines

- Keep the UI responsive; move network, LLM, and streaming work off the main thread.
- Use Qt signals, slots, or worker threads for updates that cross thread boundaries.
- Preserve the persistent model selector and the minimal chat layout.
- Avoid blocking calls inside event handlers.
- If UI changes affect message flow, validate the handoff through [sao/frontend/client.py](sao/frontend/client.py).
