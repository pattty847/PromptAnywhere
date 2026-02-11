"""Global hotkey registration and management"""
import threading
from typing import Callable, Optional
from pynput import keyboard
from pynput.keyboard import Key, KeyCode


class HotkeyManager:
    """Manages global hotkey registration"""
    
    def __init__(self, callback: Callable[[], None]):
        """
        Initialize hotkey manager
        
        Args:
            callback: Function to call when hotkey is pressed (must be thread-safe)
        """
        self.callback = callback
        self.listener = None
        self.listener_thread = None
        self.current_keys = set()
        self._running = False
    
    def register_ctrl_alt_x(self):
        """Register Ctrl+Alt+X hotkey"""
        def on_press(key):
            """Track pressed keys and check for hotkey combination"""
            # Normalize keys
            if key in (Key.ctrl_l, Key.ctrl_r):
                self.current_keys.add('ctrl')
            elif key in (Key.alt_l, Key.alt_r, Key.alt_gr):
                self.current_keys.add('alt')
            elif hasattr(key, 'char') and key.char == 'x':
                self.current_keys.add('x')
            elif hasattr(key, 'vk') and key.vk == 88:  # X key code
                self.current_keys.add('x')
            
            # Check if hotkey combination is pressed
            if 'ctrl' in self.current_keys and 'alt' in self.current_keys and 'x' in self.current_keys:
                self.callback()
        
        def on_release(key):
            """Remove released keys from tracking"""
            if key in (Key.ctrl_l, Key.ctrl_r):
                self.current_keys.discard('ctrl')
            elif key in (Key.alt_l, Key.alt_r, Key.alt_gr):
                self.current_keys.discard('alt')
            elif hasattr(key, 'char') and key.char == 'x':
                self.current_keys.discard('x')
            elif hasattr(key, 'vk') and key.vk == 88:
                self.current_keys.discard('x')
        
        def listen():
            """Start listener in background thread"""
            try:
                with keyboard.Listener(
                    on_press=on_press,
                    on_release=on_release
                ) as listener:
                    self.listener = listener
                    self._running = True
                    listener.join()
            except Exception as e:
                print(f"ERROR: Listener error: {e}")
                self._running = False

        self.listener_thread = threading.Thread(target=listen, daemon=True)
        self.listener_thread.start()
        print("* Hotkey registered: Ctrl+Alt+X")
    
    def stop(self):
        """Stop the hotkey listener"""
        self._running = False
        if self.listener:
            self.listener.stop()
