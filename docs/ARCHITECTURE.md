# PromptAnywhere â€” Architecture

Concise overview of project structure and class roles. See [AGENTS.md](../AGENTS.md) for rules and conventions.

---

## Entry & Layers

| Path | Role |
|------|------|
| `run_prompt_anywhere.py` / `python -m prompt_anywhere` | Entry; calls `ui.app.main()`. |
| `src/prompt_anywhere/core/` | Pure Python logic only. No Qt. |
| `src/prompt_anywhere/ui/` | PySide6 GUI. May import from `core/`, never the reverse. |
| `src/prompt_anywhere/common/` | Shared models (UIâ†”host contract). |
| `src/prompt_anywhere/host/` | Local CopeNet Host (FastAPI + WebSocket RPC). |

---

## Core (`src/prompt_anywhere/core/`)

### Coordinator
- **App** (`app.py`) â€” Business-logic coordinator. Holds `Config` + `HotkeyManager` and tracks selected model key for UI/gateway routing.

### Config & hotkeys
- **Config** (`config.py`) â€” Load/save JSON config from `~/.prompt_anywhere/` (hotkey, default_agent, theme).
- **HotkeyManager** (`hotkey_manager.py`) â€” Registers Ctrl+Alt+X via pynput; invokes callback on press (must be thread-safe).

### Agents (`core/agents/`)
- Legacy direct-CLI agent wrappers. CopeNet execution now runs through `core/providers/*` + `core/orchestrator.py`.

### Features (`core/features/`)
- **BaseFeature** â€” Abstract: `name`, `icon`, `hotkey`, `execute(prompt) -> str`.
- **GoogleSearchFeature** â€” Open Google Search with query.
- **FileSearchFeature** â€” Windows Explorer search-ms with query.
- **BrowserFeature** â€” Open URL in default browser.
- **TerminalFeature** â€” Launch Windows Terminal (or cmd).
- **MaximizeChatFeature** â€” Returns `"maximize_window"` (GUI handles).
- **HistoryFeature** â€” Placeholder; GUI opens history window.
- **ScreenshotFeature** â€” Placeholder; screenshot handled by UI overlay.
- **CustomizeFeature** â€” Returns `"open_customize"` (GUI handles).

### Utils
- **platform_utils** â€” `apply_blur_effect(hwnd)` for Windows DWM blur.

---

## UI (`src/prompt_anywhere/ui/`)

### Coordinator
- **PromptAnywhereApp** (`app.py`) â€” GUI coordinator. Creates `QApplication`, system tray, owns `PromptShellWindow` and `HistoryWindow`. Instantiates core `App` and all features; connects hotkey signal to `show_prompt_window`; runs gateway streaming in **GatewayWorker** and wires **StreamSignals** to chat widget.
- **StreamSignals** â€” `text_chunk`, `finished`, `error`.
- **GatewayWorker** â€” Thread: calls `GatewayClient.stream_chat()` and emits chat deltas via StreamSignals.
- **HotkeySignals** â€” `triggered`; used to invoke show_prompt from hotkey thread.

### Common (`ui/common/`)
Shared UI utilities used by the main windows (no duplicated asset/background/mask logic).
- **assets** â€” `get_asset_path(filename)`, `set_button_icon(button, filename, size)`, `load_icon_pixmap()`, `get_icon_name(icon_key)`; optional `ICON_MAP`.
- **background** â€” `FixedBackgroundLabel` (zero sizeHint), `update_background_pixmap(label, pixmap, target_size)` for scaled/cropped background.
- **window_shape** â€” `apply_rounded_mask(widget, radius=16)` for frameless rounded corners.

### Services (`ui/services/`)
UI-facing services; isolates I/O from widgets.
- **session_manager** â€” `get_history_path()`, `load_sessions(path)`, `save_session(path, session_payload)`, `load_session_by_id(path, session_id)`. Used by **ResultWindow** to read CopeNet session/transcript stores (`~/.prompt_anywhere/sessions/index.json` + `*.jsonl`); legacy write path is disabled.

### Windows (`ui/windows/`)
Main windows use `setup_ui()` split into: `_build_container()`, `_build_header()`, `_build_main_content()`, `_wire_signals()`, `_apply_initial_state()`. They rely on `ui/common` for assets, background, and rounded mask.
- **PromptShellWindow** â€” Single top-level window: prompt bar (bottom) + collapsible chat drawer (top). Embeds `MainPromptWindow` and `ResultWindow`; owns drawer open/close animation. Emits `prompt_submitted`, `follow_up_submitted`, `feature_triggered`, `session_closed`, `history_session_selected`.
- **MainPromptWindow** â€” Prompt bar: input, feature buttons, screenshot. Embeddable (`embedded=True`). Emits `prompt_submitted`, `feature_triggered`.
- **ResultWindow** â€” Chat/streaming area; renders messages and handles interaction; session load/save/find delegated to **session_manager**. Embeddable. Emits `follow_up_submitted`, `session_closed`.
- **PromptInputWindow** â€” Legacy minimal prompt input (if used).
- **HistoryWindow** â€” List/load saved sessions; emits `session_selected`.
- **ScreenshotOverlay** â€” Full-screen overlay for screenshot capture (PIL/Pillow).

### Widgets (`ui/widgets/`)
- **FeatureCard** â€” Button for a feature (icon + label).
- **GlowingButton** â€” Styled push button.

### Styles (`ui/styles/`)
- **ThemeManager** â€” Theme handling. Theme definitions in `theme_blue.py`, `theme_warm.py`.

---

## Common (`src/prompt_anywhere/common/`)

- **Attachment** â€” `kind`, `path`.
- **PromptContext** â€” `cwd`, `active_window_title`, `extra`.
- **SendPromptRequest** â€” `text`, `attachments`, `context`.
- **StreamEvent** â€” `type` (token/final/error), `text`, `meta`.

---

## Host (`src/prompt_anywhere/host/`)

- **create_app()** (`api.py`) â€” FastAPI app: `/health`, `/v1/agents/prewarm` (stub).
- **main** (`main.py`) â€” Host process entry for CopeNet gateway runtime.

---

## Data flow (summary)

1. Hotkey (pynput) â†’ HotkeyManager callback â†’ HotkeySignals.triggered â†’ `show_prompt_window()`.
2. User submits prompt in MainPromptWindow â†’ PromptShellWindow â†’ `process_prompt()` â†’ GatewayWorker calls `GatewayClient.stream_chat()` â†’ WS `chat.send`/`chat` events â†’ StreamSignals â†’ ResultWindow chat (append_text / set_finished / show_error).
3. Feature button â†’ `handle_feature()` â†’ `feature.execute(prompt)`; special results (`maximize_window`, `open_customize`, history) handled in GUI.

---

## CopeNet Transformation (2026-02-16)

This section tracks migration from the legacy direct-UI agent flow to a local CopeNet gateway flow.

### Current State (gateway-only execution path)

- UI sends chat turns through `GatewayClient` only.
- Session history for UI is sourced from CopeNet stores through `ui/services/session_manager.py`.
- Host process exists, and now includes a WS RPC entry point.

### New CopeNet Modules Added

- `src/prompt_anywhere/host/rpc_schema.py`
- `src/prompt_anywhere/host/ws_server.py`
- `src/prompt_anywhere/core/orchestrator.py`
- `src/prompt_anywhere/core/sessions/session_store.py`
- `src/prompt_anywhere/core/sessions/transcript_store.py`
- `src/prompt_anywhere/core/providers/base.py`
- `src/prompt_anywhere/core/providers/codex_cli.py`
- `src/prompt_anywhere/core/runner/cli_runner.py`

### Host API Delta

- `src/prompt_anywhere/host/api.py` now exposes `GET /health`, `POST /v1/agents/prewarm`, and `WS /ws`.
- WS protocol supports:
  - `connect`
  - `chat.send`
  - `chat.abort`
  - `chat.history`
  - `sessions.list`
  - `sessions.resolve`

### What Is Implemented vs Remaining

Implemented:

- Codex-first provider path (`codex exec` / `codex exec resume <provider_session_id>`).
- Provider-agnostic session metadata field (`provider_session_id`).
- Append-only transcript storage in `~/.prompt_anywhere/sessions/<sessionId>.jsonl`.
- Basic handshake (`connect.challenge` -> `connect` -> `hello-ok`).
- Chat streaming events (`delta`, `final`, `error`).
- In-flight run guard per session.

Remaining:

- Provider expansion for UI model selector (currently only Codex is mapped in CopeNet).
- Persisted idempotency cache policy (current is in-memory).
- Claude provider discovery and adapter.
- Gemini provider discovery and adapter.
- Daemon lifecycle commands and startup integration.
- Integration and regression tests for WS, session resume, and abort.

### Migration Path (source -> destination)

- UI send path:
  - from: `PromptShellWindow -> AgentWorker -> core/agents/*`
  - to: `PromptShellWindow -> GatewayClient -> WS /ws -> Orchestrator`
- Session metadata:
  - from: `~/.prompt_anywhere/chat_sessions.json` (UI service)
  - to: `~/.prompt_anywhere/sessions/index.json` (core session store)
- Transcript:
  - from: UI-centric session payloads
  - to: append-only JSONL per `sessionId` in sessions directory

