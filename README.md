# PromptAnywhere

Global hotkey AI assistant powered by local CLI subscriptions. Press `Ctrl+Alt+X` anywhere on Windows to open a prompt window and stream answers.

<p align="center">
  <img width="600" alt="image" src="https://github.com/user-attachments/assets/2dd66e7c-7cf3-4d3c-92ff-6de52114a9a4" />
  <img width="600" height="597" alt="image" src="https://github.com/user-attachments/assets/e5a60843-72ee-42f9-bf05-677407aad50b" />
</p>

## Quick Start

### Prerequisites

1. **Install Codex CLI**:
   ```bash
   npm install -g @openai/codex
   ```

2. **Login with Codex CLI**:
   ```bash
   codex login
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

Open two terminals:

Terminal 1 (gateway host):
```bash
prompt-anywhere-host
```

Terminal 2 (UI):
```bash
python -m prompt_anywhere
```

Then press `Ctrl+Alt+X` anywhere to open the prompt window.

If the host is not running, use tray actions:
- `Gateway Health Check`
- `Start Gateway Host`
- `Execution Mode` (`Safe`, `Tools-enabled`, `Unrestricted`)

## Features

- **Global hotkey**: `Ctrl+Alt+X` opens prompt window from anywhere
- **Screenshot support**: Capture screen regions and attach to prompts
- **Streaming responses**: Real-time CopeNet gateway output
- **Follow-up questions**: Continue conversations in result window
- **System tray**: Runs in background, accessible via tray icon
- **Subscription-backed**: Uses your existing CLI login/session

History source:
- `~/.prompt_anywhere/sessions/index.json`
- `~/.prompt_anywhere/sessions/<sessionId>.jsonl`

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
- Codex CLI installed and logged in
- PySide6, pynput, Pillow

## Architecture

Gateway-first design:
- `src/prompt_anywhere/host/`: CopeNet WebSocket gateway
- `src/prompt_anywhere/core/`: Orchestrator, provider adapters, session/transcript stores
- `src/prompt_anywhere/ui/`: PySide6 client that streams through gateway

## Gateway Settings

Optional environment variables:

- `PROMPT_ANYWHERE_USE_GATEWAY` (default `1`)
- `PROMPT_ANYWHERE_GATEWAY_URL` (default `ws://127.0.0.1:17123/ws`)
- `PROMPT_ANYWHERE_GATEWAY_TOKEN` (default `dev-token`)

See [CLAUDE.md](CLAUDE.md) for detailed architecture and development guide.

## License

MIT
