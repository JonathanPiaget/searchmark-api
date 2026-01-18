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
MODEL = "openai/gpt-4o-mini"

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
) -> RecommendationResponse:
    """Recommend a folder based on page analysis and available folders."""
    folders_data = json.loads(folders_json)
    folders_toon = toon_encode(folders_data)

    system_prompt = """You are a bookmark organization assistant. Based on the webpage analysis and the user's folder structure, recommend the best folder for this bookmark.

Rules:
1. If a suitable existing folder matches the content, set `recommended_folder` to the full folder path and `new_folder_name` to null.
2. If no existing folder is a good fit, set `recommended_folder` to "" (empty string) and suggest a `new_folder_name` that would be appropriate.
3. Choose folders based on semantic relevance to the page content (title, summary, keywords).
4. Prefer more specific folders over general ones when the content clearly fits.
5. If the folder structure is empty or not provided, always suggest a new folder name."""

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
    recommendation = await get_folder_recommendation(analysis, folders_json)
    return recommendation


@app.get("/health")
def health_check():
    return {"status": "ok"}
