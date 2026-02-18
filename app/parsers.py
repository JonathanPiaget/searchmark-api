import json
from pathlib import Path

from app.schemas.analyze import Folder


def parse_bookmarks_file(path: str | Path) -> list[Folder]:
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))

    items = data.get("folders", data) if isinstance(data, dict) else data
    return [Folder.model_validate(item) for item in items]


def folders_to_json(folders: list[Folder]) -> str:
    return json.dumps([f.model_dump() for f in folders], indent=2)
