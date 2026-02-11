"""Customize shortcuts and settings feature"""
from typing import Optional
from prompt_anywhere.core.features.base_feature import BaseFeature


class CustomizeFeature(BaseFeature):
    """Open customization/settings interface"""

    @property
    def name(self) -> str:
        """Feature name"""
        return "Customize"

    @property
    def icon(self) -> str:
        """Feature icon"""
        return "settings"

    @property
    def hotkey(self) -> Optional[str]:
        """Optional hotkey"""
        return None  # Opens from UI button

    def execute(self, prompt: str = "") -> str:
        """
        Signal to open customization dialog

        Args:
            prompt: Unused

        Returns:
            str: Status message
        """
        # This will be handled by the GUI layer via signals
        return "open_customize"
