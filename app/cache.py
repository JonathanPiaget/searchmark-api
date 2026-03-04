"""Valkey/Redis cache for URL analysis results."""

import contextlib
import hashlib
import os

import redis.asyncio as redis
from redis.exceptions import RedisError

from app.schemas.analyze import AnalyzeUrlResponse

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
ANALYSIS_TTL = 60 * 60  # 1 hour

_client: redis.Redis | None = None


def _get_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(REDIS_URL, decode_responses=True)
    return _client


def _cache_key(url: str) -> str:
    return f"analysis:{hashlib.sha256(url.encode()).hexdigest()}"


async def get_analysis(url: str) -> AnalyzeUrlResponse | None:
    """Return cached analysis for a URL, or None on miss/error."""
    try:
        data = await _get_client().get(_cache_key(url))
        if data is not None:
            return AnalyzeUrlResponse.model_validate_json(data)
    except (RedisError, OSError):
        pass
    return None


async def set_analysis(url: str, analysis: AnalyzeUrlResponse) -> None:
    """Cache an analysis result with TTL. Silently ignores errors."""
    with contextlib.suppress(RedisError, OSError):
        await _get_client().setex(_cache_key(url), ANALYSIS_TTL, analysis.model_dump_json())
