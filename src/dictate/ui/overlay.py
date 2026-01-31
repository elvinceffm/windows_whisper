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
    QFont, QFontDatabase,
)
from PySide6.QtWidgets import (
    QWidget, QGraphicsOpacityEffect, QApplication,
)

import math
from typing import Optional


# UI Constants
PILL_WIDTH = 180
PILL_HEIGHT = 44
CORNER_RADIUS = 22
WAVEFORM_BARS = 5
WAVEFORM_BAR_WIDTH = 4
WAVEFORM_BAR_GAP = 3
WAVEFORM_MAX_HEIGHT = 20
WAVEFORM_MIN_HEIGHT = 4

# Colors
BACKGROUND_COLOR = QColor(28, 28, 30)  # Dark gray
BACKGROUND_COLOR_LIGHT = QColor(242, 242, 247)  # Light gray
ACCENT_COLOR = QColor(255, 59, 48)  # Red (recording)
ACCENT_GLOW = QColor(255, 59, 48, 80)  # Red glow
TEXT_COLOR = QColor(255, 255, 255)
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
        
        Args:
            x: Screen X coordinate
            y: Screen Y coordinate
        """
        self.move(x, y)
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
        """Paint the pill widget."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Colors based on theme
        bg_color = BACKGROUND_COLOR if self._dark_mode else BACKGROUND_COLOR_LIGHT
        text_color = TEXT_COLOR if self._dark_mode else TEXT_COLOR_LIGHT
        
        # Draw background with rounded corners
        path = QPainterPath()
        path.addRoundedRect(
            QRectF(0, 0, self.width(), self.height()),
            CORNER_RADIUS, CORNER_RADIUS
        )
        
        # Glow effect (subtle shadow/glow around pill)
        if self._is_recording:
            glow_color = QColor(ACCENT_COLOR)
            glow_color.setAlphaF(self._glow_intensity * 0.3)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(glow_color)
            
            glow_path = QPainterPath()
            glow_path.addRoundedRect(
                QRectF(-4, -4, self.width() + 8, self.height() + 8),
                CORNER_RADIUS + 4, CORNER_RADIUS + 4
            )
            painter.drawPath(glow_path)
        
        # Background
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg_color)
        painter.drawPath(path)
        
        # Recording indicator dot
        dot_x = 16
        dot_y = self.height() // 2
        dot_radius = 5
        
        # Pulsing red dot
        dot_alpha = 200 + int(55 * self._glow_intensity) if self._is_recording else 200
        dot_color = QColor(ACCENT_COLOR)
        dot_color.setAlpha(dot_alpha)
        painter.setBrush(dot_color)
        painter.drawEllipse(
            QPoint(dot_x, dot_y),
            dot_radius, dot_radius
        )
        
        # Waveform bars
        waveform_start_x = 36
        waveform_center_y = self.height() // 2
        
        bar_color = ACCENT_COLOR if self._is_recording else QColor(128, 128, 128)
        painter.setBrush(bar_color)
        
        for i, height in enumerate(self._bar_heights):
            x = waveform_start_x + i * (WAVEFORM_BAR_WIDTH + WAVEFORM_BAR_GAP)
            y = waveform_center_y - height / 2
            
            bar_path = QPainterPath()
            bar_path.addRoundedRect(
                QRectF(x, y, WAVEFORM_BAR_WIDTH, height),
                WAVEFORM_BAR_WIDTH / 2, WAVEFORM_BAR_WIDTH / 2
            )
            painter.drawPath(bar_path)
        
        # Duration text
        painter.setPen(text_color)
        font = painter.font()
        font.setPointSize(14)
        font.setWeight(QFont.Weight.Medium)
        # Use monospace for stable width
        font.setFamily("Consolas, SF Mono, Monaco, monospace")
        painter.setFont(font)
        
        duration_text = self._format_duration()
        text_x = self.width() - 50
        text_rect = QRectF(text_x, 0, 40, self.height())
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
