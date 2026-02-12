# PromptAnywhere — Architecture

Concise overview of project structure and class roles. See [AGENTS.md](../AGENTS.md) for rules and conventions.

---

## Entry & Layers

| Path | Role |
|------|------|
| `run_prompt_anywhere.py` / `python -m prompt_anywhere` | Entry; calls `ui.app.main()`. |
| `src/prompt_anywhere/core/` | Pure Python logic only. No Qt. |
| `src/prompt_anywhere/ui/` | PySide6 GUI. May import from `core/`, never the reverse. |
| `src/prompt_anywhere/common/` | Shared models (UI↔host contract). |
| `src/prompt_anywhere/host/` | Local Agent Host (FastAPI); optional. |

---

## Core (`src/prompt_anywhere/core/`)

### Coordinator
- **App** (`app.py`) — Business-logic coordinator. Holds `Config`, `HotkeyManager`, default `BaseAgent` (e.g. Gemini). Registers global hotkey and exposes `get_agent()`.

### Config & hotkeys
- **Config** (`config.py`) — Load/save JSON config from `~/.prompt_anywhere/` (hotkey, default_agent, theme).
- **HotkeyManager** (`hotkey_manager.py`) — Registers Ctrl+Alt+X via pynput; invokes callback on press (must be thread-safe).

### Agents (`core/agents/`)
- **BaseAgent** — Abstract: `name`, `send_prompt(prompt, context) -> Iterator[str]`.
- **GeminiAgent** — Streams via Gemini CLI subprocess; supports image context (temp file). Windows: `gemini.cmd`.
- **ClaudeAgent** / **CodexAgent** — Placeholder stubs.

### Features (`core/features/`)
- **BaseFeature** — Abstract: `name`, `icon`, `hotkey`, `execute(prompt) -> str`.
- **GoogleSearchFeature** — Open Google Search with query.
- **FileSearchFeature** — Windows Explorer search-ms with query.
- **BrowserFeature** — Open URL in default browser.
- **TerminalFeature** — Launch Windows Terminal (or cmd).
- **MaximizeChatFeature** — Returns `"maximize_window"` (GUI handles).
- **HistoryFeature** — Placeholder; GUI opens history window.
- **ScreenshotFeature** — Placeholder; screenshot handled by UI overlay.
- **CustomizeFeature** — Returns `"open_customize"` (GUI handles).

### Utils
- **platform_utils** — `apply_blur_effect(hwnd)` for Windows DWM blur.

---

## UI (`src/prompt_anywhere/ui/`)

### Coordinator
- **PromptAnywhereApp** (`app.py`) — GUI coordinator. Creates `QApplication`, system tray, owns `PromptShellWindow` and `HistoryWindow`. Instantiates core `App` and all features; connects hotkey signal to `show_prompt_window`; runs agent in **AgentWorker** thread and wires **StreamSignals** to chat widget.
- **StreamSignals** — `text_chunk`, `finished`, `error`.
- **AgentWorker** — Thread: calls `agent.send_prompt()`, emits chunks via StreamSignals.
- **HotkeySignals** — `triggered`; used to invoke show_prompt from hotkey thread.

### Common (`ui/common/`)
Shared UI utilities used by the main windows (no duplicated asset/background/mask logic).
- **assets** — `get_asset_path(filename)`, `set_button_icon(button, filename, size)`, `load_icon_pixmap()`, `get_icon_name(icon_key)`; optional `ICON_MAP`.
- **background** — `FixedBackgroundLabel` (zero sizeHint), `update_background_pixmap(label, pixmap, target_size)` for scaled/cropped background.
- **window_shape** — `apply_rounded_mask(widget, radius=16)` for frameless rounded corners.

### Services (`ui/services/`)
UI-facing services; isolates I/O from widgets.
- **session_manager** — `get_history_path()`, `load_sessions(path)`, `save_session(path, session_payload)`, `load_session_by_id(path, session_id)`. Used by **ResultWindow** for chat history persistence (`~/.prompt_anywhere/chat_sessions.json`).

### Windows (`ui/windows/`)
Main windows use `setup_ui()` split into: `_build_container()`, `_build_header()`, `_build_main_content()`, `_wire_signals()`, `_apply_initial_state()`. They rely on `ui/common` for assets, background, and rounded mask.
- **PromptShellWindow** — Single top-level window: prompt bar (bottom) + collapsible chat drawer (top). Embeds `MainPromptWindow` and `ResultWindow`; owns drawer open/close animation. Emits `prompt_submitted`, `follow_up_submitted`, `feature_triggered`, `session_closed`, `history_session_selected`.
- **MainPromptWindow** — Prompt bar: input, feature buttons, screenshot. Embeddable (`embedded=True`). Emits `prompt_submitted`, `feature_triggered`.
- **ResultWindow** — Chat/streaming area; renders messages and handles interaction; session load/save/find delegated to **session_manager**. Embeddable. Emits `follow_up_submitted`, `session_closed`.
- **PromptInputWindow** — Legacy minimal prompt input (if used).
- **HistoryWindow** — List/load saved sessions; emits `session_selected`.
- **ScreenshotOverlay** — Full-screen overlay for screenshot capture (PIL/Pillow).

### Widgets (`ui/widgets/`)
- **FeatureCard** — Button for a feature (icon + label).
- **GlowingButton** — Styled push button.

### Styles (`ui/styles/`)
- **ThemeManager** — Theme handling. Theme definitions in `theme_blue.py`, `theme_warm.py`.

---

## Common (`src/prompt_anywhere/common/`)

- **Attachment** — `kind`, `path`.
- **PromptContext** — `cwd`, `active_window_title`, `extra`.
- **SendPromptRequest** — `text`, `attachments`, `context`.
- **StreamEvent** — `type` (token/final/error), `text`, `meta`.

---

## Host (`src/prompt_anywhere/host/`)

- **create_app()** (`api.py`) — FastAPI app: `/health`, `/v1/agents/prewarm` (stub).
- **main** (`main.py`) — Host process entry (if run as separate service).

---

## Data flow (summary)

1. Hotkey (pynput) → HotkeyManager callback → HotkeySignals.triggered → `show_prompt_window()`.
2. User submits prompt in MainPromptWindow → PromptShellWindow → `process_prompt()` → AgentWorker runs `agent.send_prompt()` → StreamSignals → ResultWindow chat (append_text / set_finished / show_error).
3. Feature button → `handle_feature()` → `feature.execute(prompt)`; special results (`maximize_window`, `open_customize`, history) handled in GUI.
