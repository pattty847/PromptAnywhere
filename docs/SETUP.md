# Windows Setup Instructions

## Prerequisites

1. **Install Python for Windows**
   - Download from https://www.python.org/downloads/
   - Make sure to check "Add Python to PATH" during installation
   - Verify: Open PowerShell and run `python --version`

2. **Install Gemini CLI**
   ```powershell
   npm install -g @google/generative-ai-cli
   # or with pnpm
   pnpm install -g @google/generative-ai-cli
   ```

3. **Configure Gemini CLI**
   ```powershell
   gemini config
   ```

## Installation

1. **Copy the project folder to Windows Desktop**
   - From WSL, you can access Windows at `/mnt/c/Users/YourUsername/Desktop/`
   - Or manually copy the `PromptAnywhere` folder to your Desktop

2. **Open PowerShell (NOT WSL)**
   - Press `Win + X` and select "Windows PowerShell" or "Terminal"
   - Navigate to the project:
     ```powershell
     cd $env:USERPROFILE\Desktop\PromptAnywhere
     ```

3. **Create Python virtual environment**
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   If you get an execution policy error, run:
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```

4. **Install dependencies**
   ```powershell
   pip install PySide6 pynput Pillow
   ```

## Running the App

From PowerShell (with venv activated):

```powershell
python prompt_anywhere.py
```

You should see:
```
✓ Gemini CLI found
✓ Hotkey registered: Ctrl+Alt+X

🚀 PromptAnywhere is running!
   Press Ctrl+Alt+X to open prompt window
   Press Ctrl+C to exit
```

## Usage

1. **Press `Ctrl+Alt+X`** anywhere on Windows
2. **Prompt window appears** with:
   - Text input field
   - "Screenshot" button (optional)
   - "Send" button
3. **Type your question** and optionally click Screenshot to attach an image
4. **Press Enter or click Send**
5. **Result window shows** with:
   - Streaming response from Gemini
   - Follow-up input field at the bottom
   - Screenshot button for follow-up questions

## Controls

**Prompt Window:**
- Type and press Enter: Submit
- ESC: Close
- Drag anywhere: Move window
- Screenshot button: Capture screen region

**Result Window:**
- ESC or Q: Close
- Drag anywhere: Move window
- Follow-up input: Continue conversation
- X button: Close window

## Troubleshooting

### Hotkey not working
- Make sure you're running from Windows PowerShell (not WSL)
- Check if another app is using Ctrl+Alt+X
- Try running as Administrator

### "Gemini CLI not found"
```powershell
# Check if gemini is in PATH
gemini --version

# If not found, reinstall
npm install -g @google/generative-ai-cli
```

### Window doesn't appear
- Check PowerShell output for errors
- Make sure Python is for Windows, not WSL
- Try running with admin privileges

### Import errors
```powershell
# Reinstall dependencies
pip uninstall PySide6 pynput Pillow
pip install PySide6 pynput Pillow
```

## Running on Startup (Optional)

Create a shortcut to run on Windows startup:

1. Create `run_prompt_anywhere.bat`:
   ```batch
   @echo off
   cd %USERPROFILE%\Desktop\PromptAnywhere
   call .venv\Scripts\activate.bat
   pythonw prompt_anywhere.py
   ```

2. Press `Win + R`, type `shell:startup`, press Enter
3. Copy the `.bat` file to the Startup folder

Note: Using `pythonw` instead of `python` runs it without a console window.
