"""
Text caret (cursor) position detection on Windows.

Uses Windows API via ctypes to find the position of the text cursor
in the active window, for positioning the recording pill overlay.
"""

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from typing import Optional, Tuple

# Windows API constants
GUI_CARETBLINKING = 0x00000001

# Load Windows DLLs
user32 = ctypes.windll.user32


class GUITHREADINFO(ctypes.Structure):
    """Windows GUITHREADINFO structure."""
    
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND),
        ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND),
        ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND),
        ("hwndCaret", wintypes.HWND),
        ("rcCaret", wintypes.RECT),
    ]


class POINT(ctypes.Structure):
    """Windows POINT structure."""
    
    _fields_ = [
        ("x", wintypes.LONG),
        ("y", wintypes.LONG),
    ]


@dataclass
class CaretPosition:
    """Position of the text caret on screen."""
    
    x: int
    y: int
    width: int
    height: int
    
    @property
    def center(self) -> Tuple[int, int]:
        """Get center point of caret rectangle."""
        return (self.x + self.width // 2, self.y + self.height // 2)
    
    @property
    def bottom_left(self) -> Tuple[int, int]:
        """Get bottom-left point (good for positioning overlay below caret)."""
        return (self.x, self.y + self.height)


def get_caret_position() -> Optional[CaretPosition]:
    """
    Get the screen position of the text caret in the active window.
    
    Returns:
        CaretPosition if found, None otherwise
    """
    # Get GUI thread info for the foreground window
    gui_info = GUITHREADINFO()
    gui_info.cbSize = ctypes.sizeof(GUITHREADINFO)
    
    # Get the foreground window's thread ID
    foreground_hwnd = user32.GetForegroundWindow()
    if not foreground_hwnd:
        return None
    
    thread_id = user32.GetWindowThreadProcessId(foreground_hwnd, None)
    if not thread_id:
        return None
    
    # Get GUI thread info
    if not user32.GetGUIThreadInfo(thread_id, ctypes.byref(gui_info)):
        return None
    
    # Check if there's a caret
    if not gui_info.hwndCaret:
        # Try getting caret from focused window
        if gui_info.hwndFocus:
            # Some applications use the focus window for caret
            pass
        else:
            return None
    
    # Get caret rectangle (in client coordinates)
    caret_rect = gui_info.rcCaret
    
    # Check if caret rect is valid
    if caret_rect.right <= caret_rect.left and caret_rect.bottom <= caret_rect.top:
        return None
    
    # Convert to screen coordinates
    caret_window = gui_info.hwndCaret or gui_info.hwndFocus or foreground_hwnd
    
    top_left = POINT(caret_rect.left, caret_rect.top)
    bottom_right = POINT(caret_rect.right, caret_rect.bottom)
    
    if not user32.ClientToScreen(caret_window, ctypes.byref(top_left)):
        return None
    if not user32.ClientToScreen(caret_window, ctypes.byref(bottom_right)):
        return None
    
    return CaretPosition(
        x=top_left.x,
        y=top_left.y,
        width=bottom_right.x - top_left.x,
        height=bottom_right.y - top_left.y,
    )


def get_foreground_window_rect() -> Optional[Tuple[int, int, int, int]]:
    """
    Get the rectangle of the foreground window.
    
    Returns:
        Tuple of (x, y, width, height) or None
    """
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    
    rect = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    
    return (
        rect.left,
        rect.top,
        rect.right - rect.left,
        rect.bottom - rect.top,
    )


def get_foreground_window_center() -> Optional[Tuple[int, int]]:
    """
    Get the center point of the foreground window.
    
    Used as fallback when caret position cannot be determined.
    
    Returns:
        Tuple of (x, y) or None
    """
    rect = get_foreground_window_rect()
    if not rect:
        return None
    
    x, y, width, height = rect
    return (x + width // 2, y + height // 2)


def get_cursor_position() -> Tuple[int, int]:
    """
    Get the current mouse cursor position.
    
    Returns:
        Tuple of (x, y)
    """
    point = POINT()
    user32.GetCursorPos(ctypes.byref(point))
    return (point.x, point.y)


def get_active_monitor_rect() -> Tuple[int, int, int, int]:
    """
    Get the rectangle of the monitor containing the foreground window.
    
    Returns:
        Tuple of (x, y, width, height)
    """
    hwnd = user32.GetForegroundWindow()
    if hwnd:
        # Get monitor from foreground window
        MONITOR_DEFAULTTONEAREST = 0x00000002
        hmonitor = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
        
        if hmonitor:
            from ctypes import wintypes
            
            class MONITORINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD),
                ]
            
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            
            if user32.GetMonitorInfoW(hmonitor, ctypes.byref(mi)):
                rect = mi.rcWork  # Work area (excludes taskbar)
                return (
                    rect.left,
                    rect.top,
                    rect.right - rect.left,
                    rect.bottom - rect.top,
                )
    
    # Fallback to primary monitor
    width = user32.GetSystemMetrics(0)  # SM_CXSCREEN
    height = user32.GetSystemMetrics(1)  # SM_CYSCREEN
    return (0, 0, width, height)


def get_overlay_position(
    offset_x: int = 10,
    offset_y: int = 5,
) -> Tuple[int, int]:
    """
    Get the best position for the recording overlay.
    
    Tries to position near the text caret, falls back to window center
    or screen center.
    
    Args:
        offset_x: Horizontal offset from caret
        offset_y: Vertical offset from caret (below)
        
    Returns:
        Tuple of (x, y) screen coordinates
    """
    # Try to get caret position
    caret = get_caret_position()
    if caret:
        # Position to the right and slightly below the caret
        return (caret.x + caret.width + offset_x, caret.y + offset_y)
    
    # Fallback to foreground window center
    center = get_foreground_window_center()
    if center:
        return center
    
    # Ultimate fallback: screen center
    monitor = get_active_monitor_rect()
    return (
        monitor[0] + monitor[2] // 2,
        monitor[1] + monitor[3] // 2,
    )
