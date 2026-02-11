"""FastAPI app for the local Agent Host.

This is intentionally minimal scaffolding:
- /health: liveness check
- /v1/agents/prewarm: stub for prewarming backends

Streaming endpoints (SSE) will be added next.
"""

from __future__ import annotations

from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="PromptAnywhere Agent Host", version="0.1.0")

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    @app.post("/v1/agents/prewarm")
    def prewarm(payload: dict) -> dict:
        # TODO: spawn/persist backend processes (gemini/claude/codex)
        return {"ok": True, "requested": payload}

    return app
