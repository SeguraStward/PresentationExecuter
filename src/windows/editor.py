from pathlib import Path

import vlc
from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from src.models.project import Project
from src.widgets.timeline_bar import TimelineBar
from src.widgets.video_widget import VideoWidget

_SPEED_OPTIONS = [("0.25x", 0.25), ("0.5x", 0.5), ("0.75x", 0.75), ("1.0x", 1.0),
                  ("1.25x", 1.25), ("1.5x", 1.5), ("2.0x", 2.0)]
_DEFAULT_SPEED_INDEX = 3  # 1.0x


class EditorWindow(QMainWindow):
    """
    Video editor: load video, play/pause/seek, add checkpoint markers,
    and save the project.
    """

    project_saved = pyqtSignal(object)  # emits updated Project instance

    def __init__(
        self,
        project: Project,
        vlc_instance: vlc.Instance,
        projects_dir: Path,
        parent=None,
    ):
        super().__init__(parent)
        self._project = project
        self._vlc_instance = vlc_instance
        self._projects_dir = projects_dir
        self._dirty = False
        self._duration_ms = 0

        self._build_ui()
        self._connect_signals()
        self.setWindowTitle(f"Editor — {project.name}")
        self.resize(1000, 600)

        # Attach VLC window handle after the widget is shown
        QTimer.singleShot(150, self._init_video)

    # ------------------------------------------------------------------ #
    # UI construction                                                      #
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # ---- Left panel: video + controls ----
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(6)

        self._video_widget = VideoWidget(self._vlc_instance)
        self._video_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        left_layout.addWidget(self._video_widget, stretch=1)  # stretch=1 keeps controls visible

        # Controls row
        controls = QHBoxLayout()
        controls.setSpacing(8)

        self._play_btn = QPushButton("Play")
        self._play_btn.setFixedWidth(70)
        self._play_btn.clicked.connect(self._on_play_pause)

        self._time_label = QLabel("00:00.000 / 00:00.000")
        self._time_label.setStyleSheet("font-family: monospace; font-size: 13px;")

        self._speed_combo = QComboBox()
        for label, _ in _SPEED_OPTIONS:
            self._speed_combo.addItem(label)
        self._speed_combo.setCurrentIndex(_DEFAULT_SPEED_INDEX)
        self._speed_combo.setFixedWidth(70)
        self._speed_combo.currentIndexChanged.connect(self._on_speed_changed)

        self._add_cp_btn = QPushButton("Add Checkpoint Here")
        self._add_cp_btn.setStyleSheet(
            "QPushButton { background: #16A34A; color: white; border-radius: 4px; padding: 4px 10px; font-weight: bold; }"
            "QPushButton:hover { background: #15803D; }"
        )
        self._add_cp_btn.clicked.connect(self._on_add_checkpoint)

        controls.addWidget(self._play_btn)
        controls.addWidget(self._time_label)
        controls.addStretch()
        controls.addWidget(QLabel("Speed:"))
        controls.addWidget(self._speed_combo)
        controls.addWidget(self._add_cp_btn)
        left_layout.addLayout(controls, stretch=0)

        # Timeline bar
        self._timeline = TimelineBar()
        left_layout.addWidget(self._timeline, stretch=0)

        splitter.addWidget(left_panel)

        # ---- Right panel: checkpoint list ----
        right_panel = QWidget()
        right_panel.setMinimumWidth(200)
        right_panel.setMaximumWidth(280)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.setSpacing(6)

        cp_header = QLabel("Checkpoints")
        cp_header.setStyleSheet("font-weight: bold; font-size: 14px;")
        right_layout.addWidget(cp_header)

        self._cp_list = QListWidget()
        self._cp_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._cp_list.customContextMenuRequested.connect(self._on_cp_right_click)
        self._cp_list.itemClicked.connect(self._on_cp_clicked)
        right_layout.addWidget(self._cp_list)

        hint = QLabel("Click → seek  •  Right-click → delete")
        hint.setStyleSheet("color: #888; font-size: 11px;")
        hint.setWordWrap(True)
        right_layout.addWidget(hint)

        self._save_btn = QPushButton("Save Project  (Ctrl+S)")
        self._save_btn.setStyleSheet(
            "QPushButton { background: #2563EB; color: white; border-radius: 4px; padding: 6px; font-weight: bold; }"
            "QPushButton:hover { background: #1D4ED8; }"
        )
        self._save_btn.clicked.connect(self._on_save)
        right_layout.addWidget(self._save_btn)

        splitter.addWidget(right_panel)
        splitter.setSizes([750, 250])

        # Status bar
        self.statusBar().showMessage("Load video to begin")

        # Keyboard shortcut
        from PyQt6.QtGui import QKeySequence, QShortcut
        save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        save_shortcut.activated.connect(self._on_save)

    def _connect_signals(self) -> None:
        self._video_widget.time_changed.connect(self._on_time_changed)
        self._video_widget.state_changed.connect(self._on_state_changed)
        self._video_widget.length_ready.connect(self._on_length_ready)
        self._timeline.seeked.connect(self._on_timeline_seeked)

    # ------------------------------------------------------------------ #
    # Video initialization                                                 #
    # ------------------------------------------------------------------ #

    def _init_video(self) -> None:
        self._video_widget.attach_vlc_window()
        if self._project.video_path and Path(self._project.video_path).exists():
            self._video_widget.load_media(self._project.video_path)
            self.statusBar().showMessage("Video loaded. Press Play to preview.")
        else:
            self.statusBar().showMessage(
                f"⚠ Video file not found: {self._project.video_path}"
            )
        self._refresh_checkpoint_list()

    # ------------------------------------------------------------------ #
    # VLC signal handlers                                                  #
    # ------------------------------------------------------------------ #

    def _on_time_changed(self, time_ms: int) -> None:
        self._timeline.set_position(time_ms)
        length_str = self._format_ms(self._duration_ms) if self._duration_ms > 0 else "??:??.???"
        self._time_label.setText(f"{self._format_ms(time_ms)} / {length_str}")

    def _on_state_changed(self, state_int: int) -> None:
        import vlc as _vlc
        try:
            state = _vlc.State(state_int)
        except (ValueError, TypeError):
            return
        if state == _vlc.State.Playing:
            self._play_btn.setText("Pause")
        else:
            self._play_btn.setText("Play")

    def _on_length_ready(self, length_ms: int) -> None:
        self._duration_ms = length_ms
        self._timeline.set_checkpoints(self._project.checkpoints_ms, length_ms)
        length_str = self._format_ms(length_ms)
        self.statusBar().showMessage(f"Duration: {length_str}  •  Checkpoints: {len(self._project.checkpoints)}")

    # ------------------------------------------------------------------ #
    # Control actions                                                      #
    # ------------------------------------------------------------------ #

    def _on_play_pause(self) -> None:
        if self._video_widget.is_playing():
            self._video_widget.pause()
        else:
            self._video_widget.play()

    def _on_speed_changed(self, index: int) -> None:
        _, rate = _SPEED_OPTIONS[index]
        self._video_widget.set_rate(rate)

    def _on_timeline_seeked(self, time_ms: int) -> None:
        self._video_widget.seek(time_ms)

    # ------------------------------------------------------------------ #
    # Checkpoint actions                                                   #
    # ------------------------------------------------------------------ #

    def _on_add_checkpoint(self) -> None:
        t_ms = self._video_widget.get_time_ms()
        if t_ms < 0:
            self.statusBar().showMessage("No video loaded.")
            return
        self._project.add_checkpoint(t_ms / 1000.0)
        self._dirty = True
        self._refresh_checkpoint_list()
        self._timeline.set_checkpoints(self._project.checkpoints_ms, self._duration_ms)
        self.statusBar().showMessage(
            f"Checkpoint added at {self._format_ms(t_ms)}  •  Total: {len(self._project.checkpoints)}"
        )

    def _on_cp_clicked(self, item: QListWidgetItem) -> None:
        index = self._cp_list.row(item)
        if 0 <= index < len(self._project.checkpoints):
            self._video_widget.seek_seconds(self._project.checkpoints[index])

    def _on_cp_right_click(self, pos) -> None:
        item = self._cp_list.itemAt(pos)
        if item is None:
            return
        index = self._cp_list.row(item)
        menu = QMenu(self)
        seek_action = menu.addAction("Seek Here")
        delete_action = menu.addAction("Delete")
        action = menu.exec(self._cp_list.viewport().mapToGlobal(pos))
        if action == seek_action:
            if 0 <= index < len(self._project.checkpoints):
                self._video_widget.seek_seconds(self._project.checkpoints[index])
        elif action == delete_action:
            self._on_delete_checkpoint(index)

    def _on_delete_checkpoint(self, index: int) -> None:
        self._project.remove_checkpoint(index)
        self._dirty = True
        self._refresh_checkpoint_list()
        self._timeline.set_checkpoints(self._project.checkpoints_ms, self._duration_ms)

    def _refresh_checkpoint_list(self) -> None:
        self._cp_list.clear()
        for i, seconds in enumerate(self._project.checkpoints):
            ms = int(seconds * 1000)
            label = f"{i + 1:02d}  →  {self._format_ms(ms)}"
            self._cp_list.addItem(label)

    # ------------------------------------------------------------------ #
    # Save                                                                 #
    # ------------------------------------------------------------------ #

    def _on_save(self) -> None:
        self._project.save(self._projects_dir)
        self._dirty = False
        self.statusBar().showMessage("Project saved.")
        self.project_saved.emit(self._project)

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _format_ms(ms: int) -> str:
        """Format milliseconds as MM:SS.mmm"""
        if ms < 0:
            return "00:00.000"
        total_seconds = ms // 1000
        millis = ms % 1000
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes:02d}:{seconds:02d}.{millis:03d}"

    # ------------------------------------------------------------------ #
    # Shutdown (called externally before replacing the window)             #
    # ------------------------------------------------------------------ #

    def shutdown(self) -> None:
        """Stop VLC and timer without triggering the unsaved-changes dialog."""
        self._video_widget.cleanup()

    # ------------------------------------------------------------------ #
    # Close handling                                                       #
    # ------------------------------------------------------------------ #

    def closeEvent(self, event) -> None:
        if self._dirty:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Save before closing?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
            )
            if reply == QMessageBox.StandardButton.Save:
                self._on_save()
            elif reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
        self._video_widget.cleanup()
        event.accept()
