"""Core testing functions with configurable model support."""

import time
from urllib.parse import urlparse

import html2text
import httpx
import litellm
from litellm import acompletion
from toon import encode as toon_encode

from app.schemas.analyze import AnalyzeUrlResponse, Folder, RecommendationResponse
from app.testing.schemas import ComparisonResult, TestCase, TestResult

BLOCKED_HOSTS = {"localhost", "127.0.0.1", "::1"}
DEFAULT_MODEL = "openai/gpt-4o-mini"

litellm.enable_json_schema_validation = True


class UrlValidationError(Exception):
    """Raised when URL validation fails."""


class ContentFetchError(Exception):
    """Raised when content fetching fails."""


def validate_url(url: str) -> None:
    """Validate URL for SSRF protection."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UrlValidationError("Only http/https URLs allowed")
    if parsed.hostname and parsed.hostname.lower() in BLOCKED_HOSTS:
        raise UrlValidationError("This host is not allowed")


async def fetch_url_content(url: str, timeout: float = 30.0) -> str:
    """Fetch and convert URL content to markdown.

    Args:
        url: URL to fetch
        timeout: Request timeout in seconds

    Returns:
        Markdown content of the page (max 15000 chars)
    """
    validate_url(url)

    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
        response = await client.get(url)
        response.raise_for_status()
        html_content = response.text

    if not html_content:
        raise ContentFetchError("No content retrieved")

    h = html2text.HTML2Text()
    h.ignore_links = True
    h.ignore_images = True
    return h.handle(html_content)[:15000]


async def analyze_url(url: str, model: str = DEFAULT_MODEL) -> AnalyzeUrlResponse:
    """Analyze a URL and extract structured information.

    Args:
        url: URL to analyze
        model: LiteLLM model identifier (e.g., "openai/gpt-4o-mini", "anthropic/claude-3-haiku-20240307")

    Returns:
        AnalyzeUrlResponse with URL, title, summary, and keywords
    """
    content = await fetch_url_content(url)

    messages = [
        {"role": "system", "content": "Analyze this web page and extract the URL, title, summary, and keywords."},
        {"role": "user", "content": f"URL: {url}\n\nContent:\n{content}"},
    ]
    response = await acompletion(model=model, messages=messages, response_format=AnalyzeUrlResponse)
    return AnalyzeUrlResponse.model_validate_json(response.choices[0].message.content)


async def get_recommendation(
    analysis: AnalyzeUrlResponse,
    folders: list[Folder],
    model: str = DEFAULT_MODEL,
) -> RecommendationResponse:
    """Get folder recommendation based on page analysis.

    Args:
        analysis: URL analysis result
        folders: List of Folder objects representing the user's folder structure
        model: LiteLLM model identifier

    Returns:
        RecommendationResponse with recommended folder or new folder suggestion
    """
    folders_data = [f.model_dump() for f in folders]
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
    response = await acompletion(model=model, messages=messages, response_format=RecommendationResponse)
    return RecommendationResponse.model_validate_json(response.choices[0].message.content)


async def run_test(test_case: TestCase, model: str = DEFAULT_MODEL) -> TestResult:
    """Run a single test case.

    Args:
        test_case: The test case to run
        model: LiteLLM model identifier

    Returns:
        TestResult with timing and output information
    """
    start_total = time.perf_counter()

    try:
        start_analysis = time.perf_counter()
        analysis = await analyze_url(test_case.url, model=model)
        analysis_time = (time.perf_counter() - start_analysis) * 1000

        start_recommendation = time.perf_counter()
        recommendation = await get_recommendation(analysis, test_case.folders, model=model)
        recommendation_time = (time.perf_counter() - start_recommendation) * 1000

        total_time = (time.perf_counter() - start_total) * 1000

        return TestResult(
            test_case=test_case,
            model=model,
            analysis=analysis,
            recommendation=recommendation,
            analysis_time_ms=analysis_time,
            recommendation_time_ms=recommendation_time,
            total_time_ms=total_time,
            success=True,
        )
    except Exception as e:
        total_time = (time.perf_counter() - start_total) * 1000
        return TestResult(
            test_case=test_case,
            model=model,
            analysis=AnalyzeUrlResponse(url=test_case.url, title="", summary="", keywords=[]),
            recommendation=RecommendationResponse(recommended_folder="", new_folder_name=None),
            analysis_time_ms=0,
            recommendation_time_ms=0,
            total_time_ms=total_time,
            success=False,
            error=str(e),
        )


async def compare_models(test_case: TestCase, models: list[str]) -> ComparisonResult:
    """Run the same test case across multiple models.

    Args:
        test_case: The test case to run
        models: List of LiteLLM model identifiers to compare

    Returns:
        ComparisonResult with results from all models
    """
    results = []
    for model in models:
        result = await run_test(test_case, model=model)
        results.append(result)

    return ComparisonResult(
        test_case=test_case,
        results=results,
        models_compared=models,
    )
