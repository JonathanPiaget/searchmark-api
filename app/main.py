from fastapi import FastAPI

app = FastAPI(title="SearchMark API", version="0.1.0")


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


@app.get("/health")
def health_check():
    return {"status": "ok"}
