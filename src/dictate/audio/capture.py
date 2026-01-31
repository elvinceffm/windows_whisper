"""
Audio capture using sounddevice for low-latency recording.
"""

import threading
from typing import Callable, Optional
from dataclasses import dataclass, field

import numpy as np
import sounddevice as sd


# Recording configuration
SAMPLE_RATE = 16000  # 16kHz for Whisper
CHANNELS = 1  # Mono
DTYPE = np.float32
BLOCK_SIZE = 1024  # Samples per callback block


@dataclass
class RecordingState:
    """State container for an active recording."""
    
    is_recording: bool = False
    audio_chunks: list[np.ndarray] = field(default_factory=list)
    start_time: float = 0.0
    duration: float = 0.0


class AudioRecorder:
    """
    Push-to-talk audio recorder with real-time amplitude feedback.
    
    Records audio independently of window focus - once started,
    recording continues until explicitly stopped.
    """
    
    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        channels: int = CHANNELS,
        on_amplitude: Optional[Callable[[float], None]] = None,
        on_duration: Optional[Callable[[float], None]] = None,
    ):
        """
        Initialize the audio recorder.
        
        Args:
            sample_rate: Sample rate in Hz
            channels: Number of channels (1 for mono)
            on_amplitude: Callback for real-time amplitude (0.0 to 1.0)
            on_duration: Callback for recording duration in seconds
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.on_amplitude = on_amplitude
        self.on_duration = on_duration
        
        self._state = RecordingState()
        self._stream: Optional[sd.InputStream] = None
        self._lock = threading.Lock()
    
    @property
    def is_recording(self) -> bool:
        """Check if currently recording."""
        with self._lock:
            return self._state.is_recording
    
    @property
    def duration(self) -> float:
        """Get current recording duration in seconds."""
        with self._lock:
            return self._state.duration
    
    def start(self) -> bool:
        """
        Start recording audio.
        
        Returns:
            True if recording started successfully
        """
        with self._lock:
            if self._state.is_recording:
                return False
            
            self._state = RecordingState(is_recording=True)
            self._state.start_time = 0.0
        
        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=DTYPE,
                blocksize=BLOCK_SIZE,
                callback=self._audio_callback,
            )
            self._stream.start()
            return True
        except Exception as e:
            print(f"Failed to start recording: {e}")
            with self._lock:
                self._state.is_recording = False
            return False
    
    def stop(self) -> Optional[np.ndarray]:
        """
        Stop recording and return the captured audio.
        
        Returns:
            NumPy array of audio samples, or None if not recording
        """
        with self._lock:
            if not self._state.is_recording:
                return None
            
            self._state.is_recording = False
            chunks = self._state.audio_chunks.copy()
        
        # Stop and close the stream
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        
        # Concatenate all audio chunks
        if not chunks:
            return np.array([], dtype=DTYPE)
        
        return np.concatenate(chunks)
    
    def cancel(self) -> None:
        """Cancel recording without returning audio."""
        self.stop()
    
    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: dict,
        status: sd.CallbackFlags,
    ) -> None:
        """
        Callback for processing audio blocks from the stream.
        
        This runs in a separate thread managed by sounddevice.
        """
        if status:
            print(f"Audio callback status: {status}")
        
        with self._lock:
            if not self._state.is_recording:
                return
            
            # Store audio chunk (copy to avoid buffer reuse issues)
            self._state.audio_chunks.append(indata.copy().flatten())
            
            # Update duration
            total_samples = sum(len(c) for c in self._state.audio_chunks)
            self._state.duration = total_samples / self.sample_rate
        
        # Calculate amplitude (RMS)
        amplitude = np.sqrt(np.mean(indata ** 2))
        # Normalize to 0-1 range (typical speech is around 0.01-0.1 RMS)
        normalized_amplitude = min(1.0, amplitude * 10)
        
        # Fire callbacks (outside lock to prevent deadlocks)
        if self.on_amplitude:
            try:
                self.on_amplitude(normalized_amplitude)
            except Exception:
                pass
        
        if self.on_duration:
            try:
                self.on_duration(self._state.duration)
            except Exception:
                pass


def get_input_devices() -> list[dict]:
    """
    Get list of available audio input devices.
    
    Returns:
        List of device info dicts with 'index', 'name', 'channels'
    """
    devices = []
    for i, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] > 0:
            devices.append({
                "index": i,
                "name": dev["name"],
                "channels": dev["max_input_channels"],
                "default": dev.get("default_input_device", False),
            })
    return devices


def get_default_input_device() -> Optional[int]:
    """Get the index of the default input device."""
    try:
        return sd.query_devices(kind="input")["index"]
    except Exception:
        return None
