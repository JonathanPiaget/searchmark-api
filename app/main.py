from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from langchain_community.document_loaders import AsyncHtmlLoader
from langchain_community.document_transformers import Html2TextTransformer
from langchain_openai import ChatOpenAI

from app.schemas.analyze import AnalyzeUrlResponse

BLOCKED_HOSTS = {"localhost", "127.0.0.1", "::1"}

app = FastAPI(title="SearchMark API", version="0.1.0")

llm = ChatOpenAI(
    model="gpt-4o-mini",
)


@app.get("/")
def welcome():
    return {
        "name": app.title,
        "version": app.version,
        "description": "API for SearchMark bookmark search and management",
    }


@app.post("/analyze", response_model=AnalyzeUrlResponse)
async def analyze_url(url: str) -> AnalyzeUrlResponse:
    parsed = urlparse(url)

    # Basic SSRF protection
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="Only http/https URLs allowed")
    if parsed.hostname and parsed.hostname.lower() in BLOCKED_HOSTS:
        raise HTTPException(status_code=403, detail="This host is not allowed")

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
    return await structured_llm.ainvoke(messages)


@app.get("/health")
def health_check():
    return {"status": "ok"}
