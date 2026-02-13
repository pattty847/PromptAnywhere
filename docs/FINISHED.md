# PromptAnywhere Finished Features

Concise list of completed feature work. Keep this file short and append new items.

## 2026-02-12
- Model selection dropdown added to prompt bottom row (next to Customize).
- Agent switching wired end-to-end:
- UI selection emits agent change signal.
- Shell forwards selection to app coordinator.
- Core app switches active agent and persists default agent in config.

## 2026-02-11 to 2026-02-12
- Shell/drawer stabilization pass completed for now.
- Kept simple drawer implementation as current baseline.
- Added focused UI debug instrumentation path for drawer investigations.

## 2026-02-10
- Shell window + collapsible drawer scaffold.
- Host skeleton (FastAPI + /health + prewarm stub).
