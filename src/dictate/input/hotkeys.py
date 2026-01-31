"""
Global hotkey management using pynput.

Provides push-to-talk functionality that works regardless of window focus.
"""

import threading
from typing import Callable, Optional, Set
from enum import Enum

from pynput import keyboard
from pynput.keyboard import Key, KeyCode


class TriggerKey(Enum):
    """Available trigger keys for push-to-talk."""
    
    CAPS_LOCK = "caps_lock"
    RIGHT_ALT = "right_alt"
    F1 = "f1"
    
    @classmethod
    def from_string(cls, s: str) -> "TriggerKey":
        """Parse trigger key from string."""
        mapping = {
            "caps_lock": cls.CAPS_LOCK,
            "capslock": cls.CAPS_LOCK,
            "right_alt": cls.RIGHT_ALT,
            "rightalt": cls.RIGHT_ALT,
            "alt_r": cls.RIGHT_ALT,
            "f1": cls.F1,
        }
        return mapping.get(s.lower().replace(" ", "_"), cls.CAPS_LOCK)


# Mapping from TriggerKey to pynput key
TRIGGER_KEY_MAP = {
    TriggerKey.CAPS_LOCK: Key.caps_lock,
    TriggerKey.RIGHT_ALT: Key.alt_r,
    TriggerKey.F1: Key.f1,
}


class HotkeyManager:
    """
    Manages global hotkeys for push-to-talk functionality.
    
    Recording is independent of window focus - once the trigger key
    is pressed, recording continues until the key is released.
    """
    
    def __init__(
        self,
        trigger_key: TriggerKey = TriggerKey.CAPS_LOCK,
        on_start: Optional[Callable[[], None]] = None,
        on_stop: Optional[Callable[[], None]] = None,
    ):
        """
        Initialize the hotkey manager.
        
        Args:
            trigger_key: The key to use for push-to-talk
            on_start: Callback when push-to-talk starts (key pressed)
            on_stop: Callback when push-to-talk stops (key released)
        """
        self.trigger_key = trigger_key
        self.on_start = on_start
        self.on_stop = on_stop
        
        self._listener: Optional[keyboard.Listener] = None
        self._pressed_keys: Set[Key | KeyCode] = set()
        self._is_triggered = False
        self._lock = threading.Lock()
        self._running = False
    
    @property
    def is_triggered(self) -> bool:
        """Check if the trigger key is currently held."""
        with self._lock:
            return self._is_triggered
    
    @property
    def is_running(self) -> bool:
        """Check if the hotkey listener is active."""
        with self._lock:
            return self._running
    
    def start(self) -> None:
        """Start listening for hotkeys."""
        with self._lock:
            if self._running:
                return
            self._running = True
        
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
            suppress=False,  # Don't suppress keys - let them pass through
        )
        self._listener.start()
    
    def stop(self) -> None:
        """Stop listening for hotkeys."""
        with self._lock:
            if not self._running:
                return
            self._running = False
        
        if self._listener:
            self._listener.stop()
            self._listener = None
    
    def set_trigger_key(self, key: TriggerKey) -> None:
        """
        Change the trigger key.
        
        Args:
            key: New trigger key
        """
        with self._lock:
            self.trigger_key = key
            self._is_triggered = False
    
    def _get_pynput_key(self) -> Key:
        """Get the pynput Key for the current trigger."""
        return TRIGGER_KEY_MAP.get(self.trigger_key, Key.caps_lock)
    
    def _is_trigger_key(self, key: Key | KeyCode) -> bool:
        """Check if a key matches the trigger key."""
        target = self._get_pynput_key()
        
        # Direct match
        if key == target:
            return True
        
        # Handle special cases
        if self.trigger_key == TriggerKey.CAPS_LOCK:
            return key == Key.caps_lock
        elif self.trigger_key == TriggerKey.RIGHT_ALT:
            # pynput may report alt_r or alt_gr depending on keyboard
            return key in (Key.alt_r, Key.alt_gr)
        elif self.trigger_key == TriggerKey.F1:
            return key == Key.f1
        
        return False
    
    def _on_press(self, key: Key | KeyCode) -> None:
        """Handle key press events."""
        if not self._is_trigger_key(key):
            return
        
        with self._lock:
            if self._is_triggered:
                # Already triggered, ignore repeat
                return
            self._is_triggered = True
        
        # Fire callback outside lock
        if self.on_start:
            try:
                self.on_start()
            except Exception as e:
                print(f"Error in on_start callback: {e}")
    
    def _on_release(self, key: Key | KeyCode) -> None:
        """Handle key release events."""
        if not self._is_trigger_key(key):
            return
        
        with self._lock:
            if not self._is_triggered:
                return
            self._is_triggered = False
        
        # Fire callback outside lock
        if self.on_stop:
            try:
                self.on_stop()
            except Exception as e:
                print(f"Error in on_stop callback: {e}")


class KeyboardController:
    """
    Wrapper around pynput keyboard controller for sending key events.
    
    Used for text injection and simulating keyboard shortcuts.
    """
    
    def __init__(self):
        self._controller = keyboard.Controller()
    
    def type_text(self, text: str, delay: float = 0.0) -> None:
        """
        Type text by simulating key presses.
        
        Args:
            text: Text to type
            delay: Delay between characters in seconds
        """
        if delay > 0:
            import time
            for char in text:
                self._controller.type(char)
                time.sleep(delay)
        else:
            self._controller.type(text)
    
    def press_key(self, key: Key | KeyCode) -> None:
        """Press a key."""
        self._controller.press(key)
    
    def release_key(self, key: Key | KeyCode) -> None:
        """Release a key."""
        self._controller.release(key)
    
    def tap_key(self, key: Key | KeyCode) -> None:
        """Press and release a key."""
        self._controller.press(key)
        self._controller.release(key)
    
    def hotkey(self, *keys: Key | KeyCode) -> None:
        """
        Press a key combination (e.g., Ctrl+V).
        
        Args:
            keys: Keys to press in order (first ones are held)
        """
        # Press all keys
        for key in keys:
            self._controller.press(key)
        
        # Release in reverse order
        for key in reversed(keys):
            self._controller.release(key)
    
    def ctrl_v(self) -> None:
        """Send Ctrl+V (paste)."""
        self.hotkey(Key.ctrl, KeyCode.from_char("v"))
    
    def shift_left(self, count: int = 1) -> None:
        """Send Shift+Left arrow to select text backwards."""
        self._controller.press(Key.shift)
        for _ in range(count):
            self._controller.tap(Key.left)
        self._controller.release(Key.shift)
    
    def right_arrow(self) -> None:
        """Send Right arrow to deselect and move cursor."""
        self.tap_key(Key.right)
    
    def delete(self) -> None:
        """Send Delete key."""
        self.tap_key(Key.delete)
    
    def escape(self) -> None:
        """Send Escape key."""
        self.tap_key(Key.esc)
