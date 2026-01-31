"""
Main application orchestrator.

Wires together all components:
- Hotkey listener (trigger)
- Audio capture (recording)
- Cloud API (transcription + processing)
- Preview card (review before injection)
- Text injection (output)
- UI overlays (feedback)
"""

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
from .ui.preview_card import PreviewCard
from .ui.tray import SystemTray, SettingsDialog
from .config.settings import get_settings, save_settings

import numpy as np


class AppState(Enum):
    """Application state machine states."""
    
    IDLE = auto()
    RECORDING = auto()
    PROCESSING = auto()
    PREVIEW = auto()  # Preview card shown, waiting for insert/cancel


@dataclass
class TranscriptionResult:
    """Result of a transcription + optional processing."""
    
    original_text: str
    processed_text: str
    mode: ProcessingMode | CustomMode
    target_language: str = "English"


class TranscriptionWorker(QObject):
    """Worker for async transcription."""
    
    finished = Signal(str)  # Transcribed text
    error = Signal(str)
    
    def __init__(self):
        super().__init__()
        self._audio_data: Optional[np.ndarray] = None
    
    def set_data(self, audio_data: np.ndarray) -> None:
        """Set audio data for transcription."""
        self._audio_data = audio_data
    
    @Slot()
    def run(self) -> None:
        """Run transcription."""
        try:
            if self._audio_data is None or len(self._audio_data) == 0:
                self.error.emit("No audio recorded")
                return
            
            # Transcribe only - no processing yet
            text = transcribe_audio(self._audio_data)
            
            if not text:
                self.error.emit("No speech detected")
                return
            
            self.finished.emit(text)
            
        except Exception as e:
            self.error.emit(str(e))


class ReprocessWorker(QObject):
    """Worker for processing text with a mode."""
    
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
        """Set data for processing."""
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
    3. Show preview card with text
    4. User clicks mode buttons to reprocess, clicks Insert or presses trigger to inject
    """
    
    # Signals for thread-safe UI updates
    _show_pill_signal = Signal(int, int)
    _hide_pill_signal = Signal()
    _set_amplitude_signal = Signal(float)
    _set_duration_signal = Signal(float)
    _show_preview_signal = Signal(str, int, int)  # text, x, y
    _hide_preview_signal = Signal()
    _update_preview_text_signal = Signal(str)
    _set_preview_processing_signal = Signal(bool)
    
    def __init__(self):
        super().__init__()
        
        # State
        self._state = AppState.IDLE
        self._is_enabled = True
        self._original_text: str = ""  # Original transcription for reprocessing
        self._caret_position: tuple[int, int] = (0, 0)  # Saved for preview card
        
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
        self._preview_card: Optional[PreviewCard] = None
        self._tray: Optional[SystemTray] = None
        
        # Worker threads
        self._transcription_thread: Optional[QThread] = None
        self._transcription_worker: Optional[TranscriptionWorker] = None
        self._reprocess_thread: Optional[QThread] = None
        self._reprocess_worker: Optional[ReprocessWorker] = None
    
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
        self._preview_card = PreviewCard()
        self._tray = SystemTray()
        
        # Connect pill signals (thread-safe cross-thread communication)
        self._show_pill_signal.connect(self._pill.show_at)
        self._hide_pill_signal.connect(self._pill.hide_pill)
        self._set_amplitude_signal.connect(self._pill.set_amplitude)
        self._set_duration_signal.connect(self._pill.set_duration)
        
        # Connect preview card signals
        self._show_preview_signal.connect(self._do_show_preview)
        self._hide_preview_signal.connect(self._preview_card.hide_card)
        self._update_preview_text_signal.connect(self._preview_card.set_text)
        self._set_preview_processing_signal.connect(self._preview_card.set_processing)
        
        # Connect preview card user actions
        self._preview_card.insert_requested.connect(self._on_insert_requested)
        self._preview_card.cancelled.connect(self._on_preview_cancelled)
        self._preview_card.mode_changed.connect(self._on_mode_changed)
        self._preview_card.language_changed.connect(self._on_language_changed)
        
        # Connect tray signals
        self._tray.show_settings.connect(self._show_settings)
        self._tray.quit_app.connect(self._quit)
        self._tray.toggle_enabled.connect(self._set_enabled)
        
        # Show tray icon
        self._tray.show()
        
        # Start hotkey listener
        self._hotkey_manager.start()
        
        print("Dictate for Windows started. Press trigger key to record.")
    
    @Slot(str, int, int)
    def _do_show_preview(self, text: str, x: int, y: int) -> None:
        """Show preview card with text at position."""
        if self._preview_card:
            # Set available modes
            modes = get_all_modes(self._settings.get_custom_modes())
            self._preview_card.set_modes(modes, ProcessingMode.NORMAL)
            
            # Set text and show
            self._preview_card.set_text(text, is_original=True)
            self._preview_card.show_at(x, y)
    
    def stop(self) -> None:
        """Stop the application."""
        self._hotkey_manager.stop()
        
        if self._pill:
            self._pill.close()
        if self._preview_card:
            self._preview_card.close()
        if self._tray:
            self._tray.hide()
    
    def _set_enabled(self, enabled: bool) -> None:
        """Enable or disable dictation."""
        self._is_enabled = enabled
    
    def _on_hotkey_pressed(self) -> None:
        """Handle push-to-talk trigger pressed."""
        if not self._is_enabled:
            return
        
        # If preview card is shown, trigger key acts as "Insert"
        if self._state == AppState.PREVIEW:
            if self._preview_card:
                self._preview_card.insert()
            return
        
        if self._state != AppState.IDLE:
            return
        
        # Save caret position for later use
        self._caret_position = get_overlay_position()
        
        # Start recording
        if self._audio_recorder.start():
            self._state = AppState.RECORDING
            
            # Show pill at caret position
            x, y = self._caret_position
            self._show_pill_signal.emit(x, y)
            
            if self._tray:
                self._tray.set_recording(True)
    
    def _on_hotkey_released(self) -> None:
        """Handle push-to-talk trigger released."""
        if self._state != AppState.RECORDING:
            return
        
        # Stop recording
        audio_data = self._audio_recorder.stop()
        
        # Hide pill
        self._hide_pill_signal.emit()
        
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
        if self._state == AppState.RECORDING:
            self._set_amplitude_signal.emit(amplitude)
    
    def _on_duration(self, duration: float) -> None:
        """Handle recording duration updates."""
        if self._state == AppState.RECORDING:
            self._set_duration_signal.emit(duration)
    
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
        self._transcription_worker.set_data(audio_data)
        
        # Connect signals
        self._transcription_thread.started.connect(self._transcription_worker.run)
        self._transcription_worker.finished.connect(self._on_transcription_complete)
        self._transcription_worker.error.connect(self._on_transcription_error)
        self._transcription_worker.finished.connect(self._transcription_thread.quit)
        self._transcription_worker.error.connect(self._transcription_thread.quit)
        
        # Start
        self._transcription_thread.start()
    
    @Slot(str)
    def _on_transcription_complete(self, text: str) -> None:
        """Handle transcription completion."""
        if self._tray:
            self._tray.set_processing(False)
        
        self._original_text = text
        
        # Show preview card near caret position
        x, y = self._caret_position
        self._show_preview_signal.emit(text, x, y + 30)  # Offset below cursor
        
        # Enter preview state
        self._state = AppState.PREVIEW
    
    @Slot(str)
    def _on_transcription_error(self, error: str) -> None:
        """Handle transcription error."""
        if self._tray:
            self._tray.set_processing(False)
        
        print(f"Transcription error: {error}")
        self._state = AppState.IDLE
    
    @Slot(str)
    def _on_insert_requested(self, text: str) -> None:
        """Handle insert button click or trigger key during preview."""
        print(f"[App] Insert requested with text: {text[:50] if text else 'EMPTY'}...")
        
        # Hide preview card first
        self._hide_preview_signal.emit()
        
        # Return to idle state
        self._state = AppState.IDLE
        self._original_text = ""
        
        # Delay injection to allow preview card to fully close and original app to regain focus
        from PySide6.QtCore import QTimer
        QTimer.singleShot(300, lambda: self._text_injector.inject(text))
    
    @Slot()
    def _on_preview_cancelled(self) -> None:
        """Handle cancel button click."""
        # Hide preview card
        self._hide_preview_signal.emit()
        
        # Return to idle without injecting
        self._state = AppState.IDLE
        self._original_text = ""
    
    @Slot(object)
    def _on_mode_changed(self, mode: ProcessingMode | CustomMode) -> None:
        """Handle mode change from preview card."""
        if self._state != AppState.PREVIEW or not self._original_text:
            return
        
        # Reprocess with new mode
        self._reprocess_text(mode)
    
    @Slot(str)
    def _on_language_changed(self, language: str) -> None:
        """Handle translation language change."""
        if self._state != AppState.PREVIEW or not self._original_text:
            return
        
        if self._preview_card and self._preview_card.current_mode == ProcessingMode.TRANSLATE:
            self._reprocess_text(ProcessingMode.TRANSLATE, language)
    
    def _reprocess_text(
        self,
        mode: ProcessingMode | CustomMode,
        target_language: Optional[str] = None,
    ) -> None:
        """Reprocess the original text with a new mode."""
        if not self._original_text:
            return
        
        if target_language is None:
            target_language = (
                self._preview_card.target_language if self._preview_card
                else self._settings.default_target_language
            )
        
        # Show processing indicator
        self._set_preview_processing_signal.emit(True)
        
        # Clean up previous thread
        if self._reprocess_thread and self._reprocess_thread.isRunning():
            self._reprocess_thread.quit()
            self._reprocess_thread.wait()
        
        # Create worker
        self._reprocess_thread = QThread()
        self._reprocess_worker = ReprocessWorker()
        self._reprocess_worker.moveToThread(self._reprocess_thread)
        
        self._reprocess_worker.set_data(
            self._original_text,
            mode,
            target_language,
        )
        
        # Connect signals
        self._reprocess_thread.started.connect(self._reprocess_worker.run)
        self._reprocess_worker.finished.connect(self._on_reprocess_complete)
        self._reprocess_worker.error.connect(self._on_reprocess_error)
        self._reprocess_worker.finished.connect(self._reprocess_thread.quit)
        self._reprocess_worker.error.connect(self._reprocess_thread.quit)
        
        self._reprocess_thread.start()
    
    @Slot(str)
    def _on_reprocess_complete(self, text: str) -> None:
        """Handle reprocessing completion."""
        self._set_preview_processing_signal.emit(False)
        
        # Update preview card text
        self._update_preview_text_signal.emit(text)
    
    @Slot(str)
    def _on_reprocess_error(self, error: str) -> None:
        """Handle reprocessing error."""
        self._set_preview_processing_signal.emit(False)
        print(f"Reprocessing error: {error}")
    
    def _show_settings(self) -> None:
        """Show the settings dialog."""
        dialog = SettingsDialog()
        dialog.settings_saved.connect(self._on_settings_saved)
        dialog.exec()
    
    @Slot()
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
