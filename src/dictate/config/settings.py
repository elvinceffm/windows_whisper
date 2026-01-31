"""
Configuration and settings management.

Persists settings to JSON file in AppData folder.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from ..api.process import CustomMode


# App data directory
APP_NAME = "DictateForWindows"
CONFIG_FILENAME = "config.json"


def get_app_data_dir() -> Path:
    """Get the application data directory."""
    # Use APPDATA on Windows, fallback to home directory
    if os.name == "nt":
        base = os.environ.get("APPDATA", str(Path.home()))
    else:
        base = str(Path.home() / ".config")
    
    app_dir = Path(base) / APP_NAME
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def get_config_path() -> Path:
    """Get the path to the config file."""
    return get_app_data_dir() / CONFIG_FILENAME


@dataclass
class Settings:
    """Application settings."""
    
    # API settings
    provider: str = "groq"  # "groq" or "openai"
    groq_api_key: str = ""
    openai_api_key: str = ""
    
    # Hotkey settings
    trigger_key: str = "caps_lock"  # "caps_lock", "right_alt", or "f1"
    
    # Translation settings
    default_target_language: str = "English"
    
    # UI settings
    theme: str = "system"  # "system", "dark", or "light"
    pill_opacity: float = 0.95
    
    # Startup settings
    run_at_startup: bool = False
    
    # Custom modes
    custom_modes: list[dict] = field(default_factory=list)
    
    def get_custom_modes(self) -> list[CustomMode]:
        """Get custom modes as CustomMode objects."""
        return [
            CustomMode(name=m["name"], prompt=m["prompt"])
            for m in self.custom_modes
            if "name" in m and "prompt" in m
        ]
    
    def add_custom_mode(self, name: str, prompt: str) -> None:
        """Add a new custom mode."""
        self.custom_modes.append({"name": name, "prompt": prompt})
    
    def remove_custom_mode(self, name: str) -> bool:
        """Remove a custom mode by name."""
        for i, m in enumerate(self.custom_modes):
            if m.get("name") == name:
                del self.custom_modes[i]
                return True
        return False
    
    def get_api_key(self) -> str:
        """Get the API key for the current provider."""
        if self.provider == "groq":
            return self.groq_api_key
        elif self.provider == "openai":
            return self.openai_api_key
        return ""
    
    def to_dict(self) -> dict:
        """Convert settings to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "Settings":
        """Create settings from dictionary."""
        # Handle legacy or missing fields
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get the current settings, loading from disk if needed.
    
    Returns:
        Settings instance
    """
    global _settings
    
    if _settings is None:
        _settings = load_settings()
    
    return _settings


def load_settings() -> Settings:
    """
    Load settings from disk.
    
    Returns:
        Settings instance (default values if file doesn't exist)
    """
    config_path = get_config_path()
    
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Settings.from_dict(data)
        except Exception as e:
            print(f"Failed to load settings: {e}")
    
    return Settings()


def save_settings(settings: Optional[Settings] = None) -> bool:
    """
    Save settings to disk.
    
    Args:
        settings: Settings to save (uses global if not provided)
        
    Returns:
        True if save was successful
    """
    global _settings
    
    if settings is None:
        settings = _settings
    
    if settings is None:
        return False
    
    config_path = get_config_path()
    
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(settings.to_dict(), f, indent=2)
        
        _settings = settings
        return True
        
    except Exception as e:
        print(f"Failed to save settings: {e}")
        return False


def update_settings(**kwargs) -> Settings:
    """
    Update specific settings values.
    
    Args:
        **kwargs: Setting names and values to update
        
    Returns:
        Updated Settings instance
    """
    settings = get_settings()
    
    for key, value in kwargs.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
    
    save_settings(settings)
    return settings


def reset_settings() -> Settings:
    """
    Reset settings to defaults.
    
    Returns:
        New default Settings instance
    """
    global _settings
    
    _settings = Settings()
    save_settings(_settings)
    return _settings


# ============================================================================
# Windows Startup Management
# ============================================================================

def get_startup_folder() -> Path:
    """Get the Windows Startup folder path."""
    if os.name == "nt":
        # Windows: %APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
        appdata = os.environ.get("APPDATA", str(Path.home()))
        return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    else:
        # Linux/Mac: Use autostart directory (for testing)
        return Path.home() / ".config" / "autostart"


def get_startup_shortcut_path() -> Path:
    """Get the path to the startup shortcut."""
    return get_startup_folder() / "Dictate for Windows.lnk"


def is_autostart_enabled() -> bool:
    """Check if autostart is currently enabled."""
    return get_startup_shortcut_path().exists()


def enable_autostart() -> bool:
    """
    Enable autostart by creating a startup shortcut.
    
    Returns:
        True if successful
    """
    if os.name != "nt":
        print("Autostart is only supported on Windows")
        return False
    
    try:
        import sys
        
        # Get the Python executable and script
        python_exe = sys.executable
        # Use pythonw.exe for no console window
        pythonw_exe = python_exe.replace("python.exe", "pythonw.exe")
        if not Path(pythonw_exe).exists():
            pythonw_exe = python_exe
        
        # Create shortcut using Windows Script Host
        startup_folder = get_startup_folder()
        startup_folder.mkdir(parents=True, exist_ok=True)
        
        shortcut_path = get_startup_shortcut_path()
        
        # Use win32com to create shortcut
        try:
            import win32com.client
            
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(str(shortcut_path))
            shortcut.TargetPath = pythonw_exe
            shortcut.Arguments = "-m dictate"
            shortcut.WorkingDirectory = str(Path.cwd())
            shortcut.Description = "Dictate for Windows - AI-powered dictation"
            shortcut.IconLocation = pythonw_exe
            shortcut.save()
            
            return True
            
        except ImportError:
            # Fallback: Use PowerShell to create shortcut
            import subprocess
            
            ps_script = f'''
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
$Shortcut.TargetPath = "{pythonw_exe}"
$Shortcut.Arguments = "-m dictate"
$Shortcut.WorkingDirectory = "{Path.cwd()}"
$Shortcut.Description = "Dictate for Windows - AI-powered dictation"
$Shortcut.Save()
'''
            
            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True,
                text=True,
            )
            
            return result.returncode == 0
            
    except Exception as e:
        print(f"Failed to enable autostart: {e}")
        return False


def disable_autostart() -> bool:
    """
    Disable autostart by removing the startup shortcut.
    
    Returns:
        True if successful
    """
    try:
        shortcut_path = get_startup_shortcut_path()
        if shortcut_path.exists():
            shortcut_path.unlink()
        return True
    except Exception as e:
        print(f"Failed to disable autostart: {e}")
        return False


def set_autostart(enabled: bool) -> bool:
    """
    Enable or disable autostart.
    
    Args:
        enabled: True to enable, False to disable
        
    Returns:
        True if successful
    """
    if enabled:
        return enable_autostart()
    else:
        return disable_autostart()
