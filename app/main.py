from fastapi import FastAPI

app = FastAPI(title="SearchMark API")


@app.get("/health")
def health_check():
    return {"status": "ok"}
