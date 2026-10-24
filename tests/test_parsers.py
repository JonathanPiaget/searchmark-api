import json

from app.parsers import firefox_leaves, folders_to_json, parse_bookmarks_file
from app.schemas.analyze import Folder

FIREFOX_EXPORT = {
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
        data = FIREFOX_EXPORT
        path = tmp_path / "bookmarks.json"
        path.write_text(json.dumps(data))

        folders = parse_bookmarks_file(path)
        assert len(folders) == 1
        assert folders[0].name == "menu"
        assert folders[0].id == "menu________"
        assert len(folders[0].children) == 1
        assert folders[0].children[0].name == "Dev"
        assert folders[0].children[0].children == []


class TestFirefoxLeaves:
    def test_leaves_with_parent_path(self, tmp_path):
        data = json.loads(json.dumps(FIREFOX_EXPORT))
        dev = data["children"][0]["children"][0]
        dev["children"] += [
            {"type": "text/x-moz-place", "uri": "place:sort=8", "title": "Smart"},
            {
                "guid": "m",
                "title": "À trier",
                "type": "text/x-moz-place-container",
                "children": [
                    {"type": "text/x-moz-place", "uri": "https://skip.me", "title": "x"},
                    {
                        "guid": "n",
                        "title": "Nested",
                        "type": "text/x-moz-place-container",
                        "children": [{"type": "text/x-moz-place", "uri": "https://skip.too", "title": "y"}],
                    },
                ],
            },
        ]
        path = tmp_path / "bookmarks.json"
        path.write_text(json.dumps(data))

        assert firefox_leaves(path) == [("https://example.com", "menu/Dev")]


class TestFoldersToJson:
    def test_roundtrip(self):
        folders = [Folder(id="1", name="Dev", children=[Folder(id="2", name="Python")])]
        result = json.loads(folders_to_json(folders))
        assert result[0]["name"] == "Dev"
        assert result[0]["children"][0]["name"] == "Python"
