"""Schemas for testing and model comparison."""

from pydantic import BaseModel, Field

from app.schemas.analyze import AnalyzeUrlResponse, Folder, RecommendationResponse


class TestCase(BaseModel):
    """A test case for bookmark recommendation."""

    name: str = Field(description="Name/identifier for this test case")
    url: str = Field(description="URL to analyze")
    folders: list[Folder] = Field(default_factory=list, description="Folder structure to use")
    expected_folder: str | None = Field(default=None, description="Expected folder recommendation (for validation)")
    description: str | None = Field(default=None, description="Optional description of what this test verifies")


class TestResult(BaseModel):
    """Result of running a single test case."""

    test_case: TestCase
    model: str = Field(description="Model used for this test")
    analysis: AnalyzeUrlResponse = Field(description="URL analysis result")
    recommendation: RecommendationResponse = Field(description="Folder recommendation result")
    analysis_time_ms: float = Field(description="Time taken for URL analysis in milliseconds")
    recommendation_time_ms: float = Field(description="Time taken for recommendation in milliseconds")
    total_time_ms: float = Field(description="Total time in milliseconds")
    success: bool = Field(description="Whether the test completed without errors")
    error: str | None = Field(default=None, description="Error message if test failed")


class ComparisonResult(BaseModel):
    """Result of comparing multiple models on the same test case."""

    test_case: TestCase
    results: list[TestResult] = Field(description="Results from each model")
    models_compared: list[str] = Field(description="List of models that were compared")


class TestSuite(BaseModel):
    """A collection of test cases."""

    name: str = Field(description="Name of the test suite")
    description: str | None = Field(default=None, description="Description of this test suite")
    test_cases: list[TestCase] = Field(default_factory=list, description="Test cases in this suite")


class TestSuiteResult(BaseModel):
    """Results from running a full test suite."""

    suite_name: str
    model: str
    results: list[TestResult]
    total_tests: int
    successful_tests: int
    failed_tests: int
    total_time_ms: float
