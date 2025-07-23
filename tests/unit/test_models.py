"""
Unit tests for Pydantic models

This module tests all Pydantic models used in the Async HTML Fetcher Service,
including validation, constraints, and edge cases.

Test Coverage:
- FetchOptions: Configuration validation and constraints
- FetchRequest: Request validation and URL processing
- FetchResult: Result validation and status handling
- FetchResponse: Response validation and progress calculation
- JobStatusResponse: Job status validation and URL generation

Author: Async HTML Fetcher Service
Version: 1.0.0
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from api.models import (
    FetchOptions, FetchRequest, FetchResult, 
    FetchResponse, JobStatusResponse
)


# =============================================================================
# FETCHOPTIONS TESTS
# =============================================================================

class TestFetchOptions:
    """Test FetchOptions model validation and constraints."""
    
    def test_valid_fetch_options(self):
        """Test valid FetchOptions creation."""
        options = FetchOptions(
            proxies=["http://proxy.example.com:8080"],
            wait_min=1,
            wait_max=3,
            concurrency_limit=5
        )
        
        assert options.proxies == ["http://proxy.example.com:8080"]
        assert options.wait_min == 1
        assert options.wait_max == 3
        assert options.concurrency_limit == 5
    
    def test_default_fetch_options(self):
        """Test FetchOptions with default values."""
        options = FetchOptions()
        
        assert options.proxies == []
        assert options.wait_min == 1
        assert options.wait_max == 3
        assert options.concurrency_limit == 5
    
    def test_wait_max_less_than_wait_min(self):
        """Test validation when wait_max is less than wait_min."""
        with pytest.raises(ValidationError) as exc_info:
            FetchOptions(wait_min=5, wait_max=2)
        
        assert "wait_max must be greater than or equal to wait_min" in str(exc_info.value)
    
    def test_wait_min_below_minimum(self):
        """Test wait_min below minimum value."""
        with pytest.raises(ValidationError) as exc_info:
            FetchOptions(wait_min=-1)
        
        assert "Input should be greater than or equal to 0" in str(exc_info.value)
    
    def test_wait_min_above_maximum(self):
        """Test wait_min above maximum value."""
        with pytest.raises(ValidationError) as exc_info:
            FetchOptions(wait_min=31)
        
        assert "Input should be less than or equal to 30" in str(exc_info.value)
    
    def test_wait_max_above_maximum(self):
        """Test wait_max above maximum value."""
        with pytest.raises(ValidationError) as exc_info:
            FetchOptions(wait_max=61)
        
        assert "Input should be less than or equal to 60" in str(exc_info.value)
    
    def test_concurrency_limit_below_minimum(self):
        """Test concurrency_limit below minimum value."""
        with pytest.raises(ValidationError) as exc_info:
            FetchOptions(concurrency_limit=0)
        
        assert "Input should be greater than or equal to 1" in str(exc_info.value)
    
    def test_concurrency_limit_above_maximum(self):
        """Test concurrency_limit above maximum value."""
        with pytest.raises(ValidationError) as exc_info:
            FetchOptions(concurrency_limit=21)
        
        assert "Input should be less than or equal to 20" in str(exc_info.value)
    
    def test_valid_proxy_validation(self):
        """Test valid proxy URL validation."""
        options = FetchOptions(
            proxies=["http://proxy.example.com:8080", "https://proxy2.com:3128"]
        )
        
        assert len(options.proxies) == 2
        assert "http://proxy.example.com:8080" in options.proxies
        assert "https://proxy2.com:3128" in options.proxies
    
    def test_invalid_proxy_format(self):
        """Test invalid proxy URL format."""
        with pytest.raises(ValidationError) as exc_info:
            FetchOptions(proxies=["invalid-proxy"])
        
        assert "Invalid proxy URL format" in str(exc_info.value)
    
    def test_too_many_proxies(self):
        """Test proxy list exceeding maximum length."""
        proxies = [f"http://proxy{i}.example.com:8080" for i in range(51)]
        
        with pytest.raises(ValidationError) as exc_info:
            FetchOptions(proxies=proxies)
        
        assert "List should have at most 50 items" in str(exc_info.value)


# =============================================================================
# FETCHREQUEST TESTS
# =============================================================================

class TestFetchRequest:
    """Test FetchRequest model validation and URL processing."""
    
    def test_valid_fetch_request(self):
        """Test valid FetchRequest creation."""
        request = FetchRequest(
            links=["https://example.com", "https://test.com"],
            options=FetchOptions()
        )
        
        assert len(request.links) == 2
        assert "https://example.com" in request.links
        assert "https://test.com" in request.links
        assert isinstance(request.options, FetchOptions)
    
    def test_empty_links_list(self):
        """Test validation with empty links list."""
        with pytest.raises(ValidationError) as exc_info:
            FetchRequest(links=[])
        
        assert "List should have at least 1 item" in str(exc_info.value)
    
    def test_too_many_links(self):
        """Test links list exceeding maximum length."""
        links = [f"https://example{i}.com" for i in range(1001)]
        
        with pytest.raises(ValidationError) as exc_info:
            FetchRequest(links=links)
        
        assert "List should have at most 1000 items" in str(exc_info.value)
    
    def test_url_without_scheme(self):
        """Test URL without scheme (should auto-prepend https://)."""
        request = FetchRequest(links=["example.com"])
        
        assert request.links == ["https://example.com"]
    
    def test_duplicate_urls(self):
        """Test duplicate URL detection."""
        with pytest.raises(ValidationError) as exc_info:
            FetchRequest(links=["https://example.com", "https://example.com"])
        
        assert "Duplicate URL found" in str(exc_info.value)
    
    def test_dangerous_url_scheme(self):
        """Test dangerous URL scheme rejection."""
        with pytest.raises(ValidationError) as exc_info:
            FetchRequest(links=["javascript:alert('xss')"])
        
        assert "Potentially dangerous URL scheme" in str(exc_info.value)
    
    def test_data_url_scheme(self):
        """Test data URL scheme rejection."""
        with pytest.raises(ValidationError) as exc_info:
            FetchRequest(links=["data:text/html,<script>alert('xss')</script>"])
        
        assert "Potentially dangerous URL scheme" in str(exc_info.value)
    
    def test_invalid_url_format(self):
        """Test invalid URL format."""
        with pytest.raises(ValidationError) as exc_info:
            FetchRequest(links=["not-a-url"])
        
        assert "Invalid URL" in str(exc_info.value)
    
    def test_url_too_long(self):
        """Test URL exceeding maximum length."""
        long_url = "https://example.com/" + "a" * 2000
        
        with pytest.raises(ValidationError) as exc_info:
            FetchRequest(links=[long_url])
        
        assert "URL too long" in str(exc_info.value)


# =============================================================================
# FETCHRESULT TESTS
# =============================================================================

class TestFetchResult:
    """Test FetchResult model validation and status handling."""
    
    def test_successful_fetch_result(self):
        """Test successful fetch result creation."""
        result = FetchResult(
            url="https://example.com",
            status="success",
            html_content="<html><body>Hello</body></html>",
            response_time_ms=1250,
            status_code=200
        )
        
        assert result.url == "https://example.com"
        assert result.status == "success"
        assert result.html_content == "<html><body>Hello</body></html>"
        assert result.response_time_ms == 1250
        assert result.status_code == 200
        assert result.error_message is None
    
    def test_error_fetch_result(self):
        """Test error fetch result creation."""
        result = FetchResult(
            url="https://broken.com",
            status="error",
            error_message="Connection timeout"
        )
        
        assert result.url == "https://broken.com"
        assert result.status == "error"
        assert result.error_message == "Connection timeout"
        assert result.html_content is None
        assert result.response_time_ms is None
        assert result.status_code is None
    
    def test_success_with_error_message(self):
        """Test validation when success status has error message."""
        with pytest.raises(ValidationError) as exc_info:
            FetchResult(
                url="https://example.com",
                status="success",
                html_content="<html></html>",
                error_message="This should not be here"
            )
        
        assert "error_message should be None for success status" in str(exc_info.value)
    
    def test_error_without_error_message(self):
        """Test validation when error status has no error message."""
        with pytest.raises(ValidationError) as exc_info:
            FetchResult(
                url="https://broken.com",
                status="error"
            )
        
        assert "error_message is required for error status" in str(exc_info.value)
    
    def test_error_with_html_content(self):
        """Test validation when error status has HTML content."""
        with pytest.raises(ValidationError) as exc_info:
            FetchResult(
                url="https://broken.com",
                status="error",
                error_message="Connection failed",
                html_content="<html></html>"
            )
        
        assert "html_content should be None for error status" in str(exc_info.value)
    
    def test_invalid_status(self):
        """Test invalid status value."""
        with pytest.raises(ValidationError) as exc_info:
            FetchResult(
                url="https://example.com",
                status="invalid_status"
            )
        
        assert "Input should be 'success' or 'error'" in str(exc_info.value)
    
    def test_negative_response_time(self):
        """Test negative response time."""
        with pytest.raises(ValidationError) as exc_info:
            FetchResult(
                url="https://example.com",
                status="success",
                html_content="<html></html>",
                response_time_ms=-100
            )
        
        assert "Input should be greater than or equal to 0" in str(exc_info.value)
    
    def test_response_time_too_high(self):
        """Test response time exceeding maximum."""
        with pytest.raises(ValidationError) as exc_info:
            FetchResult(
                url="https://example.com",
                status="success",
                html_content="<html></html>",
                response_time_ms=400000
            )
        
        assert "Input should be less than or equal to 300000" in str(exc_info.value)
    
    def test_invalid_status_code(self):
        """Test invalid HTTP status code."""
        with pytest.raises(ValidationError) as exc_info:
            FetchResult(
                url="https://example.com",
                status="success",
                html_content="<html></html>",
                status_code=999
            )
        
        assert "Input should be less than or equal to 599" in str(exc_info.value)
    
    def test_html_content_too_large(self):
        """Test HTML content exceeding maximum size."""
        large_content = "<html>" + "a" * 10000000 + "</html>"
        
        with pytest.raises(ValidationError) as exc_info:
            FetchResult(
                url="https://example.com",
                status="success",
                html_content=large_content
            )
        
        assert "String should have at most 10000000 characters" in str(exc_info.value)


# =============================================================================
# FETCHRESPONSE TESTS
# =============================================================================

class TestFetchResponse:
    """Test FetchResponse model validation and progress calculation."""
    
    def test_pending_fetch_response(self):
        """Test pending fetch response creation."""
        response = FetchResponse(
            job_id="550e8400-e29b-41d4-a716-446655440000",
            status="pending",
            total_urls=5,
            completed_urls=0
        )
        
        assert response.job_id == "550e8400-e29b-41d4-a716-446655440000"
        assert response.status == "pending"
        assert response.total_urls == 5
        assert response.completed_urls == 0
        assert response.results == []
        assert response.progress_percentage == 0.0
        assert not response.is_finished
    
    def test_in_progress_fetch_response(self):
        """Test in-progress fetch response creation."""
        response = FetchResponse(
            job_id="550e8400-e29b-41d4-a716-446655440000",
            status="in_progress",
            total_urls=10,
            completed_urls=7,
            started_at=datetime.now()
        )
        
        assert response.status == "in_progress"
        assert response.total_urls == 10
        assert response.completed_urls == 7
        assert response.progress_percentage == 70.0
        assert not response.is_finished
    
    def test_completed_fetch_response(self):
        """Test completed fetch response creation."""
        result = FetchResult(
            url="https://example.com",
            status="success",
            html_content="<html></html>"
        )
        
        response = FetchResponse(
            job_id="550e8400-e29b-41d4-a716-446655440000",
            status="completed",
            results=[result],
            total_urls=1,
            completed_urls=1,
            started_at=datetime.now(),
            completed_at=datetime.now()
        )
        
        assert response.status == "completed"
        assert response.total_urls == 1
        assert response.completed_urls == 1
        assert len(response.results) == 1
        assert response.progress_percentage == 100.0
        assert response.is_finished
    
    def test_completed_urls_exceed_total(self):
        """Test validation when completed_urls exceeds total_urls."""
        with pytest.raises(ValidationError) as exc_info:
            FetchResponse(
                job_id="550e8400-e29b-41d4-a716-446655440000",
                status="in_progress",
                total_urls=5,
                completed_urls=10
            )
        
        assert "completed_urls cannot exceed total_urls" in str(exc_info.value)
    
    def test_results_count_mismatch(self):
        """Test validation when results count doesn't match completed_urls."""
        result = FetchResult(
            url="https://example.com",
            status="success",
            html_content="<html></html>"
        )
        
        with pytest.raises(ValidationError) as exc_info:
            FetchResponse(
                job_id="550e8400-e29b-41d4-a716-446655440000",
                status="completed",
                results=[result],
                total_urls=2,
                completed_urls=2
            )
        
        assert "Number of results must match completed_urls" in str(exc_info.value)
    
    def test_completed_at_without_completion_status(self):
        """Test validation when completed_at is set without completion status."""
        with pytest.raises(ValidationError) as exc_info:
            FetchResponse(
                job_id="550e8400-e29b-41d4-a716-446655440000",
                status="in_progress",
                total_urls=1,
                completed_urls=0,
                completed_at=datetime.now()
            )
        
        assert "completed_at should only be set for completed or failed jobs" in str(exc_info.value)
    
    def test_completed_at_before_started_at(self):
        """Test validation when completed_at is before started_at."""
        started_at = datetime.now()
        completed_at = datetime(2020, 1, 1)  # Before started_at
        
        with pytest.raises(ValidationError) as exc_info:
            FetchResponse(
                job_id="550e8400-e29b-41d4-a716-446655440000",
                status="completed",
                total_urls=1,
                completed_urls=1,
                started_at=started_at,
                completed_at=completed_at
            )
        
        assert "completed_at must be after started_at" in str(exc_info.value)
    
    def test_progress_percentage_calculation(self):
        """Test progress percentage calculation."""
        response = FetchResponse(
            job_id="550e8400-e29b-41d4-a716-446655440000",
            status="in_progress",
            total_urls=4,
            completed_urls=3
        )
        
        assert response.progress_percentage == 75.0
    
    def test_progress_percentage_zero_total(self):
        """Test progress percentage with zero total URLs."""
        response = FetchResponse(
            job_id="550e8400-e29b-41d4-a716-446655440000",
            status="pending",
            total_urls=0,
            completed_urls=0
        )
        
        assert response.progress_percentage == 0.0
    
    def test_is_finished_property(self):
        """Test is_finished property for different statuses."""
        # Pending - not finished
        pending = FetchResponse(
            job_id="550e8400-e29b-41d4-a716-446655440000",
            status="pending",
            total_urls=1,
            completed_urls=0
        )
        assert not pending.is_finished
        
        # In progress - not finished
        in_progress = FetchResponse(
            job_id="550e8400-e29b-41d4-a716-446655440000",
            status="in_progress",
            total_urls=1,
            completed_urls=0
        )
        assert not in_progress.is_finished
        
        # Completed - finished
        completed = FetchResponse(
            job_id="550e8400-e29b-41d4-a716-446655440000",
            status="completed",
            total_urls=1,
            completed_urls=1
        )
        assert completed.is_finished
        
        # Failed - finished
        failed = FetchResponse(
            job_id="550e8400-e29b-41d4-a716-446655440000",
            status="failed",
            total_urls=1,
            completed_urls=0
        )
        assert failed.is_finished


# =============================================================================
# JOBSTATUSRESPONSE TESTS
# =============================================================================

class TestJobStatusResponse:
    """Test JobStatusResponse model validation."""
    
    def test_valid_job_status_response(self):
        """Test valid JobStatusResponse creation."""
        response = JobStatusResponse(
            job_id="550e8400-e29b-41d4-a716-446655440000",
            status_url="/fetch/status/550e8400-e29b-41d4-a716-446655440000"
        )
        
        assert response.job_id == "550e8400-e29b-41d4-a716-446655440000"
        assert response.status_url == "/fetch/status/550e8400-e29b-41d4-a716-446655440000"
    
    def test_invalid_job_id_format(self):
        """Test invalid job ID format."""
        with pytest.raises(ValidationError) as exc_info:
            JobStatusResponse(
                job_id="invalid-uuid",
                status_url="/fetch/status/invalid-uuid"
            )
        
        assert "Invalid UUID format" in str(exc_info.value)
    
    def test_job_id_too_short(self):
        """Test job ID below minimum length."""
        with pytest.raises(ValidationError) as exc_info:
            JobStatusResponse(
                job_id="short",
                status_url="/fetch/status/short"
            )
        
        assert "String should have at least 36 characters" in str(exc_info.value)
    
    def test_job_id_too_long(self):
        """Test job ID above maximum length."""
        long_id = "550e8400-e29b-41d4-a716-446655440000-extra"
        
        with pytest.raises(ValidationError) as exc_info:
            JobStatusResponse(
                job_id=long_id,
                status_url=f"/fetch/status/{long_id}"
            )
        
        assert "String should have at most 36 characters" in str(exc_info.value)
    
    def test_status_url_too_long(self):
        """Test status URL exceeding maximum length."""
        long_url = "/fetch/status/" + "a" * 500
        
        with pytest.raises(ValidationError) as exc_info:
            JobStatusResponse(
                job_id="550e8400-e29b-41d4-a716-446655440000",
                status_url=long_url
            )
        
        assert "String should have at most 500 characters" in str(exc_info.value)
    
    def test_dangerous_status_url(self):
        """Test dangerous status URL scheme."""
        with pytest.raises(ValidationError) as exc_info:
            JobStatusResponse(
                job_id="550e8400-e29b-41d4-a716-446655440000",
                status_url="javascript:alert('xss')"
            )
        
        assert "Potentially dangerous URL scheme" in str(exc_info.value) 