import os
import sys
import ctypes
import platform
import glob

# CRITICAL: XInitThreads must be called BEFORE any Qt or VLC imports on Linux
if platform.system() == "Linux":
    try:
        ctypes.CDLL("libX11.so.6").XInitThreads()
    except OSError:
        pass

    # On Wayland, VLC's set_xwindow() requires X11/XWayland.
    # Force Qt to use the xcb platform for proper VLC video embedding.
    if os.environ.get("XDG_SESSION_TYPE") == "wayland":
        os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

        # libxcb-cursor0 is required by Qt's xcb plugin (since Qt 6.5).
        # If not installed system-wide, try to preload from snap packages.
        if not os.environ.get("LD_PRELOAD", ""):
            candidates = glob.glob(
                "/snap/*/current/usr/lib/x86_64-linux-gnu/libxcb-cursor.so.0"
            ) + glob.glob(
                "/snap/*/[0-9]*/usr/lib/x86_64-linux-gnu/libxcb-cursor.so.0"
            )
            if candidates:
                os.environ["LD_PRELOAD"] = candidates[0]
                # Re-exec with the preloaded library
                os.execvp(sys.executable, [sys.executable] + sys.argv)

import vlc  # noqa: E402

from pathlib import Path
from PyQt6.QtWidgets import QApplication
from src.windows.project_manager import ProjectManagerWindow


def main():
    vlc_instance = vlc.Instance("--no-xlib")

    app = QApplication(sys.argv)
    app.setApplicationName("PresentationExecuter")
    app.setStyle("Fusion")

    projects_dir = Path(__file__).parent / "projects"
    projects_dir.mkdir(exist_ok=True)

    window = ProjectManagerWindow(vlc_instance, projects_dir)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
