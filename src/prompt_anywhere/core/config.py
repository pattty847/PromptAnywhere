"""Configuration and settings storage"""
import json
import os
from pathlib import Path
from typing import Any, Dict


class Config:
    """Application configuration manager"""
    
    def __init__(self, config_file: str = "prompt_anywhere_config.json"):
        """
        Initialize configuration
        
        Args:
            config_file: Name of the config file (stored in user's home directory)
        """
        self.config_dir = Path.home() / ".prompt_anywhere"
        self.config_dir.mkdir(exist_ok=True)
        self.config_file = self.config_dir / config_file
        self._config: Dict[str, Any] = {}
        self.load()
    
    def load(self):
        """Load configuration from file"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    self._config = json.load(f)
            except Exception as e:
                print(f"Error loading config: {e}")
                self._config = {}
        else:
            self._config = self._default_config()
            self.save()
    
    def save(self):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self._config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def _default_config(self) -> Dict[str, Any]:
        """Return default configuration"""
        return {
            "hotkey": "Ctrl+Alt+X",
            "default_agent": "codex",
            "theme": "default"
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value"""
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any):
        """Set a configuration value"""
        self._config[key] = value
        self.save()
    
    def __getitem__(self, key: str) -> Any:
        """Allow dict-like access"""
        return self._config.get(key)
    
    def __setitem__(self, key: str, value: Any):
        """Allow dict-like assignment"""
        self.set(key, value)
