from pydantic import BaseModel, Field


class AnalyzeUrlResponse(BaseModel):
    url: str = Field(description="The analyzed URL")
    title: str = Field(description="Page title")
    summary: str = Field(description="AI-generated summary of the page content")
    keywords: list[str] = Field(description="AI-generated keywords/tags for the page")
