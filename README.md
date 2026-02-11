# PromptAnywhere

Global hotkey AI assistant powered by Codex/Gemini/Claude CLI. Press `Ctrl+Alt+X` anywhere on Windows to open a prompt window, ask questions, attach screenshots, and get instant AI responses.

<p align="center">
  <img width="600" alt="image" src="https://github.com/user-attachments/assets/2dd66e7c-7cf3-4d3c-92ff-6de52114a9a4" />
  <img width="600" alt="image" src="https://github.com/user-attachments/assets/e9457d34-930c-42b2-8e91-b447d27355aa" />
</p>

## Quick Start

### Prerequisites

1. **Install Gemini CLI**:
   ```bash
   npm install -g @google/generative-ai-cli
   ```

2. **Configure Gemini CLI**:
   ```bash
   gemini config
   ```

### Installation

```bash
# Using uv (recommended)
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uv pip install -e .

# Or using pip
pip install -e .
```

### Run

```bash
python run_run_prompt_anywhere.py
```

Press `Ctrl+Alt+X` anywhere to open the prompt window.

## Features

- **Global hotkey**: `Ctrl+Alt+X` opens prompt window from anywhere
- **Screenshot support**: Capture screen regions and attach to prompts
- **Streaming responses**: Real-time Gemini CLI output
- **Follow-up questions**: Continue conversations in result window
- **System tray**: Runs in background, accessible via tray icon
- **No API costs**: Uses your existing Gemini subscription

## Usage

1. **Press `Ctrl+Alt+X`** → Prompt window appears at cursor
2. **Type question** → Optionally attach screenshot
3. **Press Enter** → Result window shows streaming response
4. **Ask follow-ups** → Continue conversation in result window

**Controls**:
- **ESC**: Close windows
- **Drag**: Move windows
- **Right-click/ESC**: Cancel screenshot selection

## Requirements

- Python 3.10+
- Windows (native, not WSL)
- Gemini CLI installed and configured
- PySide6, pynput, Pillow

## Architecture

Modular design with strict separation:
- `src/code/`: Pure Python logic (agents, features, core)
- `src/gui/`: Qt/PySide6 UI components

See [CLAUDE.md](CLAUDE.md) for detailed architecture and development guide.

## License

MIT
