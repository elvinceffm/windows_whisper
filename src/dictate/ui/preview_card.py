"""
Preview card widget for reviewing transcribed text before insertion.

Shows transcribed text with mode selection, language picker for translation,
and Insert/Cancel controls. All interaction is mouse-based to avoid
keyboard conflicts with the target application.
"""

from PySide6.QtCore import (
    Qt, Signal, QPropertyAnimation, QEasingCurve,
    QSize, QTimer, QRectF, Slot,
)
from PySide6.QtGui import (
    QPainter, QColor, QPainterPath, QFont, QFontMetrics,
    QLinearGradient, QCursor,
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QPushButton, QScrollArea, QGraphicsOpacityEffect,
    QApplication, QLabel, QFrame, QSizePolicy,
)

from typing import Optional, List
from ..api.process import ProcessingMode, CustomMode, get_mode_display_name


# Language data with emoji flags
LANGUAGES_WITH_FLAGS = [
    ("English", "🇬🇧"),
    ("German", "🇩🇪"),
    ("French", "🇫🇷"),
    ("Spanish", "🇪🇸"),
    ("Italian", "🇮🇹"),
    ("Portuguese", "🇵🇹"),
    ("Dutch", "🇳🇱"),
    ("Polish", "🇵🇱"),
    ("Russian", "🇷🇺"),
    ("Japanese", "🇯🇵"),
    ("Chinese", "🇨🇳"),
    ("Korean", "🇰🇷"),
    ("Arabic", "🇸🇦"),
    ("Hindi", "🇮🇳"),
    ("Turkish", "🇹🇷"),
    ("Vietnamese", "🇻🇳"),
    ("Thai", "🇹🇭"),
    ("Indonesian", "🇮🇩"),
    ("Swedish", "🇸🇪"),
    ("Norwegian", "🇳🇴"),
    ("Danish", "🇩🇰"),
    ("Finnish", "🇫🇮"),
    ("Czech", "🇨🇿"),
    ("Greek", "🇬🇷"),
    ("Hebrew", "🇮🇱"),
    ("Ukrainian", "🇺🇦"),
]

# UI Constants
CARD_MIN_WIDTH = 380
CARD_MAX_WIDTH = 500
CARD_MIN_HEIGHT = 160
CARD_MAX_HEIGHT = 400
CORNER_RADIUS = 16
TEXT_COLLAPSED_LINES = 3

# Colors
BACKGROUND_COLOR = QColor(28, 28, 30, 240)
ACCENT_COLOR = QColor(0, 122, 255)
ACCENT_GRADIENT_START = QColor(0, 122, 255)
ACCENT_GRADIENT_END = QColor(88, 86, 214)
TEXT_COLOR = QColor(255, 255, 255)
TEXT_SECONDARY = QColor(142, 142, 147)
BUTTON_BG = QColor(58, 58, 60)
BUTTON_HOVER = QColor(72, 72, 74)
SUCCESS_COLOR = QColor(52, 199, 89)
DANGER_COLOR = QColor(255, 69, 58)


class FlagButton(QPushButton):
    """Language flag pill button."""
    
    def __init__(self, language: str, flag: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.language = language
        self.flag = flag
        self._is_selected = False
        
        self.setText(flag)
        self.setToolTip(language)
        self.setFixedSize(36, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_style()
    
    @property
    def is_selected(self) -> bool:
        return self._is_selected
    
    @is_selected.setter
    def is_selected(self, value: bool) -> None:
        self._is_selected = value
        self._update_style()
    
    def _update_style(self) -> None:
        if self._is_selected:
            self.setStyleSheet("""
                QPushButton {
                    background-color: rgba(0, 122, 255, 200);
                    border: 2px solid rgb(0, 122, 255);
                    border-radius: 6px;
                    font-size: 16px;
                    padding: 2px;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: rgba(58, 58, 60, 150);
                    border: 1px solid rgba(255, 255, 255, 30);
                    border-radius: 6px;
                    font-size: 16px;
                    padding: 2px;
                }
                QPushButton:hover {
                    background-color: rgba(72, 72, 74, 200);
                    border: 1px solid rgba(255, 255, 255, 50);
                }
            """)


class LanguagePicker(QWidget):
    """Horizontal scrollable flag picker for translation target language."""
    
    language_selected = Signal(str)
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self._current_language = "English"
        self._buttons: List[FlagButton] = []
        
        # Scroll area for horizontal scrolling
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        
        # Container for flag buttons
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        
        for language, flag in LANGUAGES_WITH_FLAGS:
            btn = FlagButton(language, flag)
            btn.clicked.connect(lambda checked, lang=language: self._on_flag_clicked(lang))
            btn.is_selected = (language == self._current_language)
            self._buttons.append(btn)
            layout.addWidget(btn)
        
        layout.addStretch()
        scroll.setWidget(container)
        
        # Main layout
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)
        
        self.setFixedHeight(36)
    
    @property
    def current_language(self) -> str:
        return self._current_language
    
    @current_language.setter
    def current_language(self, language: str) -> None:
        self._current_language = language
        for btn in self._buttons:
            btn.is_selected = (btn.language == language)
    
    def _on_flag_clicked(self, language: str) -> None:
        if language != self._current_language:
            self.current_language = language
            self.language_selected.emit(language)


class ModeButton(QPushButton):
    """Mode selection button with gradient highlight when active."""
    
    def __init__(
        self,
        mode: ProcessingMode | CustomMode,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.mode = mode
        self._is_active = False
        
        self.setText(get_mode_display_name(mode))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(32)
        self.setMinimumWidth(70)
        self._update_style()
    
    @property
    def is_active(self) -> bool:
        return self._is_active
    
    @is_active.setter
    def is_active(self, value: bool) -> None:
        self._is_active = value
        self._update_style()
    
    def _update_style(self) -> None:
        if self._is_active:
            self.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 rgb(0, 122, 255), stop:1 rgb(88, 86, 214));
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-size: 12px;
                    font-weight: 600;
                    padding: 6px 12px;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: rgba(58, 58, 60, 180);
                    color: rgba(255, 255, 255, 180);
                    border: none;
                    border-radius: 8px;
                    font-size: 12px;
                    font-weight: 500;
                    padding: 6px 12px;
                }
                QPushButton:hover {
                    background-color: rgba(72, 72, 74, 200);
                    color: white;
                }
            """)


class PreviewCard(QWidget):
    """
    Floating preview card for reviewing transcribed text before insertion.
    
    Features:
    - Read-only text preview (scrollable, expandable for long text)
    - Mode buttons for reprocessing (Normal, Formal, Translate, etc.)
    - Language picker (horizontal flag pills) for translation
    - Insert (checkmark) and Cancel (X) buttons
    - Positioned near text caret with screen bounds checking
    """
    
    # Signals
    insert_requested = Signal(str)  # Emits final text to insert
    cancelled = Signal()
    mode_changed = Signal(object)  # ProcessingMode or CustomMode
    language_changed = Signal(str)
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        # Window flags for floating overlay
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # State
        self._text = ""
        self._original_text = ""  # Original transcription for reprocessing
        self._current_mode: ProcessingMode | CustomMode = ProcessingMode.NORMAL
        self._is_processing = False
        self._modes: List[ProcessingMode | CustomMode] = []
        self._mode_buttons: List[ModeButton] = []
        
        # Setup UI
        self._setup_ui()
        
        # Opacity effect for fade animations
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)
        
        # Fade animation
        self._fade_animation = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_animation.setDuration(150)
        self._fade_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # Size constraints
        self.setMinimumWidth(CARD_MIN_WIDTH)
        self.setMaximumWidth(CARD_MAX_WIDTH)
        self.setMinimumHeight(CARD_MIN_HEIGHT)
        self.setMaximumHeight(CARD_MAX_HEIGHT)
    
    def _setup_ui(self) -> None:
        """Build the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Text preview area
        self._text_edit = QTextEdit()
        self._text_edit.setReadOnly(True)
        self._text_edit.setPlaceholderText("Transcribing...")
        self._text_edit.setStyleSheet("""
            QTextEdit {
                background-color: rgba(44, 44, 46, 200);
                color: white;
                border: 1px solid rgba(255, 255, 255, 20);
                border-radius: 10px;
                padding: 10px;
                font-size: 14px;
                selection-background-color: rgba(0, 122, 255, 150);
            }
        """)
        self._text_edit.setMinimumHeight(60)
        self._text_edit.setMaximumHeight(200)
        layout.addWidget(self._text_edit)
        
        # Mode buttons row
        self._mode_layout = QHBoxLayout()
        self._mode_layout.setSpacing(6)
        layout.addLayout(self._mode_layout)
        
        # Language picker (hidden by default, shown for Translate mode)
        self._language_picker = LanguagePicker()
        self._language_picker.language_selected.connect(self._on_language_selected)
        self._language_picker.setVisible(False)
        layout.addWidget(self._language_picker)
        
        # Bottom row: Insert and Cancel buttons
        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        
        # Cancel button (X)
        self._cancel_btn = QPushButton("✕")
        self._cancel_btn.setToolTip("Cancel (discard text)")
        self._cancel_btn.setFixedSize(44, 36)
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.clicked.connect(self._on_cancel)
        self._cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 69, 58, 180);
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(255, 69, 58, 255);
            }
        """)
        button_row.addWidget(self._cancel_btn)
        
        button_row.addStretch()
        
        # Processing indicator
        self._processing_label = QLabel("Processing...")
        self._processing_label.setStyleSheet("color: rgba(255, 255, 255, 150); font-size: 12px;")
        self._processing_label.setVisible(False)
        button_row.addWidget(self._processing_label)
        
        button_row.addStretch()
        
        # Insert button (checkmark)
        self._insert_btn = QPushButton("✓")
        self._insert_btn.setToolTip("Insert text (or press trigger key)")
        self._insert_btn.setFixedSize(44, 36)
        self._insert_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._insert_btn.clicked.connect(self._on_insert)
        self._insert_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(52, 199, 89, 180);
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(52, 199, 89, 255);
            }
        """)
        button_row.addWidget(self._insert_btn)
        
        layout.addLayout(button_row)
    
    def paintEvent(self, event) -> None:
        """Draw translucent rounded background."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Background with rounded corners
        path = QPainterPath()
        path.addRoundedRect(
            QRectF(0, 0, self.width(), self.height()),
            CORNER_RADIUS, CORNER_RADIUS
        )
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(BACKGROUND_COLOR)
        painter.drawPath(path)
        
        # Subtle border
        painter.setPen(QColor(255, 255, 255, 30))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        
        painter.end()
    
    def set_modes(
        self,
        modes: List[ProcessingMode | CustomMode],
        initial_mode: ProcessingMode | CustomMode = ProcessingMode.NORMAL,
    ) -> None:
        """Set available modes and create buttons."""
        self._modes = modes
        self._current_mode = initial_mode
        
        # Clear existing buttons
        for btn in self._mode_buttons:
            btn.deleteLater()
        self._mode_buttons.clear()
        
        # Create mode buttons
        for mode in modes:
            btn = ModeButton(mode)
            btn.is_active = (mode == initial_mode)
            btn.clicked.connect(lambda checked, m=mode: self._on_mode_clicked(m))
            self._mode_buttons.append(btn)
            self._mode_layout.addWidget(btn)
        
        self._mode_layout.addStretch()
        
        # Show/hide language picker based on mode
        self._language_picker.setVisible(initial_mode == ProcessingMode.TRANSLATE)
    
    def set_text(self, text: str, is_original: bool = False) -> None:
        """Set the preview text."""
        self._text = text
        if is_original:
            self._original_text = text
        self._text_edit.setText(text)
        
        # Adjust height based on content
        doc_height = self._text_edit.document().size().height()
        new_height = min(max(60, doc_height + 24), 200)
        self._text_edit.setFixedHeight(int(new_height))
        
        self.adjustSize()
    
    @property
    def text(self) -> str:
        return self._text
    
    @property
    def original_text(self) -> str:
        return self._original_text
    
    @property
    def current_mode(self) -> ProcessingMode | CustomMode:
        return self._current_mode
    
    @property
    def target_language(self) -> str:
        return self._language_picker.current_language
    
    def set_processing(self, is_processing: bool) -> None:
        """Show/hide processing indicator."""
        self._is_processing = is_processing
        self._processing_label.setVisible(is_processing)
        self._insert_btn.setEnabled(not is_processing)
        
        # Disable mode buttons while processing
        for btn in self._mode_buttons:
            btn.setEnabled(not is_processing)
    
    @Slot(int, int)
    def show_at(self, x: int, y: int) -> None:
        """Show the card at specified position with screen bounds checking."""
        # Get screen geometry
        screen = QApplication.screenAt(QCursor.pos())
        if not screen:
            screen = QApplication.primaryScreen()
        screen_rect = screen.availableGeometry()
        
        # Adjust size before positioning
        self.adjustSize()
        
        # Clamp position to screen bounds
        card_x = x
        card_y = y
        
        # Prefer below the cursor, but flip above if no room
        if card_y + self.height() > screen_rect.bottom():
            card_y = y - self.height() - 20  # Above cursor
        
        # Horizontal bounds
        if card_x + self.width() > screen_rect.right():
            card_x = screen_rect.right() - self.width() - 10
        if card_x < screen_rect.left():
            card_x = screen_rect.left() + 10
        
        # Vertical bounds
        if card_y < screen_rect.top():
            card_y = screen_rect.top() + 10
        
        self.move(card_x, card_y)
        self.show()
        self._fade_in()
    
    @Slot()
    def hide_card(self) -> None:
        """Hide the card with fade animation."""
        self._fade_out()
    
    def _fade_in(self) -> None:
        """Animate fade in."""
        self._fade_animation.stop()
        self._fade_animation.setStartValue(self._opacity_effect.opacity())
        self._fade_animation.setEndValue(1.0)
        self._fade_animation.start()
    
    def _fade_out(self) -> None:
        """Animate fade out, then hide."""
        self._fade_animation.stop()
        self._fade_animation.setStartValue(self._opacity_effect.opacity())
        self._fade_animation.setEndValue(0.0)
        self._fade_animation.finished.connect(self._on_fade_out_finished)
        self._fade_animation.start()
    
    def _on_fade_out_finished(self) -> None:
        """Called when fade out completes."""
        try:
            self._fade_animation.finished.disconnect(self._on_fade_out_finished)
        except RuntimeError:
            pass  # Already disconnected
        self.hide()
    
    def _on_mode_clicked(self, mode: ProcessingMode | CustomMode) -> None:
        """Handle mode button click."""
        if mode == self._current_mode or self._is_processing:
            return
        
        # Update button states
        for btn in self._mode_buttons:
            btn.is_active = (btn.mode == mode)
        
        self._current_mode = mode
        
        # Show/hide language picker
        self._language_picker.setVisible(mode == ProcessingMode.TRANSLATE)
        
        self.mode_changed.emit(mode)
    
    def _on_language_selected(self, language: str) -> None:
        """Handle language selection."""
        self.language_changed.emit(language)
    
    def _on_insert(self) -> None:
        """Handle insert button click."""
        if not self._is_processing:
            self.insert_requested.emit(self._text)
    
    def _on_cancel(self) -> None:
        """Handle cancel button click."""
        self.cancelled.emit()
    
    def insert(self) -> None:
        """Programmatic insert (called when trigger key pressed)."""
        if not self._is_processing:
            self.insert_requested.emit(self._text)
