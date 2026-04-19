import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class Project:
    name: str
    video_path: str
    checkpoints: list  # list[float] — seconds
    created_at: datetime
    updated_at: datetime

    # ------------------------------------------------------------------ #
    # Constructors                                                         #
    # ------------------------------------------------------------------ #

    @classmethod
    def new(cls, name: str, video_path: str) -> "Project":
        now = datetime.now()
        return cls(
            name=name,
            video_path=str(video_path),
            checkpoints=[],
            created_at=now,
            updated_at=now,
        )

    @classmethod
    def load(cls, filepath: Path) -> "Project":
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(
            name=data["name"],
            video_path=data["video_path"],
            checkpoints=data.get("checkpoints", []),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )

    # ------------------------------------------------------------------ #
    # Persistence                                                          #
    # ------------------------------------------------------------------ #

    def save(self, projects_dir: Path) -> None:
        self.updated_at = datetime.now()
        filepath = projects_dir / self.json_filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "video_path": self.video_path,
            "checkpoints": self.checkpoints,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    # ------------------------------------------------------------------ #
    # Checkpoint management                                                #
    # ------------------------------------------------------------------ #

    def add_checkpoint(self, seconds: float) -> None:
        """Insert checkpoint in sorted order, avoid duplicates within 200ms."""
        seconds = round(seconds, 3)
        for existing in self.checkpoints:
            if abs(existing - seconds) < 0.2:
                return
        self.checkpoints.append(seconds)
        self.checkpoints.sort()

    def remove_checkpoint(self, index: int) -> None:
        if 0 <= index < len(self.checkpoints):
            self.checkpoints.pop(index)

    # ------------------------------------------------------------------ #
    # Computed properties                                                  #
    # ------------------------------------------------------------------ #

    @property
    def checkpoints_ms(self) -> list:
        """Checkpoints converted to milliseconds (int) for VLC comparison."""
        return [int(s * 1000) for s in self.checkpoints]

    @property
    def json_filename(self) -> str:
        return self._sanitize_name(self.name) + ".json"

    @staticmethod
    def _sanitize_name(name: str) -> str:
        sanitized = re.sub(r"[^\w\-]", "_", name).lower().strip("_")
        return sanitized or "project"


def load_all_projects(projects_dir: Path) -> list:
    """Load all valid .json project files from projects_dir."""
    projects = []
    for path in sorted(projects_dir.glob("*.json")):
        try:
            projects.append(Project.load(path))
        except Exception:
            pass
    return projects
