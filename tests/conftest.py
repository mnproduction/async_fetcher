"""
Pytest fixtures for Async HTML Fetcher Service tests

This module provides reusable fixtures for unit and integration tests,
including test clients, sample data, and mock objects.

Fixtures:
- test_client: FastAPI TestClient for API testing
- sample_fetch_request: Sample FetchRequest for testing
- sample_job_id: Sample job ID with cleanup
- event_loop: Async event loop for async tests
- mock_browser: Mock browser for testing
- sample_fetch_result: Sample FetchResult for testing
- rate_limiter: Rate limiter instance for testing

Author: Async HTML Fetcher Service
Version: 1.0.0
"""

import pytest
import asyncio
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient
from httpx import AsyncClient

# Import application modules
from api.main import app
from api.logic import jobs, create_job, update_job_status
from api.models import FetchRequest, FetchOptions, FetchResult, FetchResponse
from api.rate_limiting import RateLimiter, RateLimitConfig
from api.sanitization import sanitize_url, sanitize_proxy_url


# =============================================================================
# TEST CLIENT FIXTURES
# =============================================================================

@pytest.fixture
def test_client():
    """
    Create a test client for the FastAPI app.
    
    Returns:
        TestClient: FastAPI test client for making HTTP requests
    """
    return TestClient(app)


@pytest.fixture
async def async_client():
    """
    Create an async test client for the FastAPI app.
    
    Returns:
        AsyncClient: Async HTTP client for testing
    """
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


# =============================================================================
# SAMPLE DATA FIXTURES
# =============================================================================

@pytest.fixture
def sample_fetch_options():
    """
    Create sample fetch options for testing.
    
    Returns:
        FetchOptions: Sample fetch configuration
    """
    return FetchOptions(
        proxies=["http://proxy.example.com:8080", "https://proxy2.example.com:3128"],
        wait_min=1,
        wait_max=3,
        concurrency_limit=5
    )


@pytest.fixture
def sample_fetch_request(sample_fetch_options):
    """
    Create a sample fetch request for testing.
    
    Args:
        sample_fetch_options: Sample fetch options
        
    Returns:
        FetchRequest: Sample fetch request
    """
    return FetchRequest(
        links=[
            "https://example.com",
            "https://test.com",
            "https://sample.org"
        ],
        options=sample_fetch_options
    )


@pytest.fixture
def sample_fetch_request_simple():
    """
    Create a simple sample fetch request for testing.
    
    Returns:
        FetchRequest: Simple fetch request with minimal options
    """
    return FetchRequest(
        links=["https://example.com"],
        options=FetchOptions()
    )


@pytest.fixture
def sample_fetch_result_success():
    """
    Create a sample successful fetch result.
    
    Returns:
        FetchResult: Sample successful fetch result
    """
    return FetchResult(
        url="https://example.com",
        status="success",
        html_content="<html><body><h1>Hello World</h1></body></html>",
        response_time_ms=1250,
        status_code=200
    )


@pytest.fixture
def sample_fetch_result_error():
    """
    Create a sample error fetch result.
    
    Returns:
        FetchResult: Sample error fetch result
    """
    return FetchResult(
        url="https://broken.com",
        status="error",
        error_message="Connection timeout after 30 seconds",
        response_time_ms=30000
    )


@pytest.fixture
def sample_fetch_response(sample_job_id, sample_fetch_result_success):
    """
    Create a sample fetch response.
    
    Args:
        sample_job_id: Sample job ID
        sample_fetch_result_success: Sample successful fetch result
        
    Returns:
        FetchResponse: Sample fetch response
    """
    return FetchResponse(
        job_id=sample_job_id,
        status="completed",
        results=[sample_fetch_result_success],
        total_urls=1,
        completed_urls=1,
        started_at=datetime.now(),
        completed_at=datetime.now()
    )


# =============================================================================
# JOB MANAGEMENT FIXTURES
# =============================================================================

@pytest.fixture
def sample_job_id(sample_fetch_request_simple):
    """
    Create a sample job and return its ID with cleanup.
    
    Args:
        sample_fetch_request_simple: Simple sample fetch request
        
    Yields:
        str: Sample job ID
        
    Note:
        Automatically cleans up the job after the test
    """
    job_id = create_job(sample_fetch_request_simple)
    yield job_id
    
    # Clean up after the test
    if job_id in jobs:
        del jobs[job_id]


@pytest.fixture
def sample_job_id_complex(sample_fetch_request):
    """
    Create a complex sample job and return its ID with cleanup.
    
    Args:
        sample_fetch_request: Complex sample fetch request
        
    Yields:
        str: Sample job ID
        
    Note:
        Automatically cleans up the job after the test
    """
    job_id = create_job(sample_fetch_request)
    yield job_id
    
    # Clean up after the test
    if job_id in jobs:
        del jobs[job_id]


@pytest.fixture
def sample_job_id_in_progress(sample_fetch_request_simple):
    """
    Create a sample job in progress state.
    
    Args:
        sample_fetch_request_simple: Simple sample fetch request
        
    Yields:
        str: Sample job ID in progress state
    """
    job_id = create_job(sample_fetch_request_simple)
    update_job_status(job_id, "in_progress")
    yield job_id
    
    # Clean up after the test
    if job_id in jobs:
        del jobs[job_id]


@pytest.fixture
def sample_job_id_completed(sample_fetch_request_simple, sample_fetch_result_success):
    """
    Create a sample completed job.
    
    Args:
        sample_fetch_request_simple: Simple sample fetch request
        sample_fetch_result_success: Sample successful fetch result
        
    Yields:
        str: Sample job ID in completed state
    """
    from api.logic import add_job_result
    
    job_id = create_job(sample_fetch_request_simple)
    update_job_status(job_id, "in_progress")
    add_job_result(job_id, sample_fetch_result_success.model_dump())
    yield job_id
    
    # Clean up after the test
    if job_id in jobs:
        del jobs[job_id]


# =============================================================================
# MOCK FIXTURES
# =============================================================================

@pytest.fixture
def mock_browser():
    """
    Create a mock browser for testing.
    
    Returns:
        MagicMock: Mock browser object
    """
    mock = MagicMock()
    mock.fetch = AsyncMock(return_value={
        "status": "success",
        "html": "<html><body>Test content</body></html>",
        "response_time": 1000,
        "status_code": 200
    })
    return mock


@pytest.fixture
def mock_browser_error():
    """
    Create a mock browser that returns errors.
    
    Returns:
        MagicMock: Mock browser object that returns errors
    """
    mock = MagicMock()
    mock.fetch = AsyncMock(side_effect=Exception("Browser error"))
    return mock


@pytest.fixture
def mock_rate_limiter():
    """
    Create a mock rate limiter for testing.
    
    Returns:
        MagicMock: Mock rate limiter
    """
    mock = MagicMock()
    mock.is_allowed = AsyncMock(return_value=(True, {
        "limit": 60,
        "remaining": 59,
        "reset_time": 1234567890
    }))
    return mock


# =============================================================================
# RATE LIMITING FIXTURES
# =============================================================================

@pytest.fixture
def test_rate_limiter():
    """
    Create a test rate limiter instance.
    
    Returns:
        RateLimiter: Test rate limiter with minimal configuration
    """
    config = RateLimitConfig(
        requests_per_minute=10,
        requests_per_hour=100,
        burst_limit=5,
        window_size_seconds=60
    )
    return RateLimiter(config)


@pytest.fixture
def test_rate_limiter_strict():
    """
    Create a strict test rate limiter instance.
    
    Returns:
        RateLimiter: Test rate limiter with strict limits
    """
    config = RateLimitConfig(
        requests_per_minute=2,
        requests_per_hour=10,
        burst_limit=1,
        window_size_seconds=60
    )
    return RateLimiter(config)


# =============================================================================
# ASYNC EVENT LOOP FIXTURES
# =============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """
    Create an event loop for async tests.
    
    Returns:
        asyncio.AbstractEventLoop: Event loop for async testing
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    
    yield loop
    
    # Clean up
    if not loop.is_closed():
        loop.close()


# =============================================================================
# TEST DATA FIXTURES
# =============================================================================

@pytest.fixture
def sample_urls():
    """
    Create a list of sample URLs for testing.
    
    Returns:
        List[str]: List of sample URLs
    """
    return [
        "https://example.com",
        "https://test.com",
        "https://sample.org",
        "https://demo.net",
        "https://mock.io"
    ]


@pytest.fixture
def sample_proxies():
    """
    Create a list of sample proxy URLs for testing.
    
    Returns:
        List[str]: List of sample proxy URLs
    """
    return [
        "http://proxy1.example.com:8080",
        "https://proxy2.example.com:3128",
        "socks5://proxy3.example.com:1080"
    ]


@pytest.fixture
def invalid_urls():
    """
    Create a list of invalid URLs for testing validation.
    
    Returns:
        List[str]: List of invalid URLs
    """
    return [
        "not-a-url",
        "javascript:alert('xss')",
        "data:text/html,<script>alert('xss')</script>",
        "ftp://example.com",
        "http://" + "a" * 3000  # Too long URL
    ]


@pytest.fixture
def invalid_proxies():
    """
    Create a list of invalid proxy URLs for testing validation.
    
    Returns:
        List[str]: List of invalid proxy URLs
    """
    return [
        "not-a-proxy",
        "http://proxy.example.com",  # Missing port
        "invalid://proxy.example.com:8080",  # Invalid protocol
        "http://" + "a" * 600  # Too long proxy URL
    ]


# =============================================================================
# UTILITY FIXTURES
# =============================================================================

@pytest.fixture
def clean_jobs():
    """
    Clean up all jobs before and after tests.
    
    Yields:
        None: Cleanup fixture
        
    Note:
        Clears all jobs before and after each test
    """
    # Clean up before test
    jobs.clear()
    yield
    # Clean up after test
    jobs.clear()


@pytest.fixture
def mock_time(monkeypatch):
    """
    Mock time.time() for consistent testing.
    
    Args:
        monkeypatch: Pytest monkeypatch fixture
        
    Returns:
        float: Mock timestamp
    """
    mock_time_value = 1234567890.0
    
    def mock_time_func():
        return mock_time_value
    
    monkeypatch.setattr("time.time", mock_time_func)
    return mock_time_value


@pytest.fixture
def mock_uuid(monkeypatch):
    """
    Mock uuid.uuid4() for consistent testing.
    
    Args:
        monkeypatch: Pytest monkeypatch fixture
        
    Returns:
        str: Mock UUID
    """
    mock_uuid_value = "550e8400-e29b-41d4-a716-446655440000"
    
    def mock_uuid_func():
        return mock_uuid_value
    
    monkeypatch.setattr("uuid.uuid4", mock_uuid_func)
    return mock_uuid_value


# =============================================================================
# INTEGRATION TEST FIXTURES
# =============================================================================

@pytest.fixture
def api_test_data():
    """
    Create comprehensive test data for API integration tests.
    
    Returns:
        Dict: Comprehensive test data
    """
    return {
        "valid_request": {
            "links": ["https://example.com", "https://test.com"],
            "options": {
                "proxies": ["http://proxy.example.com:8080"],
                "wait_min": 1,
                "wait_max": 3,
                "concurrency_limit": 5
            }
        },
        "invalid_request": {
            "links": [],  # Empty links
            "options": {
                "wait_min": 10,
                "wait_max": 5  # Invalid timing
            }
        },
        "malformed_request": {
            "links": ["not-a-url"],
            "options": {
                "proxies": ["invalid-proxy"]
            }
        }
    }


@pytest.fixture
def expected_responses():
    """
    Create expected response data for API tests.
    
    Returns:
        Dict: Expected response data
    """
    return {
        "job_status_response": {
            "job_id": "550e8400-e29b-41d4-a716-446655440000",
            "status_url": "/fetch/status/550e8400-e29b-41d4-a716-446655440000"
        },
        "fetch_response": {
            "job_id": "550e8400-e29b-41d4-a716-446655440000",
            "status": "pending",
            "results": [],
            "total_urls": 1,
            "completed_urls": 0,
            "started_at": None,
            "completed_at": None
        },
        "error_response": {
            "error": "Validation failed",
            "detail": ["links: List should have at least 1 item"],
            "type": "validation_error"
        }
    } 