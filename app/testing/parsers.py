"""Parsers for browser bookmark exports."""

import json
import re
import uuid
from html.parser import HTMLParser
from pathlib import Path

from app.schemas.analyze import Folder


class NetscapeBookmarkParser(HTMLParser):
    """Parse Netscape bookmark HTML format (used by Chrome, Firefox, etc.)."""

    def __init__(self):
        super().__init__()
        self.folders: list[Folder] = []
        self.folder_stack: list[Folder] = []
        self.current_folder: Folder | None = None
        self.in_h3 = False
        self.current_text = ""

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "h3":
            self.in_h3 = True
            self.current_text = ""
        elif tag == "dl":
            if self.current_folder:
                self.folder_stack.append(self.current_folder)
                self.current_folder = None

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "h3":
            self.in_h3 = False
            folder_name = self.current_text.strip()
            if folder_name:
                self.current_folder = Folder(
                    id=str(uuid.uuid4()),
                    name=folder_name,
                    children=[],
                )
                if self.folder_stack:
                    self.folder_stack[-1].children.append(self.current_folder)
                else:
                    self.folders.append(self.current_folder)
        elif tag == "dl":
            if self.folder_stack:
                self.current_folder = self.folder_stack.pop()

    def handle_data(self, data):
        if self.in_h3:
            self.current_text += data


def parse_netscape_html(content: str) -> list[Folder]:
    """Parse Netscape bookmark HTML format and extract folder structure.

    This format is used by Chrome, Firefox, Edge, and most browsers
    when exporting bookmarks as HTML.

    Args:
        content: HTML content of the bookmark export

    Returns:
        List of top-level Folder objects with nested children
    """
    parser = NetscapeBookmarkParser()
    parser.feed(content)
    return parser.folders


def parse_chrome_json(data: dict) -> list[Folder]:
    """Parse Chrome bookmark JSON format (from chrome://bookmarks or Bookmarks file).

    Chrome stores bookmarks as JSON with roots like 'bookmark_bar', 'other', 'synced'.

    Args:
        data: Parsed JSON dictionary from Chrome bookmark export

    Returns:
        List of top-level Folder objects with nested children
    """

    def convert_node(node: dict) -> Folder | None:
        if node.get("type") == "folder":
            children = []
            for child in node.get("children", []):
                child_folder = convert_node(child)
                if child_folder:
                    children.append(child_folder)
            return Folder(
                id=node.get("id", str(uuid.uuid4())),
                name=node.get("name", "Unnamed"),
                children=children,
            )
        return None

    folders = []

    if "roots" in data:
        for root_name in ["bookmark_bar", "other", "synced"]:
            root = data["roots"].get(root_name)
            if root:
                folder = convert_node(root)
                if folder and (folder.children or folder.name not in ["Other Bookmarks", "Mobile Bookmarks"]):
                    folders.append(folder)
    elif "children" in data:
        for child in data["children"]:
            folder = convert_node(child)
            if folder:
                folders.append(folder)
    elif "name" in data and "children" in data:
        folder = convert_node(data)
        if folder:
            folders.append(folder)

    return folders


def parse_simple_json(data: list | dict) -> list[Folder]:
    """Parse a simple JSON folder structure.

    Expects either a list of folder objects or a single folder object
    matching the Folder schema.

    Args:
        data: List of folder dicts or single folder dict

    Returns:
        List of Folder objects
    """
    if isinstance(data, dict):
        data = [data]

    folders = []
    for item in data:
        try:
            folders.append(Folder.model_validate(item))
        except Exception:
            continue
    return folders


def parse_bookmarks_file(path: str | Path) -> list[Folder]:
    """Auto-detect and parse a bookmark file.

    Supports:
    - Netscape HTML format (.html, .htm)
    - Chrome JSON format (.json with roots structure)
    - Simple JSON format (.json with Folder schema)

    Args:
        path: Path to the bookmark file

    Returns:
        List of Folder objects representing the folder structure

    Raises:
        ValueError: If the file format cannot be detected or parsed
        FileNotFoundError: If the file does not exist
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Bookmark file not found: {path}")

    content = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()

    if suffix in (".html", ".htm"):
        folders = parse_netscape_html(content)
        if not folders:
            raise ValueError("No folders found in HTML bookmark file")
        return folders

    if suffix == ".json":
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in bookmark file: {e}") from e

        if isinstance(data, dict) and "roots" in data:
            return parse_chrome_json(data)

        return parse_simple_json(data)

    if re.search(r"<!DOCTYPE\s+NETSCAPE-Bookmark-file", content, re.IGNORECASE):
        return parse_netscape_html(content)

    try:
        data = json.loads(content)
        if isinstance(data, dict) and "roots" in data:
            return parse_chrome_json(data)
        return parse_simple_json(data)
    except json.JSONDecodeError:
        pass

    raise ValueError(f"Cannot detect bookmark format for file: {path}")


def folders_to_json(folders: list[Folder]) -> str:
    """Convert folders to JSON string."""
    return json.dumps([f.model_dump() for f in folders], indent=2)


def extract_folder_names(folders: list[Folder], prefix: str = "") -> list[str]:
    """Extract all folder paths from a folder structure.

    Args:
        folders: List of Folder objects
        prefix: Current path prefix

    Returns:
        List of folder paths (e.g., ["Tech", "Tech/Python", "Tech/Python/Libraries"])
    """
    paths = []
    for folder in folders:
        current_path = f"{prefix}/{folder.name}" if prefix else folder.name
        paths.append(current_path)
        if folder.children:
            paths.extend(extract_folder_names(folder.children, current_path))
    return paths
