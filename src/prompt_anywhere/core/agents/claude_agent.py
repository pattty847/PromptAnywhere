"""Placeholder for Claude agent implementation"""
from typing import Iterator, Optional
from prompt_anywhere.core.agents.base_agent import BaseAgent


class ClaudeAgent(BaseAgent):
    """Placeholder for Claude agent (future implementation)"""
    
    @property
    def name(self) -> str:
        """Agent name"""
        return "claude"
    
    def send_prompt(self, prompt: str, context: Optional[dict] = None) -> Iterator[str]:
        """Placeholder implementation"""
        yield "Claude agent not yet implemented"
