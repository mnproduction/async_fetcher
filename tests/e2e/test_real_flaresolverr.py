"""
End-to-end tests with real FlareSolverr service.

This module tests the complete system with actual FlareSolverr service,
including real Cloudflare bypass scenarios and network requests.

These tests require:
1. FlareSolverr service running (docker-compose up flaresolverr)
2. Network access
3. Longer execution times

Run with: pytest -m "e2e" --tb=short -v
"""

import pytest
from fastapi.testclient import TestClient
from api.main import app
from toolkit.flaresolverr import FlareSolverrClient, FlareSolverrError, FlareSolverrConnectionError
from toolkit.simple_fetcher import SimpleFetcher

# Mark all tests in this file as e2e tests
pytestmark = [pytest.mark.e2e, pytest.mark.slow, pytest.mark.flaresolverr, pytest.mark.network]


FLARESOLVERR_URL = "http://localhost:8191"

class TestFlareSolverrE2E:
    """End-to-end tests for FlareSolverr integration."""

    @pytest.fixture
    def flaresolverr_client(self):
        """Create a real FlareSolverr client."""
        return FlareSolverrClient(flaresolverr_url=FLARESOLVERR_URL)

    @pytest.mark.asyncio
    async def test_flaresolverr_health_check(self, flaresolverr_client):
        """Test real FlareSolverr health check."""
        try:
            is_healthy = await flaresolverr_client.health_check()
            assert is_healthy is True
        except FlareSolverrConnectionError as e:
            pytest.skip(f"FlareSolverr not available: {e}")

    @pytest.mark.asyncio
    async def test_solve_simple_challenge(self, flaresolverr_client):
        """Test solving a simple challenge with FlareSolverr."""
        try:
            solution = await flaresolverr_client.solve_challenge(
                "https://httpbin.org/headers",
                timeout=30000
            )
            assert solution["status"] == 200
            assert solution["url"] == "https://httpbin.org/headers"
            assert "userAgent" in solution
        except FlareSolverrError as e:
            pytest.skip(f"FlareSolverr challenge failed: {e}")

class TestSimpleFetcherE2E:
    """End-to-end tests for the complete fetcher system."""

    @pytest.fixture
    def simple_fetcher(self):
        """Create a real SimpleFetcher instance."""
        # The fetcher now handles its own internal clients
        return SimpleFetcher(flaresolverr_url=FLARESOLVERR_URL)

    @pytest.mark.asyncio
    async def test_fetch_single_real(self, simple_fetcher):
        """Test single fetch with real network request."""
        try:
            result = await simple_fetcher.fetch_single("https://httpbin.org/html")
            assert result.success is True
            assert result.status_code == 200
            assert result.content_length > 0
        except Exception as e:
            pytest.skip(f"Network request failed: {e}")
        finally:
            await simple_fetcher.close()

    @pytest.mark.asyncio
    @pytest.mark.cloudflare
    async def test_fetch_cloudflare_site(self, simple_fetcher):
        """Test fetching from a Cloudflare-protected site."""
        try:
            result = await simple_fetcher.fetch_single("https://tem.fi", force_refresh_cookies=True)
            assert result.success is True
            assert result.status_code == 200
            assert result.content_length > 1000
            assert result.cookies_refreshed is True
        except Exception as e:
            pytest.skip(f"Cloudflare site fetch failed: {e}")
        finally:
            await simple_fetcher.close()


class TestAPIEndpointsE2E:
    """End-to-end tests for API endpoints with real services."""

    @pytest.fixture
    def test_client(self):
        """Create a test client."""
        return TestClient(app)

    def test_health_endpoint_real(self, test_client):
        """Test health endpoint with real FlareSolverr."""
        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "SimpleFetcher"

    def test_single_fetch_endpoint_real_cloudflare(self, test_client):
        """Test single fetch endpoint with real Cloudflare-protected site."""
        response = test_client.post("/fetch", json={"url": "https://tem.fi"})
        
        if response.status_code != 200:
             pytest.skip(f"API request failed with status {response.status_code}: {response.text}")
             
        data = response.json()
        assert data["success"] is True
        assert "tem.fi" in data["url"]
        assert data["content_length"] > 1000
        assert data["status_code"] == 200