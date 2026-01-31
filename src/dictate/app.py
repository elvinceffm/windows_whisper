"""
Main application orchestrator.

Wires together all components:
- Hotkey listener (trigger)
- Audio capture (recording)
- Cloud API (transcription + processing)
- Text injection (output)
- UI overlays (feedback)
"""

import threading
from typing import Optional
from dataclasses import dataclass
from enum import Enum, auto

from PySide6.QtCore import QObject, Signal, Slot, QThread
from PySide6.QtWidgets import QApplication

from .audio.capture import AudioRecorder
from .input.hotkeys import HotkeyManager, TriggerKey
from .input.caret import get_overlay_position, get_active_monitor_rect
from .input.text_inject import TextInjector
from .api.client import get_client, set_client
from .api.transcribe import transcribe_audio
from .api.process import (
    ProcessingMode, CustomMode, process_text, get_all_modes,
)
from .ui.overlay import RecordingPill
from .ui.mode_bar import ModeBar
from .ui.tray import SystemTray, SettingsDialog
from .config.settings import get_settings, save_settings

import numpy as np


class AppState(Enum):
    """Application state machine states."""
    
    IDLE = auto()
    RECORDING = auto()
    PROCESSING = auto()
    TENTATIVE = auto()  # Text injected, waiting for accept/cancel/cycle


@dataclass
class TranscriptionResult:
    """Result of a transcription + optional processing."""
    
    original_text: str
    processed_text: str
    mode: ProcessingMode | CustomMode
    target_language: str = "English"


class TranscriptionWorker(QObject):
    """Worker for async transcription and processing."""
    
    finished = Signal(object)  # TranscriptionResult
    error = Signal(str)
    
    def __init__(self):
        super().__init__()
        self._audio_data: Optional[np.ndarray] = None
        self._mode: ProcessingMode | CustomMode = ProcessingMode.NORMAL
        self._target_language: str = "English"
    
    def set_data(
        self,
        audio_data: np.ndarray,
        mode: ProcessingMode | CustomMode = ProcessingMode.NORMAL,
        target_language: str = "English",
    ) -> None:
        """Set data for transcription."""
        self._audio_data = audio_data
        self._mode = mode
        self._target_language = target_language
    
    @Slot()
    def run(self) -> None:
        """Run transcription and processing."""
        try:
            if self._audio_data is None or len(self._audio_data) == 0:
                self.error.emit("No audio recorded")
                return
            
            # Transcribe
            original_text = transcribe_audio(self._audio_data)
            
            if not original_text:
                self.error.emit("No speech detected")
                return
            
            # Process if not Normal mode
            if self._mode == ProcessingMode.NORMAL:
                processed_text = original_text
            else:
                processed_text = process_text(
                    original_text,
                    self._mode,
                    self._target_language,
                )
            
            result = TranscriptionResult(
                original_text=original_text,
                processed_text=processed_text,
                mode=self._mode,
                target_language=self._target_language,
            )
            
            self.finished.emit(result)
            
        except Exception as e:
            self.error.emit(str(e))


class ReprocessWorker(QObject):
    """Worker for reprocessing text with a different mode."""
    
    finished = Signal(str)  # Processed text
    error = Signal(str)
    
    def __init__(self):
        super().__init__()
        self._text: str = ""
        self._mode: ProcessingMode | CustomMode = ProcessingMode.NORMAL
        self._target_language: str = "English"
    
    def set_data(
        self,
        text: str,
        mode: ProcessingMode | CustomMode,
        target_language: str = "English",
    ) -> None:
        """Set data for reprocessing."""
        self._text = text
        self._mode = mode
        self._target_language = target_language
    
    @Slot()
    def run(self) -> None:
        """Run processing."""
        try:
            if self._mode == ProcessingMode.NORMAL:
                self.finished.emit(self._text)
            else:
                processed = process_text(
                    self._text,
                    self._mode,
                    self._target_language,
                )
                self.finished.emit(processed)
        except Exception as e:
            self.error.emit(str(e))


class DictateApp(QObject):
    """
    Main application controller.
    
    Manages the complete flow:
    1. Hotkey press → start recording, show pill
    2. Hotkey release → stop recording, transcribe
    3. Show mode bar, inject tentative text
    4. Handle Tab (cycle mode), Enter (accept), Esc (cancel)
    """
    
    def __init__(self):
        super().__init__()
        
        # State
        self._state = AppState.IDLE
        self._is_enabled = True
        self._current_result: Optional[TranscriptionResult] = None
        
        # Load settings
        self._settings = get_settings()
        self._init_api_client()
        
        # Components
        self._audio_recorder = AudioRecorder(
            on_amplitude=self._on_amplitude,
            on_duration=self._on_duration,
        )
        
        self._hotkey_manager = HotkeyManager(
            trigger_key=TriggerKey.from_string(self._settings.trigger_key),
            on_start=self._on_hotkey_pressed,
            on_stop=self._on_hotkey_released,
        )
        
        self._text_injector = TextInjector()
        
        # UI components (created later in start())
        self._pill: Optional[RecordingPill] = None
        self._mode_bar: Optional[ModeBar] = None
        self._tray: Optional[SystemTray] = None
        
        # Worker threads
        self._transcription_thread: Optional[QThread] = None
        self._transcription_worker: Optional[TranscriptionWorker] = None
        self._reprocess_thread: Optional[QThread] = None
        self._reprocess_worker: Optional[ReprocessWorker] = None
        
        # Keyboard listener for tentative state
        self._tentative_listener = None
    
    def _init_api_client(self) -> None:
        """Initialize the API client from settings."""
        api_key = self._settings.get_api_key()
        if api_key:
            try:
                set_client(self._settings.provider, api_key)
            except Exception as e:
                print(f"Failed to initialize API client: {e}")
    
    def start(self) -> None:
        """Start the application."""
        # Create UI components
        self._pill = RecordingPill()
        self._mode_bar = ModeBar()
        self._tray = SystemTray()
        
        # Connect mode bar signals
        self._mode_bar.mode_changed.connect(self._on_mode_changed)
        self._mode_bar.language_changed.connect(self._on_language_changed)
        
        # Connect tray signals
        self._tray.show_settings.connect(self._show_settings)
        self._tray.quit_app.connect(self._quit)
        self._tray.toggle_enabled.connect(self._set_enabled)
        
        # Show tray icon
        self._tray.show()
        
        # Start hotkey listener
        self._hotkey_manager.start()
        
        print("Dictate for Windows started. Press trigger key to record.")
    
    def stop(self) -> None:
        """Stop the application."""
        self._hotkey_manager.stop()
        
        if self._pill:
            self._pill.close()
        if self._mode_bar:
            self._mode_bar.close()
        if self._tray:
            self._tray.hide()
    
    def _set_enabled(self, enabled: bool) -> None:
        """Enable or disable dictation."""
        self._is_enabled = enabled
    
    def _on_hotkey_pressed(self) -> None:
        """Handle push-to-talk trigger pressed."""
        if not self._is_enabled:
            return
        
        if self._state == AppState.TENTATIVE:
            # Cancel current tentative text
            self._cancel_tentative()
        
        if self._state != AppState.IDLE:
            return
        
        # Get caret position for pill placement
        x, y = get_overlay_position()
        
        # Start recording
        if self._audio_recorder.start():
            self._state = AppState.RECORDING
            
            # Show pill
            if self._pill:
                # Use QTimer to update UI from main thread
                from PySide6.QtCore import QMetaObject, Qt, Q_ARG
                QMetaObject.invokeMethod(
                    self._pill, "show_at",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(int, x), Q_ARG(int, y)
                )
            
            if self._tray:
                self._tray.set_recording(True)
    
    def _on_hotkey_released(self) -> None:
        """Handle push-to-talk trigger released."""
        if self._state != AppState.RECORDING:
            return
        
        # Stop recording
        audio_data = self._audio_recorder.stop()
        
        # Hide pill
        if self._pill:
            from PySide6.QtCore import QMetaObject, Qt
            QMetaObject.invokeMethod(
                self._pill, "hide_pill",
                Qt.ConnectionType.QueuedConnection
            )
        
        if self._tray:
            self._tray.set_recording(False)
        
        if audio_data is None or len(audio_data) < 1600:  # Less than 0.1s
            self._state = AppState.IDLE
            return
        
        # Start transcription
        self._state = AppState.PROCESSING
        if self._tray:
            self._tray.set_processing(True)
        
        self._start_transcription(audio_data)
    
    def _on_amplitude(self, amplitude: float) -> None:
        """Handle real-time amplitude updates."""
        if self._pill and self._state == AppState.RECORDING:
            from PySide6.QtCore import QMetaObject, Qt, Q_ARG
            QMetaObject.invokeMethod(
                self._pill, "set_amplitude",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(float, amplitude)
            )
    
    def _on_duration(self, duration: float) -> None:
        """Handle recording duration updates."""
        if self._pill and self._state == AppState.RECORDING:
            from PySide6.QtCore import QMetaObject, Qt, Q_ARG
            QMetaObject.invokeMethod(
                self._pill, "set_duration",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(float, duration)
            )
    
    def _start_transcription(self, audio_data: np.ndarray) -> None:
        """Start async transcription."""
        # Clean up previous thread
        if self._transcription_thread and self._transcription_thread.isRunning():
            self._transcription_thread.quit()
            self._transcription_thread.wait()
        
        # Create worker and thread
        self._transcription_thread = QThread()
        self._transcription_worker = TranscriptionWorker()
        self._transcription_worker.moveToThread(self._transcription_thread)
        
        # Set data
        self._transcription_worker.set_data(
            audio_data,
            ProcessingMode.NORMAL,  # Start with Normal mode
            self._settings.default_target_language,
        )
        
        # Connect signals
        self._transcription_thread.started.connect(self._transcription_worker.run)
        self._transcription_worker.finished.connect(self._on_transcription_complete)
        self._transcription_worker.error.connect(self._on_transcription_error)
        self._transcription_worker.finished.connect(self._transcription_thread.quit)
        self._transcription_worker.error.connect(self._transcription_thread.quit)
        
        # Start
        self._transcription_thread.start()
    
    def _on_transcription_complete(self, result: TranscriptionResult) -> None:
        """Handle transcription completion."""
        if self._tray:
            self._tray.set_processing(False)
        
        self._current_result = result
        
        # Inject text and select it
        self._text_injector.inject(result.processed_text, select=True)
        
        # Show mode bar
        modes = get_all_modes(self._settings.get_custom_modes())
        if self._mode_bar:
            self._mode_bar.set_modes(modes, initial_index=0)
            self._mode_bar.show_bar()
        
        # Enter tentative state
        self._state = AppState.TENTATIVE
        self._start_tentative_listener()
    
    def _on_transcription_error(self, error: str) -> None:
        """Handle transcription error."""
        if self._tray:
            self._tray.set_processing(False)
        
        print(f"Transcription error: {error}")
        self._state = AppState.IDLE
    
    def _start_tentative_listener(self) -> None:
        """Start listening for Tab/Enter/Esc in tentative state."""
        from pynput import keyboard
        
        def on_press(key):
            if self._state != AppState.TENTATIVE:
                return
            
            try:
                if key == keyboard.Key.enter:
                    self._accept_tentative()
                    return False  # Stop listener
                elif key == keyboard.Key.tab:
                    self._cycle_mode()
                    return False  # Will restart listener after reprocess
                elif key == keyboard.Key.esc:
                    self._cancel_tentative()
                    return False
            except Exception as e:
                print(f"Tentative listener error: {e}")
        
        self._tentative_listener = keyboard.Listener(on_press=on_press)
        self._tentative_listener.start()
    
    def _stop_tentative_listener(self) -> None:
        """Stop the tentative state keyboard listener."""
        if self._tentative_listener:
            self._tentative_listener.stop()
            self._tentative_listener = None
    
    def _accept_tentative(self) -> None:
        """Accept the tentative text."""
        self._stop_tentative_listener()
        self._text_injector.accept()
        
        if self._mode_bar:
            self._mode_bar.hide_bar()
        
        self._state = AppState.IDLE
        self._current_result = None
    
    def _cancel_tentative(self) -> None:
        """Cancel and delete the tentative text."""
        self._stop_tentative_listener()
        self._text_injector.cancel()
        
        if self._mode_bar:
            self._mode_bar.hide_bar()
        
        self._state = AppState.IDLE
        self._current_result = None
    
    def _cycle_mode(self) -> None:
        """Cycle to the next processing mode."""
        if not self._mode_bar or not self._current_result:
            return
        
        self._stop_tentative_listener()
        self._mode_bar.cycle_next()
        
        # Reprocess with new mode
        new_mode = self._mode_bar.current_mode
        if new_mode:
            self._reprocess_text(new_mode)
    
    def _on_mode_changed(self, mode: ProcessingMode | CustomMode) -> None:
        """Handle mode change from mode bar click."""
        if self._state != AppState.TENTATIVE or not self._current_result:
            return
        
        self._stop_tentative_listener()
        self._reprocess_text(mode)
    
    def _on_language_changed(self, language: str) -> None:
        """Handle translation language change."""
        if self._state != AppState.TENTATIVE or not self._current_result:
            return
        
        if self._mode_bar and self._mode_bar.current_mode == ProcessingMode.TRANSLATE:
            self._stop_tentative_listener()
            self._reprocess_text(ProcessingMode.TRANSLATE, language)
    
    def _reprocess_text(
        self,
        mode: ProcessingMode | CustomMode,
        target_language: Optional[str] = None,
    ) -> None:
        """Reprocess the original text with a new mode."""
        if not self._current_result:
            return
        
        if target_language is None:
            target_language = (
                self._mode_bar.target_language if self._mode_bar
                else self._settings.default_target_language
            )
        
        # Show processing indicator
        if self._mode_bar:
            self._mode_bar.show_processing(True)
        
        # Clean up previous thread
        if self._reprocess_thread and self._reprocess_thread.isRunning():
            self._reprocess_thread.quit()
            self._reprocess_thread.wait()
        
        # Create worker
        self._reprocess_thread = QThread()
        self._reprocess_worker = ReprocessWorker()
        self._reprocess_worker.moveToThread(self._reprocess_thread)
        
        self._reprocess_worker.set_data(
            self._current_result.original_text,
            mode,
            target_language,
        )
        
        # Connect signals
        self._reprocess_thread.started.connect(self._reprocess_worker.run)
        self._reprocess_worker.finished.connect(
            lambda text: self._on_reprocess_complete(text, mode, target_language)
        )
        self._reprocess_worker.error.connect(self._on_reprocess_error)
        self._reprocess_worker.finished.connect(self._reprocess_thread.quit)
        self._reprocess_worker.error.connect(self._reprocess_thread.quit)
        
        self._reprocess_thread.start()
    
    def _on_reprocess_complete(
        self,
        text: str,
        mode: ProcessingMode | CustomMode,
        target_language: str,
    ) -> None:
        """Handle reprocessing completion."""
        if self._mode_bar:
            self._mode_bar.show_processing(False)
        
        if not self._current_result:
            return
        
        # Update result
        self._current_result.processed_text = text
        self._current_result.mode = mode
        self._current_result.target_language = target_language
        
        # Replace the selected text
        self._text_injector.replace(text)
        
        # Restart tentative listener
        self._start_tentative_listener()
    
    def _on_reprocess_error(self, error: str) -> None:
        """Handle reprocessing error."""
        if self._mode_bar:
            self._mode_bar.show_processing(False)
        
        print(f"Reprocessing error: {error}")
        
        # Restart tentative listener without changing text
        self._start_tentative_listener()
    
    def _show_settings(self) -> None:
        """Show the settings dialog."""
        dialog = SettingsDialog()
        dialog.settings_saved.connect(self._on_settings_saved)
        dialog.exec()
    
    def _on_settings_saved(self) -> None:
        """Handle settings being saved."""
        # Reload settings
        self._settings = get_settings()
        
        # Update API client
        self._init_api_client()
        
        # Update hotkey
        self._hotkey_manager.set_trigger_key(
            TriggerKey.from_string(self._settings.trigger_key)
        )
    
    def _quit(self) -> None:
        """Quit the application."""
        self.stop()
        QApplication.quit()


def run_app() -> int:
    """Run the Dictate application."""
    import sys
    
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # Keep running with just tray
    
    # Set app metadata
    app.setApplicationName("Dictate for Windows")
    app.setOrganizationName("Dictate")
    
    # Create and start the main controller
    dictate = DictateApp()
    dictate.start()
    
    return app.exec()
