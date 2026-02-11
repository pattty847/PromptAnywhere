"""Placeholder for Browser feature"""
from typing import Optional
from prompt_anywhere.core.features.base_feature import BaseFeature


class BrowserFeature(BaseFeature):
    """Placeholder for Browser feature (future implementation)"""
    
    @property
    def name(self) -> str:
        """Feature name"""
        return "browser"
    
    @property
    def icon(self) -> str:
        """Feature icon"""
        return "browser"
    
    @property
    def hotkey(self) -> Optional[str]:
        """Optional hotkey"""
        return "Ctrl+Shift+B"

    def execute(self, prompt: str) -> str:
        """
        Open default browser

        Args:
            prompt: Optional URL to open

        Returns:
            str: Status message
        """
        import webbrowser

        url = prompt if prompt else "https://www.google.com"

        # Add protocol if missing
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        webbrowser.open(url)
        return f"Opened browser: {url}"
