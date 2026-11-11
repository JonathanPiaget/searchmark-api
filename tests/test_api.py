import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import main
from app.main import _folder_paths, app, resolve_folder_path, validate_url
from app.schemas.analyze import AnalyzeUrlResponse

client = TestClient(app)

ANALYSIS_JSON = '{"url": "https://x", "title": "T", "summary": "S"}'


class FakeResponse:
    """The parts of a LiteLLM ModelResponse that _complete reads."""

    def __init__(self, content: str, cost: float | None = None):
        self._hidden_params = {"response_cost": cost}
        self.choices = [SimpleNamespace(message=SimpleNamespace(content=content))]


@pytest.fixture
def llm(monkeypatch):
    """Replace acompletion with a stub returning `response`; returns the list of recorded call kwargs."""
    calls: list[dict] = []

    def install(response):
        async def acompletion(**kwargs):
            calls.append(kwargs)
            return response

        monkeypatch.setattr(main, "acompletion", acompletion)
        return calls

    return install


class TestWelcome:
    def test_returns_app_info(self):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "SearchMark API"
        assert "version" in data

    def test_health(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestValidateUrl:
    def test_valid_https(self):
        validate_url("https://example.com")  # should not raise

    def test_valid_http(self):
        validate_url("http://example.com")  # should not raise

    def test_rejects_ftp(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_url("ftp://example.com")
        assert exc_info.value.status_code == 400

    def test_rejects_localhost(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_url("http://localhost/secret")
        assert exc_info.value.status_code == 403

    def test_rejects_127(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_url("http://127.0.0.1/admin")
        assert exc_info.value.status_code == 403

    def test_rejects_ipv6_loopback(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_url("http://[::1]/admin")
        assert exc_info.value.status_code == 403


class TestRecommendEndpoint:
    def test_missing_url(self):
        resp = client.post("/recommend", json={})
        assert resp.status_code == 422

    def test_too_many_folders(self):
        folders = [{"id": str(i), "name": f"f{i}"} for i in range(main.MAX_FOLDERS + 1)]
        resp = client.post("/recommend", json={"url": "https://example.com", "folders": folders})
        assert resp.status_code == 413


class TestComplete:
    def test_bounded_call_and_parsed_result(self, llm):
        calls = llm(FakeResponse(ANALYSIS_JSON))
        result = asyncio.run(main._complete([], AnalyzeUrlResponse))
        assert result.title == "T"
        assert calls[0]["max_tokens"] == 1000
        assert calls[0]["timeout"] == 30

    def test_alert_when_cost_above_threshold(self, llm, monkeypatch):
        alerts: list[str] = []
        monkeypatch.setattr(main.sentry_sdk, "capture_message", alerts.append)
        llm(FakeResponse(ANALYSIS_JSON, cost=main.COST_ALERT_USD * 2))
        asyncio.run(main._complete([], AnalyzeUrlResponse))
        assert len(alerts) == 1

    @pytest.mark.parametrize("cost", [None, 0.0001])
    def test_no_alert_otherwise(self, llm, monkeypatch, cost):
        alerts: list[str] = []
        monkeypatch.setattr(main.sentry_sdk, "capture_message", alerts.append)
        llm(FakeResponse(ANALYSIS_JSON, cost=cost))
        asyncio.run(main._complete([], AnalyzeUrlResponse))
        assert alerts == []


class TestRecommendationPrompt:
    def test_folder_tree_before_page_analysis(self, llm):
        calls = llm(FakeResponse('{"reasoning": "r", "recommended_folder": "toolbar/A"}'))
        analysis = AnalyzeUrlResponse(url="https://x", title="T", summary="S")
        folders = json.dumps([{"id": "1", "name": "toolbar", "children": [{"id": "2", "name": "A", "children": []}]}])
        rec = asyncio.run(main.get_folder_recommendation(analysis, folders))
        tree, page = calls[0]["messages"][1]["content"]
        assert "Folder Structure" in tree["text"]
        assert "Webpage Analysis" in page["text"]
        # the cache stops after the tree, so another page with the same tree is a cache hit
        assert tree["prompt_cache_breakpoint"] == {"mode": "explicit"}
        assert "prompt_cache_breakpoint" not in page
        assert calls[0]["extra_body"] == {"prompt_cache_options": {"mode": "explicit"}}
        assert rec.recommended_folder == "toolbar/A"


class TestResolveFolderPath:
    paths = _folder_paths([
        {
            "name": "toolbar",
            "children": [
                {"name": "Computing", "children": [{"name": "Design", "children": [{"name": "Colors"}]}]},
                {"name": "Django", "children": [{"name": "Librairies - apps", "children": [{"name": "Shell"}]}]},
                {"name": "Privé", "children": [{"name": "Design"}]},
                {"name": "Articles", "children": [{"name": "Entretien technique / HR"}]},
                {"name": "Management", "children": [{"name": "HR"}]},
            ],
        }
    ])

    def test_exact_path_kept(self):
        assert resolve_folder_path("toolbar/Computing/Design", self.paths) == "toolbar/Computing/Design"

    def test_spaces_around_separator(self):
        assert resolve_folder_path("toolbar / Django / Librairies - apps / Shell", self.paths) == (
            "toolbar/Django/Librairies - apps/Shell"
        )

    def test_missing_root(self):
        assert resolve_folder_path("Computing/Design/Colors", self.paths) == "toolbar/Computing/Design/Colors"

    def test_skipped_level(self):
        assert resolve_folder_path("toolbar/Design/Colors", self.paths) == "toolbar/Computing/Design/Colors"

    def test_slash_in_folder_name(self):
        assert resolve_folder_path("toolbar/Articles/Entretien technique / HR", self.paths) == (
            "toolbar/Articles/Entretien technique / HR"
        )
        assert resolve_folder_path("Management/HR", self.paths) == "toolbar/Management/HR"

    def test_ambiguous_tail_stays_as_given(self):
        assert resolve_folder_path("Design", self.paths) == "Design"

    def test_unknown_path_stays_normalized(self):
        assert resolve_folder_path("Nope / Nowhere", self.paths) == "Nope/Nowhere"
