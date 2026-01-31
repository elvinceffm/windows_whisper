"""
Audio transcription using cloud Whisper API.
"""

import io
import wave
from typing import Optional

import numpy as np

from .client import get_client


def transcribe_audio(
    audio_data: np.ndarray,
    sample_rate: int = 16000,
    language: Optional[str] = None,
) -> str:
    """
    Transcribe audio data using the cloud Whisper API.
    
    Args:
        audio_data: NumPy array of audio samples (float32, mono)
        sample_rate: Sample rate in Hz (default 16000)
        language: Optional language code (e.g., "en", "de", "es")
        
    Returns:
        Transcribed text string
    """
    client = get_client()
    
    # Convert float32 audio to int16 WAV format
    wav_buffer = _audio_to_wav(audio_data, sample_rate)
    
    # Create a file-like object for the API
    wav_buffer.name = "audio.wav"
    
    # Call transcription API
    kwargs = {
        "file": wav_buffer,
        "model": client.transcription_model,
        "response_format": "text",
    }
    
    if language:
        kwargs["language"] = language
    
    response = client.client.audio.transcriptions.create(**kwargs)
    
    # Response is just the text string when format is "text"
    return response.strip() if isinstance(response, str) else response.text.strip()


def _audio_to_wav(audio_data: np.ndarray, sample_rate: int) -> io.BytesIO:
    """
    Convert numpy audio array to WAV format in memory.
    
    Args:
        audio_data: Float32 audio samples (-1.0 to 1.0)
        sample_rate: Sample rate in Hz
        
    Returns:
        BytesIO buffer containing WAV data
    """
    # Ensure audio is float32 and normalized
    audio_data = np.asarray(audio_data, dtype=np.float32)
    
    # Clip to valid range
    audio_data = np.clip(audio_data, -1.0, 1.0)
    
    # Convert to int16
    int16_data = (audio_data * 32767).astype(np.int16)
    
    # Create WAV in memory
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(int16_data.tobytes())
    
    buffer.seek(0)
    return buffer
