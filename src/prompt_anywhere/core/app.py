"""Main application coordinator (pure Python, no Qt)"""
import shutil
from typing import Optional
from prompt_anywhere.core.config import Config
from prompt_anywhere.core.hotkey_manager import HotkeyManager
from prompt_anywhere.core.agents.base_agent import BaseAgent
from prompt_anywhere.core.agents.gemini_agent import GeminiAgent
from prompt_anywhere.core.agents.claude_agent import ClaudeAgent
from prompt_anywhere.core.agents.codex_agent import CodexAgent


class App:
    """Main application coordinator (business logic only, no GUI)"""
    
    def __init__(self):
        """Initialize application"""
        self.config = Config()
        self.hotkey_manager: Optional[HotkeyManager] = None
        self.agent: Optional[BaseAgent] = None
        self.agent_error: Optional[str] = None
        self._initialize_agent()
    
    def _initialize_agent(self):
        """Initialize the default agent"""
        agent_name = self.config.get("default_agent", "codex")
        try:
            self.agent = self._create_agent(agent_name)
            self.agent_error = None
            print(f"* {self.agent.name.capitalize()} CLI found")
        except FileNotFoundError as e:
            self.agent = None
            self.agent_error = str(e)
            print(f"ERROR: {e}")
        except ValueError as e:
            self.agent = None
            self.agent_error = str(e)
            print(f"ERROR: {e}")

    def _create_agent(self, agent_name: str) -> BaseAgent:
        """Instantiate an agent by configured name."""
        if agent_name == "gemini":
            return GeminiAgent()
        if agent_name == "claude":
            return ClaudeAgent()
        if agent_name == "codex":
            return CodexAgent()
        raise ValueError(f"Unknown agent: {agent_name}")
    
    def register_hotkey(self, callback):
        """Register global hotkey with callback"""
        self.hotkey_manager = HotkeyManager(callback)
        self.hotkey_manager.register_ctrl_alt_x()
    
    def get_agent(self) -> BaseAgent:
        """Get the current agent"""
        if self.agent is None:
            raise RuntimeError(self.agent_error or "No agent is currently available.")
        return self.agent
    
    def check_gemini_available(self) -> bool:
        """Check if Gemini CLI is available"""
        return bool(shutil.which('gemini') or shutil.which('gemini.cmd'))
