"""Platform-specific utilities"""
import sys
import ctypes


def apply_blur_effect(hwnd: int) -> bool:
    """
    Apply Windows blur effect (acrylic/mica style) to a window
    
    Args:
        hwnd: Window handle (integer)
        
    Returns:
        bool: True if blur was applied successfully
    """
    if sys.platform != 'win32':
        return False
    
    try:
        # DWM_BLURBEHIND structure
        DWM_BB_ENABLE = 0x1
        DWM_BB_BLURREGION = 0x2

        class DWM_BLURBEHIND(ctypes.Structure):
            _fields_ = [
                ("dwFlags", ctypes.c_int),
                ("fEnable", ctypes.c_int),
                ("hRgnBlur", ctypes.c_int),
                ("fTransitionOnMaximized", ctypes.c_int)
            ]

        bb = DWM_BLURBEHIND()
        bb.dwFlags = DWM_BB_ENABLE
        bb.fEnable = 1
        bb.hRgnBlur = 0
        bb.fTransitionOnMaximized = 0

        ctypes.windll.dwmapi.DwmEnableBlurBehindWindow(hwnd, ctypes.byref(bb))
        return True
    except Exception as e:
        print(f"Could not apply blur effect: {e}")
        return False
