# Dictate for Windows - The Cursor Companion

A sleek, AI-powered dictation overlay that floats above the OS, allowing you to dictate, reword, and format text directly into *any* active application.

## Features

- 🎙️ **Push-to-Talk Dictation**: Hold a hotkey (Caps Lock, Right Alt, or F1) to record, release to transcribe
- 🌐 **Cloud-Powered**: Uses Groq (default) or OpenAI for fast, accurate transcription
- ✨ **Smart Processing Modes**:
  - **Normal**: Direct transcription
  - **Formal**: Professional rewording
  - **Translate**: Auto-detect → target language
  - **Structure**: Organize as bullet points
  - **Summarize**: Condense to key points
  - **Custom**: Your own prompts
- 🎯 **Direct Text Injection**: Text appears selected in your active field, ready to accept or modify
- 🌓 **Dark/Light Mode**: Auto-syncs with Windows theme

## Installation

### Prerequisites

- Python 3.10+
- Windows 10/11
- Groq API key (free tier available) or OpenAI API key

### Install from source

```bash
# Clone the repository
git clone https://github.com/yourusername/windows_whisper.git
cd windows_whisper

# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -e .
```

## Usage

### First Run

1. **Start the app**:
   ```bash
   python -m dictate
   ```
   Or if installed:
   ```bash
   dictate
   ```

2. **Configure API Key**:
   - Right-click the tray icon → Settings
   - Enter your Groq or OpenAI API key
   - Click Save

### Dictating

1. **Record**: Hold the trigger key (default: Caps Lock)
   - A floating pill appears with waveform and timer

2. **Release**: Release the key to stop recording
   - Text is transcribed and injected into your active field (selected)
   - Mode bar appears at bottom of screen

3. **Navigate**:
   - `Tab` — Cycle through modes (Normal → Formal → Translate → Structure → Summarize → Custom)
   - `Enter` — Accept text (deselect and commit)
   - `Esc` — Cancel (delete injected text)

### Modes

| Mode | Description |
|------|-------------|
| **Normal** | Raw transcription, no processing |
| **Formal** | Rewrite professionally and clearly |
| **Translate** | Translate to selected language (default: English) |
| **Structure** | Format as organized bullet points |
| **Summarize** | Condense to key points |

### Custom Modes

Create your own modes in Settings → Custom Modes:
- **Name**: Display name (e.g., "Code Comment")
- **Prompt**: System prompt for the LLM (e.g., "Rewrite as a concise code comment")

## Configuration

Settings are stored in `%APPDATA%\DictateForWindows\config.json`

### Available Settings

| Setting | Options | Default |
|---------|---------|---------|
| Provider | `groq`, `openai` | `groq` |
| Trigger Key | `caps_lock`, `right_alt`, `f1` | `caps_lock` |
| Default Language | Any language | `English` |

## API Providers

### Groq (Recommended)

- **Free tier**: 7,200 audio seconds/hour, 12,000 tokens/min
- **Models**: `whisper-large-v3-turbo` (transcription), `llama-3.3-70b-versatile` (processing)
- **Speed**: Extremely fast inference

Get your API key at [console.groq.com](https://console.groq.com)

### OpenAI

- **Paid**: Usage-based pricing
- **Models**: `whisper-1` (transcription), `gpt-4o` (processing)
- **Quality**: High accuracy

## Architecture

```
src/dictate/
├── api/           # Cloud API clients (Groq, OpenAI)
│   ├── client.py      # Multi-provider client
│   ├── transcribe.py  # Whisper transcription
│   └── process.py     # LLM text processing
├── audio/         # Audio capture
│   └── capture.py     # sounddevice recording
├── input/         # System integration
│   ├── hotkeys.py     # Global hotkey listener
│   ├── caret.py       # Text cursor detection
│   └── text_inject.py # Clipboard injection
├── ui/            # User interface
│   ├── overlay.py     # Recording pill
│   ├── mode_bar.py    # Mode switcher
│   └── tray.py        # System tray + settings
├── config/        # Settings management
│   └── settings.py    # JSON config persistence
├── app.py         # Main orchestrator
└── __main__.py    # Entry point
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/
ruff check src/
```

## Troubleshooting

### "No API key found"
- Open Settings from the tray icon
- Enter your Groq or OpenAI API key

### Hotkey not working
- Some applications may intercept certain keys
- Try a different trigger key in Settings

### Text not appearing
- Ensure the target application accepts keyboard input
- Some elevated/admin windows may block input

### Audio not recording
- Check Windows microphone permissions
- Ensure default microphone is set correctly

## License

MIT License - See [LICENSE](LICENSE) for details.

## Acknowledgments

- [OpenAI Whisper](https://openai.com/research/whisper) for speech recognition
- [Groq](https://groq.com) for lightning-fast inference
- [PySide6](https://www.qt.io/qt-for-python) for the UI framework
