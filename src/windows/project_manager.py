from pathlib import Path

import vlc
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.models.project import Project, load_all_projects


class ProjectManagerWindow(QMainWindow):
    def __init__(self, vlc_instance: vlc.Instance, projects_dir: Path):
        super().__init__()
        self._vlc_instance = vlc_instance
        self._projects_dir = projects_dir
        self._projects: list[Project] = []

        # Child windows (kept as attributes to prevent GC)
        self._editor = None
        self._presenter = None

        self._build_ui()
        self._refresh_table()

    # ------------------------------------------------------------------ #
    # UI construction                                                      #
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        self.setWindowTitle("PresentationExecuter")
        self.setMinimumSize(700, 400)
        self.resize(800, 500)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        # Title
        title = QLabel("PresentationExecuter")
        title.setStyleSheet("font-size: 22px; font-weight: bold; margin-bottom: 4px;")
        layout.addWidget(title)

        subtitle = QLabel("Manage your video presentation projects")
        subtitle.setStyleSheet("color: #888; margin-bottom: 8px;")
        layout.addWidget(subtitle)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Name", "Video File", "Checkpoints", "Last Modified"])
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.doubleClicked.connect(self._on_edit)
        self._table.selectionModel().selectionChanged.connect(self._update_button_states)
        layout.addWidget(self._table)

        # Button bar
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self._new_btn = QPushButton("New Project")
        self._new_btn.setFixedHeight(34)
        self._new_btn.clicked.connect(self._on_new)

        self._edit_btn = QPushButton("Edit")
        self._edit_btn.setFixedHeight(34)
        self._edit_btn.setEnabled(False)
        self._edit_btn.clicked.connect(self._on_edit)

        self._present_btn = QPushButton("Present")
        self._present_btn.setFixedHeight(34)
        self._present_btn.setEnabled(False)
        self._present_btn.setStyleSheet(
            "QPushButton { background: #2563EB; color: white; border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background: #1D4ED8; }"
            "QPushButton:disabled { background: #93C5FD; color: white; }"
        )
        self._present_btn.clicked.connect(self._on_present)

        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setFixedHeight(34)
        self._delete_btn.setEnabled(False)
        self._delete_btn.setStyleSheet(
            "QPushButton { background: #DC2626; color: white; border-radius: 4px; }"
            "QPushButton:hover { background: #B91C1C; }"
            "QPushButton:disabled { background: #FCA5A5; color: white; }"
        )
        self._delete_btn.clicked.connect(self._on_delete)

        btn_layout.addWidget(self._new_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self._edit_btn)
        btn_layout.addWidget(self._present_btn)
        btn_layout.addWidget(self._delete_btn)
        layout.addLayout(btn_layout)

    # ------------------------------------------------------------------ #
    # Data                                                                 #
    # ------------------------------------------------------------------ #

    def _refresh_table(self) -> None:
        self._projects = load_all_projects(self._projects_dir)
        self._table.setRowCount(len(self._projects))

        for row, project in enumerate(self._projects):
            video_name = Path(project.video_path).name if project.video_path else "—"
            checkpoint_count = str(len(project.checkpoints))
            last_modified = project.updated_at.strftime("%Y-%m-%d %H:%M")

            self._table.setItem(row, 0, QTableWidgetItem(project.name))
            self._table.setItem(row, 1, QTableWidgetItem(video_name))

            cp_item = QTableWidgetItem(checkpoint_count)
            cp_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 2, cp_item)

            self._table.setItem(row, 3, QTableWidgetItem(last_modified))

        self._update_button_states()

    def _get_selected_project(self) -> "Project | None":
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return None
        idx = rows[0].row()
        if 0 <= idx < len(self._projects):
            return self._projects[idx]
        return None

    def _update_button_states(self) -> None:
        has_selection = self._get_selected_project() is not None
        self._edit_btn.setEnabled(has_selection)
        self._present_btn.setEnabled(has_selection)
        self._delete_btn.setEnabled(has_selection)

    # ------------------------------------------------------------------ #
    # Actions                                                              #
    # ------------------------------------------------------------------ #

    def _on_new(self) -> None:
        name, ok = QInputDialog.getText(self, "New Project", "Project name:")
        if not ok or not name.strip():
            return

        name = name.strip()

        video_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video File",
            "",
            "Video Files (*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.m4v *.mpg *.mpeg);;All Files (*)",
        )
        if not video_path:
            return

        project = Project.new(name, video_path)
        project.save(self._projects_dir)
        self._refresh_table()
        self._open_editor(project)

    def _on_edit(self) -> None:
        project = self._get_selected_project()
        if project:
            self._open_editor(project)

    def _on_present(self) -> None:
        project = self._get_selected_project()
        if project:
            self._open_presenter(project)

    def _on_delete(self) -> None:
        project = self._get_selected_project()
        if not project:
            return

        reply = QMessageBox.question(
            self,
            "Delete Project",
            f'Are you sure you want to delete "{project.name}"?\nThis cannot be undone.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            filepath = self._projects_dir / project.json_filename
            if filepath.exists():
                filepath.unlink()
            self._refresh_table()

    # ------------------------------------------------------------------ #
    # Child window management                                              #
    # ------------------------------------------------------------------ #

    def _open_editor(self, project: Project) -> None:
        from src.windows.editor import EditorWindow

        if self._editor is not None:
            # Stop VLC/timer first to prevent freeze, then close without auto-delete race
            self._editor.shutdown()
            self._editor.hide()
            self._editor.deleteLater()
            self._editor = None

        self._editor = EditorWindow(project, self._vlc_instance, self._projects_dir, parent=None)
        self._editor.project_saved.connect(lambda _: self._refresh_table())
        self._editor.show()

    def _open_presenter(self, project: Project) -> None:
        from src.windows.presenter import PresenterWindow

        if self._presenter is not None:
            self._presenter.close()
            self._presenter = None

        self._presenter = PresenterWindow(project, self._vlc_instance, parent=None)
        self._presenter.show()
