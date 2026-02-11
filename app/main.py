import json
from urllib.parse import urlparse

import html2text
import httpx
import litellm
from fastapi import FastAPI, HTTPException
from litellm import acompletion
from toon import encode as toon_encode

from app.schemas.analyze import AnalyseUrlRequest, AnalyzeUrlResponse, RecommendationResponse

BLOCKED_HOSTS = {"localhost", "127.0.0.1", "::1"}
MODEL = "openai/gpt-4o"

app = FastAPI(title="SearchMark API", version="0.1.0")

litellm.enable_json_schema_validation = True


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

    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
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
        {"role": "system", "content": "Analyze this web page and extract the URL, title, summary, and keywords."},
        {"role": "user", "content": f"URL: {url}\n\nContent:\n{content}"},
    ]
    response = await acompletion(model=MODEL, messages=messages, response_format=AnalyzeUrlResponse)
    return AnalyzeUrlResponse.model_validate_json(response.choices[0].message.content)


async def get_folder_recommendation(
    analysis: AnalyzeUrlResponse,
    folders_json: str,
    create_new_folder: bool = False,
) -> RecommendationResponse:
    """Recommend a folder based on page analysis and available folders."""
    folders_data = json.loads(folders_json)
    folders_toon = toon_encode(folders_data)

    if create_new_folder:
        system_prompt = """You are a bookmark organization assistant. Based on the webpage analysis, create a new folder for this bookmark.

Rules:
1. You MUST create a new folder. Set `recommended_folder` to "" (empty string) and suggest a `new_folder_name`.
2. The new folder name should be concise and descriptive, based on the page content (title, summary, keywords).
3. Do NOT reuse any existing folder name from the folder structure."""
    else:
        system_prompt = """You are a bookmark organization assistant. Based on the webpage analysis and the user's folder structure, recommend the best existing folder for this bookmark.

Rules:
1. You MUST choose an existing folder. Set `recommended_folder` to the full folder path and `new_folder_name` to null.
2. Choose folders based on semantic relevance to the page content (title, summary, keywords).
3. Prefer more specific folders over general ones when the content clearly fits."""

    human_message = f"""Webpage Analysis:
- URL: {analysis.url}
- Title: {analysis.title}
- Summary: {analysis.summary}
- Keywords: {", ".join(analysis.keywords)}

User's Folder Structure (TOON format):
{folders_toon}

Please recommend the best folder for this bookmark."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": human_message},
    ]
    response = await acompletion(model=MODEL, messages=messages, response_format=RecommendationResponse)
    return RecommendationResponse.model_validate_json(response.choices[0].message.content)


@app.post("/recommend", response_model=RecommendationResponse)
async def recommend_folder(request: AnalyseUrlRequest) -> RecommendationResponse:
    analysis = await fetch_and_analyze_url(request.url)
    folders_json = json.dumps([f.model_dump() for f in request.folders])
    recommendation = await get_folder_recommendation(analysis, folders_json, request.create_new_folder)
    return recommendation


@app.get("/health")
def health_check():
    return {"status": "ok"}
