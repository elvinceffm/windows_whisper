"""
Floating pill overlay for recording state.

Shows a minimal pill with breathing waveform animation and time display
near the text caret while recording.
"""

from PySide6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve,
    Property, QPoint, QSize, Signal, QRectF, Slot,
)
from PySide6.QtGui import (
    QPainter, QColor, QPainterPath, QLinearGradient,
    QFont, QFontDatabase, QPen,
)
from PySide6.QtWidgets import (
    QWidget, QGraphicsOpacityEffect, QApplication,
)

import math
from typing import Optional


# UI Constants
PILL_WIDTH = 160
PILL_HEIGHT = 42
CORNER_RADIUS = 21
WAVEFORM_BARS = 5
WAVEFORM_BAR_WIDTH = 3
WAVEFORM_BAR_GAP = 3
WAVEFORM_MAX_HEIGHT = 18
WAVEFORM_MIN_HEIGHT = 4

# Colors - Modern dark theme matching preview card
BACKGROUND_COLOR = QColor(18, 18, 20, 248)  # Near black
BACKGROUND_COLOR_LIGHT = QColor(242, 242, 247)  # Light gray
ACCENT_COLOR = QColor(239, 68, 68)  # Red-500 (recording)
ACCENT_GLOW = QColor(239, 68, 68, 60)  # Red glow
WAVEFORM_COLOR = QColor(248, 113, 113)  # Red-400
TEXT_COLOR = QColor(244, 244, 245)  # Zinc-100
TEXT_COLOR_LIGHT = QColor(0, 0, 0)


class RecordingPill(QWidget):
    """
    Floating pill widget showing recording status.
    
    Features:
    - Breathing waveform animation synced to audio amplitude
    - Sleek time counter display
    - Appears near text caret, stays visible during recording
    - Smooth fade in/out animations
    """
    
    # Signals
    recording_started = Signal()
    recording_stopped = Signal()
    
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
        
        # Size
        self.setFixedSize(PILL_WIDTH, PILL_HEIGHT)
        
        # State
        self._amplitude = 0.0
        self._duration = 0.0
        self._is_recording = False
        self._glow_intensity = 0.0
        self._dark_mode = True
        
        # Waveform bar heights (for smooth animation)
        self._bar_heights = [WAVEFORM_MIN_HEIGHT] * WAVEFORM_BARS
        self._target_bar_heights = [WAVEFORM_MIN_HEIGHT] * WAVEFORM_BARS
        
        # Opacity effect for fade animations
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)
        
        # Animation timers
        self._animation_timer = QTimer(self)
        self._animation_timer.timeout.connect(self._update_animation)
        self._animation_timer.setInterval(16)  # ~60 FPS
        
        self._glow_timer = QTimer(self)
        self._glow_timer.timeout.connect(self._update_glow)
        self._glow_timer.setInterval(50)
        
        # Fade animation
        self._fade_animation = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_animation.setDuration(150)
        self._fade_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # Detect system theme
        self._detect_theme()
    
    def _detect_theme(self) -> None:
        """Detect system dark/light mode."""
        # Simple detection based on palette
        palette = QApplication.palette()
        bg_color = palette.color(palette.ColorRole.Window)
        self._dark_mode = bg_color.lightness() < 128
    
    @property
    def is_recording(self) -> bool:
        """Check if recording is active."""
        return self._is_recording
    
    @Slot(float)
    def set_amplitude(self, amplitude: float) -> None:
        """
        Set the current audio amplitude for waveform visualization.
        
        Args:
            amplitude: Value from 0.0 to 1.0
        """
        self._amplitude = max(0.0, min(1.0, amplitude))
        
        # Update target bar heights based on amplitude
        import random
        for i in range(WAVEFORM_BARS):
            # Add some variation between bars
            variation = 0.7 + random.random() * 0.3
            target = WAVEFORM_MIN_HEIGHT + (
                (WAVEFORM_MAX_HEIGHT - WAVEFORM_MIN_HEIGHT) * 
                self._amplitude * variation
            )
            self._target_bar_heights[i] = target
    
    @Slot(float)
    def set_duration(self, duration: float) -> None:
        """
        Set the current recording duration.
        
        Args:
            duration: Duration in seconds
        """
        self._duration = duration
        self.update()
    
    @Slot(int, int)
    def show_at(self, x: int, y: int) -> None:
        """
        Show the pill at the specified screen position.
        
        Ensures pill stays within screen bounds.
        
        Args:
            x: Screen X coordinate
            y: Screen Y coordinate
        """
        from PySide6.QtGui import QCursor
        
        # Get screen geometry for bounds checking
        screen = QApplication.screenAt(QCursor.pos())
        if not screen:
            screen = QApplication.primaryScreen()
        
        if screen:
            screen_rect = screen.availableGeometry()
            
            # Clamp position to screen bounds
            pill_x = max(screen_rect.left() + 10, 
                        min(x, screen_rect.right() - self.width() - 10))
            pill_y = max(screen_rect.top() + 10,
                        min(y, screen_rect.bottom() - self.height() - 10))
        else:
            pill_x, pill_y = x, y
        
        self.move(pill_x, pill_y)
        self._start_recording_state()
        self.show()
        self._fade_in()
    
    @Slot()
    def hide_pill(self) -> None:
        """Hide the pill with fade animation."""
        self._stop_recording_state()
        self._fade_out()
    
    def _start_recording_state(self) -> None:
        """Start recording animations and state."""
        self._is_recording = True
        self._duration = 0.0
        self._amplitude = 0.0
        self._bar_heights = [WAVEFORM_MIN_HEIGHT] * WAVEFORM_BARS
        self._target_bar_heights = [WAVEFORM_MIN_HEIGHT] * WAVEFORM_BARS
        
        self._animation_timer.start()
        self._glow_timer.start()
        
        self.recording_started.emit()
    
    def _stop_recording_state(self) -> None:
        """Stop recording animations and state."""
        self._is_recording = False
        self._animation_timer.stop()
        self._glow_timer.stop()
        
        self.recording_stopped.emit()
    
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
        self._fade_animation.finished.disconnect(self._on_fade_out_finished)
        self.hide()
    
    def _update_animation(self) -> None:
        """Update waveform bar animations (called at 60 FPS)."""
        # Smoothly interpolate bar heights toward targets
        for i in range(WAVEFORM_BARS):
            diff = self._target_bar_heights[i] - self._bar_heights[i]
            self._bar_heights[i] += diff * 0.3  # Smooth interpolation
        
        self.update()
    
    def _update_glow(self) -> None:
        """Update glow pulsing animation."""
        # Subtle breathing effect
        import time
        t = time.time() * 2  # Speed of breathing
        self._glow_intensity = 0.3 + 0.2 * math.sin(t)
        self.update()
    
    def _format_duration(self) -> str:
        """Format duration as M:SS."""
        minutes = int(self._duration // 60)
        seconds = int(self._duration % 60)
        return f"{minutes}:{seconds:02d}"
    
    def paintEvent(self, event) -> None:
        """Paint the pill widget with modern styling."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Colors based on theme
        text_color = TEXT_COLOR if self._dark_mode else TEXT_COLOR_LIGHT
        
        # Outer glow/shadow effect for depth
        for i in range(3):
            glow_path = QPainterPath()
            offset = (3 - i) * 2
            glow_path.addRoundedRect(
                QRectF(offset, offset, self.width() - offset * 2, self.height() - offset * 2),
                CORNER_RADIUS - offset // 2, CORNER_RADIUS - offset // 2
            )
            glow_color = QColor(0, 0, 0, 20 + i * 10)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(glow_color)
            painter.drawPath(glow_path)
        
        # Main background with gradient
        path = QPainterPath()
        path.addRoundedRect(
            QRectF(3, 3, self.width() - 6, self.height() - 6),
            CORNER_RADIUS, CORNER_RADIUS
        )
        
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, QColor(24, 24, 27, 252))
        gradient.setColorAt(1, QColor(18, 18, 20, 252))
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawPath(path)
        
        # Subtle top highlight
        highlight_path = QPainterPath()
        highlight_path.addRoundedRect(
            QRectF(3, 3, self.width() - 6, 2),
            1, 1
        )
        painter.setBrush(QColor(255, 255, 255, 8))
        painter.drawPath(highlight_path)
        
        # Border
        border_pen = QPen(QColor(255, 255, 255, 12))
        border_pen.setWidth(1)
        painter.setPen(border_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(
            QRectF(3.5, 3.5, self.width() - 7, self.height() - 7),
            CORNER_RADIUS, CORNER_RADIUS
        )
        
        # Recording indicator dot with glow
        dot_x = 18
        dot_y = self.height() // 2
        dot_radius = 5
        
        if self._is_recording:
            # Glow behind dot
            glow_radius = dot_radius + 4 + int(3 * self._glow_intensity)
            glow_color = QColor(ACCENT_COLOR)
            glow_color.setAlpha(int(40 + 30 * self._glow_intensity))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(glow_color)
            painter.drawEllipse(QPoint(dot_x, dot_y), glow_radius, glow_radius)
        
        # Pulsing red dot
        dot_color = QColor(ACCENT_COLOR)
        if self._is_recording:
            dot_color.setAlpha(200 + int(55 * self._glow_intensity))
        else:
            dot_color.setAlpha(150)
        painter.setBrush(dot_color)
        painter.drawEllipse(QPoint(dot_x, dot_y), dot_radius, dot_radius)
        
        # Waveform bars
        waveform_start_x = 38
        waveform_center_y = self.height() // 2
        
        for i, height in enumerate(self._bar_heights):
            x = waveform_start_x + i * (WAVEFORM_BAR_WIDTH + WAVEFORM_BAR_GAP)
            y = waveform_center_y - height / 2
            
            # Gradient for each bar
            bar_gradient = QLinearGradient(x, y, x, y + height)
            if self._is_recording:
                bar_gradient.setColorAt(0, QColor(248, 113, 113))  # Red-400
                bar_gradient.setColorAt(1, QColor(239, 68, 68))    # Red-500
            else:
                bar_gradient.setColorAt(0, QColor(113, 113, 122))
                bar_gradient.setColorAt(1, QColor(82, 82, 91))
            
            bar_path = QPainterPath()
            bar_path.addRoundedRect(
                QRectF(x, y, WAVEFORM_BAR_WIDTH, height),
                WAVEFORM_BAR_WIDTH / 2, WAVEFORM_BAR_WIDTH / 2
            )
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(bar_gradient)
            painter.drawPath(bar_path)
        
        # Duration text
        painter.setPen(text_color)
        font = painter.font()
        font.setPointSize(13)
        font.setWeight(QFont.Weight.Medium)
        font.setFamily("Segoe UI")
        painter.setFont(font)
        
        duration_text = self._format_duration()
        text_x = self.width() - 52
        text_rect = QRectF(text_x, 0, 44, self.height())
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, duration_text)
        
        painter.end()


class ProcessingSpinner(QWidget):
    """
    Small processing indicator shown while transcription is happening.
    
    Displays a subtle spinning animation.
    """
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        
        self.setFixedSize(48, 48)
        
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)
        self._timer.setInterval(16)
    
    def show_at(self, x: int, y: int) -> None:
        """Show spinner at position."""
        self.move(x, y)
        self._angle = 0
        self._timer.start()
        self.show()
    
    def hide_spinner(self) -> None:
        """Hide the spinner."""
        self._timer.stop()
        self.hide()
    
    def _rotate(self) -> None:
        """Update rotation angle."""
        self._angle = (self._angle + 8) % 360
        self.update()
    
    def paintEvent(self, event) -> None:
        """Paint the spinner."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Background circle
        bg_color = QColor(28, 28, 30, 230)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg_color)
        painter.drawEllipse(4, 4, 40, 40)
        
        # Spinning arc
        painter.translate(24, 24)
        painter.rotate(self._angle)
        
        arc_color = ACCENT_COLOR
        painter.setPen(QPen(arc_color, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        
        # Draw arc (270 degrees)
        painter.drawArc(-12, -12, 24, 24, 0, 270 * 16)
        
        painter.end()


# Need to import QPen for ProcessingSpinner
from PySide6.QtGui import QPen
