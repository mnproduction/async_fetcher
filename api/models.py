"""
Pydantic Data Models for Async HTML Fetcher Service

This module defines all data models used throughout the Async HTML Fetcher Service API.
It provides comprehensive validation, type safety, and clear data contracts for:

- Request/Response models for API endpoints
- Configuration options with advanced validation
- Result tracking with progress monitoring
- Job status management with lifecycle tracking

All models follow Pydantic v2 best practices with:
- Strict type annotations using Literal types
- Cross-field validation for data integrity
- Comprehensive error messages for debugging
- Performance-optimized field validation
- Production-ready constraint enforcement

Author: Async HTML Fetcher Service
Version: 1.0.0
"""

import re
import uuid
from datetime import datetime
from typing import List, Optional, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, HttpUrl, AnyHttpUrl

# Import sanitization functions
from .sanitization import (
    sanitize_url, sanitize_proxy_url, sanitize_html_content, 
    sanitize_error_message, sanitize_uuid, sanitize_url_list, 
    sanitize_proxy_list
)


# =============================================================================
# VALIDATION UTILITIES
# =============================================================================

def validate_uuid_format(value: str) -> str:
    """
    Validate UUID format for job IDs.
    
    Args:
        value: String to validate as UUID
        
    Returns:
        str: Validated UUID string
        
    Raises:
        ValueError: If value is not a valid UUID format
    """
    return sanitize_uuid(value)

def validate_proxy_url(proxy: str) -> str:
    """
    Validate proxy URL format with enhanced security checks.
    
    Args:
        proxy: Proxy URL string
        
    Returns:
        str: Validated proxy URL
        
    Raises:
        ValueError: If proxy URL is invalid
    """
    return sanitize_proxy_url(proxy)


# =============================================================================
# CONFIGURATION MODELS
# =============================================================================

class FetchOptions(BaseModel):
    """
    Configuration options for fetch requests with advanced validation.
    
    This model defines all user-configurable parameters for the fetching process,
    including proxy settings, timing constraints, and concurrency limits.
    
    Attributes:
        proxies: List of proxy URLs for request routing (supports HTTP/HTTPS/SOCKS)
        wait_min: Minimum wait time between requests (0-30 seconds)
        wait_max: Maximum wait time between requests (0-60 seconds, must be >= wait_min)
        concurrency_limit: Maximum concurrent browser instances (1-20)
    
    Validation:
        - Proxy URLs must have valid protocol prefixes and format
        - Wait times have sensible bounds to prevent abuse
        - wait_max must be greater than or equal to wait_min
        - Concurrency is limited to prevent resource exhaustion
        - Enhanced security checks for proxy URLs
    
    Example:
        ```python
        options = FetchOptions(
            proxies=["http://proxy1:8080", "https://proxy2:3128"],
            wait_min=2,
            wait_max=5,
            concurrency_limit=10
        )
        ```
    """
    
    proxies: List[str] = Field(
        default=[], 
        max_length=50,  # Limit number of proxies to prevent abuse
        description="List of proxy URLs to use for fetching (format: http://user:pass@host:port)"
    )
    wait_min: int = Field(
        default=1, 
        ge=0, 
        le=30,
        description="Minimum wait time in seconds between requests"
    )
    wait_max: int = Field(
        default=3, 
        ge=0, 
        le=60,
        description="Maximum wait time in seconds between requests"
    )
    concurrency_limit: int = Field(
        default=5, 
        ge=1, 
        le=20, 
        description="Maximum number of concurrent browser instances"
    )
    
    @field_validator('wait_max')
    @classmethod
    def validate_wait_max(cls, v, info):
        """
        Ensure wait_max is greater than or equal to wait_min.
        
        This prevents invalid timing configurations that could cause
        random wait time generation to fail.
        """
        if 'wait_min' in info.data and v < info.data['wait_min']:
            raise ValueError('wait_max must be greater than or equal to wait_min')
        return v
    
    @field_validator('proxies')
    @classmethod
    def validate_proxies(cls, v):
        """
        Validate proxy URL format for supported protocols with enhanced security.
        
        Ensures all proxy URLs have valid format and pass security checks
        to prevent runtime connection errors and potential attacks.
        """
        return sanitize_proxy_list(v)


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class FetchRequest(BaseModel):
    """
    Request model for initiating fetch jobs with comprehensive validation.
    
    This model represents the complete request payload for starting a new
    fetch job, including the list of URLs to process and configuration options.
    
    Attributes:
        links: List of URLs to fetch (1-1000 URLs, no duplicates)
        options: Configuration options for the fetch process
    
    Validation:
        - URL count limited to prevent abuse (1-1000 URLs)
        - Duplicate URL detection to avoid redundant work
        - URL format validation and sanitization (HTTP/HTTPS only)
        - Enhanced security checks for URLs
        - Integration with FetchOptions validation
    
    Example:
        ```python
        request = FetchRequest(
            links=["https://example.com", "https://test.com"],
            options=FetchOptions(concurrency_limit=3)
        )
        ```
    """
    
    links: List[str] = Field(
        ..., 
        min_length=1,
        max_length=1000,
        description="List of URLs to fetch (1-1000 URLs allowed)"
    )
    options: FetchOptions = Field(
        default_factory=FetchOptions, 
        description="Fetch configuration options"
    )
    
    @field_validator('links')
    @classmethod
    def validate_links(cls, v):
        """
        Validate URLs and detect duplicates with enhanced security.
        
        Ensures all URLs are properly formatted, sanitized, and removes duplicate
        processing by detecting identical URLs in the request.
        """
        return sanitize_url_list(v)


class JobStatusResponse(BaseModel):
    """
    Response model for job submission with validated identifiers.
    
    This model represents the immediate response returned when a fetch job
    is successfully submitted to the service.
    
    Attributes:
        job_id: Unique identifier for tracking the job
        status_url: Complete URL for checking job progress
    
    Validation:
        - job_id format validation for security (UUID format)
        - status_url format validation (HTTP/HTTPS URL)
        - Length constraints to prevent abuse
        - Enhanced security checks
    
    Example:
        ```python
        response = JobStatusResponse(
            job_id="550e8400-e29b-41d4-a716-446655440000",
            status_url="https://api.example.com/jobs/550e8400-e29b-41d4-a716-446655440000"
        )
        ```
    """
    
    job_id: str = Field(
        ..., 
        min_length=36,  # UUID length
        max_length=36,  # UUID length
        description="Unique job identifier (UUID format)"
    )
    status_url: str = Field(
        ..., 
        max_length=500,  # Reasonable URL length limit
        description="Complete URL to check job status"
    )
    
    @field_validator('job_id')
    @classmethod
    def validate_job_id(cls, v):
        """
        Validate job_id format for security.
        
        Ensures job IDs are valid UUIDs to prevent
        injection attacks and maintain URL safety.
        """
        return sanitize_uuid(v)
    
    @field_validator('status_url')
    @classmethod
    def validate_status_url(cls, v):
        """
        Validate status URL format with enhanced security.
        
        Ensures the status URL is a proper HTTP/HTTPS URL that
        clients can use to check job progress.
        """
        return sanitize_url(v, max_length=500)


# =============================================================================
# RESULT MODELS
# =============================================================================

class FetchResult(BaseModel):
    """
    Result model for individual URL fetch with comprehensive validation and status tracking.
    
    This model represents the outcome of fetching a single URL, including
    success/failure status, content, timing, and error information.
    
    Attributes:
        url: The URL that was processed
        status: Fetch outcome (success/error)
        html_content: Page content (success only)
        error_message: Error details (error only)
        response_time_ms: Request timing in milliseconds
        status_code: HTTP status code from server
    
    Validation:
        - Status-dependent field validation (content vs errors)
        - URL format validation and sanitization
        - HTTP status code range validation
        - Cross-field logical consistency
        - Enhanced security checks
    
    Example:
        ```python
        # Successful fetch
        result = FetchResult(
            url="https://example.com",
            status="success",
            html_content="<html>...</html>",
            response_time_ms=1250,
            status_code=200
        )
        
        # Failed fetch
        result = FetchResult(
            url="https://broken.com",
            status="error",
            error_message="Connection timeout after 30 seconds"
        )
        ```
    """
    
    url: str = Field(
        ..., 
        max_length=2000,  # URL length limit
        description="The URL that was fetched"
    )
    status: Literal["success", "error"] = Field(
        ..., 
        description="Fetch operation status - 'success' for successful fetch, 'error' for any failure"
    )
    html_content: Optional[str] = Field(
        None, 
        max_length=10_000_000,  # 10MB limit for HTML content
        description="The complete HTML content of the fetched page (only present on success)"
    )
    error_message: Optional[str] = Field(
        None, 
        max_length=1000,  # Reasonable error message length
        description="Detailed error message explaining the failure (only present on error)"
    )
    response_time_ms: Optional[int] = Field(
        None,
        ge=0,
        le=300_000,  # 5 minutes max response time
        description="Response time in milliseconds for the fetch operation"
    )
    status_code: Optional[int] = Field(
        None,
        ge=100,
        le=599,
        description="HTTP status code returned by the server (if available)"
    )
    
    @field_validator('url')
    @classmethod
    def validate_url(cls, v):
        """Validate URL format consistency with enhanced security."""
        return sanitize_url(v, max_length=2000)
    
    @field_validator('html_content')
    @classmethod
    def validate_html_content(cls, v, info):
        """Ensure html_content is only present with success status."""
        if v is not None and info.data.get('status') == 'error':
            raise ValueError('html_content should be None for error status')
        
        # Sanitize HTML content if present
        if v is not None:
            return sanitize_html_content(v)
        
        return v
    
    @field_validator('error_message')
    @classmethod
    def validate_error_message(cls, v, info):
        """Ensure error_message follows status-dependent rules."""
        if v is not None and info.data.get('status') == 'success':
            raise ValueError('error_message should be None for success status')
        if info.data.get('status') == 'error' and not v:
            raise ValueError('error_message is required for error status')
        
        # Sanitize error message if present
        if v is not None:
            return sanitize_error_message(v)
        
        return v


class FetchResponse(BaseModel):
    """
    Response model for comprehensive job status tracking and results with progress monitoring.
    
    This model represents the complete job status response, including progress tracking,
    timing information, and all individual fetch results.
    
    Attributes:
        job_id: Unique job identifier
        status: Current job status (pending/in_progress/completed/failed)
        results: List of individual fetch results
        total_urls: Total number of URLs in the job
        completed_urls: Number of processed URLs
        started_at: Job start timestamp
        completed_at: Job completion timestamp
    
    Properties:
        progress_percentage: Calculated completion percentage (0-100%)
        is_finished: Boolean indicating terminal status
    
    Validation:
        - Progress consistency (completed <= total)
        - Results count matches completed count
        - Timestamp logic for job lifecycle
        - Status-dependent field validation
        - Enhanced security checks
    
    Example:
        ```python
        # Job in progress
        response = FetchResponse(
            job_id="abc123",
            status="in_progress",
            total_urls=10,
            completed_urls=7,
            results=[...],  # 7 FetchResult objects
            started_at=datetime.now()
        )
        
        print(f"Progress: {response.progress_percentage}%")  # 70.0%
        print(f"Finished: {response.is_finished}")  # False
        ```
    """
    
    job_id: str = Field(
        ..., 
        min_length=36,  # UUID length
        max_length=36,  # UUID length
        description="Unique job identifier"
    )
    status: Literal["pending", "in_progress", "completed", "failed"] = Field(
        ..., 
        description="Current job status - pending: queued, in_progress: actively fetching, completed: all done, failed: job-level failure"
    )
    results: List[FetchResult] = Field(
        default=[], 
        max_length=1000,  # Match max URLs limit
        description="List of individual fetch results (populated as URLs are processed)"
    )
    total_urls: int = Field(
        ..., 
        ge=1,
        le=1000,  # Match max URLs limit
        description="Total number of URLs in this job"
    )
    completed_urls: int = Field(
        ..., 
        ge=0,
        le=1000,  # Match max URLs limit
        description="Number of URLs that have been processed (success or error)"
    )
    started_at: Optional[datetime] = Field(
        None,
        description="Timestamp when job processing started"
    )
    completed_at: Optional[datetime] = Field(
        None,
        description="Timestamp when job completed (success or failure)"
    )
    
    @field_validator('job_id')
    @classmethod
    def validate_job_id(cls, v):
        """Validate job_id format for security."""
        return sanitize_uuid(v)
    
    @field_validator('completed_urls')
    @classmethod
    def validate_completed_urls(cls, v, info):
        """Ensure progress consistency."""
        if 'total_urls' in info.data and v > info.data['total_urls']:
            raise ValueError('completed_urls cannot exceed total_urls')
        return v
    
    @field_validator('results')
    @classmethod
    def validate_results_count(cls, v, info):
        """Ensure results array matches completion count."""
        if 'completed_urls' in info.data and len(v) != info.data['completed_urls']:
            raise ValueError('Number of results must match completed_urls')
        return v
    
    @field_validator('completed_at')
    @classmethod
    def validate_completed_at(cls, v, info):
        """Ensure completion timestamp follows lifecycle rules."""
        if v is not None and info.data.get('status') not in ['completed', 'failed']:
            raise ValueError('completed_at should only be set for completed or failed jobs')
        
        # Ensure completed_at is after started_at if both exist
        if v is not None and 'started_at' in info.data and info.data['started_at'] is not None:
            if v <= info.data['started_at']:
                raise ValueError('completed_at must be after started_at')
        
        return v
    
    @property
    def progress_percentage(self) -> float:
        """
        Calculate job completion percentage.
        
        Returns:
            float: Completion percentage (0.0 to 100.0)
        """
        if self.total_urls == 0:
            return 0.0
        return (self.completed_urls / self.total_urls) * 100.0
    
    @property
    def is_finished(self) -> bool:
        """
        Check if job is in a terminal state.
        
        Returns:
            bool: True if job is completed or failed
        """
        return self.status in ['completed', 'failed']


# =============================================================================
# MODEL EXPORTS
# =============================================================================

__all__ = [
    'FetchOptions',
    'FetchRequest', 
    'JobStatusResponse',
    'FetchResult',
    'FetchResponse',
    'validate_uuid_format',
    'validate_proxy_url'
] 