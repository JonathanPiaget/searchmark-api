import json

from app.parsers import folders_to_json, parse_bookmarks_file
from app.schemas.analyze import Folder


class TestParseBookmarksFile:
    def test_parse_list_format(self, tmp_path):
        data = [{"id": "1", "name": "Dev"}, {"id": "2", "name": "News"}]
        path = tmp_path / "bookmarks.json"
        path.write_text(json.dumps(data))

        folders = parse_bookmarks_file(path)
        assert len(folders) == 2
        assert folders[0].name == "Dev"

    def test_parse_dict_with_folders_key(self, tmp_path):
        data = {"folders": [{"id": "1", "name": "Dev"}]}
        path = tmp_path / "bookmarks.json"
        path.write_text(json.dumps(data))

        folders = parse_bookmarks_file(path)
        assert len(folders) == 1

    def test_nested_children(self, tmp_path):
        data = [{"id": "1", "name": "Dev", "children": [{"id": "2", "name": "Python"}]}]
        path = tmp_path / "bookmarks.json"
        path.write_text(json.dumps(data))

        folders = parse_bookmarks_file(path)
        assert len(folders[0].children) == 1
        assert folders[0].children[0].name == "Python"

    def test_parse_firefox_places_format(self, tmp_path):
        data = {
            "guid": "root________",
            "title": "",
            "type": "text/x-moz-place-container",
            "children": [
                {
                    "guid": "menu________",
                    "title": "menu",
                    "type": "text/x-moz-place-container",
                    "children": [
                        {
                            "guid": "abc",
                            "title": "Dev",
                            "type": "text/x-moz-place-container",
                            "children": [
                                {
                                    "guid": "xyz",
                                    "title": "Example",
                                    "type": "text/x-moz-place",
                                    "uri": "https://example.com",
                                }
                            ],
                        }
                    ],
                },
            ],
        }
        path = tmp_path / "bookmarks.json"
        path.write_text(json.dumps(data))

        folders = parse_bookmarks_file(path)
        assert len(folders) == 1
        assert folders[0].name == "menu"
        assert folders[0].id == "menu________"
        assert len(folders[0].children) == 1
        assert folders[0].children[0].name == "Dev"
        assert folders[0].children[0].children == []


class TestFoldersToJson:
    def test_roundtrip(self):
        folders = [Folder(id="1", name="Dev", children=[Folder(id="2", name="Python")])]
        result = json.loads(folders_to_json(folders))
        assert result[0]["name"] == "Dev"
        assert result[0]["children"][0]["name"] == "Python"
