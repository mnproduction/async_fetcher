from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class FetchOptions(BaseModel):
    """Configuration options for fetch requests."""
    proxies: List[str] = Field(default=[], description="List of proxy URLs")
    wait_min: int = Field(default=1, ge=1, le=30, description="Minimum wait time in seconds")
    wait_max: int = Field(default=3, ge=1, le=60, description="Maximum wait time in seconds")
    concurrency_limit: int = Field(default=5, ge=1, le=20, description="Maximum concurrent fetches")


class FetchRequest(BaseModel):
    """Request model for initiating fetch jobs."""
    links: List[str] = Field(..., min_items=1, description="List of URLs to fetch")
    options: FetchOptions = Field(default_factory=FetchOptions, description="Fetch configuration")


class JobStatusResponse(BaseModel):
    """Response model for job submission."""
    job_id: str = Field(..., description="Unique job identifier")
    status_url: str = Field(..., description="URL to check job status")


class FetchResult(BaseModel):
    """Result model for individual URL fetch."""
    url: str = Field(..., description="The fetched URL")
    status: str = Field(..., description="Fetch status: 'success' or 'error'")
    html_content: Optional[str] = Field(None, description="Fetched HTML content")
    error_message: Optional[str] = Field(None, description="Error message if failed")


class FetchResponse(BaseModel):
    """Response model for job status and results."""
    job_id: str = Field(..., description="Job identifier")
    status: str = Field(..., description="Job status: 'pending', 'running', 'completed'")
    results: List[FetchResult] = Field(default=[], description="List of fetch results") 