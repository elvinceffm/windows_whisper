"""
Mode bar widget anchored at bottom-center of screen.

Shows the current processing mode with Tab-cycle navigation,
language picker for translation, and keyboard hints.
"""

from PySide6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve,
    Signal, QRectF, QPoint,
)
from PySide6.QtGui import (
    QPainter, QColor, QPainterPath, QFont, QPen,
    QFontMetrics,
)
from PySide6.QtWidgets import (
    QWidget, QGraphicsOpacityEffect, QApplication,
    QHBoxLayout, QLabel, QPushButton, QComboBox,
    QVBoxLayout, QFrame,
)

from typing import Optional, List
from ..api.process import ProcessingMode, CustomMode, LANGUAGES, get_mode_display_name


# UI Constants
MODE_BAR_HEIGHT = 52
MODE_BAR_MIN_WIDTH = 320
MODE_BAR_MAX_WIDTH = 500
CORNER_RADIUS = 16
BOTTOM_MARGIN = 60  # Distance from screen bottom

# Colors
BACKGROUND_COLOR = QColor(28, 28, 30, 245)
BACKGROUND_COLOR_LIGHT = QColor(242, 242, 247, 245)
ACCENT_COLOR = QColor(0, 122, 255)  # Blue
TEXT_COLOR = QColor(255, 255, 255)
TEXT_COLOR_LIGHT = QColor(0, 0, 0)
TEXT_SECONDARY = QColor(142, 142, 147)
MODE_ACTIVE_BG = QColor(0, 122, 255)
MODE_INACTIVE_BG = QColor(58, 58, 60)
MODE_INACTIVE_BG_LIGHT = QColor(209, 209, 214)


class ModeButton(QWidget):
    """Individual mode button in the mode bar."""
    
    clicked = Signal()
    
    def __init__(
        self,
        mode: ProcessingMode | CustomMode,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        
        self.mode = mode
        self._is_active = False
        self._is_hovered = False
        self._dark_mode = True
        
        self.setFixedHeight(32)
        self.setMinimumWidth(60)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    
    @property
    def is_active(self) -> bool:
        return self._is_active
    
    @is_active.setter
    def is_active(self, value: bool) -> None:
        self._is_active = value
        self.update()
    
    def set_dark_mode(self, dark: bool) -> None:
        self._dark_mode = dark
        self.update()
    
    def enterEvent(self, event) -> None:
        self._is_hovered = True
        self.update()
    
    def leaveEvent(self, event) -> None:
        self._is_hovered = False
        self.update()
    
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
    
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Background
        if self._is_active:
            bg_color = MODE_ACTIVE_BG
            text_color = QColor(255, 255, 255)
        elif self._is_hovered:
            bg_color = MODE_INACTIVE_BG if self._dark_mode else MODE_INACTIVE_BG_LIGHT
            bg_color = QColor(bg_color)
            bg_color.setAlpha(200)
            text_color = TEXT_COLOR if self._dark_mode else TEXT_COLOR_LIGHT
        else:
            bg_color = QColor(0, 0, 0, 0)  # Transparent
            text_color = TEXT_SECONDARY
        
        # Draw rounded background
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, self.width(), self.height()), 8, 8)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg_color)
        painter.drawPath(path)
        
        # Draw text
        painter.setPen(text_color)
        font = painter.font()
        font.setPointSize(11)
        font.setWeight(QFont.Weight.Medium)
        painter.setFont(font)
        
        text = get_mode_display_name(self.mode)
        painter.drawText(
            QRectF(0, 0, self.width(), self.height()),
            Qt.AlignmentFlag.AlignCenter,
            text
        )
        
        painter.end()
    
    def sizeHint(self):
        font = self.font()
        font.setPointSize(11)
        fm = QFontMetrics(font)
        text = get_mode_display_name(self.mode)
        width = fm.horizontalAdvance(text) + 24
        return QSize(max(60, width), 32)


from PySide6.QtCore import QSize


class LanguagePicker(QComboBox):
    """Dropdown for selecting translation target language."""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self.addItems(LANGUAGES)
        self.setCurrentText("English")
        
        # Styling
        self.setFixedHeight(28)
        self.setMinimumWidth(100)
        
        self.setStyleSheet("""
            QComboBox {
                background-color: rgba(58, 58, 60, 200);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QComboBox:hover {
                background-color: rgba(72, 72, 74, 200);
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid white;
                margin-right: 6px;
            }
            QComboBox QAbstractItemView {
                background-color: rgb(44, 44, 46);
                color: white;
                selection-background-color: rgb(0, 122, 255);
                border: 1px solid rgb(58, 58, 60);
                border-radius: 6px;
            }
        """)


class ModeBar(QWidget):
    """
    Bottom-anchored mode bar for cycling through processing modes.
    
    Features:
    - Mode buttons for Normal, Formal, Translate, Structure, Summarize, Custom
    - Language picker (shown only for Translate mode)
    - Keyboard hints
    - Processing indicator
    """
    
    # Signals
    mode_changed = Signal(object)  # ProcessingMode or CustomMode
    language_changed = Signal(str)
    accepted = Signal()
    cancelled = Signal()
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        # Window flags for floating overlay
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        
        # State
        self._current_mode_index = 0
        self._modes: List[ProcessingMode | CustomMode] = []
        self._mode_buttons: List[ModeButton] = []
        self._is_processing = False
        self._dark_mode = True
        
        # Set up UI
        self._setup_ui()
        
        # Opacity effect
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)
        
        # Fade animation
        self._fade_animation = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_animation.setDuration(150)
        self._fade_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # Processing animation
        self._processing_timer = QTimer(self)
        self._processing_timer.timeout.connect(self._update_processing)
        self._processing_dots = 0
        
        # Detect theme
        self._detect_theme()
    
    def _detect_theme(self) -> None:
        """Detect system dark/light mode."""
        palette = QApplication.palette()
        bg_color = palette.color(palette.ColorRole.Window)
        self._dark_mode = bg_color.lightness() < 128
    
    def _setup_ui(self) -> None:
        """Set up the UI layout."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 8, 12, 8)
        main_layout.setSpacing(6)
        
        # Top row: mode buttons + language picker
        top_row = QHBoxLayout()
        top_row.setSpacing(6)
        
        # Mode buttons container
        self._modes_container = QHBoxLayout()
        self._modes_container.setSpacing(4)
        top_row.addLayout(self._modes_container)
        
        # Spacer
        top_row.addStretch()
        
        # Language picker (hidden by default)
        self._language_picker = LanguagePicker()
        self._language_picker.currentTextChanged.connect(
            lambda t: self.language_changed.emit(t)
        )
        self._language_picker.hide()
        top_row.addWidget(self._language_picker)
        
        main_layout.addLayout(top_row)
        
        # Bottom row: keyboard hints + processing indicator
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(16)
        
        # Keyboard hints
        hints_text = "↵ Insert   ⇥ Cycle   ⎋ Cancel"
        self._hints_label = QLabel(hints_text)
        self._hints_label.setStyleSheet("""
            QLabel {
                color: rgba(142, 142, 147, 200);
                font-size: 10px;
            }
        """)
        bottom_row.addWidget(self._hints_label)
        
        bottom_row.addStretch()
        
        # Processing indicator
        self._processing_label = QLabel("")
        self._processing_label.setStyleSheet("""
            QLabel {
                color: rgba(0, 122, 255, 200);
                font-size: 10px;
            }
        """)
        self._processing_label.hide()
        bottom_row.addWidget(self._processing_label)
        
        main_layout.addLayout(bottom_row)
        
        self.setFixedHeight(MODE_BAR_HEIGHT + 24)
    
    def set_modes(
        self,
        modes: List[ProcessingMode | CustomMode],
        initial_index: int = 0
    ) -> None:
        """
        Set the available modes.
        
        Args:
            modes: List of modes to show
            initial_index: Index of initially selected mode
        """
        self._modes = modes
        self._current_mode_index = initial_index
        
        # Clear existing buttons
        for btn in self._mode_buttons:
            btn.deleteLater()
        self._mode_buttons.clear()
        
        # Create new buttons
        for i, mode in enumerate(modes):
            btn = ModeButton(mode)
            btn.is_active = (i == initial_index)
            btn.set_dark_mode(self._dark_mode)
            btn.clicked.connect(lambda checked=False, idx=i: self._on_mode_clicked(idx))
            self._modes_container.addWidget(btn)
            self._mode_buttons.append(btn)
        
        # Show/hide language picker
        self._update_language_picker_visibility()
        
        # Adjust width
        self._adjust_width()
    
    def _on_mode_clicked(self, index: int) -> None:
        """Handle mode button click."""
        self.set_current_mode_index(index)
    
    def set_current_mode_index(self, index: int) -> None:
        """Set the current mode by index."""
        if 0 <= index < len(self._modes):
            # Update button states
            for i, btn in enumerate(self._mode_buttons):
                btn.is_active = (i == index)
            
            self._current_mode_index = index
            self._update_language_picker_visibility()
            self.mode_changed.emit(self._modes[index])
    
    def cycle_next(self) -> None:
        """Cycle to the next mode."""
        if self._modes:
            next_index = (self._current_mode_index + 1) % len(self._modes)
            self.set_current_mode_index(next_index)
    
    def cycle_previous(self) -> None:
        """Cycle to the previous mode."""
        if self._modes:
            prev_index = (self._current_mode_index - 1) % len(self._modes)
            self.set_current_mode_index(prev_index)
    
    @property
    def current_mode(self) -> Optional[ProcessingMode | CustomMode]:
        """Get the current mode."""
        if 0 <= self._current_mode_index < len(self._modes):
            return self._modes[self._current_mode_index]
        return None
    
    @property
    def target_language(self) -> str:
        """Get the selected target language."""
        return self._language_picker.currentText()
    
    def _update_language_picker_visibility(self) -> None:
        """Show/hide language picker based on current mode."""
        current = self.current_mode
        show_picker = current == ProcessingMode.TRANSLATE
        self._language_picker.setVisible(show_picker)
    
    def _adjust_width(self) -> None:
        """Adjust bar width based on content."""
        # Calculate required width
        total_width = 24  # Margins
        for btn in self._mode_buttons:
            total_width += btn.sizeHint().width() + 4
        
        if self._language_picker.isVisible():
            total_width += self._language_picker.width() + 12
        
        total_width = max(MODE_BAR_MIN_WIDTH, min(total_width, MODE_BAR_MAX_WIDTH))
        self.setFixedWidth(total_width)
    
    def show_processing(self, show: bool = True) -> None:
        """Show or hide processing indicator."""
        self._is_processing = show
        if show:
            self._processing_dots = 0
            self._processing_timer.start(400)
            self._processing_label.show()
            self._update_processing()
        else:
            self._processing_timer.stop()
            self._processing_label.hide()
    
    def _update_processing(self) -> None:
        """Update processing dots animation."""
        dots = "." * ((self._processing_dots % 3) + 1)
        self._processing_label.setText(f"Processing{dots}")
        self._processing_dots += 1
    
    def show_bar(self) -> None:
        """Show the mode bar at bottom-center of screen."""
        # Get active monitor geometry
        screen = QApplication.primaryScreen()
        if screen:
            geometry = screen.availableGeometry()
        else:
            geometry = QApplication.desktop().availableGeometry()
        
        # Position at bottom-center
        x = geometry.x() + (geometry.width() - self.width()) // 2
        y = geometry.y() + geometry.height() - self.height() - BOTTOM_MARGIN
        
        self.move(x, y)
        self.show()
        self._fade_in()
    
    def hide_bar(self) -> None:
        """Hide the mode bar with animation."""
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
            pass
        self.hide()
    
    def paintEvent(self, event) -> None:
        """Paint the background."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Background
        bg_color = BACKGROUND_COLOR if self._dark_mode else BACKGROUND_COLOR_LIGHT
        
        path = QPainterPath()
        path.addRoundedRect(
            QRectF(0, 0, self.width(), self.height()),
            CORNER_RADIUS, CORNER_RADIUS
        )
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg_color)
        painter.drawPath(path)
        
        # Subtle border
        border_color = QColor(255, 255, 255, 20) if self._dark_mode else QColor(0, 0, 0, 20)
        painter.setPen(QPen(border_color, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        
        painter.end()
