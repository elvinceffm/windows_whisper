"""Input handling: hotkeys, caret detection, text injection."""

from .hotkeys import HotkeyManager
from .caret import get_caret_position
from .text_inject import TextInjector

__all__ = ["HotkeyManager", "get_caret_position", "TextInjector"]
