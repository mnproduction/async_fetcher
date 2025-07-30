"""
Integration tests for API endpoints.

This module tests the API endpoints with mocked dependencies,
focusing on request/response handling, validation, and error cases.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from api.models import FetchResult, BatchFetchResponse

# Mark all tests in this file as integration tests
pytestmark = [pytest.mark.integration, pytest.mark.fast, pytest.mark.mock]


class TestHealthEndpoint:
    """Test cases for health endpoint."""

    def test_health_endpoint_success(self, test_client):
        """Test successful health check."""
        # Mock the global fetcher variable
        mock_fetcher = MagicMock()
        mock_fetcher.health_check = AsyncMock(return_value={
            "service": "SimpleFetcher",
            "status": "healthy",
            "flaresolverr_healthy": True,
            "cached_domains": 5,
            "timestamp": 1234567890.0
        })

        with patch('api.main.fetcher', mock_fetcher):
            response = test_client.get("/health")

            assert response.status_code == 200
            data = response.json()
            assert data["service"] == "SimpleFetcher"
            assert data["status"] == "healthy"
            assert data["flaresolverr_healthy"] is True
            assert "timestamp" in data

    def test_health_endpoint_flaresolverr_failure(self, test_client):
        """Test health check when FlareSolverr is down."""
        # Mock the global fetcher variable with failure
        mock_fetcher = MagicMock()
        mock_fetcher.health_check = AsyncMock(side_effect=Exception("FlareSolverr connection failed"))

        with patch('api.main.fetcher', mock_fetcher):
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
        
        # Check that all expected endpoints are listed
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
            content_length=35,
            status_code=200,
            execution_time=1.5,
            used_cookies=True,
            cookies_refreshed=False
        )

        # Mock the global fetcher variable
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_single = AsyncMock(return_value=mock_result)

        with patch('api.main.fetcher', mock_fetcher):
            response = test_client.post("/fetch", json={
                "url": "https://example.com",
                "force_refresh_cookies": False
            })

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["url"] == "https://example.com"
            assert data["content_length"] == 35
            assert data["status_code"] == 200
            assert data["used_cookies"] is True
            assert data["cookies_refreshed"] is False

    def test_single_fetch_failure(self, test_client):
        """Test single URL fetch failure."""
        mock_result = FetchResult(
            url="https://broken.com",
            success=False,
            content=None,
            content_length=0,
            status_code=None,
            execution_time=5.0,
            used_cookies=False,
            cookies_refreshed=False,
            error="Connection timeout"
        )

        # Mock the global fetcher variable
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_single = AsyncMock(return_value=mock_result)

        with patch('api.main.fetcher', mock_fetcher):
            response = test_client.post("/fetch", json={
                "url": "https://broken.com",
                "force_refresh_cookies": False
            })

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert data["error"] == "Connection timeout"
            assert data["content_length"] == 0

    def test_single_fetch_invalid_url(self, test_client):
        """Test single fetch with invalid URL."""
        response = test_client.post("/fetch", json={
            "url": "not-a-url",
            "force_refresh_cookies": False
        })
        
        assert response.status_code == 422  # Validation error

    def test_single_fetch_missing_url(self, test_client):
        """Test single fetch with missing URL."""
        response = test_client.post("/fetch", json={
            "force_refresh_cookies": False
        })
        
        assert response.status_code == 422  # Validation error


class TestBatchFetchEndpoint:
    """Test cases for batch fetch endpoint."""

    def test_batch_fetch_success(self, test_client):
        """Test successful batch fetch."""
        mock_response = BatchFetchResponse(
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
        )

        # Mock the global fetcher variable
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_batch = AsyncMock(return_value=mock_response)

        with patch('api.main.fetcher', mock_fetcher):
            response = test_client.post("/fetch/batch", json={
                "urls": ["https://example.com", "https://test.com"],
                "max_concurrent": 2,
                "force_refresh_cookies": False
            })

            assert response.status_code == 200
            data = response.json()
            assert data["total_urls"] == 2
            assert data["successful_urls"] == 2
            assert data["failed_urls"] == 0
            assert data["success_rate"] == 100.0
            assert len(data["results"]) == 2

    def test_batch_fetch_mixed_results(self, test_client):
        """Test batch fetch with mixed success/failure."""
        mock_response = BatchFetchResponse(
            total_urls=2,
            successful_urls=1,
            failed_urls=1,
            success_rate=50.0,
            total_execution_time=4.0,
            results=[
                FetchResult(
                    url="https://example.com",
                    success=True,
                    content="<html>Success</html>",
                    content_length=20,
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

        # Mock the global fetcher variable
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_batch = AsyncMock(return_value=mock_response)

        with patch('api.main.fetcher', mock_fetcher):
            response = test_client.post("/fetch/batch", json={
                "urls": ["https://example.com", "https://broken.com"],
                "max_concurrent": 2,
                "force_refresh_cookies": False
            })

            assert response.status_code == 200
            data = response.json()
            assert data["success_rate"] == 50.0
            assert data["successful_urls"] == 1
            assert data["failed_urls"] == 1

    def test_batch_fetch_empty_urls(self, test_client):
        """Test batch fetch with empty URL list."""
        response = test_client.post("/fetch/batch", json={
            "urls": [],
            "max_concurrent": 2,
            "force_refresh_cookies": False
        })
        
        assert response.status_code == 422  # Validation error

    def test_batch_fetch_invalid_concurrency(self, test_client):
        """Test batch fetch with invalid concurrency."""
        response = test_client.post("/fetch/batch", json={
            "urls": ["https://example.com"],
            "max_concurrent": 0,  # Invalid
            "force_refresh_cookies": False
        })
        
        assert response.status_code == 422  # Validation error


class TestCookieInfoEndpoint:
    """Test cases for cookie info endpoint."""

    def test_cookie_info_success(self, test_client):
        """Test successful cookie info retrieval."""
        mock_info = {
            "cached_domains": 2,
            "sessions": {
                "example.com": {
                    "cookies_count": 3,
                    "age_seconds": 300.0,
                    "user_agent": "Mozilla/5.0..."
                },
                "test.com": {
                    "cookies_count": 2,
                    "age_seconds": 150.0,
                    "user_agent": "Mozilla/5.0..."
                }
            }
        }

        # Mock the global fetcher variable
        mock_fetcher = MagicMock()
        mock_fetcher.cookie_manager.get_session_info = AsyncMock(return_value=mock_info)

        with patch('api.main.fetcher', mock_fetcher):
            response = test_client.get("/cookies/info")

            assert response.status_code == 200
            data = response.json()
            assert data["cached_domains"] == 2
            assert len(data["sessions"]) == 2
            assert "example.com" in data["sessions"]
            assert "test.com" in data["sessions"]

    def test_cookie_info_empty(self, test_client):
        """Test cookie info when no sessions exist."""
        mock_info = {
            "cached_domains": 0,
            "sessions": {}
        }

        # Mock the global fetcher variable
        mock_fetcher = MagicMock()
        mock_fetcher.cookie_manager.get_session_info = AsyncMock(return_value=mock_info)

        with patch('api.main.fetcher', mock_fetcher):
            response = test_client.get("/cookies/info")

            assert response.status_code == 200
            data = response.json()
            assert data["cached_domains"] == 0
            assert data["sessions"] == {}


class TestCleanupEndpoint:
    """Test cases for cleanup endpoint."""

    def test_cleanup_success(self, test_client):
        """Test successful cleanup of expired cookies."""
        # Mock the global fetcher variable
        mock_fetcher = MagicMock()
        mock_fetcher.cleanup_stale_cookies = AsyncMock(return_value=3)  # 3 sessions cleaned up

        with patch('api.main.fetcher', mock_fetcher):
            response = test_client.post("/cleanup")

            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Cleanup completed"
            assert data["sessions_cleaned"] == 3

    def test_cleanup_no_expired(self, test_client):
        """Test cleanup when no expired sessions exist."""
        # Mock the global fetcher variable
        mock_fetcher = MagicMock()
        mock_fetcher.cleanup_stale_cookies = AsyncMock(return_value=0)  # No sessions cleaned up

        with patch('api.main.fetcher', mock_fetcher):
            response = test_client.post("/cleanup")

            assert response.status_code == 200
            data = response.json()
            assert data["sessions_cleaned"] == 0
