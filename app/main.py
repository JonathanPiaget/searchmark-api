from fastapi import FastAPI
from langchain_openai import ChatOpenAI

app = FastAPI(title="SearchMark API", version="0.1.0")

llm = ChatOpenAI(
    model="gpt-5-nano",
)


@app.get("/")
def welcome():
    return {
        "name": app.title,
        "version": app.version,
        "description": "API for SearchMark bookmark search and management",
        "endpoints": {
            "health": {"path": "/health", "method": "GET", "description": "Health check"},
        },
    }


@app.get("/complete")
async def complete_text():
    messages = [
        (
            "system",
            "You are a helpful assistant that explains programming concepts in simple terms.",
        ),
        ("human", "Explain me the concept of dependency injection in programming."),
    ]
    return llm.invoke(messages)


@app.get("/health")
def health_check():
    return {"status": "ok"}
