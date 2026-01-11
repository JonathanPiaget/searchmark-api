from pydantic import BaseModel, Field


class AnalyseUrlRequest(BaseModel):
    url: str = Field(description="The URL to be analyzed")
    folders: str = Field(default="", description="Optional JSON string representing folder structure")


class AnalyzeUrlResponse(BaseModel):
    url: str = Field(description="The analyzed URL")
    title: str = Field(description="Page title")
    summary: str = Field(description="AI-generated summary of the page content")
    keywords: list[str] = Field(description="AI-generated keywords/tags for the page")


class RecommendationResponse(BaseModel):
    recommended_folder: str = Field(description="AI-recommended folder for the bookmark")
    new_folder_name: str | None = Field(default=None, description="Suggested name for a new folder, if applicable")
