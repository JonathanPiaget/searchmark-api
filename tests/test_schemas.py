import pytest
from pydantic import ValidationError

from app.schemas.analyze import (
    AnalyseUrlRequest,
    AnalyzeUrlResponse,
    ExistingFolderRecommendation,
    Folder,
    NewFolderRecommendation,
    RecommendationResponse,
)


class TestFolder:
    def test_simple_folder(self):
        f = Folder(id="1", name="Dev")
        assert f.id == "1"
        assert f.name == "Dev"
        assert f.children == []

    def test_nested_folders(self):
        f = Folder(id="1", name="Dev", children=[Folder(id="2", name="Python")])
        assert len(f.children) == 1
        assert f.children[0].name == "Python"


class TestAnalyseUrlRequest:
    def test_minimal(self):
        req = AnalyseUrlRequest(url="https://example.com")
        assert req.url == "https://example.com"
        assert req.folders == []
        assert req.create_new_folder is False

    def test_with_folders(self):
        req = AnalyseUrlRequest(
            url="https://example.com",
            folders=[Folder(id="1", name="Dev")],
            create_new_folder=True,
        )
        assert len(req.folders) == 1
        assert req.create_new_folder is True

    def test_missing_url(self):
        with pytest.raises(ValidationError):
            AnalyseUrlRequest()  # type: ignore[missing-argument]


class TestAnalyzeUrlResponse:
    def test_roundtrip_json(self):
        resp = AnalyzeUrlResponse(url="https://example.com", title="Example", summary="A summary")
        parsed = AnalyzeUrlResponse.model_validate_json(resp.model_dump_json())
        assert parsed == resp


class TestRecommendationResponse:
    def test_existing_folder(self):
        resp = RecommendationResponse(
            title="Page",
            summary="Summary",
            reasoning="Best match",
            recommended_folder="Dev/Python",
        )
        assert resp.new_folder_name is None

    def test_new_folder(self):
        resp = RecommendationResponse(
            title="Page",
            summary="Summary",
            reasoning="New category needed",
            recommended_folder="Dev",
            new_folder_name="Rust",
        )
        assert resp.new_folder_name == "Rust"


class TestLLMResponseModels:
    def test_existing_folder_recommendation(self):
        r = ExistingFolderRecommendation(reasoning="Good fit", recommended_folder="Dev/Python")
        assert r.recommended_folder == "Dev/Python"

    def test_new_folder_recommendation(self):
        r = NewFolderRecommendation(reasoning="New topic", recommended_folder="Dev", new_folder_name="Rust")
        assert r.new_folder_name == "Rust"
