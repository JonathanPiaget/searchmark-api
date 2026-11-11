import json
import logging
import os
import ssl
from typing import TypeVar, cast
from urllib.parse import urlparse

import html2text
import httpx
import litellm
import sentry_sdk
from fastapi import FastAPI, HTTPException
from litellm import ModelResponse, acompletion
from pydantic import BaseModel
from toon import encode as toon_encode

from app.schemas.analyze import (
    AnalyseUrlRequest,
    AnalyzeUrlResponse,
    ExistingFolderRecommendation,
    NewFolderRecommendation,
    RecommendationResponse,
)

from . import cache
from .prompts import EXISTING_FOLDER_RECOMMENDATION_PROMPT, NEW_FOLDER_RECOMMENDATION_PROMPT

BLOCKED_HOSTS = {"localhost", "127.0.0.1", "::1"}
MODEL = os.environ.get("SEARCHMARK_MODEL", "openai/gpt-6-luna")
MAX_FOLDERS = int(os.environ.get("SEARCHMARK_MAX_FOLDERS", "2000"))
# reasoning tokens count against the cap: at 300 a reasoning model sometimes left no room for the answer
MAX_TOKENS = 1000
COST_ALERT_USD = float(os.environ.get("SEARCHMARK_COST_ALERT_USD", "0.02"))
# OpenAI's default caches the whole prompt, so a new page never hits and every call pays a cache write.
# Explicit mode caches only up to the marked block (the folder tree).
OPENAI_CACHE = MODEL.startswith("openai/")
OPENAI_CACHE_OPTIONS = {"extra_body": {"prompt_cache_options": {"mode": "explicit"}}} if OPENAI_CACHE else {}
T = TypeVar("T", bound=BaseModel)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)
sentry_sdk.init(dsn=os.environ.get("SENTRY_DSN"))  # no DSN = disabled


def _create_ssl_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    context.set_ciphers("DEFAULT@SECLEVEL=1")
    return context


SSL_CONTEXT = _create_ssl_context()

app = FastAPI(title="SearchMark API", version="0.1.0")

litellm.enable_json_schema_validation = True


async def _complete(messages: list[dict], response_format: type[T]) -> T:
    """One structured LLM call, bounded in output and time, with its real cost logged."""
    # non-streaming call, so never a CustomStreamWrapper
    response = cast(
        ModelResponse,
        await acompletion(
            model=MODEL,
            messages=messages,
            response_format=response_format,
            max_tokens=MAX_TOKENS,
            timeout=30,
            **OPENAI_CACHE_OPTIONS,
        ),
    )
    cost = response._hidden_params.get("response_cost")
    usage = getattr(response, "usage", None)
    cached = getattr(getattr(usage, "prompt_tokens_details", None), "cached_tokens", None)
    log.info(
        "llm model=%s cost_usd=%s prompt_tokens=%s cached_tokens=%s",
        MODEL,
        cost,
        getattr(usage, "prompt_tokens", None),
        cached,
    )
    if cost is not None and cost > COST_ALERT_USD:
        sentry_sdk.capture_message(f"LLM call cost ${cost:.4f} > ${COST_ALERT_USD} ({MODEL})")
    return response_format.model_validate_json(response.choices[0].message.content or "")


@app.get("/")
def welcome():
    return {
        "name": app.title,
        "version": app.version,
        "description": "API for SearchMark bookmark search and management",
    }


def validate_url(url: str) -> None:
    """Validate URL for SSRF protection."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="Only http/https URLs allowed")
    if parsed.hostname and parsed.hostname.lower() in BLOCKED_HOSTS:
        raise HTTPException(status_code=403, detail="This host is not allowed")


async def fetch_and_analyze_url(url: str) -> AnalyzeUrlResponse:
    validate_url(url)

    cached = await cache.get_analysis(url)
    if cached is not None:
        return cached

    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0, verify=SSL_CONTEXT) as client:
        response = await client.get(url)
        response.raise_for_status()
        html_content = response.text

    if not html_content:
        raise HTTPException(status_code=400, detail="No content retrieved")

    h = html2text.HTML2Text()
    h.ignore_links = True
    h.ignore_images = True
    content = h.handle(html_content)[:15000]

    messages = [
        {"role": "system", "content": "Analyze this web page and extract the URL, title and summary."},
        {"role": "user", "content": f"URL: {url}\n\nContent:\n{content}"},
    ]
    result = await _complete(messages, AnalyzeUrlResponse)
    await cache.set_analysis(url, result)
    return result


def _folder_paths(folders: list[dict], prefix: str = "") -> set[str]:
    paths: set[str] = set()
    for f in folders:
        path = f"{prefix}{f['name']}"
        paths.add(path)
        paths.update(_folder_paths(f.get("children") or [], f"{path}/"))
    return paths


def _norm(path: str) -> str:
    return "/".join(p.strip() for p in path.split("/") if p.strip())


def resolve_folder_path(raw: str, paths: set[str]) -> str:
    """Map the LLM's folder path onto an existing one.

    The model often strips the root, adds spaces around "/" or skips a level.
    Longest tail of the given path that identifies exactly one folder wins.
    Both sides are normalized so folder names containing " / " still match.
    """
    by_norm = {_norm(p): p for p in paths}
    parts = _norm(raw).split("/")
    for k in range(len(parts), 0, -1):
        tail = "/".join(parts[-k:])
        matches = [p for n, p in by_norm.items() if n == tail or n.endswith("/" + tail)]
        if len(matches) == 1:
            return matches[0]
    return "/".join(parts)


async def get_folder_recommendation(
    analysis: AnalyzeUrlResponse,
    folders_json: str,
    create_new_folder: bool = False,
) -> RecommendationResponse:
    """Recommend a folder based on page analysis and available folders."""
    folders_data = json.loads(folders_json)
    folders_toon = toon_encode(folders_data)

    # tree first: it is the stable prefix per user, cached up to the end of this block
    tree_block: dict = {"type": "text", "text": f"User's Folder Structure (TOON format):\n{folders_toon}"}
    if OPENAI_CACHE:
        tree_block["prompt_cache_breakpoint"] = {"mode": "explicit"}
    analysis_text = f"""

Webpage Analysis:
- URL: {analysis.url}
- Title: {analysis.title}
- Summary: {analysis.summary}"""

    if create_new_folder:
        system_prompt = NEW_FOLDER_RECOMMENDATION_PROMPT
        response_format = NewFolderRecommendation
    else:
        system_prompt = EXISTING_FOLDER_RECOMMENDATION_PROMPT
        response_format = ExistingFolderRecommendation

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": [tree_block, {"type": "text", "text": analysis_text}]},
    ]
    result = await _complete(messages, response_format)
    result.recommended_folder = resolve_folder_path(result.recommended_folder, _folder_paths(folders_data))

    analysis_fields = {
        "title": analysis.title,
        "summary": analysis.summary,
        "reasoning": result.reasoning,
    }
    if isinstance(result, NewFolderRecommendation):
        return RecommendationResponse(
            **analysis_fields, recommended_folder=result.recommended_folder, new_folder_name=result.new_folder_name
        )
    return RecommendationResponse(**analysis_fields, recommended_folder=result.recommended_folder)


@app.post("/recommend", response_model=RecommendationResponse)
async def recommend_folder(request: AnalyseUrlRequest) -> RecommendationResponse:
    folders = [f.model_dump() for f in request.folders]
    if len(_folder_paths(folders)) > MAX_FOLDERS:
        raise HTTPException(status_code=413, detail=f"Too many folders (max {MAX_FOLDERS})")
    analysis = await fetch_and_analyze_url(request.url)
    folders_json = json.dumps(folders)
    recommendation = await get_folder_recommendation(analysis, folders_json, request.create_new_folder)
    return recommendation


@app.get("/health")
def health_check():
    return {"status": "ok"}
