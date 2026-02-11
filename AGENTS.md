# PromptAnywhere - AGENTS Guide

## Purpose
Keep the app stable while extending features. This file is the execution guide for AI agents working in this repo.

## Non-Negotiables
- Strict separation: `src/code/` is pure Python logic only. No Qt/PySide6 imports.
- GUI only in `src/gui/`. GUI may import from `src/code/`, never the reverse.
- Preserve existing behavior. Ask before making breaking changes.
- Windows-first: use `gemini.cmd`, handle Windows paths correctly.

## Repo Map (Key Paths)
- `prompt_anywhere.py`: entry point; should stay minimal.
- `src/code/`: core logic, agents, features, utilities.
- `src/gui/`: PySide6 UI, windows, widgets, styles.
- `src/code/core/app.py`: business-logic coordinator.
- `src/gui/app.py`: GUI coordinator.

## Architecture Rules
- Agents extend `BaseAgent` and implement `send_prompt()` returning `Iterator[str]`.
- Features extend `BaseFeature` and implement `execute()` returning `str`.
- Threaded work uses a `Thread` plus Qt signals for GUI-safe updates.
- No circular dependencies across layers.

## When Adding an Agent
1. Create class in `src/code/agents/`.
2. Implement `send_prompt()` as a streaming iterator.
3. Wire into the app coordinator.
4. Add minimal tests or a manual verification note.

## When Adding a Feature
1. Create class in `src/code/features/`.
2. Implement `execute()`.
3. Register it with the app coordinator.
4. If UI is needed, add to `src/gui/` and connect via signals.

## Debugging Flow
1. Confirm which layer: `src/gui/` vs `src/code/`.
2. Verify the hotkey thread is running.
3. Confirm Gemini CLI is installed and configured.
4. Check Windows-specific paths and `.cmd` usage.

## Code Quality
- Type hints for function signatures.
- Docstrings for classes and public methods.
- Small, focused functions.
- No Qt imports in `src/code/`.

## Smoke Tests (Manual)
- App launches without errors.
- `Ctrl+Alt+X` opens the prompt window.
- Screenshot capture works.
- Streaming responses work.
- System tray icon appears.
- No Qt imports in `src/code/`.

## Reminders
`prompt_anywhere.py` should remain a thin wrapper that calls `src/gui/app.py:main()`.
