"""Terminal launcher feature"""
import subprocess
import os
from typing import Optional
from prompt_anywhere.core.features.base_feature import BaseFeature


class TerminalFeature(BaseFeature):
    """Open a new terminal window"""

    @property
    def name(self) -> str:
        """Feature name"""
        return "New Terminal"

    @property
    def icon(self) -> str:
        """Feature icon"""
        return "terminal"

    @property
    def hotkey(self) -> Optional[str]:
        """Optional hotkey"""
        return "Ctrl+J"

    def execute(self, prompt: str = "") -> str:
        """
        Open a new terminal window

        Args:
            prompt: Optional directory path to open terminal in

        Returns:
            str: Status message
        """
        try:
            # Use Windows Terminal if available, otherwise cmd
            if os.path.exists(os.path.expandvars("%LOCALAPPDATA%\\Microsoft\\WindowsApps\\wt.exe")):
                subprocess.Popen(["wt.exe"], shell=True)
                return "Opened Windows Terminal"
            else:
                subprocess.Popen(["cmd.exe"], creationflags=subprocess.CREATE_NEW_CONSOLE)
                return "Opened Command Prompt"
        except Exception as e:
            return f"Failed to open terminal: {str(e)}"
