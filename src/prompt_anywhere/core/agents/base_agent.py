"""Abstract base class for AI agents"""
from abc import ABC, abstractmethod
from typing import Iterator, Optional


class BaseAgent(ABC):
    """Abstract base class for all AI agents"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Agent name"""
        pass
    
    @abstractmethod
    def send_prompt(self, prompt: str, context: Optional[dict] = None) -> Iterator[str]:
        """
        Send a prompt to the agent and stream the response
        
        Args:
            prompt: The user's prompt/question
            context: Optional context (e.g., image bytes, previous messages)
            
        Yields:
            str: Chunks of the response as they arrive
        """
        pass
