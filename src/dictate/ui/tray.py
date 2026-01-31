"""
System tray integration and settings dialog.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QAction
from PySide6.QtWidgets import (
    QSystemTrayIcon, QMenu, QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QComboBox, QPushButton, QFormLayout,
    QGroupBox, QListWidget, QListWidgetItem, QTextEdit,
    QTabWidget, QWidget, QMessageBox, QApplication, QCheckBox,
)

from typing import Optional
from ..config.settings import Settings, get_settings, save_settings, set_autostart
from ..api.client import PROVIDERS


def create_tray_icon() -> QIcon:
    """Create a simple microphone icon for the tray."""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    # Microphone shape
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(255, 59, 48))  # Red
    
    # Mic body
    painter.drawRoundedRect(10, 4, 12, 16, 6, 6)
    
    # Mic stand
    painter.setBrush(QColor(200, 200, 200))
    painter.drawRect(14, 20, 4, 4)
    painter.drawRect(10, 24, 12, 3)
    
    painter.end()
    
    return QIcon(pixmap)


class SettingsDialog(QDialog):
    """Settings dialog for configuring the application."""
    
    settings_saved = Signal()
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self.setWindowTitle("Dictate Settings")
        self.setMinimumSize(480, 400)
        self.setModal(True)
        
        self._settings = get_settings()
        self._setup_ui()
        self._load_settings()
    
    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        
        # Tab widget
        tabs = QTabWidget()
        
        # General tab
        general_tab = QWidget()
        general_layout = QVBoxLayout(general_tab)
        
        # API Settings group
        api_group = QGroupBox("API Settings")
        api_layout = QFormLayout()
        
        # Provider selection
        self._provider_combo = QComboBox()
        for provider_id, config in PROVIDERS.items():
            self._provider_combo.addItem(config.name, provider_id)
        self._provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        api_layout.addRow("Provider:", self._provider_combo)
        
        # API Key inputs
        self._groq_key_input = QLineEdit()
        self._groq_key_input.setPlaceholderText("Enter Groq API key...")
        self._groq_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        api_layout.addRow("Groq API Key:", self._groq_key_input)
        
        self._openai_key_input = QLineEdit()
        self._openai_key_input.setPlaceholderText("Enter OpenAI API key...")
        self._openai_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        api_layout.addRow("OpenAI API Key:", self._openai_key_input)
        
        api_group.setLayout(api_layout)
        general_layout.addWidget(api_group)
        
        # Hotkey settings group
        hotkey_group = QGroupBox("Hotkey Settings")
        hotkey_layout = QFormLayout()
        
        self._hotkey_combo = QComboBox()
        self._hotkey_combo.addItem("Caps Lock", "caps_lock")
        self._hotkey_combo.addItem("Right Alt", "right_alt")
        self._hotkey_combo.addItem("F1", "f1")
        hotkey_layout.addRow("Trigger Key:", self._hotkey_combo)
        
        hotkey_group.setLayout(hotkey_layout)
        general_layout.addWidget(hotkey_group)
        
        # Translation settings
        translation_group = QGroupBox("Translation Settings")
        translation_layout = QFormLayout()
        
        self._language_combo = QComboBox()
        from ..api.process import LANGUAGES
        self._language_combo.addItems(LANGUAGES)
        translation_layout.addRow("Default Target:", self._language_combo)
        
        translation_group.setLayout(translation_layout)
        general_layout.addWidget(translation_group)
        
        # Startup settings
        startup_group = QGroupBox("Startup")
        startup_layout = QVBoxLayout()
        
        self._autostart_checkbox = QCheckBox("Start with Windows")
        self._autostart_checkbox.setToolTip(
            "Automatically start Dictate when you log in to Windows"
        )
        startup_layout.addWidget(self._autostart_checkbox)
        
        startup_group.setLayout(startup_layout)
        general_layout.addWidget(startup_group)
        
        general_layout.addStretch()
        tabs.addTab(general_tab, "General")
        
        # Custom Modes tab
        modes_tab = QWidget()
        modes_layout = QVBoxLayout(modes_tab)
        
        modes_label = QLabel(
            "Add custom processing modes with your own prompts.\n"
            "They will appear in the mode bar after the built-in modes."
        )
        modes_label.setWordWrap(True)
        modes_layout.addWidget(modes_label)
        
        # Modes list
        self._modes_list = QListWidget()
        self._modes_list.currentItemChanged.connect(self._on_mode_selected)
        modes_layout.addWidget(self._modes_list)
        
        # Mode editor
        editor_layout = QFormLayout()
        
        self._mode_name_input = QLineEdit()
        self._mode_name_input.setPlaceholderText("e.g., Code Comment")
        editor_layout.addRow("Mode Name:", self._mode_name_input)
        
        self._mode_prompt_input = QTextEdit()
        self._mode_prompt_input.setPlaceholderText(
            "Enter the system prompt for this mode...\n"
            "e.g., 'Rewrite the following text as a concise code comment.'"
        )
        self._mode_prompt_input.setMaximumHeight(100)
        editor_layout.addRow("Prompt:", self._mode_prompt_input)
        
        modes_layout.addLayout(editor_layout)
        
        # Mode buttons
        mode_buttons = QHBoxLayout()
        
        self._add_mode_btn = QPushButton("Add Mode")
        self._add_mode_btn.clicked.connect(self._add_custom_mode)
        mode_buttons.addWidget(self._add_mode_btn)
        
        self._update_mode_btn = QPushButton("Update")
        self._update_mode_btn.clicked.connect(self._update_custom_mode)
        self._update_mode_btn.setEnabled(False)
        mode_buttons.addWidget(self._update_mode_btn)
        
        self._delete_mode_btn = QPushButton("Delete")
        self._delete_mode_btn.clicked.connect(self._delete_custom_mode)
        self._delete_mode_btn.setEnabled(False)
        mode_buttons.addWidget(self._delete_mode_btn)
        
        mode_buttons.addStretch()
        modes_layout.addLayout(mode_buttons)
        
        tabs.addTab(modes_tab, "Custom Modes")
        
        layout.addWidget(tabs)
        
        # Dialog buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("Save")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._save_settings)
        buttons_layout.addWidget(save_btn)
        
        layout.addLayout(buttons_layout)
    
    def _load_settings(self) -> None:
        """Load current settings into the UI."""
        # Provider
        index = self._provider_combo.findData(self._settings.provider)
        if index >= 0:
            self._provider_combo.setCurrentIndex(index)
        
        # API keys
        self._groq_key_input.setText(self._settings.groq_api_key)
        self._openai_key_input.setText(self._settings.openai_api_key)
        
        # Hotkey
        index = self._hotkey_combo.findData(self._settings.trigger_key)
        if index >= 0:
            self._hotkey_combo.setCurrentIndex(index)
        
        # Language
        index = self._language_combo.findText(self._settings.default_target_language)
        if index >= 0:
            self._language_combo.setCurrentIndex(index)
        
        # Autostart
        self._autostart_checkbox.setChecked(self._settings.run_at_startup)
        
        # Custom modes
        self._refresh_modes_list()
    
    def _refresh_modes_list(self) -> None:
        """Refresh the custom modes list."""
        self._modes_list.clear()
        for mode in self._settings.custom_modes:
            item = QListWidgetItem(mode.get("name", "Untitled"))
            item.setData(Qt.ItemDataRole.UserRole, mode)
            self._modes_list.addItem(item)
    
    def _on_provider_changed(self, index: int) -> None:
        """Handle provider selection change."""
        provider = self._provider_combo.currentData()
        # Could show/hide relevant API key field
    
    def _on_mode_selected(self, current: Optional[QListWidgetItem], previous: Optional[QListWidgetItem]) -> None:
        """Handle mode selection in list."""
        if current:
            mode = current.data(Qt.ItemDataRole.UserRole)
            self._mode_name_input.setText(mode.get("name", ""))
            self._mode_prompt_input.setPlainText(mode.get("prompt", ""))
            self._update_mode_btn.setEnabled(True)
            self._delete_mode_btn.setEnabled(True)
        else:
            self._mode_name_input.clear()
            self._mode_prompt_input.clear()
            self._update_mode_btn.setEnabled(False)
            self._delete_mode_btn.setEnabled(False)
    
    def _add_custom_mode(self) -> None:
        """Add a new custom mode."""
        name = self._mode_name_input.text().strip()
        prompt = self._mode_prompt_input.toPlainText().strip()
        
        if not name or not prompt:
            QMessageBox.warning(self, "Invalid Mode", "Please enter both a name and prompt.")
            return
        
        self._settings.add_custom_mode(name, prompt)
        self._refresh_modes_list()
        self._mode_name_input.clear()
        self._mode_prompt_input.clear()
    
    def _update_custom_mode(self) -> None:
        """Update the selected custom mode."""
        current = self._modes_list.currentItem()
        if not current:
            return
        
        name = self._mode_name_input.text().strip()
        prompt = self._mode_prompt_input.toPlainText().strip()
        
        if not name or not prompt:
            QMessageBox.warning(self, "Invalid Mode", "Please enter both a name and prompt.")
            return
        
        # Get the index and update
        index = self._modes_list.currentRow()
        if 0 <= index < len(self._settings.custom_modes):
            self._settings.custom_modes[index] = {"name": name, "prompt": prompt}
            self._refresh_modes_list()
    
    def _delete_custom_mode(self) -> None:
        """Delete the selected custom mode."""
        current = self._modes_list.currentItem()
        if not current:
            return
        
        mode = current.data(Qt.ItemDataRole.UserRole)
        name = mode.get("name", "")
        
        reply = QMessageBox.question(
            self, "Delete Mode",
            f"Are you sure you want to delete '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self._settings.remove_custom_mode(name)
            self._refresh_modes_list()
    
    def _save_settings(self) -> None:
        """Save settings and close dialog."""
        # Update settings object
        self._settings.provider = self._provider_combo.currentData()
        self._settings.groq_api_key = self._groq_key_input.text()
        self._settings.openai_api_key = self._openai_key_input.text()
        self._settings.trigger_key = self._hotkey_combo.currentData()
        self._settings.default_target_language = self._language_combo.currentText()
        
        # Handle autostart change
        new_autostart = self._autostart_checkbox.isChecked()
        if new_autostart != self._settings.run_at_startup:
            if set_autostart(new_autostart):
                self._settings.run_at_startup = new_autostart
            else:
                QMessageBox.warning(
                    self,
                    "Autostart Error",
                    "Failed to update autostart setting. Please try again."
                )
        
        # Save to disk
        save_settings(self._settings)
        
        self.settings_saved.emit()
        self.accept()


class SystemTray(QSystemTrayIcon):
    """System tray icon with context menu."""
    
    # Signals
    show_settings = Signal()
    quit_app = Signal()
    toggle_enabled = Signal(bool)
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self.setIcon(create_tray_icon())
        self.setToolTip("Dictate for Windows")
        
        self._is_enabled = True
        self._setup_menu()
        
        # Handle clicks
        self.activated.connect(self._on_activated)
    
    def _setup_menu(self) -> None:
        """Set up the context menu."""
        menu = QMenu()
        
        # Status
        self._status_action = QAction("● Ready", menu)
        self._status_action.setEnabled(False)
        menu.addAction(self._status_action)
        
        menu.addSeparator()
        
        # Enable/Disable
        self._enable_action = QAction("Disable", menu)
        self._enable_action.triggered.connect(self._toggle_enabled)
        menu.addAction(self._enable_action)
        
        menu.addSeparator()
        
        # Settings
        settings_action = QAction("Settings...", menu)
        settings_action.triggered.connect(lambda: self.show_settings.emit())
        menu.addAction(settings_action)
        
        menu.addSeparator()
        
        # Quit
        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(lambda: self.quit_app.emit())
        menu.addAction(quit_action)
        
        self.setContextMenu(menu)
    
    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Handle tray icon activation."""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_settings.emit()
    
    def _toggle_enabled(self) -> None:
        """Toggle enabled state."""
        self._is_enabled = not self._is_enabled
        self._update_status()
        self.toggle_enabled.emit(self._is_enabled)
    
    def _update_status(self) -> None:
        """Update status display."""
        if self._is_enabled:
            self._status_action.setText("● Ready")
            self._enable_action.setText("Disable")
        else:
            self._status_action.setText("○ Disabled")
            self._enable_action.setText("Enable")
    
    def set_recording(self, is_recording: bool) -> None:
        """Update status to show recording state."""
        if is_recording:
            self._status_action.setText("🔴 Recording...")
        else:
            self._update_status()
    
    def set_processing(self, is_processing: bool) -> None:
        """Update status to show processing state."""
        if is_processing:
            self._status_action.setText("⏳ Processing...")
        else:
            self._update_status()
