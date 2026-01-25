"""Tests for bookmark parsing functionality."""

from pathlib import Path

import pytest

from app.testing.parsers import (
    extract_folder_names,
    parse_bookmarks_file,
    parse_chrome_json,
    parse_netscape_html,
    parse_simple_json,
)

FIXTURES_DIR = Path(__file__).parent.parent / "app" / "testing" / "fixtures"


class TestNetscapeHtmlParser:
    """Tests for Netscape HTML bookmark format parsing."""

    def test_parse_simple_structure(self):
        html = """<!DOCTYPE NETSCAPE-Bookmark-file-1>
        <TITLE>Bookmarks</TITLE>
        <H1>Bookmarks</H1>
        <DL><p>
            <DT><H3>Technology</H3>
            <DL><p>
                <DT><H3>Python</H3>
                <DL><p></DL><p>
            </DL><p>
        </DL><p>
        """
        folders = parse_netscape_html(html)
        assert len(folders) == 1
        assert folders[0].name == "Technology"
        assert len(folders[0].children) == 1
        assert folders[0].children[0].name == "Python"

    def test_parse_multiple_top_level_folders(self):
        html = """<!DOCTYPE NETSCAPE-Bookmark-file-1>
        <DL><p>
            <DT><H3>Folder A</H3>
            <DL><p></DL><p>
            <DT><H3>Folder B</H3>
            <DL><p></DL><p>
        </DL><p>
        """
        folders = parse_netscape_html(html)
        assert len(folders) == 2
        assert folders[0].name == "Folder A"
        assert folders[1].name == "Folder B"

    def test_parse_empty_html_returns_empty_list(self):
        folders = parse_netscape_html("")
        assert folders == []


class TestChromeJsonParser:
    """Tests for Chrome JSON bookmark format parsing."""

    def test_parse_chrome_format_with_roots(self):
        data = {
            "roots": {
                "bookmark_bar": {
                    "type": "folder",
                    "name": "Bookmarks Bar",
                    "id": "1",
                    "children": [
                        {
                            "type": "folder",
                            "name": "Tech",
                            "id": "2",
                            "children": [],
                        }
                    ],
                },
                "other": {"type": "folder", "name": "Other Bookmarks", "id": "3", "children": []},
            }
        }
        folders = parse_chrome_json(data)
        assert len(folders) == 1
        assert folders[0].name == "Bookmarks Bar"
        assert len(folders[0].children) == 1
        assert folders[0].children[0].name == "Tech"

    def test_parse_chrome_format_with_children_only(self):
        data = {
            "children": [
                {"type": "folder", "name": "Work", "id": "1", "children": []},
                {"type": "folder", "name": "Personal", "id": "2", "children": []},
            ]
        }
        folders = parse_chrome_json(data)
        assert len(folders) == 2


class TestSimpleJsonParser:
    """Tests for simple JSON folder format parsing."""

    def test_parse_list_of_folders(self):
        data = [
            {"id": "1", "name": "Folder 1", "children": []},
            {"id": "2", "name": "Folder 2", "children": []},
        ]
        folders = parse_simple_json(data)
        assert len(folders) == 2
        assert folders[0].name == "Folder 1"

    def test_parse_single_folder_dict(self):
        data = {"id": "1", "name": "Single Folder", "children": []}
        folders = parse_simple_json(data)
        assert len(folders) == 1
        assert folders[0].name == "Single Folder"

    def test_parse_nested_folders(self):
        data = [
            {
                "id": "1",
                "name": "Parent",
                "children": [{"id": "2", "name": "Child", "children": []}],
            }
        ]
        folders = parse_simple_json(data)
        assert len(folders) == 1
        assert folders[0].name == "Parent"
        assert len(folders[0].children) == 1
        assert folders[0].children[0].name == "Child"


class TestParseBookmarksFile:
    """Tests for auto-detection bookmark file parsing."""

    def test_parse_json_fixture(self):
        path = FIXTURES_DIR / "sample_bookmarks.json"
        if path.exists():
            folders = parse_bookmarks_file(path)
            assert len(folders) > 0
            folder_names = [f.name for f in folders]
            assert "Technology" in folder_names

    def test_parse_html_fixture(self):
        path = FIXTURES_DIR / "sample_bookmarks.html"
        if path.exists():
            folders = parse_bookmarks_file(path)
            assert len(folders) > 0
            folder_names = [f.name for f in folders]
            assert "Technology" in folder_names

    def test_file_not_found_raises_error(self):
        with pytest.raises(FileNotFoundError):
            parse_bookmarks_file("/nonexistent/file.json")


class TestExtractFolderNames:
    """Tests for folder path extraction."""

    def test_extract_flat_folders(self):
        data = [
            {"id": "1", "name": "A", "children": []},
            {"id": "2", "name": "B", "children": []},
        ]
        folders = parse_simple_json(data)
        paths = extract_folder_names(folders)
        assert paths == ["A", "B"]

    def test_extract_nested_folders(self):
        data = [
            {
                "id": "1",
                "name": "Parent",
                "children": [
                    {
                        "id": "2",
                        "name": "Child",
                        "children": [{"id": "3", "name": "Grandchild", "children": []}],
                    }
                ],
            }
        ]
        folders = parse_simple_json(data)
        paths = extract_folder_names(folders)
        assert paths == ["Parent", "Parent/Child", "Parent/Child/Grandchild"]
