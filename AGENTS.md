# PromptAnywhere - AGENTS Guide

## Purpose
Keep the app stable while extending features. This file is the execution guide for AI agents working in this repo.

## Non-Negotiables
- Strict separation: `src/prompt_anywhere/core/` is pure Python logic only. No Qt/PySide6 imports.
- GUI only in `src/prompt_anywhere/ui/`. UI may import from `core/`, never the reverse.
- Preserve existing behavior. Ask before making breaking changes.
- Windows-first: use `gemini.cmd`, handle Windows paths correctly.

## Repo Map (Key Paths)
- `run_prompt_anywhere.py` / `python -m prompt_anywhere`: entry; calls `ui.app.main()`.
- `src/prompt_anywhere/core/`: logic, agents, features, utils (no Qt).
- `src/prompt_anywhere/ui/`: PySide6 UI. Subdirs: `windows/`, `common/`, `services/`, `widgets/`, `styles/`, `assets/`.
- `core/app.py`: business-logic coordinator. `ui/app.py`: GUI coordinator.
- `ui/common/`: shared assets, background, window_shape (used by main windows).
- `ui/services/`: session_manager (session load/save); UI calls it, no Qt in services.

## Architecture Rules
- Agents extend `BaseAgent` and implement `send_prompt()` returning `Iterator[str]`.
- Features extend `BaseFeature` and implement `execute()` returning `str`.
- Threaded work uses a `Thread` plus Qt signals for GUI-safe updates.
- No circular dependencies across layers.
- Main windows (MainPromptWindow, ResultWindow, PromptShellWindow) use `setup_ui()` split into: `_build_container()`, `_build_header()`, `_build_main_content()`, `_wire_signals()`, `_apply_initial_state()`. Prefer reusing `ui/common` (assets, background, window_shape) over duplicating.

## When Adding an Agent
1. Create class in `core/agents/`.
2. Implement `send_prompt()` as a streaming iterator.
3. Wire into the app coordinator.
4. Add minimal tests or a manual verification note.

## When Adding a Feature
1. Create class in `core/features/`.
2. Implement `execute()`.
3. Register it with the app coordinator.
4. If UI is needed, add to `ui/` and connect via signals.

## Debugging Flow
1. Confirm which layer: `ui/` vs `core/`.
2. Verify the hotkey thread is running.
3. Confirm Gemini CLI is installed and configured.
4. Check Windows-specific paths and `.cmd` usage.

## Code Quality
- Type hints for function signatures.
- Docstrings for classes and public methods.
- Small, focused functions.
- No Qt imports in `core/`.

## Smoke Tests (Manual)
- App launches without errors.
- `Ctrl+Alt+X` opens the prompt window.
- Screenshot capture works.
- Streaming responses work.
- System tray icon appears.
- Rounded corners/background clipping correct.
- No Qt imports in `core/`.

## Reminders
Entry stays minimal and calls `ui.app.main()`. Session persistence lives in `ui/services/session_manager`; UI widgets call it, don’t re-implement file I/O in windows.
