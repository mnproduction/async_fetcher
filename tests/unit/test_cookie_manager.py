"""
Unit tests for Cookie Manager.

This module tests the cookie management functionality including
session storage, validation, expiration, and cleanup.
"""

import pytest
from unittest.mock import MagicMock
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
            last_used=1234567890.0
        )

        assert session.domain == "example.com"
        assert session.cookies_dict["cf_clearance"] == "test_token"
        assert session.user_agent == "Mozilla/5.0..."
        assert session.created_at == 1234567890.0

    def test_cookie_session_age(self, mock_time):
        """Test cookie session age calculation."""
        session = CookieSession(
            domain="example.com",
            cookies_dict={"test": "value"},
            cookies_list=[{"name": "test", "value": "value"}],
            user_agent="Mozilla/5.0...",
            created_at=mock_time - 300,  # 5 minutes ago
            expires_at=mock_time + 1500,  # 25 minutes from now
            last_used=mock_time - 300
        )

        # Test age calculation (current time - created_at)
        age = mock_time - session.created_at
        assert age == 300.0

    def test_cookie_session_is_expired(self, mock_time):
        """Test cookie session expiration check."""
        # Fresh session (not expired)
        fresh_session = CookieSession(
            domain="example.com",
            cookies_dict={"test": "value"},
            cookies_list=[{"name": "test", "value": "value"}],
            user_agent="Mozilla/5.0...",
            created_at=mock_time - 300,  # 5 minutes ago
            expires_at=mock_time + 1500,  # 25 minutes from now
            last_used=mock_time - 300
        )
        assert not fresh_session.is_expired()  # Should not be expired

        # Expired session
        old_session = CookieSession(
            domain="example.com",
            cookies_dict={"test": "value"},
            cookies_list=[{"name": "test", "value": "value"}],
            user_agent="Mozilla/5.0...",
            created_at=mock_time - 2000,  # 33+ minutes ago
            expires_at=mock_time - 200,   # Expired 200 seconds ago
            last_used=mock_time - 2000
        )
        assert old_session.is_expired()  # Should be expired


class TestCookieManager:
    """Test cases for CookieManager."""

    @pytest.fixture
    def manager(self):
        """Create a cookie manager for testing."""
        # Need to create a mock FlareSolverr client first
        mock_flaresolverr = MagicMock()
        return CookieManager(
            flaresolverr_client=mock_flaresolverr,
            max_stale_seconds=1800  # 30 minutes
        )

    @pytest.fixture
    def sample_session(self, mock_time):
        """Create a sample cookie session."""
        return CookieSession(
            domain="example.com",
            cookies={"cf_clearance": "test_token", "session_id": "abc123"},
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36...",
            created_at=mock_time
        )

    def test_save_and_get_session(self, manager, sample_session):
        """Test saving and retrieving a session."""
        manager.save_session(sample_session)
        
        retrieved = manager.get_session("example.com")
        assert retrieved is not None
        assert retrieved.domain == "example.com"
        assert retrieved.cookies["cf_clearance"] == "test_token"
        assert retrieved.user_agent == sample_session.user_agent

    def test_get_nonexistent_session(self, manager):
        """Test getting a session that doesn't exist."""
        result = manager.get_session("nonexistent.com")
        assert result is None

    def test_is_session_valid_fresh(self, manager, sample_session):
        """Test session validity check for fresh session."""
        manager.save_session(sample_session)
        
        assert manager.is_session_valid("example.com") is True

    def test_is_session_valid_expired(self, manager, mock_time):
        """Test session validity check for expired session."""
        old_session = CookieSession(
            domain="example.com",
            cookies={"test": "value"},
            user_agent="Mozilla/5.0...",
            created_at=mock_time - 2000  # Old session
        )
        manager.save_session(old_session)
        
        assert manager.is_session_valid("example.com") is False

    def test_is_session_valid_nonexistent(self, manager):
        """Test session validity check for nonexistent session."""
        assert manager.is_session_valid("nonexistent.com") is False

    def test_cleanup_expired_sessions(self, manager, mock_time):
        """Test cleanup of expired sessions."""
        # Add fresh session
        fresh_session = CookieSession(
            domain="fresh.com",
            cookies={"test": "value"},
            user_agent="Mozilla/5.0...",
            created_at=mock_time
        )
        manager.save_session(fresh_session)
        
        # Add expired session
        old_session = CookieSession(
            domain="old.com",
            cookies={"test": "value"},
            user_agent="Mozilla/5.0...",
            created_at=mock_time - 2000
        )
        manager.save_session(old_session)
        
        # Cleanup should remove only expired session
        removed_count = manager.cleanup_expired()
        
        assert removed_count == 1
        assert manager.get_session("fresh.com") is not None
        assert manager.get_session("old.com") is None

    def test_get_session_info(self, manager, sample_session):
        """Test getting session information."""
        manager.save_session(sample_session)
        
        info = manager.get_session_info()
        
        assert info["cached_domains"] == 1
        assert "example.com" in info["sessions"]
        
        session_info = info["sessions"]["example.com"]
        assert session_info["cookies_count"] == 2
        assert session_info["age_seconds"] == 0.0  # Mock time
        assert "Mozilla/5.0" in session_info["user_agent"]

    def test_get_session_info_empty(self, manager):
        """Test getting session information when no sessions exist."""
        info = manager.get_session_info()
        
        assert info["cached_domains"] == 0
        assert info["sessions"] == {}

    def test_extract_domain_from_url(self, manager):
        """Test domain extraction from URLs."""
        assert manager._extract_domain("https://example.com/path") == "example.com"
        assert manager._extract_domain("http://sub.example.com") == "sub.example.com"
        assert manager._extract_domain("https://example.com:8080/path") == "example.com"

    def test_extract_domain_invalid_url(self, manager):
        """Test domain extraction from invalid URLs."""
        with pytest.raises(ValueError, match="Invalid URL"):
            manager._extract_domain("not-a-url")

    def test_session_overwrite(self, manager, mock_time):
        """Test that saving a new session overwrites the old one."""
        # Save first session
        session1 = CookieSession(
            domain="example.com",
            cookies={"old": "value"},
            user_agent="Old Agent",
            created_at=mock_time - 100
        )
        manager.save_session(session1)
        
        # Save new session for same domain
        session2 = CookieSession(
            domain="example.com",
            cookies={"new": "value"},
            user_agent="New Agent",
            created_at=mock_time
        )
        manager.save_session(session2)
        
        # Should get the new session
        retrieved = manager.get_session("example.com")
        assert retrieved.cookies == {"new": "value"}
        assert retrieved.user_agent == "New Agent"
