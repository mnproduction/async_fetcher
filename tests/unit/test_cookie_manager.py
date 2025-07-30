"""
Unit tests for Cookie Manager.

This module tests the cookie management functionality including
session storage, validation, expiration, and cleanup.
"""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from toolkit.cookie_manager import CookieManager, CookieSession

# Mark all tests in this file as unit tests
pytestmark = [pytest.mark.unit, pytest.mark.fast, pytest.mark.mock]


class TestCookieSession:
    """Test cases for CookieSession."""

    def test_cookie_session_creation(self):
        """Test cookie session creation."""
        session = CookieSession(
            domain="example.com",
            cookies_dict={"cf_clearance": "test_token", "session_id": "abc123"},
            cookies_list=[{"name": "cf_clearance", "value": "test_token"}],
            user_agent="Mozilla/5.0...",
            created_at=1234567890.0,
            expires_at=1234567890.0 + 1800,  # 30 minutes later
            last_used=1234567890.0,
        )

        assert session.domain == "example.com"
        assert session.cookies_dict["cf_clearance"] == "test_token"
        assert session.user_agent == "Mozilla/5.0..."
        assert session.created_at == 1234567890.0

    def test_cookie_session_is_expired(self):
        """Test cookie session expiration check."""
        current_time = time.time()

        # Fresh session (not expired)
        fresh_session = CookieSession(
            domain="example.com",
            cookies_dict={"test": "value"},
            cookies_list=[{"name": "test", "value": "value"}],
            user_agent="Mozilla/5.0...",
            created_at=current_time - 300,  # 5 minutes ago
            expires_at=current_time + 1500,  # 25 minutes from now
            last_used=current_time - 300,
        )
        assert not fresh_session.is_expired()  # Should not be expired

        # Expired session
        old_session = CookieSession(
            domain="example.com",
            cookies_dict={"test": "value"},
            cookies_list=[{"name": "test", "value": "value"}],
            user_agent="Mozilla/5.0...",
            created_at=current_time - 2000,  # 33+ minutes ago
            expires_at=current_time - 200,  # Expired 200 seconds ago
            last_used=current_time - 2000,
        )
        assert old_session.is_expired()  # Should be expired

    def test_cookie_session_is_stale(self):
        """Test cookie session staleness check."""
        current_time = time.time()

        # Fresh session (not stale)
        fresh_session = CookieSession(
            domain="example.com",
            cookies_dict={"test": "value"},
            cookies_list=[{"name": "test", "value": "value"}],
            user_agent="Mozilla/5.0...",
            created_at=current_time - 300,
            expires_at=current_time + 1500,
            last_used=current_time - 100,  # Used recently
        )
        assert not fresh_session.is_stale()  # Should not be stale

        # Stale session
        stale_session = CookieSession(
            domain="example.com",
            cookies_dict={"test": "value"},
            cookies_list=[{"name": "test", "value": "value"}],
            user_agent="Mozilla/5.0...",
            created_at=current_time - 2000,
            expires_at=current_time + 1500,
            last_used=current_time - 2000,  # Used long ago
        )
        assert stale_session.is_stale()  # Should be stale

    def test_cookie_session_touch(self):
        """Test updating last_used timestamp."""
        current_time = time.time()
        session = CookieSession(
            domain="example.com",
            cookies_dict={"test": "value"},
            cookies_list=[{"name": "test", "value": "value"}],
            user_agent="Mozilla/5.0...",
            created_at=current_time,
            expires_at=current_time + 1800,
            last_used=current_time - 1000,
        )

        original_last_used = session.last_used
        session.touch()

        assert session.last_used > original_last_used

    def test_cookie_session_serialization(self):
        """Test session serialization and deserialization."""
        session = CookieSession(
            domain="example.com",
            cookies_dict={"test": "value"},
            cookies_list=[{"name": "test", "value": "value"}],
            user_agent="Mozilla/5.0...",
            created_at=1234567890.0,
            expires_at=1234567890.0 + 1800,
            last_used=1234567890.0,
        )

        # Test to_dict
        session_dict = session.to_dict()
        assert session_dict["domain"] == "example.com"
        assert session_dict["cookies_dict"] == {"test": "value"}

        # Test from_dict
        restored_session = CookieSession.from_dict(session_dict)
        assert restored_session.domain == session.domain
        assert restored_session.cookies_dict == session.cookies_dict
        assert restored_session.cookies_list == session.cookies_list


class TestCookieManager:
    """Test cases for CookieManager."""

    @pytest.fixture
    def manager(self):
        """Create a cookie manager for testing."""
        mock_flaresolverr = MagicMock()
        return CookieManager(
            flaresolverr_client=mock_flaresolverr,
            max_stale_seconds=1800,  # 30 minutes
        )

    @pytest.fixture
    def sample_session(self):
        """Create a sample cookie session."""
        current_time = time.time()
        return CookieSession(
            domain="example.com",
            cookies_dict={"cf_clearance": "test_token", "session_id": "abc123"},
            cookies_list=[{"name": "cf_clearance", "value": "test_token"}],
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36...",
            created_at=current_time,
            expires_at=current_time + 1800,
            last_used=current_time,
        )

    def test_extract_domain_from_url(self, manager):
        """Test domain extraction from URLs."""
        assert manager._extract_domain("https://example.com/path") == "example.com"
        assert manager._extract_domain("http://sub.example.com") == "sub.example.com"
        assert manager._extract_domain("https://example.com:8080/path") == "example.com"

    def test_extract_domain_invalid_url(self, manager):
        """Test domain extraction from invalid URLs."""
        with pytest.raises(ValueError, match="Invalid URL"):
            manager._extract_domain("not-a-url")

    @pytest.mark.asyncio
    async def test_get_session_new_domain(self, manager):
        """Test getting session for a new domain."""
        # Mock FlareSolverr response
        mock_cookie_data = {
            "cookies_dict": {"cf_clearance": "test_token"},
            "cookies_list": [{"name": "cf_clearance", "value": "test_token"}],
            "user_agent": "Mozilla/5.0...",
        }
        manager.flaresolverr.get_cookies_for_domain = AsyncMock(return_value=mock_cookie_data)

        session = await manager.get_session("https://example.com")

        assert session.domain == "example.com"
        assert session.cookies_dict == {"cf_clearance": "test_token"}
        assert session.user_agent == "Mozilla/5.0..."

    @pytest.mark.asyncio
    async def test_get_session_existing_valid(self, manager, sample_session):
        """Test getting an existing valid session."""
        # Manually add session to internal storage
        manager._sessions["example.com"] = sample_session

        session = await manager.get_session("https://example.com")

        assert session.domain == "example.com"
        assert session.cookies_dict == sample_session.cookies_dict

    @pytest.mark.asyncio
    async def test_get_session_force_refresh(self, manager, sample_session):
        """Test force refresh of existing session."""
        # Manually add session to internal storage
        manager._sessions["example.com"] = sample_session

        # Mock FlareSolverr response for refresh
        mock_cookie_data = {
            "cookies_dict": {"cf_clearance": "new_token"},
            "cookies_list": [{"name": "cf_clearance", "value": "new_token"}],
            "user_agent": "New User Agent",
        }
        manager.flaresolverr.get_cookies_for_domain = AsyncMock(return_value=mock_cookie_data)

        session = await manager.get_session("https://example.com", force_refresh=True)

        assert session.cookies_dict == {"cf_clearance": "new_token"}
        assert session.user_agent == "New User Agent"

    @pytest.mark.asyncio
    async def test_get_cookies_dict(self, manager, sample_session):
        """Test getting cookies dictionary."""
        manager._sessions["example.com"] = sample_session

        cookies = await manager.get_cookies_dict("https://example.com")

        assert cookies == {"cf_clearance": "test_token", "session_id": "abc123"}

    @pytest.mark.asyncio
    async def test_get_headers(self, manager, sample_session):
        """Test getting headers with user agent and standard headers."""
        manager._sessions["example.com"] = sample_session

        headers = await manager.get_headers("https://example.com")

        assert "User-Agent" in headers
        assert "Accept" in headers
        assert "Accept-Language" in headers
        assert "Connection" in headers
        assert headers["User-Agent"] == sample_session.user_agent

    @pytest.mark.asyncio
    async def test_invalidate_domain(self, manager, sample_session):
        """Test invalidating a domain's session."""
        manager._sessions["example.com"] = sample_session

        await manager.invalidate_domain("https://example.com")

        assert "example.com" not in manager._sessions

    @pytest.mark.asyncio
    async def test_cleanup_stale_sessions(self, manager):
        """Test cleanup of stale sessions."""
        current_time = time.time()

        # Add fresh session
        fresh_session = CookieSession(
            domain="fresh.com",
            cookies_dict={"test": "value"},
            cookies_list=[{"name": "test", "value": "value"}],
            user_agent="Mozilla/5.0...",
            created_at=current_time,
            expires_at=current_time + 1800,
            last_used=current_time - 100,  # Used recently
        )
        manager._sessions["fresh.com"] = fresh_session

        # Add stale session
        stale_session = CookieSession(
            domain="stale.com",
            cookies_dict={"test": "value"},
            cookies_list=[{"name": "test", "value": "value"}],
            user_agent="Mozilla/5.0...",
            created_at=current_time - 2000,
            expires_at=current_time + 1800,
            last_used=current_time - 2000,  # Used long ago
        )
        manager._sessions["stale.com"] = stale_session

        # Cleanup should remove only stale session
        removed_count = await manager.cleanup_stale_sessions()

        assert removed_count == 1
        assert "fresh.com" in manager._sessions
        assert "stale.com" not in manager._sessions

    @pytest.mark.asyncio
    async def test_get_session_info(self, manager, sample_session):
        """Test getting session information."""
        manager._sessions["example.com"] = sample_session

        info = await manager.get_session_info()

        assert "example.com" in info

        session_info = info["example.com"]
        assert session_info["cookies_count"] == 2
        assert "Mozilla/5.0" in session_info["user_agent"]
        assert "is_expired" in session_info
        assert "is_stale" in session_info
        assert "age_seconds" in session_info

    @pytest.mark.asyncio
    async def test_get_session_info_empty(self, manager):
        """Test getting session information when no sessions exist."""
        info = await manager.get_session_info()

        assert info == {}

    @pytest.mark.asyncio
    async def test_extract_cookies_error_handling(self, manager):
        """Test error handling in cookie extraction."""
        manager.flaresolverr.get_cookies_for_domain = AsyncMock(
            side_effect=Exception("FlareSolverr error")
        )

        with pytest.raises(Exception, match="Cookie extraction failed"):
            await manager._extract_cookies("https://example.com", "example.com")
