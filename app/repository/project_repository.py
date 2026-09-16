"""プロジェクトの永続化（設計書 17.7）。

1プロジェクト = 1つのJSONファイルとして保存する。
"""

from __future__ import annotations

import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _standalone_data_dir() -> Path:
    """スタンドアロンアプリでの保存先。OSごとの標準的なアプリデータ置き場を使う。"""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "GuitarTabMaker" / "projects"
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        return base / "GuitarTabMaker" / "projects"
    # Linux 等
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "GuitarTabMaker" / "projects"


def default_data_dir() -> Path:
    configured = os.environ.get("TAB_MAKER_DATA_DIR")
    if configured:
        return Path(configured).expanduser()
    if getattr(sys, "frozen", False):
        # スタンドアロンアプリでは、インストール場所によらず同じ場所にプロジェクトを保存する
        return _standalone_data_dir()
    return Path(__file__).resolve().parents[2] / "data" / "projects"


class ProjectRepository:
    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = Path(base_dir) if base_dir else default_data_dir()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, project_id: str) -> Path:
        if not PROJECT_ID_PATTERN.match(project_id):
            raise ValueError(f"invalid project id: {project_id}")
        return self.base_dir / f"{project_id}.json"

    def _write(self, project: dict[str, Any]) -> dict[str, Any]:
        path = self._path(project["projectId"])
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, path)
        return project

    def list(self) -> list[dict[str, Any]]:
        summaries: list[dict[str, Any]] = []
        for path in self.base_dir.glob("*.json"):
            try:
                project = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            summaries.append(
                {
                    "projectId": project.get("projectId", path.stem),
                    "name": project.get("name", "無題のプロジェクト"),
                    "createdAt": project.get("createdAt"),
                    "updatedAt": project.get("updatedAt"),
                    "noteCount": len(project.get("notes", [])),
                    "measureCount": len(project.get("measures", [])),
                    "hasGeneratedTab": bool(project.get("generatedTab")),
                }
            )
        summaries.sort(key=lambda item: item.get("updatedAt") or "", reverse=True)
        return summaries

    def create(
        self,
        name: str,
        notes: list[dict] | None = None,
        measures: list[dict] | None = None,
        settings: dict | None = None,
    ) -> dict[str, Any]:
        timestamp = _now()
        project = {
            "projectId": uuid.uuid4().hex,
            "name": name or "無題のプロジェクト",
            "createdAt": timestamp,
            "updatedAt": timestamp,
            "measures": measures if measures is not None else [
                {"measureIndex": 0, "keySignature": "C", "timeSignature": "4/4"},
                {"measureIndex": 1, "keySignature": "C", "timeSignature": "4/4"},
            ],
            "notes": notes or [],
            "settings": settings or {},
            "generatedTab": None,
        }
        return self._write(project)

    def get(self, project_id: str) -> dict[str, Any] | None:
        try:
            path = self._path(project_id)
        except ValueError:
            return None
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def update(self, project_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        project = self.get(project_id)
        if project is None:
            return None
        for key in ("name", "notes", "measures", "settings", "generatedTab"):
            if key in patch and patch[key] is not None:
                project[key] = patch[key]
        project["updatedAt"] = _now()
        return self._write(project)

    def delete(self, project_id: str) -> bool:
        try:
            path = self._path(project_id)
        except ValueError:
            return False
        if not path.exists():
            return False
        path.unlink()
        return True

    def duplicate(self, project_id: str, new_name: str | None = None) -> dict[str, Any] | None:
        source = self.get(project_id)
        if source is None:
            return None
        timestamp = _now()
        copy = dict(source)
        copy["projectId"] = uuid.uuid4().hex
        copy["name"] = new_name or f"{source['name']} のコピー"
        copy["createdAt"] = timestamp
        copy["updatedAt"] = timestamp
        return self._write(copy)
