from pydantic import BaseModel, Field


class SearchResultItem(BaseModel):
    title: str
    url: str
    snippet: str
    published_date: str | None = None
    engine: str | None = None
    score: float | None = None


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search terms")
    max_results: int = Field(default=5, ge=1, le=50, description="Max number of results to return")
    categories: list[str] | None = Field(default=None, description="Optional search categories")
    language: str = Field(default="auto", description="Search language code")


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResultItem]
    total_results: int
    search_duration_ms: float


class SearchHealthStatus(BaseModel):
    status: str
    service: str = "searxng"
    base_url: str
    error: str | None = None
