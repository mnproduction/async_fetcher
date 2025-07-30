"""
Simplified Data Models for Cloudflare-Protected Content Fetcher

This module defines simplified data models for the FlareSolverr-based content fetcher.
It provides validation and type safety for:

- Single URL and batch fetch requests
- Fetch results with timing and error information
- Service health and status monitoring

All models are optimized for the cookie extraction + aiohttp approach with:
- Minimal complexity for fast processing
- Clear error reporting for debugging
- Performance-focused validation
- Production-ready constraints

Author: Simplified Async Fetcher Service
Version: 2.0.0
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

# Import sanitization functions
from .sanitization import (
    sanitize_error_message,
    sanitize_html_content,
    sanitize_url,
    sanitize_url_list,
)

# =============================================================================
# REQUEST MODELS
# =============================================================================


class SingleFetchRequest(BaseModel):
    """
    Request model for fetching a single URL.

    Attributes:
        url: The URL to fetch
        force_refresh_cookies: Whether to force cookie refresh
    """

    url: str = Field(..., max_length=2000, description="URL to fetch content from")
    force_refresh_cookies: bool = Field(
        default=False, description="Force refresh of cached cookies even if they're still valid"
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v):
        """Validate URL format."""
        return sanitize_url(v, max_length=2000)


class BatchFetchRequest(BaseModel):
    """
    Request model for fetching multiple URLs.

    Attributes:
        urls: List of URLs to fetch
        max_concurrent: Maximum concurrent requests
        force_refresh_cookies: Whether to force cookie refresh for all URLs
    """

    urls: list[str] = Field(
        ..., min_length=1, max_length=100, description="List of URLs to fetch (1-100 URLs allowed)"
    )
    max_concurrent: int = Field(default=5, ge=1, le=20, description="Maximum concurrent requests")
    force_refresh_cookies: bool = Field(
        default=False, description="Force refresh of cached cookies for all URLs"
    )

    @field_validator("urls")
    @classmethod
    def validate_urls(cls, v):
        """Validate URLs and remove duplicates."""
        return sanitize_url_list(v)


# =============================================================================
# RESPONSE MODELS
# =============================================================================


class FetchResult(BaseModel):
    """
    Simplified result model for URL fetch operations.

    Attributes:
        url: The URL that was processed
        success: Whether the fetch was successful
        status_code: HTTP status code (if available)
        content: HTML content (success only)
        content_length: Length of content in characters
        execution_time: Time taken for the operation in seconds
        error: Error message (failure only)
        used_cookies: Whether cached cookies were used
        cookies_refreshed: Whether cookies were refreshed during this request
    """

    url: str = Field(..., max_length=2000, description="The URL that was fetched")
    success: bool = Field(..., description="Whether the fetch was successful")
    status_code: int | None = Field(None, ge=100, le=599, description="HTTP status code")
    content: str | None = Field(
        None, max_length=10_000_000, description="HTML content (success only)"
    )
    content_length: int = Field(default=0, ge=0, description="Length of content in characters")
    execution_time: float = Field(default=0.0, ge=0.0, description="Execution time in seconds")
    error: str | None = Field(None, max_length=1000, description="Error message (failure only)")
    used_cookies: bool = Field(default=False, description="Whether cached cookies were used")
    cookies_refreshed: bool = Field(default=False, description="Whether cookies were refreshed")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v):
        """Validate URL format."""
        return sanitize_url(v, max_length=2000)

    @field_validator("content")
    @classmethod
    def validate_content(cls, v, info):
        """Sanitize HTML content if present."""
        if v is not None:
            return sanitize_html_content(v)
        return v

    @field_validator("error")
    @classmethod
    def validate_error(cls, v):
        """Sanitize error message if present."""
        if v is not None:
            return sanitize_error_message(v)
        return v


class BatchFetchResponse(BaseModel):
    """
    Response model for batch fetch operations.

    Attributes:
        results: List of individual fetch results
        total_urls: Total number of URLs processed
        successful_urls: Number of successful fetches
        failed_urls: Number of failed fetches
        total_execution_time: Total time for the batch operation
    """

    results: list[FetchResult] = Field(..., description="List of individual fetch results")
    total_urls: int = Field(..., ge=0, description="Total number of URLs processed")
    successful_urls: int = Field(..., ge=0, description="Number of successful fetches")
    failed_urls: int = Field(..., ge=0, description="Number of failed fetches")
    total_execution_time: float = Field(..., ge=0.0, description="Total execution time in seconds")

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_urls == 0:
            return 0.0
        return (self.successful_urls / self.total_urls) * 100.0


class HealthResponse(BaseModel):
    """
    Response model for service health checks.

    Attributes:
        service: Service name
        status: Overall health status
        flaresolverr_healthy: Whether FlareSolverr is accessible
        cached_domains: Number of domains with cached cookies
        cookie_sessions: Detailed cookie session information
        timestamp: Health check timestamp
    """

    service: str = Field(..., description="Service name")
    status: Literal["healthy", "degraded", "unhealthy"] = Field(
        ..., description="Overall health status"
    )
    flaresolverr_healthy: bool = Field(
        ..., description="Whether FlareSolverr service is accessible"
    )
    cached_domains: int = Field(..., ge=0, description="Number of domains with cached cookies")
    cookie_sessions: dict[str, Any] = Field(
        default={}, description="Detailed cookie session information"
    )
    timestamp: float = Field(..., description="Health check timestamp")
    issues: list[str] | None = Field(None, description="List of issues if status is not healthy")
    error: str | None = Field(None, description="Error message if health check failed")


# =============================================================================
# MODEL EXPORTS
# =============================================================================

__all__ = [
    "SingleFetchRequest",
    "BatchFetchRequest",
    "FetchResult",
    "BatchFetchResponse",
    "HealthResponse",
]
