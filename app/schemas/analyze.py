from pydantic import BaseModel, Field


class Folder(BaseModel):
    id: str
    name: str
    children: list["Folder"] = Field(default_factory=list)


class AnalyseUrlRequest(BaseModel):
    url: str = Field(description="The URL to be analyzed")
    folders: list[Folder] = Field(default_factory=list, description="Folder structure")
    create_new_folder: bool = Field(
        default=False, description="If true, always create a new folder instead of choosing an existing one"
    )


class AnalyzeUrlResponse(BaseModel):
    url: str = Field(description="The analyzed URL")
    title: str = Field(description="Page title")
    summary: str = Field(description="AI-generated summary of the page content")


class ExistingFolderRecommendation(BaseModel):
    """LLM response model when selecting an existing folder."""

    reasoning: str = Field(description="Brief explanation of why this folder was chosen over alternatives")
    recommended_folder: str = Field(description="Full path of the existing folder to use")


class NewFolderRecommendation(BaseModel):
    """LLM response model when creating a new folder."""

    reasoning: str = Field(description="Brief explanation of why this parent folder and new folder name were chosen")
    recommended_folder: str = Field(description="Full path of the parent folder where the new folder will be created")
    new_folder_name: str = Field(description="Name of the new category folder to create")


class RecommendationResponse(BaseModel):
    title: str = Field(description="Page title")
    summary: str = Field(description="AI-generated summary of the page content")
    reasoning: str = Field(description="Brief explanation of the recommendation")
    recommended_folder: str = Field(description="AI-recommended folder for the bookmark")
    new_folder_name: str | None = Field(default=None, description="Suggested name for a new folder, if applicable")
