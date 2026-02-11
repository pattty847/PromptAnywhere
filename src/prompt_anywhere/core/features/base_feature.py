"""Abstract base class for features"""
from abc import ABC, abstractmethod
from typing import Optional


class BaseFeature(ABC):
    """Abstract base class for all features"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Feature name"""
        pass
    
    @property
    @abstractmethod
    def icon(self) -> str:
        """Feature icon (emoji or icon identifier)"""
        pass
    
    @property
    @abstractmethod
    def hotkey(self) -> Optional[str]:
        """Optional hotkey combination (e.g., 'Ctrl+Shift+S')"""
        pass
    
    @abstractmethod
    def execute(self, prompt: str) -> str:
        """
        Execute the feature
        
        Args:
            prompt: Optional prompt/context for the feature
            
        Returns:
            str: Result or data from the feature execution
        """
        pass
