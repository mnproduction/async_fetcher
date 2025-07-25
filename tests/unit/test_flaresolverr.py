"""
Unit tests for FlareSolverr client.

This module tests the FlareSolverr client functionality including
health checks, challenge solving, and error handling.
"""

import asyncio
import pytest
import aiohttp
from unittest.mock import AsyncMock, MagicMock, patch
from toolkit.flaresolverr import FlareSolverrClient, FlareSolverrError

# Mark all tests in this file as unit tests
pytestmark = [pytest.mark.unit, pytest.mark.fast, pytest.mark.mock]


class TestFlareSolverrClient:
    """Test cases for FlareSolverr client."""

    @pytest.fixture
    def client(self):
        """Create a FlareSolverr client for testing."""
        return FlareSolverrClient(flaresolverr_url="http://localhost:8191")

    @pytest.fixture
    def mock_session_response(self):
        """Create a mock aiohttp response."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "status": "ok",
            "message": "",
            "version": "3.3.25",
            "userAgent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36..."
        })
        return mock_response

    @pytest.mark.asyncio
    async def test_health_check_success(self, client, mock_session_response):
        """Test successful health check."""
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_session_response
            
            result = await client.health_check()
            
            assert result["status"] == "ok"
            assert result["version"] == "3.3.25"
            assert "userAgent" in result
            mock_get.assert_called_once_with("http://localhost:8191/v1")

    @pytest.mark.asyncio
    async def test_health_check_failure(self, client):
        """Test health check failure."""
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.side_effect = aiohttp.ClientError("Connection failed")
            
            with pytest.raises(FlareSolverrError, match="Health check failed"):
                await client.health_check()

    @pytest.mark.asyncio
    async def test_solve_challenge_success(self, client):
        """Test successful challenge solving."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "status": "ok",
            "message": "",
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
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.return_value.__aenter__.return_value = mock_response
            
            result = await client.solve_challenge("https://example.com")
            
            assert result["solution"]["url"] == "https://example.com"
            assert result["solution"]["status"] == 200
            assert len(result["solution"]["cookies"]) == 2
            assert result["solution"]["cookies"][0]["name"] == "cf_clearance"

    @pytest.mark.asyncio
    async def test_solve_challenge_failure(self, client):
        """Test challenge solving failure."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "status": "error",
            "message": "Challenge solving failed"
        })
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.return_value.__aenter__.return_value = mock_response
            
            with pytest.raises(FlareSolverrError, match="Challenge solving failed"):
                await client.solve_challenge("https://example.com")

    @pytest.mark.asyncio
    async def test_solve_challenge_timeout(self, client):
        """Test challenge solving timeout."""
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.side_effect = asyncio.TimeoutError()
            
            with pytest.raises(FlareSolverrError, match="Request timeout"):
                await client.solve_challenge("https://example.com", timeout=5)

    def test_invalid_url(self):
        """Test client creation with invalid URL."""
        # FlareSolverr client doesn't validate URL in constructor
        # It will fail during actual requests
        client = FlareSolverrClient(flaresolverr_url="not-a-url")
        assert client.flaresolverr_url == "not-a-url"
        assert client.api_endpoint == "not-a-url/v1"

    @pytest.mark.asyncio
    async def test_solve_challenge_request_payload(self, client):
        """Test that solve_challenge sends correct payload."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "status": "ok",
            "solution": {"url": "https://example.com", "status": 200, "cookies": []}
        })
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.return_value.__aenter__.return_value = mock_response
            
            await client.solve_challenge("https://example.com", timeout=30)
            
            # Verify the request payload
            call_args = mock_post.call_args
            assert call_args[0][0] == "http://localhost:8191/v1"
            
            payload = call_args[1]['json']
            assert payload['cmd'] == 'request.get'
            assert payload['url'] == 'https://example.com'
            assert payload['maxTimeout'] == 30000  # 30 seconds in milliseconds

    @pytest.mark.asyncio
    async def test_http_error_handling(self, client):
        """Test HTTP error handling."""
        mock_response = MagicMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Internal Server Error")
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_response
            
            with pytest.raises(FlareSolverrError, match="HTTP 500"):
                await client.health_check()
