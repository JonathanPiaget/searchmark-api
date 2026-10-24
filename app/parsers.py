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


CATCH_ALL_WORDS = ("trier", "divers", "misc", "unsorted")


def firefox_leaves(path: str | Path) -> list[tuple[str, str]]:
    """Return (url, parent folder path) for every http(s) bookmark of a Firefox JSON export.

    Bookmarks under a catch-all folder (any ancestor title containing one of
    CATCH_ALL_WORDS) are skipped: they carry no meaningful expected folder.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    leaves: list[tuple[str, str]] = []

    def walk(node: dict[str, Any], parents: list[str]) -> None:
        for child in node.get("children") or []:
            if child.get("type") == MOZ_FOLDER_TYPE:
                title = child.get("title") or ""
                if not any(w in title.lower() for w in CATCH_ALL_WORDS):
                    walk(child, [*parents, title])
            elif str(child.get("uri", "")).startswith(("http://", "https://")):
                leaves.append((child["uri"], "/".join(parents)))

    walk(data, [])
    return leaves
