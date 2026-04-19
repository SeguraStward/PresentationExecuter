from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QSlider, QWidget

_CHECKPOINT_COLOR = QColor("#FF6B35")
_CHECKPOINT_WIDTH = 3
_CHECKPOINT_HEIGHT_FRAC = 0.7  # fraction of slider height


class TimelineBar(QSlider):
    """
    A horizontal QSlider that paints checkpoint tick marks.

    Anti-feedback-loop pattern:
      - Set user_dragging=True on sliderPressed
      - Set user_dragging=False on sliderReleased
      - Only update position from external code when not user_dragging
      - Emit `seeked(ms)` only on sliderReleased
    """

    seeked = pyqtSignal(int)  # emitted with time_ms when user releases the slider

    def __init__(self, parent: QWidget = None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setRange(0, 1000)  # permille resolution
        self.setFixedHeight(24)

        self._checkpoints_permille: list[int] = []  # 0–1000
        self._duration_ms: int = 0
        self.user_dragging: bool = False

        self.sliderPressed.connect(self._on_pressed)
        self.sliderReleased.connect(self._on_released)

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def set_checkpoints(self, checkpoints_ms: list, duration_ms: int) -> None:
        self._duration_ms = duration_ms
        if duration_ms > 0:
            self._checkpoints_permille = [
                int(ms / duration_ms * 1000) for ms in checkpoints_ms
            ]
        else:
            self._checkpoints_permille = []
        self.update()

    def set_position(self, time_ms: int) -> None:
        """Update slider position from external source (e.g. VLC poll)."""
        if self.user_dragging:
            return
        if self._duration_ms > 0:
            value = int(time_ms / self._duration_ms * 1000)
            self.setValue(min(1000, max(0, value)))

    def get_time_ms(self) -> int:
        """Convert current slider value back to milliseconds."""
        if self._duration_ms <= 0:
            return 0
        return int(self.value() / 1000 * self._duration_ms)

    # ------------------------------------------------------------------ #
    # Slider event handlers                                                #
    # ------------------------------------------------------------------ #

    def _on_pressed(self) -> None:
        self.user_dragging = True

    def _on_released(self) -> None:
        self.user_dragging = False
        self.seeked.emit(self.get_time_ms())

    # ------------------------------------------------------------------ #
    # Paint checkpoint markers                                             #
    # ------------------------------------------------------------------ #

    def paintEvent(self, event) -> None:
        super().paintEvent(event)

        if not self._checkpoints_permille:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        pen = QPen(_CHECKPOINT_COLOR, _CHECKPOINT_WIDTH)
        painter.setPen(pen)

        h = self.height()
        marker_top = int(h * (1 - _CHECKPOINT_HEIGHT_FRAC) / 2)
        marker_bottom = h - marker_top

        # Account for the slider groove margins (approx 8px each side on most styles)
        margin = 8
        available_width = self.width() - 2 * margin

        for permille in self._checkpoints_permille:
            x = margin + int(permille / 1000 * available_width)
            painter.drawLine(x, marker_top, x, marker_bottom)

        painter.end()
