import json
from pathlib import Path
from typing import Any

from app.schemas.analyze import Folder

MOZ_FOLDER_TYPE = "text/x-moz-place-container"


def parse_bookmarks_file(path: str | Path) -> list[Folder]:
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))

    if isinstance(data, dict) and data.get("type") == MOZ_FOLDER_TYPE:
        return _moz_children_to_folders(data)

    items = data.get("folders", data) if isinstance(data, dict) else data
    return [Folder.model_validate(item) for item in items]


def _moz_children_to_folders(node: dict[str, Any]) -> list[Folder]:
    folders: list[Folder] = []
    for child in node.get("children") or []:
        if child.get("type") != MOZ_FOLDER_TYPE:
            continue
        folders.append(
            Folder(
                id=child.get("guid") or "",
                name=child.get("title") or "",
                children=_moz_children_to_folders(child),
            )
        )
    return folders


def folders_to_json(folders: list[Folder]) -> str:
    return json.dumps([f.model_dump() for f in folders], indent=2)
