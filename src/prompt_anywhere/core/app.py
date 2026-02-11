"""Main application coordinator (pure Python, no Qt)"""
import sys
import shutil
from typing import Optional
from prompt_anywhere.core.config import Config
from prompt_anywhere.core.hotkey_manager import HotkeyManager
from prompt_anywhere.core.agents.base_agent import BaseAgent
from prompt_anywhere.core.agents.gemini_agent import GeminiAgent


class App:
    """Main application coordinator (business logic only, no GUI)"""
    
    def __init__(self):
        """Initialize application"""
        self.config = Config()
        self.hotkey_manager: Optional[HotkeyManager] = None
        self.agent: Optional[BaseAgent] = None
        self._initialize_agent()
    
    def _initialize_agent(self):
        """Initialize the default agent"""
        agent_name = self.config.get("default_agent", "gemini")
        try:
            if agent_name == "gemini":
                self.agent = GeminiAgent()
                print("* Gemini CLI found")
            else:
                raise ValueError(f"Unknown agent: {agent_name}")
        except FileNotFoundError as e:
            print(f"ERROR: {e}")
            sys.exit(1)
    
    def register_hotkey(self, callback):
        """Register global hotkey with callback"""
        self.hotkey_manager = HotkeyManager(callback)
        self.hotkey_manager.register_ctrl_alt_x()
    
    def get_agent(self) -> BaseAgent:
        """Get the current agent"""
        return self.agent
    
    def check_gemini_available(self) -> bool:
        """Check if Gemini CLI is available"""
        return bool(shutil.which('gemini') or shutil.which('gemini.cmd'))
