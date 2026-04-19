import sys

import vlc
from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QFrame, QWidget


class VideoWidget(QFrame):
    """
    A QFrame that embeds a VLC MediaPlayer for video playback.

    Usage:
        widget = VideoWidget(vlc_instance, parent)
        widget.show()                        # must be shown before attaching
        widget.attach_vlc_window()           # or call via QTimer.singleShot(100, ...)
        widget.load_media("/path/to/video")
        widget.play()
    """

    time_changed = pyqtSignal(int)   # current position in ms
    state_changed = pyqtSignal(int)  # vlc.State integer value
    media_ended = pyqtSignal()
    length_ready = pyqtSignal(int)   # emitted once when duration becomes known

    def __init__(self, vlc_instance: vlc.Instance, parent: QWidget = None):
        super().__init__(parent)
        self.setMinimumSize(320, 180)
        self.setStyleSheet("background: black;")

        self._instance = vlc_instance
        self._player: vlc.MediaPlayer = vlc_instance.media_player_new()

        # Disable VLC's own input handling so Qt receives key/mouse events
        self._player.video_set_key_input(False)
        self._player.video_set_mouse_input(False)

        self._last_time: int = -1
        self._last_state = vlc.State.NothingSpecial
        self._length_emitted: bool = False

        # Polling timer — drives all UI updates (never use VLC event callbacks)
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(100)
        self._poll_timer.timeout.connect(self._poll)
        self._poll_timer.start()

    # ------------------------------------------------------------------ #
    # VLC window attachment                                                #
    # ------------------------------------------------------------------ #

    def attach_vlc_window(self) -> None:
        """Attach VLC renderer to this widget's native window handle.
        Must be called AFTER the widget is shown (winId() must be valid).
        """
        win_id = int(self.winId())
        if sys.platform == "linux":
            # On Wayland, set_xwindow may fail with XCB errors.
            # Force Qt to use X11 (via QT_QPA_PLATFORM=xcb in main.py) for
            # reliable VLC XEmbed. Fallback: try set_xwindow anyway.
            self._player.set_xwindow(win_id)
        elif sys.platform == "win32":
            self._player.set_hwnd(win_id)
        elif sys.platform == "darwin":
            self._player.set_nsobject(win_id)

    # ------------------------------------------------------------------ #
    # Media control                                                        #
    # ------------------------------------------------------------------ #

    def load_media(self, video_path: str) -> None:
        media = self._instance.media_new(video_path)
        self._player.set_media(media)
        self._length_emitted = False
        self._last_time = -1

    def play(self) -> None:
        self._player.play()

    def pause(self) -> None:
        """Deterministically pause (not a toggle)."""
        self._player.set_pause(1)

    def resume(self) -> None:
        """Deterministically resume (not a toggle)."""
        self._player.set_pause(0)

    def stop(self) -> None:
        self._player.stop()

    def cleanup(self) -> None:
        """Stop the poll timer first, then the player. Call before destroying the widget."""
        self._poll_timer.stop()
        self._player.stop()

    def seek(self, time_ms: int) -> None:
        self._player.set_time(max(0, time_ms))

    def seek_seconds(self, seconds: float) -> None:
        self.seek(int(seconds * 1000))

    def set_rate(self, rate: float) -> None:
        self._player.set_rate(rate)

    # ------------------------------------------------------------------ #
    # State queries                                                        #
    # ------------------------------------------------------------------ #

    def get_time_ms(self) -> int:
        return self._player.get_time()

    def get_length_ms(self) -> int:
        return self._player.get_length()

    def get_state(self) -> vlc.State:
        return self._player.get_state()

    def is_playing(self) -> bool:
        return self._player.is_playing() == 1

    # ------------------------------------------------------------------ #
    # Internal polling (runs every 100ms)                                  #
    # ------------------------------------------------------------------ #

    def _poll(self) -> None:
        t = self._player.get_time()
        if t != self._last_time:
            self._last_time = t
            self.time_changed.emit(t)

        state = self._player.get_state()
        if state != self._last_state:
            self._last_state = state
            # python-vlc State enum .value can be bytes on some versions;
            # convert safely to int for the signal.
            try:
                state_int = state.value
                if isinstance(state_int, bytes):
                    state_int = int.from_bytes(state_int, byteorder="little")
                else:
                    state_int = int(state_int)
            except (ValueError, TypeError):
                state_int = -1
            self.state_changed.emit(state_int)
            if state == vlc.State.Ended:
                self.media_ended.emit()

        # Emit length once it becomes available
        if not self._length_emitted:
            length = self._player.get_length()
            if length > 0:
                self._length_emitted = True
                self.length_ready.emit(length)

    # ------------------------------------------------------------------ #
    # Qt overrides                                                         #
    # ------------------------------------------------------------------ #

    def paintEvent(self, event) -> None:
        """Fill black when no video is rendered to avoid grey flicker."""
        if not self.is_playing():
            painter = QPainter(self)
            painter.fillRect(self.rect(), self.palette().window())
        super().paintEvent(event)
