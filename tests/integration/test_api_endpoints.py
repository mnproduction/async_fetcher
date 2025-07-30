"""
Integration tests for API endpoints.

This module tests the API endpoints with mocked dependencies,
focusing on request/response handling, validation, and error cases.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.models import FetchResult

# Mark all tests in this file as integration tests
pytestmark = [pytest.mark.integration, pytest.mark.fast, pytest.mark.mock]


class TestHealthEndpoint:
    """Test cases for health endpoint."""

    def test_health_endpoint_success(self, test_client):
        """Test successful health check."""
        mock_fetcher = MagicMock()
        mock_fetcher.health_check = AsyncMock(
            return_value={
                "service": "SimpleFetcher",
                "status": "healthy",
                "flaresolverr_healthy": True,
                "cached_domains": 5,
                "timestamp": 1234567890.0,
            }
        )

        with patch("api.main.fetcher", mock_fetcher):
            response = test_client.get("/health")

            assert response.status_code == 200
            data = response.json()
            assert data["service"] == "SimpleFetcher"
            assert data["status"] == "healthy"
            assert data["flaresolverr_healthy"] is True
            assert "timestamp" in data

    def test_health_endpoint_flaresolverr_failure(self, test_client):
        """Test health check when FlareSolverr is down."""
        mock_fetcher = MagicMock()
        mock_fetcher.health_check = AsyncMock(
            side_effect=Exception("FlareSolverr connection failed")
        )

        with patch("api.main.fetcher", mock_fetcher):
            response = test_client.get("/health")

            assert response.status_code == 200
            data = response.json()
            assert data["service"] == "SimpleFetcher"
            assert data["status"] == "unhealthy"
            assert data["flaresolverr_healthy"] is False
            assert "FlareSolverr connection failed" in data["error"]


class TestRootEndpoint:
    """Test cases for root endpoint."""

    def test_root_endpoint(self, test_client):
        """Test root endpoint returns service information."""
        response = test_client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Simplified Content Fetcher"
        assert data["version"] == "2.0.0"
        assert "endpoints" in data
        assert "features" in data

        endpoints = data["endpoints"]
        assert "health" in endpoints
        assert "fetch_single" in endpoints
        assert "fetch_batch" in endpoints
        assert "cookie_info" in endpoints


class TestSingleFetchEndpoint:
    """Test cases for single fetch endpoint."""

    def test_single_fetch_success(self, test_client):
        """Test successful single URL fetch."""
        mock_result = FetchResult(
            url="https://example.com",
            success=True,
            content="<html><body>Test content</body></html>",
            content_length=38,
            status_code=200,
            execution_time=1.5,
            used_cookies=True,
            cookies_refreshed=False,
        )
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_single = AsyncMock(return_value=mock_result)

        with patch("api.main.fetcher", mock_fetcher):
            response = test_client.post(
                "/fetch", json={"url": "https://example.com", "force_refresh_cookies": False}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["url"] == "https://example.com"
            assert data["content_length"] == 38
            assert data["status_code"] == 200

    def test_single_fetch_invalid_url(self, test_client):
        """Test single fetch with invalid URL."""
        response = test_client.post("/fetch", json={"url": "not-a-url"})
        assert response.status_code == 422


class TestBatchFetchEndpoint:
    """Test cases for batch fetch endpoint."""

    def test_batch_fetch_success(self, test_client):
        """Test successful batch fetch."""
        # The fetcher's fetch_batch method returns a LIST of FetchResult objects
        mock_results_list = [
            FetchResult(
                url="https://example.com", success=True, status_code=200, execution_time=1.5
            ),
            FetchResult(url="https://test.com", success=True, status_code=200, execution_time=1.8),
        ]
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_batch = AsyncMock(return_value=mock_results_list)

        with patch("api.main.fetcher", mock_fetcher):
            response = test_client.post(
                "/fetch/batch", json={"urls": ["https://example.com", "https://test.com"]}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["total_urls"] == 2
            assert data["successful_urls"] == 2
            assert data["failed_urls"] == 0
            assert len(data["results"]) == 2

    def test_batch_fetch_mixed_results(self, test_client):
        """Test batch fetch with mixed success/failure."""
        mock_results_list = [
            FetchResult(url="https://example.com", success=True, status_code=200),
            FetchResult(url="https://broken.com", success=False, error="Connection failed"),
        ]
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_batch = AsyncMock(return_value=mock_results_list)

        with patch("api.main.fetcher", mock_fetcher):
            response = test_client.post(
                "/fetch/batch", json={"urls": ["https://example.com", "https://broken.com"]}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["successful_urls"] == 1
            assert data["failed_urls"] == 1


class TestCookieInfoEndpoint:
    """Test cases for cookie info endpoint."""

    def test_cookie_info_success(self, test_client):
        """Test successful cookie info retrieval."""
        mock_info = {"example.com": {"cookies_count": 3}, "test.com": {"cookies_count": 2}}
        # The API endpoint calls fetcher.get_cookie_info directly
        mock_fetcher = MagicMock()
        mock_fetcher.get_cookie_info = AsyncMock(return_value=mock_info)

        with patch("api.main.fetcher", mock_fetcher):
            response = test_client.get("/cookies/info")

            assert response.status_code == 200
            data = response.json()
            assert data["cached_domains"] == 2
            assert "example.com" in data["sessions"]
