"""
Pytest fixtures for Simplified Content Fetcher tests

This module provides reusable fixtures for unit and integration tests,
including test clients, sample data, and mock objects for the simplified
FlareSolverr + aiohttp architecture.

Fixtures:
- test_client: FastAPI TestClient for API testing
- mock_flaresolverr: Mock FlareSolverr client
- mock_cookie_manager: Mock cookie manager
- sample_fetch_requests: Sample request data
- sample_fetch_results: Sample result data

Author: Simplified Content Fetcher
Version: 2.0.0
"""

import pytest
import pytest_asyncio
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient
from httpx import AsyncClient

# Import application modules
from api.main import app
from api.models import (
    SingleFetchRequest, BatchFetchRequest, FetchResult,
    BatchFetchResponse
)
from toolkit.flaresolverr import FlareSolverrClient
from toolkit.cookie_manager import CookieManager, CookieSession
from toolkit.simple_fetcher import SimpleFetcher


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


@pytest_asyncio.fixture
async def async_client():
    """
    Create an async test client for the FastAPI app.

    Returns:
        AsyncClient: Async HTTP client for testing
    """
    from httpx import ASGITransport

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client


# =============================================================================
# SAMPLE DATA FIXTURES
# =============================================================================

@pytest.fixture
def sample_single_fetch_request():
    """
    Create a sample single fetch request for testing.

    Returns:
        SingleFetchRequest: Sample single fetch request
    """
    return SingleFetchRequest(
        url="https://example.com",
        force_refresh_cookies=False
    )


@pytest.fixture
def sample_batch_fetch_request():
    """
    Create a sample batch fetch request for testing.

    Returns:
        BatchFetchRequest: Sample batch fetch request
    """
    return BatchFetchRequest(
        urls=["https://example.com", "https://test.com", "https://sample.org"],
        max_concurrent=3,
        force_refresh_cookies=False
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
        success=True,
        content="<html><body><h1>Hello World</h1></body></html>",
        content_length=45,
        status_code=200,
        execution_time=1.25,
        used_cookies=True,
        cookies_refreshed=False,
        error=None
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
        success=False,
        content=None,
        content_length=0,
        status_code=None,
        execution_time=30.0,
        used_cookies=False,
        cookies_refreshed=False,
        error="Connection timeout after 30 seconds"
    )


@pytest.fixture
def sample_batch_response():
    """
    Create a sample batch fetch response.

    Returns:
        BatchFetchResponse: Sample batch response
    """
    return BatchFetchResponse(
        total_urls=3,
        successful_urls=2,
        failed_urls=1,
        success_rate=66.7,
        total_execution_time=5.5,
        results=[
            FetchResult(
                url="https://example.com",
                success=True,
                content="<html>Example</html>",
                content_length=20,
                status_code=200,
                execution_time=1.5,
                used_cookies=True,
                cookies_refreshed=False
            ),
            FetchResult(
                url="https://test.com",
                success=True,
                content="<html>Test</html>",
                content_length=17,
                status_code=200,
                execution_time=2.0,
                used_cookies=True,
                cookies_refreshed=False
            ),
            FetchResult(
                url="https://broken.com",
                success=False,
                content=None,
                content_length=0,
                status_code=None,
                execution_time=2.0,
                used_cookies=False,
                cookies_refreshed=False,
                error="Connection failed"
            )
        ]
    )


# =============================================================================
# MOCK FIXTURES
# =============================================================================

@pytest.fixture
def mock_flaresolverr_client():
    """
    Create a mock FlareSolverr client for testing.

    Returns:
        MagicMock: Mock FlareSolverr client
    """
    mock = MagicMock(spec=FlareSolverrClient)
    mock.health_check = AsyncMock(return_value={
        "status": "ok",
        "version": "3.3.25",
        "userAgent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36..."
    })
    mock.solve_challenge = AsyncMock(return_value={
        "solution": {
            "url": "https://example.com",
            "status": 200,
            "cookies": [
                {"name": "cf_clearance", "value": "test_token", "domain": "example.com"},
                {"name": "session_id", "value": "abc123", "domain": "example.com"}
            ],
            "userAgent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36..."
        }
    })
    return mock


@pytest.fixture
def mock_cookie_manager():
    """
    Create a mock cookie manager for testing.

    Returns:
        MagicMock: Mock cookie manager
    """
    mock = MagicMock(spec=CookieManager)
    mock.get_session = MagicMock(return_value=CookieSession(
        domain="example.com",
        cookies_dict={"cf_clearance": "test_token", "session_id": "abc123"},
        cookies_list=[{"name": "cf_clearance", "value": "test_token"}],
        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36...",
        created_at=time.time(),
        expires_at=time.time() + 1800,
        last_used=time.time()
    ))
    mock.save_session = MagicMock()
    mock.is_session_valid = MagicMock(return_value=True)
    mock.cleanup_expired = MagicMock()
    mock.get_session_info = MagicMock(return_value={
        "cached_domains": 1,
        "sessions": {
            "example.com": {
                "cookies_count": 2,
                "age_seconds": 300.0,
                "user_agent": "Mozilla/5.0..."
            }
        }
    })
    return mock


@pytest.fixture
def mock_simple_fetcher():
    """
    Create a mock simple fetcher for testing.

    Returns:
        MagicMock: Mock simple fetcher
    """
    mock = MagicMock(spec=SimpleFetcher)
    mock.fetch_single = AsyncMock(return_value=FetchResult(
        url="https://example.com",
        success=True,
        content="<html><body>Test content</body></html>",
        content_length=35,
        status_code=200,
        execution_time=1.5,
        used_cookies=True,
        cookies_refreshed=False
    ))
    mock.fetch_batch = AsyncMock(return_value=BatchFetchResponse(
        total_urls=2,
        successful_urls=2,
        failed_urls=0,
        success_rate=100.0,
        total_execution_time=3.0,
        results=[
            FetchResult(
                url="https://example.com",
                success=True,
                content="<html>Example</html>",
                content_length=20,
                status_code=200,
                execution_time=1.5,
                used_cookies=True,
                cookies_refreshed=False
            ),
            FetchResult(
                url="https://test.com",
                success=True,
                content="<html>Test</html>",
                content_length=17,
                status_code=200,
                execution_time=1.5,
                used_cookies=True,
                cookies_refreshed=False
            )
        ]
    ))
    return mock


# =============================================================================
# UTILITY FIXTURES
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
        "https://httpbin.org/html"
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
def mock_aiohttp_session():
    """
    Create a mock aiohttp session for testing.

    Returns:
        MagicMock: Mock aiohttp session
    """
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value="<html><body>Test content</body></html>")
    mock_response.headers = {"content-type": "text/html"}

    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    return mock_session


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
        "valid_single_request": {
            "url": "https://example.com",
            "force_refresh_cookies": False
        },
        "valid_batch_request": {
            "urls": ["https://example.com", "https://test.com"],
            "max_concurrent": 2,
            "force_refresh_cookies": False
        },
        "invalid_single_request": {
            "url": "not-a-url",
            "force_refresh_cookies": False
        },
        "invalid_batch_request": {
            "urls": [],  # Empty URLs
            "max_concurrent": 0  # Invalid concurrency
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
        "health_response": {
            "service": "SimpleFetcher",
            "status": "healthy",
            "flaresolverr_healthy": True,
            "cached_domains": 0
        },
        "single_fetch_success": {
            "url": "https://example.com",
            "success": True,
            "content_length": 1000,
            "status_code": 200,
            "used_cookies": True,
            "cookies_refreshed": False
        },
        "batch_fetch_success": {
            "total_urls": 2,
            "successful_urls": 2,
            "failed_urls": 0,
            "success_rate": 100.0
        }
    }