"""Placeholder for Codex agent implementation"""
from typing import Iterator, Optional
from prompt_anywhere.core.agents.base_agent import BaseAgent


class CodexAgent(BaseAgent):
    """Placeholder for Codex agent (future implementation)"""
    
    @property
    def name(self) -> str:
        """Agent name"""
        return "codex"
    
    def send_prompt(self, prompt: str, context: Optional[dict] = None) -> Iterator[str]:
        """Placeholder implementation"""
        yield "Codex agent not yet implemented"
