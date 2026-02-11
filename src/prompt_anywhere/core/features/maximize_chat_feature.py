"""Maximize chat window feature"""
from typing import Optional
from prompt_anywhere.core.features.base_feature import BaseFeature


class MaximizeChatFeature(BaseFeature):
    """Maximize the chat/response window"""

    @property
    def name(self) -> str:
        """Feature name"""
        return "Maximize Chat"

    @property
    def icon(self) -> str:
        """Feature icon"""
        return "maximize"

    @property
    def hotkey(self) -> Optional[str]:
        """Optional hotkey"""
        return "Ctrl+Alt+E"

    def execute(self, prompt: str = "") -> str:
        """
        Signal to maximize the chat window

        Args:
            prompt: Unused

        Returns:
            str: Status message
        """
        # This will be handled by the GUI layer via signals
        return "maximize_window"
