import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import _folder_paths, app, resolve_folder_path, validate_url

client = TestClient(app)


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
