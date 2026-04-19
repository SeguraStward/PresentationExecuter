from pathlib import Path

import vlc
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QKeyEvent
from PyQt6.QtWidgets import (
    QLabel,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from src.models.project import Project
from src.widgets.video_widget import VideoWidget

_CHECKPOINT_LOOKAHEAD_MS = 80  # trigger pause this many ms before checkpoint


class PresenterWindow(QMainWindow):
    """
    Fullscreen presentation window.

    - Video plays fullscreen.
    - At each checkpoint the video auto-pauses and shows an overlay.
    - Space / Tab resumes to the next checkpoint.
    - ESC exits.
    """

    presentation_ended = pyqtSignal()

    def __init__(self, project: Project, vlc_instance: vlc.Instance, parent=None):
        super().__init__(parent)
        self._project = project
        self._vlc_instance = vlc_instance
        self._checkpoints_ms: list[int] = list(project.checkpoints_ms)
        self._checkpoint_index: int = 0
        self._paused_at_checkpoint: bool = False

        self._build_ui()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.showFullScreen()

        # Delay VLC attachment until fullscreen transition completes
        QTimer.singleShot(200, self._attach_and_play)

        # Checkpoint polling timer (50ms for tighter accuracy)
        self._check_timer = QTimer(self)
        self._check_timer.setInterval(50)
        self._check_timer.timeout.connect(self._check_checkpoint)

    # ------------------------------------------------------------------ #
    # UI construction                                                      #
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        self.setStyleSheet("background: black;")

        # Central stacking container
        self._central = QWidget()
        self._central.setStyleSheet("background: black;")
        self.setCentralWidget(self._central)

        # Video widget fills the entire window
        self._video_widget = VideoWidget(self._vlc_instance, parent=self._central)
        self._video_widget.setGeometry(0, 0, self.width() or 1920, self.height() or 1080)

        # HUD — top-right corner, shows checkpoint counter
        self._hud_label = QLabel(self._central)
        self._hud_label.setStyleSheet(
            "color: rgba(255,255,255,180);"
            "background: rgba(0,0,0,120);"
            "padding: 4px 10px;"
            "border-radius: 4px;"
            "font-size: 13px;"
        )
        self._hud_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._hud_label.hide()

        # Pause indicator — small red dot, top-left corner
        self._pause_dot = QLabel(self._central)
        self._pause_dot.setFixedSize(14, 14)
        self._pause_dot.setStyleSheet(
            "background: #E53935;"
            "border-radius: 7px;"
        )
        self._pause_dot.hide()

        # End overlay — only used for "Presentation finished" / errors
        self._end_overlay = QWidget(self._central)
        self._end_overlay.setStyleSheet("background: rgba(0,0,0,170);")
        self._end_overlay.hide()

        overlay_layout = QVBoxLayout(self._end_overlay)
        overlay_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        overlay_layout.setSpacing(16)

        self._end_main_label = QLabel("Presentation finished")
        font_main = QFont()
        font_main.setPointSize(36)
        font_main.setBold(True)
        self._end_main_label.setFont(font_main)
        self._end_main_label.setStyleSheet("color: white;")
        self._end_main_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._end_sub_label = QLabel("Press ESC to exit")
        font_sub = QFont()
        font_sub.setPointSize(18)
        self._end_sub_label.setFont(font_sub)
        self._end_sub_label.setStyleSheet("color: rgba(255,255,255,200);")
        self._end_sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        overlay_layout.addWidget(self._end_main_label)
        overlay_layout.addWidget(self._end_sub_label)

        # Connect video signals
        self._video_widget.media_ended.connect(self._on_media_ended)

    # ------------------------------------------------------------------ #
    # Resize handling                                                      #
    # ------------------------------------------------------------------ #

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        w, h = self.width(), self.height()
        self._video_widget.setGeometry(0, 0, w, h)
        self._end_overlay.setGeometry(0, 0, w, h)
        # HUD top-right
        self._hud_label.adjustSize()
        self._hud_label.move(w - self._hud_label.width() - 16, 16)
        # Pause dot top-left
        self._pause_dot.move(16, 16)

    # ------------------------------------------------------------------ #
    # VLC initialization                                                   #
    # ------------------------------------------------------------------ #

    def _attach_and_play(self) -> None:
        self._video_widget.attach_vlc_window()
        if self._project.video_path and Path(self._project.video_path).exists():
            self._video_widget.load_media(self._project.video_path)
            self._video_widget.play()
            self._check_timer.start()
            self._update_hud()
        else:
            self._end_main_label.setText("Video file not found")
            self._end_sub_label.setText(self._project.video_path)
            self._show_end_overlay()

    # ------------------------------------------------------------------ #
    # Checkpoint engine                                                    #
    # ------------------------------------------------------------------ #

    def _check_checkpoint(self) -> None:
        if self._paused_at_checkpoint:
            return
        if self._checkpoint_index >= len(self._checkpoints_ms):
            return

        current_ms = self._video_widget.get_time_ms()
        if current_ms < 0:
            return

        target_ms = self._checkpoints_ms[self._checkpoint_index]

        if current_ms >= target_ms - _CHECKPOINT_LOOKAHEAD_MS:
            self._video_widget.pause()
            self._video_widget.seek(target_ms)
            self._paused_at_checkpoint = True
            self._pause_dot.show()
            self._pause_dot.raise_()
            self._update_hud()

    def _resume(self) -> None:
        if not self._paused_at_checkpoint:
            return
        self._checkpoint_index += 1
        self._paused_at_checkpoint = False
        self._pause_dot.hide()
        self._update_hud()
        self._video_widget.resume()

    # ------------------------------------------------------------------ #
    # Overlay / badge helpers                                              #
    # ------------------------------------------------------------------ #

    def _show_end_overlay(self) -> None:
        self._end_overlay.setGeometry(0, 0, self.width(), self.height())
        self._end_overlay.show()
        self._end_overlay.raise_()

    def _update_hud(self) -> None:
        total = len(self._checkpoints_ms)
        if total == 0:
            self._hud_label.hide()
            return
        next_idx = self._checkpoint_index + (1 if not self._paused_at_checkpoint else 0)
        if next_idx <= total:
            self._hud_label.setText(f"Checkpoint {next_idx} / {total}")
        else:
            self._hud_label.setText("Last segment")
        self._hud_label.adjustSize()
        self._hud_label.move(self.width() - self._hud_label.width() - 16, 16)
        self._hud_label.show()
        self._hud_label.raise_()

    # ------------------------------------------------------------------ #
    # Media end                                                            #
    # ------------------------------------------------------------------ #

    def _on_media_ended(self) -> None:
        self._check_timer.stop()
        self._pause_dot.hide()
        self._show_end_overlay()

    # ------------------------------------------------------------------ #
    # Key handling                                                         #
    # ------------------------------------------------------------------ #

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key in (Qt.Key.Key_Space, Qt.Key.Key_Tab):
            self._resume()
        elif key == Qt.Key.Key_Escape:
            self._exit_presentation()
        event.accept()  # prevent event reaching VLC

    # ------------------------------------------------------------------ #
    # Exit                                                                 #
    # ------------------------------------------------------------------ #

    def _exit_presentation(self) -> None:
        self._check_timer.stop()
        self._video_widget.cleanup()
        self.close()

    def closeEvent(self, event) -> None:
        self._check_timer.stop()
        self._video_widget.cleanup()
        self.presentation_ended.emit()
        event.accept()
