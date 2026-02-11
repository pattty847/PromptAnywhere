"""Screenshot capture feature"""
from typing import Optional
from prompt_anywhere.core.features.base_feature import BaseFeature


class ScreenshotFeature(BaseFeature):
    """Screenshot capture feature"""
    
    @property
    def name(self) -> str:
        """Feature name"""
        return "screenshot"
    
    @property
    def icon(self) -> str:
        """Feature icon"""
        return "screenshot"
    
    @property
    def hotkey(self) -> Optional[str]:
        """Optional hotkey"""
        return None  # Screenshot is triggered from UI
    
    def execute(self, prompt: str) -> str:
        """
        Execute screenshot capture
        
        Note: This feature is primarily handled by the GUI overlay.
        This method is a placeholder for future programmatic access.
        
        Args:
            prompt: Not used for screenshot
            
        Returns:
            str: Empty string (screenshot handled by GUI)
        """
        return ""
