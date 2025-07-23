"""
Unit tests for the StealthBrowserToolkit and custom error classes.

This module tests the browser toolkit functionality, error categorization,
and custom exception handling for the async web fetching service.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from toolkit.browser import (
    StealthBrowserToolkit, 
    FetchError, 
    TimeoutError, 
    NavigationError, 
    CaptchaError, 
    ProxyError,
    BrowserError
)


class TestCustomErrorClasses:
    """Test custom error classes for fetch operations."""

    def test_fetch_error_inheritance(self):
        """Test that all custom errors inherit from FetchError."""
        assert issubclass(TimeoutError, FetchError)
        assert issubclass(NavigationError, FetchError)
        assert issubclass(CaptchaError, FetchError)
        assert issubclass(ProxyError, FetchError)
        assert issubclass(BrowserError, FetchError)

    def test_error_instantiation(self):
        """Test that error classes can be instantiated with messages."""
        timeout_error = TimeoutError("Navigation timed out")
        navigation_error = NavigationError("HTTP 404")
        captcha_error = CaptchaError("Captcha detected")
        proxy_error = ProxyError("Proxy connection failed")
        browser_error = BrowserError("Browser crashed")

        assert str(timeout_error) == "Navigation timed out"
        assert str(navigation_error) == "HTTP 404"
        assert str(captcha_error) == "Captcha detected"
        assert str(proxy_error) == "Proxy connection failed"
        assert str(browser_error) == "Browser crashed"

    def test_error_class_names(self):
        """Test that error classes have correct names."""
        assert TimeoutError.__name__ == "TimeoutError"
        assert NavigationError.__name__ == "NavigationError"
        assert CaptchaError.__name__ == "CaptchaError"
        assert ProxyError.__name__ == "ProxyError"
        assert BrowserError.__name__ == "BrowserError"


class TestStealthBrowserToolkitErrorCategorization:
    """Test error categorization in StealthBrowserToolkit.get_page_content method."""

    @pytest.fixture
    def browser_toolkit(self):
        """Create a browser toolkit instance for testing."""
        return StealthBrowserToolkit(headless=True)

    @pytest.fixture
    def mock_context(self):
        """Create mock browser context and page."""
        context = MagicMock()
        page = MagicMock()
        context.new_page.return_value = page
        return context, page

    @pytest.mark.asyncio
    async def test_successful_fetch(self, browser_toolkit, mock_context):
        """Test successful fetch returns HTML content."""
        context, page = mock_context

        # Mock successful response
        response = MagicMock()
        response.status = 200
        page.goto.return_value = response
        page.content.return_value = "<html><body>Success</body></html>"
        
        with patch.object(browser_toolkit, 'create_context', return_value=context):
            result = await browser_toolkit.get_page_content("https://example.com")
        
        assert result == "<html><body>Success</body></html>"

    @pytest.mark.asyncio
    async def test_timeout_error_categorization(self, browser_toolkit, mock_context):
        """Test that timeout errors are correctly categorized."""
        context, page = mock_context
        
        # Mock timeout error
        page.goto.side_effect = Exception("Navigation timeout of 30000 ms exceeded")
        
        with patch.object(browser_toolkit, 'create_context', return_value=context):
            with pytest.raises(TimeoutError) as exc_info:
                await browser_toolkit.get_page_content("https://example.com")
            
            assert "timeout" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_proxy_error_categorization(self, browser_toolkit, mock_context):
        """Test that proxy errors are correctly categorized."""
        context, page = mock_context
        
        # Mock proxy error
        page.goto.side_effect = Exception("Proxy connection failed")
        
        with patch.object(browser_toolkit, 'create_context', return_value=context):
            with pytest.raises(ProxyError) as exc_info:
                await browser_toolkit.get_page_content("https://example.com")
            
            assert "proxy" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_navigation_error_categorization(self, browser_toolkit, mock_context):
        """Test that navigation errors are correctly categorized."""
        context, page = mock_context
        
        # Mock navigation error
        page.goto.side_effect = Exception("Failed to navigate to URL")
        
        with patch.object(browser_toolkit, 'create_context', return_value=context):
            with pytest.raises(NavigationError) as exc_info:
                await browser_toolkit.get_page_content("https://example.com")
            
            assert "navigation" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_http_error_categorization(self, browser_toolkit, mock_context):
        """Test that HTTP errors are correctly categorized as navigation errors."""
        context, page = mock_context
        
        # Mock HTTP error response
        response = MagicMock()
        response.status = 404
        page.goto.return_value = response
        
        with patch.object(browser_toolkit, 'create_context', return_value=context):
            with pytest.raises(NavigationError) as exc_info:
                await browser_toolkit.get_page_content("https://example.com")
            
            assert "HTTP error: 404" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_captcha_detection(self, browser_toolkit, mock_context):
        """Test that captcha detection works correctly."""
        context, page = mock_context
        
        # Mock successful response but with captcha content
        response = MagicMock()
        response.status = 200
        page.goto.return_value = response
        page.content.return_value = "<html><body>Please complete this captcha</body></html>"
        
        with patch.object(browser_toolkit, 'create_context', return_value=context):
            with pytest.raises(CaptchaError) as exc_info:
                await browser_toolkit.get_page_content("https://example.com")
            
            assert "captcha" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_captcha_detection_variations(self, browser_toolkit, mock_context):
        """Test captcha detection with different captcha patterns."""
        context, page = mock_context
        
        captcha_patterns = [
            "Please verify you are human",
            "Robot verification required",
            "Human verification needed"
        ]
        
        for pattern in captcha_patterns:
            response = MagicMock()
            response.status = 200
            page.goto.return_value = response
            page.content.return_value = f"<html><body>{pattern}</body></html>"
            
            with patch.object(browser_toolkit, 'create_context', return_value=context):
                with pytest.raises(CaptchaError):
                    await browser_toolkit.get_page_content("https://example.com")

    @pytest.mark.asyncio
    async def test_no_response_error(self, browser_toolkit, mock_context):
        """Test handling when no response is received."""
        context, page = mock_context
        
        # Mock no response
        page.goto.return_value = None
        
        with patch.object(browser_toolkit, 'create_context', return_value=context):
            with pytest.raises(NavigationError) as exc_info:
                await browser_toolkit.get_page_content("https://example.com")
            
            assert "No response received" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_unexpected_error_categorization(self, browser_toolkit, mock_context):
        """Test that unexpected errors are categorized as navigation errors."""
        context, page = mock_context
        
        # Mock unexpected error
        page.goto.side_effect = Exception("Unexpected browser error")
        
        with patch.object(browser_toolkit, 'create_context', return_value=context):
            with pytest.raises(NavigationError) as exc_info:
                await browser_toolkit.get_page_content("https://example.com")
            
            assert "Navigation failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_resource_cleanup_on_error(self, browser_toolkit, mock_context):
        """Test that resources are properly cleaned up even when errors occur."""
        context, page = mock_context
        
        # Mock error during navigation
        page.goto.side_effect = Exception("Navigation failed")
        
        with patch.object(browser_toolkit, 'create_context', return_value=context):
            with pytest.raises(NavigationError):
                await browser_toolkit.get_page_content("https://example.com")
            
            # Verify cleanup was called
            page.close.assert_called_once()
            context.close.assert_called_once()


class TestFetchResultModelWithErrorType:
    """Test FetchResult model with error_type field."""

    def test_successful_result_without_error_type(self):
        """Test that successful results don't require error_type."""
        from api.models import FetchResult
        
        result = FetchResult(
            url="https://example.com",
            status="success",
            html_content="<html><body>Success</body></html>",
            response_time_ms=1000
        )
        
        assert result.status == "success"
        assert result.error_type is None

    def test_error_result_requires_error_type(self):
        """Test that error results require error_type field."""
        from api.models import FetchResult
        
        with pytest.raises(ValueError):
            FetchResult(
                url="https://example.com",
                status="error",
                error_message="Connection failed"
                # Missing error_type
            )

    def test_error_result_with_error_type(self):
        """Test that error results work correctly with error_type."""
        from api.models import FetchResult
        
        result = FetchResult(
            url="https://example.com",
            status="error",
            error_message="Connection timeout",
            error_type="TimeoutError",
            response_time_ms=30000
        )
        
        assert result.status == "error"
        assert result.error_type == "TimeoutError"
        assert result.error_message == "Connection timeout"

    def test_success_result_cannot_have_error_type(self):
        """Test that success results cannot have error_type."""
        from api.models import FetchResult
        
        with pytest.raises(ValueError):
            FetchResult(
                url="https://example.com",
                status="success",
                html_content="<html><body>Success</body></html>",
                error_type="SomeError"  # Should not be allowed for success
            )

    def test_error_type_sanitization(self):
        """Test that error_type is properly sanitized."""
        from api.models import FetchResult
        
        result = FetchResult(
            url="https://example.com",
            status="error",
            error_message="Test error",
            error_type="  TimeoutError  ",  # With whitespace
            response_time_ms=1000
        )
        
        assert result.error_type == "TimeoutError"  # Should be trimmed 