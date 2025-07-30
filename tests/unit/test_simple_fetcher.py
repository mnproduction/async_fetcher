"""
Unit tests for Simple Fetcher.

This module tests the simplified fetcher functionality including
single URL fetching, batch processing, and error handling.
"""

import pytest
import aiohttp
from unittest.mock import AsyncMock, MagicMock, patch
from toolkit.simple_fetcher import SimpleFetcher, FetchResult
from toolkit.cookie_manager import CookieSession

# Mark all tests in this file as unit tests
pytestmark = [pytest.mark.unit, pytest.mark.fast, pytest.mark.mock]


class TestSimpleFetcher:
    """Test cases for SimpleFetcher."""

    @pytest.fixture
    def fetcher(self):
        """Create a SimpleFetcher for testing."""
        # We patch the dependencies inside the tests themselves
        return SimpleFetcher(flaresolverr_url="http://mock-flaresolverr:8191")

    @pytest.mark.asyncio
    async def test_fetch_single_with_cached_cookies(self, fetcher):
        """Test single fetch with cached cookies."""
        mock_result = FetchResult(url="https://example.com", success=True, used_cookies=True, cookies_refreshed=False)
        
        with patch.object(fetcher, '_fetch_with_cookies', AsyncMock(return_value=mock_result)) as mock_fetch, \
             patch.object(fetcher.flaresolverr_client, 'health_check', AsyncMock(return_value=True)):
            
            result = await fetcher.fetch_single("https://example.com")
            
            assert result.success is True
            assert result.used_cookies is True
            assert result.cookies_refreshed is False
            mock_fetch.assert_called_once_with("https://example.com")

    @pytest.mark.asyncio
    async def test_fetch_single_needs_cookie_refresh(self, fetcher):
        """Test single fetch where initial attempt fails and cookies are refreshed."""
        # First call to _fetch_with_cookies fails, second succeeds
        mock_results = [
            FetchResult(url="https://example.com", success=False, error="HTTP 403"),
            FetchResult(url="https://example.com", success=True, used_cookies=True)
        ]

        with patch.object(fetcher, '_fetch_with_cookies', AsyncMock(side_effect=mock_results)) as mock_fetch, \
             patch.object(fetcher.flaresolverr_client, 'health_check', AsyncMock(return_value=True)), \
             patch.object(fetcher.cookie_manager, 'invalidate_domain', AsyncMock()) as mock_invalidate:

            result = await fetcher.fetch_single("https://example.com")
            
            assert result.success is True
            assert result.cookies_refreshed is True  # Should be marked as refreshed
            assert mock_invalidate.call_count == 1
            assert mock_fetch.call_count == 2
            
    @pytest.mark.asyncio
    async def test_fetch_batch(self, fetcher):
        """Test batch fetch with all successful requests."""
        urls = ["https://example1.com", "https://example2.com"]
        
        # Mock fetch_single to return a successful result for any URL
        mock_result = FetchResult(url="", success=True)
        with patch.object(fetcher, 'fetch_single', AsyncMock(return_value=mock_result)) as mock_fetch_single:
            results = await fetcher.fetch_batch(urls, max_concurrent=2)
            
            assert len(results) == 2
            assert all(r.success for r in results)
            assert mock_fetch_single.call_count == 2

    @pytest.mark.asyncio
    async def test_fetch_single_flaresolverr_unavailable(self, fetcher):
        """Test fetch_single when FlareSolverr is not healthy."""
        with patch.object(fetcher.flaresolverr_client, 'health_check', AsyncMock(return_value=False)):
            result = await fetcher.fetch_single("https://example.com")
            
            assert result.success is False
            assert result.error == "FlareSolverr service is not available"

    @pytest.mark.asyncio
    async def test_close_session(self, fetcher):
        """Test that the close method closes the aiohttp session."""
        # Ensure a session is created
        await fetcher._ensure_http_session()
        assert fetcher._http_session is not None
        
        await fetcher.close()
        
        assert fetcher._http_session.closed