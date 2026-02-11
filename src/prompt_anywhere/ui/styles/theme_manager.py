"""Theme management (placeholder for future theme system)"""


class ThemeManager:
    """Manages application themes"""
    
    def __init__(self):
        """Initialize theme manager"""
        self.current_theme = "default"
    
    def get_theme(self):
        """Get current theme"""
        return self.current_theme
    
    def set_theme(self, theme_name: str):
        """Set theme"""
        self.current_theme = theme_name
