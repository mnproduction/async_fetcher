"""
Unit tests for Simple Fetcher.

This module tests the simplified fetcher functionality including
single URL fetching, batch processing, and error handling.
"""

import pytest
import aiohttp
from unittest.mock import AsyncMock, MagicMock, patch
from toolkit.simple_fetcher import SimpleFetcher
from toolkit.cookie_manager import CookieSession

# Mark all tests in this file as unit tests
pytestmark = [pytest.mark.unit, pytest.mark.fast, pytest.mark.mock]


class TestSimpleFetcher:
    """Test cases for SimpleFetcher."""

    @pytest.fixture
    def fetcher(self, mock_flaresolverr_client, mock_cookie_manager):
        """Create a SimpleFetcher for testing."""
        return SimpleFetcher(
            flaresolverr_client=mock_flaresolverr_client,
            cookie_manager=mock_cookie_manager
        )

    @pytest.mark.asyncio
    async def test_fetch_single_with_cached_cookies(self, fetcher, mock_cookie_manager, mock_aiohttp_session):
        """Test single fetch with cached cookies."""
        # Setup: cookies are available and valid
        mock_cookie_manager.is_session_valid.return_value = True
        mock_cookie_manager.get_session.return_value = CookieSession(
            domain="example.com",
            cookies={"cf_clearance": "test_token"},
            user_agent="Mozilla/5.0...",
            created_at=1234567890.0
        )
        
        # Mock aiohttp response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="<html><body>Test content</body></html>")
        mock_response.headers = {"content-type": "text/html"}
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = mock_aiohttp_session
            mock_session.get.return_value.__aenter__.return_value = mock_response
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            result = await fetcher.fetch_single("https://example.com")
            
            assert result.success is True
            assert result.url == "https://example.com"
            assert result.content == "<html><body>Test content</body></html>"
            assert result.content_length == 35
            assert result.status_code == 200
            assert result.used_cookies is True
            assert result.cookies_refreshed is False
            assert result.error is None

    @pytest.mark.asyncio
    async def test_fetch_single_without_cookies(self, fetcher, mock_flaresolverr_client, mock_cookie_manager):
        """Test single fetch without cached cookies (requires FlareSolverr)."""
        # Setup: no cached cookies
        mock_cookie_manager.is_session_valid.return_value = False
        mock_cookie_manager.get_session.return_value = None
        
        # Mock FlareSolverr response
        mock_flaresolverr_client.solve_challenge.return_value = {
            "solution": {
                "url": "https://example.com",
                "status": 200,
                "cookies": [
                    {"name": "cf_clearance", "value": "new_token", "domain": "example.com"}
                ],
                "userAgent": "Mozilla/5.0..."
            }
        }
        
        result = await fetcher.fetch_single("https://example.com")
        
        assert result.success is True
        assert result.url == "https://example.com"
        assert result.used_cookies is False  # No cached cookies used
        assert result.cookies_refreshed is True  # New cookies obtained
        mock_flaresolverr_client.solve_challenge.assert_called_once()
        mock_cookie_manager.save_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_single_force_refresh(self, fetcher, mock_flaresolverr_client, mock_cookie_manager):
        """Test single fetch with forced cookie refresh."""
        # Setup: cookies exist but force refresh is True
        mock_cookie_manager.is_session_valid.return_value = True
        
        # Mock FlareSolverr response
        mock_flaresolverr_client.solve_challenge.return_value = {
            "solution": {
                "url": "https://example.com",
                "status": 200,
                "cookies": [
                    {"name": "cf_clearance", "value": "refreshed_token", "domain": "example.com"}
                ],
                "userAgent": "Mozilla/5.0..."
            }
        }
        
        result = await fetcher.fetch_single("https://example.com", force_refresh_cookies=True)
        
        assert result.success is True
        assert result.cookies_refreshed is True
        mock_flaresolverr_client.solve_challenge.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_single_error_handling(self, fetcher, mock_cookie_manager):
        """Test single fetch error handling."""
        # Setup: cookies available
        mock_cookie_manager.is_session_valid.return_value = True
        mock_cookie_manager.get_session.return_value = CookieSession(
            domain="example.com",
            cookies={"cf_clearance": "test_token"},
            user_agent="Mozilla/5.0...",
            created_at=1234567890.0
        )
        
        # Mock aiohttp to raise an exception
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = MagicMock()
            mock_session.get.side_effect = aiohttp.ClientError("Connection failed")
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            result = await fetcher.fetch_single("https://example.com")
            
            assert result.success is False
            assert result.error == "Connection failed"
            assert result.content is None
            assert result.status_code is None

    @pytest.mark.asyncio
    async def test_fetch_batch_success(self, fetcher, mock_cookie_manager, mock_aiohttp_session):
        """Test batch fetch with all successful URLs."""
        # Setup: cookies available for all domains
        mock_cookie_manager.is_session_valid.return_value = True
        mock_cookie_manager.get_session.return_value = CookieSession(
            domain="example.com",
            cookies={"cf_clearance": "test_token"},
            user_agent="Mozilla/5.0...",
            created_at=1234567890.0
        )
        
        # Mock aiohttp responses
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="<html>Content</html>")
        mock_response.headers = {"content-type": "text/html"}
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = mock_aiohttp_session
            mock_session.get.return_value.__aenter__.return_value = mock_response
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            urls = ["https://example.com", "https://test.com"]
            result = await fetcher.fetch_batch(urls, max_concurrent=2)
            
            assert result.total_urls == 2
            assert result.successful_urls == 2
            assert result.failed_urls == 0
            assert result.success_rate == 100.0
            assert len(result.results) == 2
            assert all(r.success for r in result.results)

    @pytest.mark.asyncio
    async def test_fetch_batch_mixed_results(self, fetcher, mock_cookie_manager):
        """Test batch fetch with mixed success/failure results."""
        # Setup: cookies available
        mock_cookie_manager.is_session_valid.return_value = True
        mock_cookie_manager.get_session.return_value = CookieSession(
            domain="example.com",
            cookies={"cf_clearance": "test_token"},
            user_agent="Mozilla/5.0...",
            created_at=1234567890.0
        )
        
        # Mock aiohttp to succeed for first URL, fail for second
        def mock_get_side_effect(url, **kwargs):
            if "example.com" in str(url):
                mock_response = MagicMock()
                mock_response.status = 200
                mock_response.text = AsyncMock(return_value="<html>Success</html>")
                mock_response.headers = {"content-type": "text/html"}
                return mock_response
            else:
                raise aiohttp.ClientError("Connection failed")
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = MagicMock()
            mock_session.get.side_effect = mock_get_side_effect
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            urls = ["https://example.com", "https://broken.com"]
            result = await fetcher.fetch_batch(urls, max_concurrent=2)
            
            assert result.total_urls == 2
            assert result.successful_urls == 1
            assert result.failed_urls == 1
            assert result.success_rate == 50.0
            assert len(result.results) == 2
            
            # Check individual results
            success_result = next(r for r in result.results if r.success)
            error_result = next(r for r in result.results if not r.success)
            
            assert success_result.url == "https://example.com"
            assert error_result.url == "https://broken.com"
            assert error_result.error == "Connection failed"

    @pytest.mark.asyncio
    async def test_fetch_batch_concurrency_limit(self, fetcher, mock_cookie_manager, mock_aiohttp_session):
        """Test batch fetch respects concurrency limits."""
        # Setup: cookies available
        mock_cookie_manager.is_session_valid.return_value = True
        mock_cookie_manager.get_session.return_value = CookieSession(
            domain="example.com",
            cookies={"cf_clearance": "test_token"},
            user_agent="Mozilla/5.0...",
            created_at=1234567890.0
        )
        
        # Mock aiohttp response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="<html>Content</html>")
        mock_response.headers = {"content-type": "text/html"}
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = mock_aiohttp_session
            mock_session.get.return_value.__aenter__.return_value = mock_response
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            # Test with 5 URLs but max_concurrent=2
            urls = [f"https://example{i}.com" for i in range(5)]
            result = await fetcher.fetch_batch(urls, max_concurrent=2)
            
            assert result.total_urls == 5
            assert result.successful_urls == 5
            assert len(result.results) == 5

    def test_extract_domain(self, fetcher):
        """Test domain extraction utility method."""
        assert fetcher._extract_domain("https://example.com/path") == "example.com"
        assert fetcher._extract_domain("http://sub.example.com") == "sub.example.com"
        assert fetcher._extract_domain("https://example.com:8080/path") == "example.com"
