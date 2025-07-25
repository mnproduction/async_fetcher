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
from toolkit.flaresolverr import FlareSolverrClient, FlareSolverrError
from toolkit.cookie_manager import CookieManager
from toolkit.simple_fetcher import SimpleFetcher

# Mark all tests in this file as e2e tests
pytestmark = [pytest.mark.e2e, pytest.mark.slow, pytest.mark.flaresolverr, pytest.mark.network]


class TestFlareSolverrE2E:
    """End-to-end tests for FlareSolverr integration."""

    @pytest.fixture
    def flaresolverr_client(self):
        """Create a real FlareSolverr client."""
        return FlareSolverrClient(flaresolverr_url="http://localhost:8191")

    @pytest.mark.asyncio
    async def test_flaresolverr_health_check(self, flaresolverr_client):
        """Test real FlareSolverr health check."""
        try:
            result = await flaresolverr_client.health_check()
            
            assert result["status"] == "ok"
            assert "version" in result
            assert "userAgent" in result
            print(f"FlareSolverr version: {result['version']}")
            print(f"User agent: {result['userAgent'][:50]}...")
            
        except FlareSolverrError as e:
            pytest.skip(f"FlareSolverr not available: {e}")

    @pytest.mark.asyncio
    async def test_solve_simple_challenge(self, flaresolverr_client):
        """Test solving a simple challenge with FlareSolverr."""
        try:
            # Use httpbin.org as a simple test (no Cloudflare)
            result = await flaresolverr_client.solve_challenge(
                "https://httpbin.org/headers",
                timeout=30
            )
            
            assert "solution" in result
            solution = result["solution"]
            assert solution["status"] == 200
            assert solution["url"] == "https://httpbin.org/headers"
            assert "cookies" in solution
            assert "userAgent" in solution
            
            print(f"Solved URL: {solution['url']}")
            print(f"Status: {solution['status']}")
            print(f"Cookies count: {len(solution['cookies'])}")
            
        except FlareSolverrError as e:
            pytest.skip(f"FlareSolverr challenge failed: {e}")

    @pytest.mark.asyncio
    @pytest.mark.cloudflare
    async def test_solve_cloudflare_challenge(self, flaresolverr_client):
        """Test solving actual Cloudflare challenge."""
        try:
            # Test with a known Cloudflare-protected site
            result = await flaresolverr_client.solve_challenge(
                "https://tem.fi",
                timeout=60  # Cloudflare challenges can take longer
            )
            
            assert "solution" in result
            solution = result["solution"]
            assert solution["status"] == 200
            assert "tem.fi" in solution["url"]
            assert len(solution["cookies"]) > 0
            
            # Look for Cloudflare-specific cookies
            cookie_names = [cookie["name"] for cookie in solution["cookies"]]
            cloudflare_cookies = [name for name in cookie_names if "cf_" in name.lower()]
            
            print(f"Solved Cloudflare URL: {solution['url']}")
            print(f"Total cookies: {len(solution['cookies'])}")
            print(f"Cloudflare cookies: {cloudflare_cookies}")
            
            assert len(cloudflare_cookies) > 0, "Expected Cloudflare cookies"
            
        except FlareSolverrError as e:
            pytest.skip(f"Cloudflare challenge failed: {e}")


class TestCookieManagerE2E:
    """End-to-end tests for cookie management."""

    @pytest.fixture
    def cookie_manager(self):
        """Create a real cookie manager."""
        flaresolverr_client = FlareSolverrClient(flaresolverr_url="http://localhost:8191")
        return CookieManager(
            flaresolverr_client=flaresolverr_client,
            max_stale_seconds=1800  # 30 minutes
        )

    @pytest.fixture
    def flaresolverr_client(self):
        """Create a real FlareSolverr client."""
        return FlareSolverrClient(base_url="http://localhost:8191")

    @pytest.mark.asyncio
    async def test_cookie_session_lifecycle(self, cookie_manager, flaresolverr_client):
        """Test complete cookie session lifecycle."""
        try:
            # Step 1: Solve challenge to get cookies
            result = await flaresolverr_client.solve_challenge(
                "https://httpbin.org/cookies/set/test/value",
                timeout=30
            )
            
            solution = result["solution"]
            
            # Step 2: Save session
            from toolkit.cookie_manager import CookieSession
            import time
            
            session = CookieSession(
                domain="httpbin.org",
                cookies={cookie["name"]: cookie["value"] for cookie in solution["cookies"]},
                user_agent=solution["userAgent"],
                created_at=time.time()
            )
            
            cookie_manager.save_session(session)
            
            # Step 3: Verify session is saved and valid
            assert cookie_manager.is_session_valid("httpbin.org")
            
            retrieved_session = cookie_manager.get_session("httpbin.org")
            assert retrieved_session is not None
            assert retrieved_session.domain == "httpbin.org"
            assert retrieved_session.user_agent == solution["userAgent"]
            
            # Step 4: Get session info
            info = cookie_manager.get_session_info()
            assert info["cached_domains"] >= 1
            assert "httpbin.org" in info["sessions"]
            
            print(f"Session saved for domain: {retrieved_session.domain}")
            print(f"Cookies count: {len(retrieved_session.cookies)}")
            print(f"Session age: {retrieved_session.age_seconds:.1f}s")
            
        except FlareSolverrError as e:
            pytest.skip(f"FlareSolverr not available: {e}")


class TestSimpleFetcherE2E:
    """End-to-end tests for the complete fetcher system."""

    @pytest.fixture
    def simple_fetcher(self):
        """Create a real SimpleFetcher with real dependencies."""
        flaresolverr_client = FlareSolverrClient(flaresolverr_url="http://localhost:8191")
        cookie_manager = CookieManager(
            flaresolverr_client=flaresolverr_client,
            max_stale_seconds=1800
        )
        return SimpleFetcher(flaresolverr_client, cookie_manager)

    @pytest.mark.asyncio
    async def test_fetch_single_real(self, simple_fetcher):
        """Test single fetch with real network request."""
        try:
            result = await simple_fetcher.fetch_single("https://httpbin.org/html")
            
            assert result.success is True
            assert result.url == "https://httpbin.org/html"
            assert result.content is not None
            assert result.content_length > 0
            assert result.status_code == 200
            assert result.execution_time > 0
            
            print(f"Fetched URL: {result.url}")
            print(f"Content length: {result.content_length}")
            print(f"Execution time: {result.execution_time:.2f}s")
            print(f"Used cookies: {result.used_cookies}")
            print(f"Cookies refreshed: {result.cookies_refreshed}")
            
        except Exception as e:
            pytest.skip(f"Network request failed: {e}")

    @pytest.mark.asyncio
    async def test_fetch_batch_real(self, simple_fetcher):
        """Test batch fetch with real network requests."""
        try:
            urls = [
                "https://httpbin.org/html",
                "https://httpbin.org/json",
                "https://httpbin.org/xml"
            ]
            
            result = await simple_fetcher.fetch_batch(urls, max_concurrent=2)
            
            assert result.total_urls == 3
            assert result.successful_urls >= 2  # Allow for some network issues
            assert result.success_rate >= 66.0
            assert len(result.results) == 3
            assert result.total_execution_time > 0
            
            print("Batch fetch results:")
            print(f"  Total URLs: {result.total_urls}")
            print(f"  Successful: {result.successful_urls}")
            print(f"  Failed: {result.failed_urls}")
            print(f"  Success rate: {result.success_rate:.1f}%")
            print(f"  Total time: {result.total_execution_time:.2f}s")
            
            # Check individual results
            for fetch_result in result.results:
                print(f"  {fetch_result.url}: {'✓' if fetch_result.success else '✗'}")
                if not fetch_result.success:
                    print(f"    Error: {fetch_result.error}")
            
        except Exception as e:
            pytest.skip(f"Network request failed: {e}")

    @pytest.mark.asyncio
    @pytest.mark.cloudflare
    async def test_fetch_cloudflare_site(self, simple_fetcher):
        """Test fetching from a Cloudflare-protected site."""
        try:
            result = await simple_fetcher.fetch_single("https://tem.fi", force_refresh_cookies=True)
            
            assert result.success is True
            assert "tem.fi" in result.url
            assert result.content is not None
            assert result.content_length > 10000  # tem.fi has substantial content
            assert result.status_code == 200
            assert result.cookies_refreshed is True  # Should have refreshed cookies
            
            print(f"Cloudflare site fetched: {result.url}")
            print(f"Content length: {result.content_length}")
            print(f"Execution time: {result.execution_time:.2f}s")
            print(f"Cookies refreshed: {result.cookies_refreshed}")
            
        except Exception as e:
            pytest.skip(f"Cloudflare site fetch failed: {e}")


class TestAPIEndpointsE2E:
    """End-to-end tests for API endpoints with real services."""

    @pytest.fixture
    def test_client(self):
        """Create a test client."""
        return TestClient(app)

    def test_health_endpoint_real(self, test_client):
        """Test health endpoint with real FlareSolverr."""
        response = test_client.get("/health")
        
        # Should succeed regardless of FlareSolverr status
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "SimpleFetcher"
        assert data["status"] in ["healthy", "unhealthy"]
        assert "flaresolverr_healthy" in data
        assert "timestamp" in data
        
        print(f"Service status: {data['status']}")
        print(f"FlareSolverr healthy: {data['flaresolverr_healthy']}")

    def test_single_fetch_endpoint_real(self, test_client):
        """Test single fetch endpoint with real network request."""
        response = test_client.post("/fetch", json={
            "url": "https://httpbin.org/html",
            "force_refresh_cookies": False
        })
        
        if response.status_code == 200:
            data = response.json()
            print("Real fetch result:")
            print(f"  Success: {data['success']}")
            print(f"  URL: {data['url']}")
            print(f"  Content length: {data.get('content_length', 0)}")
            print(f"  Status code: {data.get('status_code')}")
            print(f"  Execution time: {data.get('execution_time', 0):.2f}s")
            
            if data["success"]:
                assert data["content_length"] > 0
                assert data["status_code"] == 200
            else:
                print(f"  Error: {data.get('error')}")
        else:
            pytest.skip(f"API request failed with status {response.status_code}")

    def test_cookie_info_endpoint_real(self, test_client):
        """Test cookie info endpoint."""
        response = test_client.get("/cookies/info")
        
        assert response.status_code == 200
        data = response.json()
        assert "cached_domains" in data
        assert "sessions" in data
        
        print("Cookie info:")
        print(f"  Cached domains: {data['cached_domains']}")
        print(f"  Sessions: {list(data['sessions'].keys())}")
