"""FastAPI app for the local Agent Host.

This is intentionally minimal scaffolding:
- /health: liveness check
- /v1/agents/prewarm: stub for prewarming backends

Streaming endpoints (SSE) will be added next.
"""

from __future__ import annotations

from fastapi import FastAPI, WebSocket

from prompt_anywhere.host.ws_server import CopeNetWsServer


def create_app() -> FastAPI:
    app = FastAPI(title="PromptAnywhere Agent Host", version="0.1.0")
    ws_server = CopeNetWsServer()

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    @app.post("/v1/agents/prewarm")
    def prewarm(payload: dict) -> dict:
        # TODO: spawn/persist backend processes (gemini/claude/codex)
        return {"ok": True, "requested": payload}

    @app.websocket("/ws")
    async def websocket_rpc(websocket: WebSocket) -> None:
        await ws_server.handle(websocket)

    return app
