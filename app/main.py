import json
from urllib.parse import urlparse

import html2text
import httpx
import litellm
from fastapi import FastAPI, HTTPException
from litellm import acompletion
from toon import encode as toon_encode

from app.schemas.analyze import (
    AnalyseUrlRequest,
    AnalyzeUrlResponse,
    ExistingFolderRecommendation,
    NewFolderRecommendation,
    RecommendationResponse,
)

from .prompts import EXISTING_FOLDER_RECOMMENDATION_PROMPT, NEW_FOLDER_RECOMMENDATION_PROMPT

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
        {"role": "system", "content": "Analyze this web page and extract the URL, title and summary."},
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

    human_message = f"""Webpage Analysis:
- URL: {analysis.url}
- Title: {analysis.title}
- Summary: {analysis.summary}

User's Folder Structure (TOON format):
{folders_toon}"""

    if create_new_folder:
        system_prompt = NEW_FOLDER_RECOMMENDATION_PROMPT
        response_format = NewFolderRecommendation
    else:
        system_prompt = EXISTING_FOLDER_RECOMMENDATION_PROMPT
        response_format = ExistingFolderRecommendation

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": human_message},
    ]
    response = await acompletion(model=MODEL, messages=messages, response_format=response_format)
    result = response_format.model_validate_json(response.choices[0].message.content)

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
    analysis = await fetch_and_analyze_url(request.url)
    folders_json = json.dumps([f.model_dump() for f in request.folders])
    recommendation = await get_folder_recommendation(analysis, folders_json, request.create_new_folder)
    return recommendation


@app.get("/health")
def health_check():
    return {"status": "ok"}
