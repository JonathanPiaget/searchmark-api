import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app, validate_url

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
