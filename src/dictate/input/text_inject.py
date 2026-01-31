"""
Text injection into the active application.

Simple clipboard-based paste - no text selection or tentative state.
Text is reviewed in the PreviewCard before injection.
"""

import time
import threading
from typing import Optional

import pyperclip
from pynput.keyboard import Key, KeyCode, Controller as KeyboardController


class TextInjector:
    """
    Injects text into the active application via clipboard paste.
    
    Simple, single-purpose class - pastes text at cursor position
    without selecting it afterwards.
    """
    
    def __init__(self):
        self._keyboard = KeyboardController()
        self._original_clipboard: Optional[str] = None
    
    def inject(self, text: str) -> bool:
        """
        Inject text into the active application at cursor position.
        
        Uses clipboard paste (Ctrl+V) for reliable cross-app support.
        
        Args:
            text: Text to inject
            
        Returns:
            True if injection was successful
        """
        if not text:
            return False
        
        try:
            # Save original clipboard
            try:
                self._original_clipboard = pyperclip.paste()
            except Exception:
                self._original_clipboard = None
            
            # Copy text to clipboard
            pyperclip.copy(text)
            
            # Longer delay for clipboard to update and app to receive focus
            time.sleep(0.15)
            
            # Paste via Ctrl+V
            v_key = KeyCode.from_char('v')
            self._keyboard.press(Key.ctrl)
            self._keyboard.tap(v_key)
            self._keyboard.release(Key.ctrl)
            
            # Wait for paste to complete before restoring clipboard
            time.sleep(0.2)
            
            return True
            
        except Exception as e:
            print(f"Text injection failed: {e}")
            return False
        
        finally:
            # Restore original clipboard after a longer delay in background
            # to ensure paste has fully completed
            if self._original_clipboard is not None:
                def restore_later():
                    time.sleep(0.5)
                    try:
                        pyperclip.copy(self._original_clipboard)
                    except Exception:
                        pass
                threading.Thread(target=restore_later, daemon=True).start()
                self._original_clipboard = None


def inject_text(text: str) -> bool:
    """
    Convenience function to inject text.
    
    Args:
        text: Text to inject
        
    Returns:
        True if successful
    """
    injector = TextInjector()
    return injector.inject(text)
