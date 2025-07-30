"""
Unit tests for FlareSolverr client.

This module tests the FlareSolverr client functionality including
health checks, challenge solving, and error handling.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from toolkit.flaresolverr import (
    FlareSolverrClient,
    FlareSolverrConnectionError,
    FlareSolverrError,
    FlareSolverrTimeoutError,
)

# Mark all tests in this file as unit tests
pytestmark = [pytest.mark.unit, pytest.mark.fast, pytest.mark.mock]


class TestFlareSolverrClient:
    """Test cases for FlareSolverr client."""

    @pytest.fixture
    def client(self):
        """Create a FlareSolverr client for testing."""
        return FlareSolverrClient(flaresolverr_url="http://localhost:8191")

    @pytest.mark.asyncio
    async def test_health_check_success(self, client):
        """Test successful health check."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "msg": "FlareSolverr is ready!",
                "version": "3.3.25",
                "userAgent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36...",
            }
        )

        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_response

            result = await client.health_check()

            assert result is True
            # Check that the call was made with the correct URL (ignore timeout parameter)
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert call_args[0][0] == "http://localhost:8191"

    @pytest.mark.asyncio
    async def test_health_check_failure(self, client):
        """Test health check failure."""
        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_get.side_effect = aiohttp.ClientError("Connection failed")

            result = await client.health_check()
            assert result is False

    @pytest.mark.asyncio
    async def test_health_check_invalid_response(self, client):
        """Test health check with invalid response."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"msg": "Service not ready", "version": "3.3.25"}
        )

        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_response

            result = await client.health_check()
            assert result is False

    @pytest.mark.asyncio
    async def test_solve_challenge_success(self, client):
        """Test successful challenge solving."""
        mock_response = {
            "status": "ok",
            "message": "",
            "solution": {
                "url": "https://example.com",
                "status": 200,
                "cookies": [
                    {"name": "cf_clearance", "value": "test_token", "domain": "example.com"},
                    {"name": "session_id", "value": "abc123", "domain": "example.com"},
                ],
                "userAgent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36...",
            },
        }

        with patch.object(client, "_make_request") as mock_request:
            mock_request.return_value = mock_response

            result = await client.solve_challenge("https://example.com")

            assert result["url"] == "https://example.com"
            assert result["status"] == 200
            assert len(result["cookies"]) == 2
            assert result["cookies"][0]["name"] == "cf_clearance"

    @pytest.mark.asyncio
    async def test_solve_challenge_failure(self, client):
        """Test challenge solving failure."""
        mock_response = {"status": "error", "message": "Challenge solving failed"}

        with patch.object(client, "_make_request") as mock_request:
            mock_request.return_value = mock_response

            with pytest.raises(FlareSolverrError, match="Failed to solve challenge"):
                await client.solve_challenge("https://example.com")

    @pytest.mark.asyncio
    async def test_solve_challenge_timeout(self, client):
        """Test challenge solving timeout."""
        with patch.object(client, "_make_request") as mock_request:
            mock_request.side_effect = FlareSolverrTimeoutError("Request to FlareSolverr timed out")

            with pytest.raises(FlareSolverrTimeoutError, match="Request to FlareSolverr timed out"):
                await client.solve_challenge("https://example.com", timeout=5)

    @pytest.mark.asyncio
    async def test_solve_challenge_request_payload(self, client):
        """Test that solve_challenge sends correct payload."""
        mock_response = {
            "status": "ok",
            "solution": {"url": "https://example.com", "status": 200, "cookies": []},
        }

        with patch.object(client, "_make_request") as mock_request:
            mock_request.return_value = mock_response

            await client.solve_challenge("https://example.com", timeout=30)

            # Verify the request payload
            call_args = mock_request.call_args
            payload = call_args[0][0]
            assert payload["cmd"] == "request.get"
            assert payload["url"] == "https://example.com"
            assert payload["maxTimeout"] == 30  # Timeout is passed as-is to the method

    @pytest.mark.asyncio
    async def test_get_cookies_for_domain(self, client):
        """Test getting cookies for domain."""
        mock_solution = {
            "url": "https://example.com",
            "status": 200,
            "cookies": [
                {"name": "cf_clearance", "value": "test_token", "domain": "example.com"},
                {"name": "session_id", "value": "abc123", "domain": "example.com"},
            ],
            "userAgent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36...",
        }

        with patch.object(client, "solve_challenge") as mock_solve:
            mock_solve.return_value = mock_solution

            result = await client.get_cookies_for_domain("https://example.com")

            assert result["cookies_dict"]["cf_clearance"] == "test_token"
            assert result["cookies_dict"]["session_id"] == "abc123"
            assert result["cookies_list"] == mock_solution["cookies"]
            assert result["user_agent"] == mock_solution["userAgent"]
            assert result["domain"] == "example.com"
            assert result["final_url"] == "https://example.com"
            assert result["status_code"] == 200

    @pytest.mark.asyncio
    async def test_create_session(self, client):
        """Test creating a session."""
        mock_response = {"status": "ok", "message": "", "session": "test_session_id"}

        with patch.object(client, "_make_request") as mock_request:
            mock_request.return_value = mock_response

            result = await client.create_session("test_session_id")

            assert result is True
            call_args = mock_request.call_args
            payload = call_args[0][0]
            assert payload["cmd"] == "sessions.create"
            assert payload["session"] == "test_session_id"

    @pytest.mark.asyncio
    async def test_destroy_session(self, client):
        """Test destroying a session."""
        mock_response = {"status": "ok", "message": ""}

        with patch.object(client, "_make_request") as mock_request:
            mock_request.return_value = mock_response

            result = await client.destroy_session("test_session_id")

            assert result is True
            call_args = mock_request.call_args
            payload = call_args[0][0]
            assert payload["cmd"] == "sessions.destroy"
            assert payload["session"] == "test_session_id"

    @pytest.mark.asyncio
    async def test_http_error_handling(self, client):
        """Test HTTP error handling."""
        with patch.object(client, "_make_request") as mock_request:
            mock_request.side_effect = FlareSolverrConnectionError(
                "HTTP 500: Internal Server Error"
            )

            with pytest.raises(FlareSolverrConnectionError, match="HTTP 500"):
                await client.solve_challenge("https://example.com")

    @pytest.mark.asyncio
    async def test_connection_error_handling(self, client):
        """Test connection error handling."""
        with patch.object(client, "_make_request") as mock_request:
            mock_request.side_effect = FlareSolverrConnectionError(
                "Connection error: Network unreachable"
            )

            with pytest.raises(FlareSolverrConnectionError, match="Connection error"):
                await client.solve_challenge("https://example.com")

    def test_client_initialization(self):
        """Test client initialization with different URLs."""
        client = FlareSolverrClient(flaresolverr_url="http://custom:8191")
        assert client.flaresolverr_url == "http://custom:8191"
        assert client.api_endpoint == "http://custom:8191/v1"
        assert client.default_timeout == 60000

    def test_client_initialization_with_trailing_slash(self):
        """Test client initialization with trailing slash in URL."""
        client = FlareSolverrClient(flaresolverr_url="http://localhost:8191/")
        assert client.flaresolverr_url == "http://localhost:8191"
        assert client.api_endpoint == "http://localhost:8191/v1"
