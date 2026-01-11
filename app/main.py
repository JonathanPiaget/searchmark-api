from typing import cast
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from langchain_community.document_loaders import AsyncHtmlLoader
from langchain_community.document_transformers import Html2TextTransformer
from langchain_openai import ChatOpenAI

from app.schemas.analyze import AnalyseUrlRequest, AnalyzeUrlResponse, RecommendationResponse

BLOCKED_HOSTS = {"localhost", "127.0.0.1", "::1"}

app = FastAPI(title="SearchMark API", version="0.1.0")

llm = ChatOpenAI(
    model="gpt-4o-mini",  # type: ignore[call-arg]
)


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

    loader = AsyncHtmlLoader([url])
    docs = await loader.aload()
    if not docs:
        raise HTTPException(status_code=400, detail="No content retrieved")

    transformer = Html2TextTransformer()
    docs_transformed = transformer.transform_documents(docs)
    content = docs_transformed[0].page_content[:15000] if docs_transformed else ""

    structured_llm = llm.with_structured_output(AnalyzeUrlResponse)
    messages = [
        ("system", "Analyze this web page and extract the URL, title, summary, and keywords."),
        ("human", f"URL: {url}\n\nContent:\n{content}"),
    ]
    return cast(AnalyzeUrlResponse, await structured_llm.ainvoke(messages))


async def get_folder_recommendation(
    analysis: AnalyzeUrlResponse,
    folders_json: str,
) -> RecommendationResponse:
    """Recommend a folder based on page analysis and available folders."""
    structured_llm = llm.with_structured_output(RecommendationResponse)

    has_folders = bool(folders_json and folders_json.strip() and folders_json.strip() not in ("[]", "{}"))

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

User's Folder Structure:
{folders_json if has_folders else "(No folders available)"}

Please recommend the best folder for this bookmark."""

    messages = [
        ("system", system_prompt),
        ("human", human_message),
    ]
    return cast(RecommendationResponse, await structured_llm.ainvoke(messages))


@app.post("/recommend", response_model=RecommendationResponse)
async def recommend_folder(request: AnalyseUrlRequest) -> RecommendationResponse:
    analysis = await fetch_and_analyze_url(request.url)
    recommendation = await get_folder_recommendation(analysis, request.folders)
    return recommendation


@app.get("/health")
def health_check():
    return {"status": "ok"}
