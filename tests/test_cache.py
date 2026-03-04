from app.cache import _cache_key


class TestCacheKey:
    def test_deterministic(self):
        assert _cache_key("https://example.com") == _cache_key("https://example.com")

    def test_different_urls_different_keys(self):
        assert _cache_key("https://a.com") != _cache_key("https://b.com")

    def test_prefix(self):
        assert _cache_key("https://example.com").startswith("analysis:")
