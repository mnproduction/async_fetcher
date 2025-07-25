"""
Unit tests for Pydantic models.

This module tests the simplified Pydantic models used in the
Simplified Content Fetcher.
"""

import pytest
from pydantic import ValidationError
from api.models import (
    SingleFetchRequest, BatchFetchRequest, FetchResult,
    BatchFetchResponse, HealthResponse
)

# Mark all tests in this file as unit tests
pytestmark = [pytest.mark.unit, pytest.mark.fast, pytest.mark.mock]



class TestSingleFetchRequest:
    """Test cases for SingleFetchRequest model."""

    def test_valid_single_fetch_request(self):
        """Test valid SingleFetchRequest creation."""
        request = SingleFetchRequest(
            url="https://example.com",
            force_refresh_cookies=False
        )

        assert request.url == "https://example.com"
        assert request.force_refresh_cookies is False

    def test_single_fetch_request_defaults(self):
        """Test SingleFetchRequest with default values."""
        request = SingleFetchRequest(url="https://example.com")

        assert request.url == "https://example.com"
        assert request.force_refresh_cookies is False

    def test_invalid_url(self):
        """Test SingleFetchRequest with invalid URL."""
        with pytest.raises(ValidationError):
            SingleFetchRequest(url="not-a-url")

    def test_dangerous_url_scheme(self):
        """Test SingleFetchRequest with dangerous URL scheme."""
        with pytest.raises(ValidationError):
            SingleFetchRequest(url="javascript:alert('xss')")


class TestBatchFetchRequest:
    """Test cases for BatchFetchRequest model."""

    def test_valid_batch_fetch_request(self):
        """Test valid BatchFetchRequest creation."""
        request = BatchFetchRequest(
            urls=["https://example.com", "https://test.com"],
            max_concurrent=2,
            force_refresh_cookies=False
        )

        assert len(request.urls) == 2
        assert request.max_concurrent == 2
        assert request.force_refresh_cookies is False

    def test_batch_fetch_request_defaults(self):
        """Test BatchFetchRequest with default values."""
        request = BatchFetchRequest(urls=["https://example.com"])

        assert len(request.urls) == 1
        assert request.max_concurrent == 5
        assert request.force_refresh_cookies is False

    def test_empty_urls_list(self):
        """Test BatchFetchRequest with empty URLs list."""
        with pytest.raises(ValidationError):
            BatchFetchRequest(urls=[])

    def test_invalid_max_concurrent(self):
        """Test BatchFetchRequest with invalid max_concurrent."""
        with pytest.raises(ValidationError):
            BatchFetchRequest(
                urls=["https://example.com"],
                max_concurrent=0
            )


class TestFetchResult:
    """Test cases for FetchResult model."""

    def test_successful_fetch_result(self):
        """Test successful FetchResult creation."""
        result = FetchResult(
            url="https://example.com",
            success=True,
            content="<html><body>Test</body></html>",
            content_length=30,
            status_code=200,
            execution_time=1.5,
            used_cookies=True,
            cookies_refreshed=False
        )

        assert result.url == "https://example.com"
        assert result.success is True
        assert result.content == "<html><body>Test</body></html>"
        assert result.content_length == 30
        assert result.status_code == 200
        assert result.execution_time == 1.5
        assert result.used_cookies is True
        assert result.cookies_refreshed is False
        assert result.error is None

    def test_failed_fetch_result(self):
        """Test failed FetchResult creation."""
        result = FetchResult(
            url="https://broken.com",
            success=False,
            content=None,
            content_length=0,
            status_code=None,
            execution_time=5.0,
            used_cookies=False,
            cookies_refreshed=False,
            error="Connection failed"
        )

        assert result.url == "https://broken.com"
        assert result.success is False
        assert result.content is None
        assert result.content_length == 0
        assert result.status_code is None
        assert result.execution_time == 5.0
        assert result.used_cookies is False
        assert result.cookies_refreshed is False
        assert result.error == "Connection failed"


class TestBatchFetchResponse:
    """Test cases for BatchFetchResponse model."""

    def test_batch_fetch_response(self):
        """Test BatchFetchResponse creation."""
        results = [
            FetchResult(
                url="https://example.com",
                success=True,
                content="<html>Example</html>",
                content_length=20,
                status_code=200,
                execution_time=1.0,
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

        response = BatchFetchResponse(
            total_urls=2,
            successful_urls=1,
            failed_urls=1,
            success_rate=50.0,
            total_execution_time=3.0,
            results=results
        )

        assert response.total_urls == 2
        assert response.successful_urls == 1
        assert response.failed_urls == 1
        assert response.success_rate == 50.0
        assert response.total_execution_time == 3.0
        assert len(response.results) == 2


class TestHealthResponse:
    """Test cases for HealthResponse model."""

    def test_healthy_response(self):
        """Test healthy HealthResponse creation."""
        response = HealthResponse(
            service="SimpleFetcher",
            status="healthy",
            flaresolverr_healthy=True,
            cached_domains=5,
            timestamp=1234567890.0
        )

        assert response.service == "SimpleFetcher"
        assert response.status == "healthy"
        assert response.flaresolverr_healthy is True
        assert response.cached_domains == 5
        assert response.timestamp == 1234567890.0
        assert response.error is None

    def test_unhealthy_response(self):
        """Test unhealthy HealthResponse creation."""
        response = HealthResponse(
            service="SimpleFetcher",
            status="unhealthy",
            flaresolverr_healthy=False,
            cached_domains=0,
            timestamp=1234567890.0,
            error="FlareSolverr connection failed"
        )

        assert response.service == "SimpleFetcher"
        assert response.status == "unhealthy"
        assert response.flaresolverr_healthy is False
        assert response.cached_domains == 0
        assert response.timestamp == 1234567890.0
        assert response.error == "FlareSolverr connection failed"
