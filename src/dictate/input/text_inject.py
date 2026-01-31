"""
Text injection into the active application.

Implements clipboard-based paste with text selection for "tentative" state,
allowing easy replacement when cycling through modes.
"""

import time
from dataclasses import dataclass
from typing import Optional

import pyperclip
from pynput.keyboard import Key, Controller as KeyboardController


@dataclass 
class InjectionState:
    """State of injected tentative text."""
    
    text: str
    char_count: int
    is_tentative: bool = True
    
    
class TextInjector:
    """
    Injects text into the active application with tentative state support.
    
    Text is injected via clipboard paste and immediately selected,
    allowing easy replacement when cycling modes or cancellation.
    """
    
    def __init__(self):
        self._keyboard = KeyboardController()
        self._state: Optional[InjectionState] = None
        self._original_clipboard: Optional[str] = None
    
    @property
    def has_tentative_text(self) -> bool:
        """Check if there's tentative (uncommitted) text."""
        return self._state is not None and self._state.is_tentative
    
    @property
    def tentative_text(self) -> Optional[str]:
        """Get the current tentative text."""
        return self._state.text if self._state else None
    
    def inject(self, text: str, select: bool = True) -> bool:
        """
        Inject text into the active application.
        
        Args:
            text: Text to inject
            select: If True, select the text after injection (tentative state)
            
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
            
            # Small delay for clipboard to update
            time.sleep(0.05)
            
            # Paste via Ctrl+V
            self._keyboard.press(Key.ctrl)
            self._keyboard.tap(Key.from_vk(0x56))  # 'v' key
            self._keyboard.release(Key.ctrl)
            
            # Wait for paste to complete
            time.sleep(0.05)
            
            if select:
                # Select the pasted text by pressing Shift+Left for each character
                self._select_backwards(len(text))
                
                self._state = InjectionState(
                    text=text,
                    char_count=len(text),
                    is_tentative=True,
                )
            else:
                self._state = None
            
            return True
            
        except Exception as e:
            print(f"Text injection failed: {e}")
            return False
        
        finally:
            # Restore original clipboard after a delay
            if self._original_clipboard is not None:
                try:
                    time.sleep(0.1)
                    pyperclip.copy(self._original_clipboard)
                except Exception:
                    pass
    
    def replace(self, new_text: str) -> bool:
        """
        Replace the current tentative text with new text.
        
        Args:
            new_text: New text to inject
            
        Returns:
            True if replacement was successful
        """
        if not self._state or not self._state.is_tentative:
            # No tentative text, just inject normally
            return self.inject(new_text, select=True)
        
        try:
            # The text should already be selected, so just type/paste to replace
            # Save clipboard
            try:
                self._original_clipboard = pyperclip.paste()
            except Exception:
                self._original_clipboard = None
            
            pyperclip.copy(new_text)
            time.sleep(0.05)
            
            # Paste replaces selection
            self._keyboard.press(Key.ctrl)
            self._keyboard.tap(Key.from_vk(0x56))  # 'v' key  
            self._keyboard.release(Key.ctrl)
            
            time.sleep(0.05)
            
            # Re-select the new text
            self._select_backwards(len(new_text))
            
            self._state = InjectionState(
                text=new_text,
                char_count=len(new_text),
                is_tentative=True,
            )
            
            return True
            
        except Exception as e:
            print(f"Text replacement failed: {e}")
            return False
        
        finally:
            if self._original_clipboard is not None:
                try:
                    time.sleep(0.1)
                    pyperclip.copy(self._original_clipboard)
                except Exception:
                    pass
    
    def accept(self) -> bool:
        """
        Accept the tentative text (deselect and commit).
        
        Returns:
            True if there was tentative text to accept
        """
        if not self._state or not self._state.is_tentative:
            return False
        
        try:
            # Press Right arrow to deselect and move cursor to end
            self._keyboard.tap(Key.right)
            
            self._state.is_tentative = False
            self._state = None
            
            return True
            
        except Exception as e:
            print(f"Accept failed: {e}")
            return False
    
    def cancel(self) -> bool:
        """
        Cancel the tentative text (delete selection).
        
        Returns:
            True if there was tentative text to cancel
        """
        if not self._state or not self._state.is_tentative:
            return False
        
        try:
            # Press Delete to remove selected text
            self._keyboard.tap(Key.delete)
            
            self._state = None
            
            return True
            
        except Exception as e:
            print(f"Cancel failed: {e}")
            return False
    
    def clear_state(self) -> None:
        """Clear the injection state without affecting the text."""
        self._state = None
    
    def _select_backwards(self, char_count: int) -> None:
        """
        Select text backwards from cursor position.
        
        Args:
            char_count: Number of characters to select
        """
        # Use Shift+Left arrow to select backwards
        self._keyboard.press(Key.shift)
        
        for _ in range(char_count):
            self._keyboard.tap(Key.left)
            # Small delay to ensure selection registers
            time.sleep(0.002)
        
        self._keyboard.release(Key.shift)
    
    def _type_directly(self, text: str) -> None:
        """
        Type text directly using keyboard simulation.
        
        Fallback method for apps that don't support paste.
        
        Args:
            text: Text to type
        """
        for char in text:
            self._keyboard.type(char)
            time.sleep(0.01)


def inject_text(text: str, select: bool = True) -> bool:
    """
    Convenience function to inject text.
    
    Args:
        text: Text to inject
        select: Whether to select after injection
        
    Returns:
        True if successful
    """
    injector = TextInjector()
    return injector.inject(text, select=select)
