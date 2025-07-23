from pydantic import BaseModel, Field, field_validator, HttpUrl
from typing import List, Optional, Literal
import uuid
from datetime import datetime


class FetchOptions(BaseModel):
    """Configuration options for fetch requests with advanced validation."""
    
    proxies: List[str] = Field(
        default=[], 
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
        """Ensure wait_max is greater than or equal to wait_min."""
        if 'wait_min' in info.data and v < info.data['wait_min']:
            raise ValueError('wait_max must be greater than or equal to wait_min')
        return v
    
    @field_validator('proxies')
    @classmethod
    def validate_proxies(cls, v):
        """Validate proxy URL format."""
        for proxy in v:
            if not proxy.startswith(('http://', 'https://', 'socks4://', 'socks5://')):
                raise ValueError(f'Proxy URL must start with http://, https://, socks4://, or socks5://: {proxy}')
        return v


class FetchRequest(BaseModel):
    """Request model for initiating fetch jobs with comprehensive validation."""
    
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
        """Validate that all links are valid URLs and not duplicates."""
        validated_links = []
        seen_links = set()
        
        for link in v:
            # Check URL format
            if not link.startswith(('http://', 'https://')):
                raise ValueError(f'URL must start with http:// or https://: {link}')
            
            # Check for duplicates
            if link in seen_links:
                raise ValueError(f'Duplicate URL found: {link}')
            
            seen_links.add(link)
            validated_links.append(link)
        
        return validated_links


class JobStatusResponse(BaseModel):
    """Response model for job submission with validated identifiers."""
    
    job_id: str = Field(
        ..., 
        min_length=1,
        max_length=100,
        description="Unique job identifier (UUID format recommended)"
    )
    status_url: str = Field(
        ..., 
        description="Complete URL to check job status"
    )
    
    @field_validator('job_id')
    @classmethod
    def validate_job_id(cls, v):
        """Validate job_id format - should be a valid UUID or alphanumeric string."""
        if not v.replace('-', '').replace('_', '').isalnum():
            raise ValueError('job_id must contain only alphanumeric characters, hyphens, and underscores')
        return v
    
    @field_validator('status_url')
    @classmethod
    def validate_status_url(cls, v):
        """Validate that status_url is a proper URL."""
        if not v.startswith(('http://', 'https://')):
            raise ValueError('status_url must be a valid HTTP/HTTPS URL')
        return v


class FetchResult(BaseModel):
    """Result model for individual URL fetch with comprehensive validation and status tracking."""
    
    url: str = Field(
        ..., 
        description="The URL that was fetched"
    )
    status: Literal["success", "error"] = Field(
        ..., 
        description="Fetch operation status - 'success' for successful fetch, 'error' for any failure"
    )
    html_content: Optional[str] = Field(
        None, 
        description="The complete HTML content of the fetched page (only present on success)"
    )
    error_message: Optional[str] = Field(
        None, 
        description="Detailed error message explaining the failure (only present on error)"
    )
    response_time_ms: Optional[int] = Field(
        None,
        ge=0,
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
        """Validate that URL is properly formatted."""
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v
    
    @field_validator('html_content')
    @classmethod
    def validate_html_content(cls, v, info):
        """Validate html_content is only present with success status."""
        if v is not None and info.data.get('status') == 'error':
            raise ValueError('html_content should be None for error status')
        return v
    
    @field_validator('error_message')
    @classmethod
    def validate_error_message(cls, v, info):
        """Validate error_message is only present with error status."""
        if v is not None and info.data.get('status') == 'success':
            raise ValueError('error_message should be None for success status')
        if info.data.get('status') == 'error' and not v:
            raise ValueError('error_message is required for error status')
        return v


class FetchResponse(BaseModel):
    """Response model for comprehensive job status tracking and results with progress monitoring."""
    
    job_id: str = Field(
        ..., 
        description="Unique job identifier"
    )
    status: Literal["pending", "in_progress", "completed", "failed"] = Field(
        ..., 
        description="Current job status - pending: queued, in_progress: actively fetching, completed: all done, failed: job-level failure"
    )
    results: List[FetchResult] = Field(
        default=[], 
        description="List of individual fetch results (populated as URLs are processed)"
    )
    total_urls: int = Field(
        ..., 
        ge=1,
        description="Total number of URLs in this job"
    )
    completed_urls: int = Field(
        ..., 
        ge=0,
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
    
    @field_validator('completed_urls')
    @classmethod
    def validate_completed_urls(cls, v, info):
        """Ensure completed_urls doesn't exceed total_urls."""
        if 'total_urls' in info.data and v > info.data['total_urls']:
            raise ValueError('completed_urls cannot exceed total_urls')
        return v
    
    @field_validator('results')
    @classmethod
    def validate_results_count(cls, v, info):
        """Ensure results count matches completed_urls."""
        if 'completed_urls' in info.data and len(v) != info.data['completed_urls']:
            raise ValueError('Number of results must match completed_urls')
        return v
    
    @field_validator('completed_at')
    @classmethod
    def validate_completed_at(cls, v, info):
        """Ensure completed_at is only set for completed/failed status."""
        if v is not None and info.data.get('status') not in ['completed', 'failed']:
            raise ValueError('completed_at should only be set for completed or failed jobs')
        return v
    
    @property
    def progress_percentage(self) -> float:
        """Calculate job completion percentage."""
        if self.total_urls == 0:
            return 0.0
        return (self.completed_urls / self.total_urls) * 100.0
    
    @property
    def is_finished(self) -> bool:
        """Check if job is in a terminal state."""
        return self.status in ['completed', 'failed'] 