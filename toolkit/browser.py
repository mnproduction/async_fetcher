import asyncio
import platform
from typing import Optional, Any

from settings.logger import get_logger

# Import the correct async API from patchright
from patchright.async_api import async_playwright


# =============================================================================
# CUSTOM ERROR CLASSES FOR FETCH OPERATIONS
# =============================================================================

class FetchError(Exception):
    """
    Base class for fetch-related errors.
    
    This is the parent class for all errors that can occur during
    web fetching operations. It provides a common interface for
    error handling and categorization.
    """
    pass


class TimeoutError(FetchError):
    """
    Error raised when a fetch operation times out.
    
    This error occurs when navigation or page loading takes longer
    than the configured timeout period.
    """
    pass


class NavigationError(FetchError):
    """
    Error raised when navigation to a URL fails.
    
    This error occurs when the browser cannot successfully navigate
    to the target URL, including HTTP errors (4xx, 5xx) and
    network connectivity issues.
    """
    pass


class CaptchaError(FetchError):
    """
    Error raised when a captcha is detected on the page.
    
    This error occurs when the fetched page contains captcha
    verification mechanisms that prevent automated access.
    """
    pass


class ProxyError(FetchError):
    """
    Error raised when there's an issue with the proxy configuration.
    
    This error occurs when the proxy server is unreachable,
    authentication fails, or other proxy-related issues arise.
    """
    pass


class BrowserError(FetchError):
    """
    Error raised when there's an issue with the browser itself.
    
    This error occurs when the browser instance cannot be created,
    crashes, or encounters other browser-level problems.
    """
    pass


class StealthBrowserToolkit:
    """
    A toolkit for managing stealth browser instances for web scraping using Patchright.
    
    This class provides an async interface for browser automation with stealth features
    to avoid detection. It supports proxy configuration and proper resource management.
    """
    
    def __init__(self, headless: bool = True):
        """
        Initialize the StealthBrowserToolkit.
        
        Args:
            headless: Whether to run the browser in headless mode (default: True)
        """
        self.headless = headless
        self.logger = get_logger("toolkit.browser")
        self._playwright = None
        self._browser = None
        self._initialized = False
    
    async def initialize(self) -> bool:
        """
        Initialize the browser instance using patchright's async API.

        This method sets up the playwright instance and launches the browser
        with stealth configuration to avoid detection.

        Returns:
            bool: True if initialization was successful, False otherwise
        """
        if self._initialized:
            self.logger.debug("Browser already initialized, skipping")
            return True

        self.logger.info("Initializing stealth browser", headless=self.headless)

        try:
            # Fix Windows asyncio event loop policy issue
            if platform.system() == "Windows":
                # Set the event loop policy to WindowsProactorEventLoopPolicy
                # This fixes subprocess creation issues on Windows
                if isinstance(asyncio.get_event_loop_policy(), asyncio.WindowsProactorEventLoopPolicy):
                    pass  # Already using the correct policy
                else:
                    self.logger.debug("Setting Windows event loop policy for subprocess support")
                    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

            # Initialize patchright using its async API
            self.logger.debug("Starting patchright instance")
            self._playwright = await async_playwright().start()

            # Launch browser with stealth settings
            stealth_args = [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding"
            ]

            # Add Windows-specific arguments
            if platform.system() == "Windows":
                stealth_args.extend([
                    "--disable-gpu",
                    "--disable-gpu-sandbox"
                ])

            self.logger.debug(
                "Launching browser with stealth settings",
                headless=self.headless,
                platform=platform.system(),
                args_count=len(stealth_args)
            )

            # Try to launch browser with fallback options
            try:
                self._browser = await self._playwright.chromium.launch(
                    headless=self.headless,
                    # Use chrome channel for better undetection (if available)
                    channel="chrome" if not self.headless else None,
                    # Additional stealth arguments
                    args=stealth_args
                )
            except Exception as channel_error:
                self.logger.warning(
                    "Failed to launch with chrome channel, trying without channel",
                    error=str(channel_error)
                )
                # Fallback: launch without specific channel
                self._browser = await self._playwright.chromium.launch(
                    headless=self.headless,
                    args=stealth_args
                )

            self._initialized = True
            self.logger.info(
                "Stealth browser initialized successfully",
                headless=self.headless,
                browser_type="chromium",
                platform=platform.system()
            )
            return True
            
        except Exception as e:
            self.logger.error(
                "Failed to initialize browser",
                error=str(e),
                exception_class=e.__class__.__name__
            )
            await self.close()
            return False
    
    async def create_context(self, proxy: Optional[str] = None) -> Any:
        """
        Create a new browser context with stealth settings and optional proxy.
        
        Args:
            proxy: Optional proxy URL (e.g., "http://proxy:port")
            
        Returns:
            Browser context with stealth configuration
        """
        await self.initialize()
        
        context_options = {
            # Stealth user agent
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            # Realistic viewport
            "viewport": {"width": 1920, "height": 1080},
            # Disable touch and mobile features
            "has_touch": False,
            "is_mobile": False,
            # Set locale and timezone
            "locale": "en-US",
            "timezone_id": "America/New_York",
            # Additional stealth settings
            "ignore_https_errors": True,
            "java_script_enabled": True,
            "bypass_csp": True,
        }
        
        # Add proxy configuration if provided
        if proxy:
            self.logger.info("Creating context with proxy", proxy=proxy)
            context_options["proxy"] = {"server": proxy}
        else:
            self.logger.debug("Creating context without proxy")
        
        try:
            self.logger.debug("Creating browser context with stealth settings", headless=self.headless)
            context = await self._browser.new_context(**context_options)
            self.logger.debug(
                "Browser context created successfully", 
                proxy=proxy is not None,
                viewport=context_options["viewport"],
                user_agent=context_options["user_agent"][:50] + "..."  # Truncate for logging
            )
            return context
            
        except Exception as e:
            self.logger.error(
                "Failed to create browser context", 
                error=str(e), 
                proxy=proxy,
                exception_class=e.__class__.__name__
            )
            raise
    
    async def get_page_content(self, url: str, proxy: Optional[str] = None, wait_time: int = 2) -> Optional[str]:
        """
        Fetch a URL using a stealth browser context and return the HTML content.
        
        Args:
            url: The URL to fetch
            proxy: Optional proxy URL
            wait_time: Time to wait after page load (default: 2 seconds)
            
        Returns:
            HTML content as string, or None if fetch failed
            
        Raises:
            FetchError: Base class for all fetch-related errors
            TimeoutError: When navigation times out
            NavigationError: When navigation fails
            CaptchaError: When captcha is detected
            ProxyError: When proxy connection fails
        """
        context = None
        page = None
        
        try:
            self.logger.info(
                "Starting URL fetch", 
                url=url, 
                proxy=proxy is not None,
                wait_time=wait_time,
                headless=self.headless
            )
            
            # Create stealth context
            self.logger.debug("Creating browser context", proxy=proxy is not None)
            context = await self.create_context(proxy)
            page = await context.new_page()
            
            # Set timeout for navigation
            page.set_default_navigation_timeout(30000)  # 30 seconds
            self.logger.debug("Navigation timeout set", timeout_ms=30000)
            
            # Navigate to the URL with stealth settings
            self.logger.debug("Starting navigation", url=url, wait_until="networkidle")
            try:
                response = await page.goto(
                    url, 
                    wait_until="networkidle",
                    timeout=30000  # 30 second timeout
                )
            except Exception as e:
                error_str = str(e).lower()
                self.logger.warning("Navigation failed", url=url, error=str(e))
                if "timeout" in error_str:
                    raise TimeoutError(f"Navigation timed out: {str(e)}")
                elif "proxy" in error_str or "connection" in error_str:
                    raise ProxyError(f"Proxy error: {str(e)}")
                else:
                    raise NavigationError(f"Navigation failed: {str(e)}")
            
            if not response:
                self.logger.error("No response received", url=url)
                raise NavigationError("No response received from the server")
            
            self.logger.info(
                "Navigation complete", 
                url=url, 
                status_code=response.status,
                content_type=response.headers.get("content-type", "unknown")
            )
            
            if response.status >= 400:
                self.logger.warning("HTTP error response", url=url, status_code=response.status)
                raise NavigationError(f"HTTP error: {response.status}")
            
            # Wait for additional time to ensure page is fully loaded
            self.logger.debug("Waiting for page to fully load", wait_time=wait_time)
            await asyncio.sleep(wait_time)
            
            # Get the HTML content
            self.logger.debug("Retrieving page content", url=url)
            content = await page.content()
            
            # Check for common captcha patterns
            captcha_patterns = ["captcha", "robot", "human verification", "verify you are human"]
            if any(pattern in content.lower() for pattern in captcha_patterns):
                self.logger.warning("Captcha detected", url=url, content_length=len(content))
                raise CaptchaError("Captcha detected on the page")
            
            self.logger.info(
                "Successfully fetched URL", 
                url=url, 
                content_length=len(content),
                status_code=response.status
            )
            return content
            
        except Exception as e:
            # Categorize and re-raise specific errors
            error_str = str(e).lower()
            if "timeout" in error_str:
                raise TimeoutError(f"Navigation timed out: {e}") from e
            if "proxy" in error_str:
                raise ProxyError(f"Proxy connection failed: {e}") from e
            if isinstance(e, (NavigationError, CaptchaError)):
                raise e  # Re-raise our own custom errors
            # Fallback for other playwright errors
            raise NavigationError(f"Navigation failed: {e}") from e
            
        finally:
            # Clean up resources
            self.logger.debug("Cleaning up browser resources", url=url)
            
            if page:
                try:
                    await page.close()
                    self.logger.debug("Page closed successfully", url=url)
                except Exception as e:
                    self.logger.warning(
                        "Error closing page", 
                        url=url, 
                        error=str(e),
                        exception_class=e.__class__.__name__
                    )
            
            if context:
                try:
                    await context.close()
                    self.logger.debug("Context closed successfully", url=url)
                except Exception as e:
                    self.logger.warning(
                        "Error closing context", 
                        url=url, 
                        error=str(e),
                        exception_class=e.__class__.__name__
                    )
    
    async def close(self) -> None:
        """
        Close the browser instance and free resources.
        """
        self.logger.debug("Starting browser cleanup")
        
        if self._browser:
            self.logger.info("Closing browser instance")
            try:
                await self._browser.close()
                self.logger.debug("Browser closed successfully")
            except Exception as e:
                self.logger.warning(
                    "Error closing browser", 
                    error=str(e),
                    exception_class=e.__class__.__name__
                )
            finally:
                self._browser = None
        
        if self._playwright:
            self.logger.debug("Stopping playwright instance")
            try:
                await self._playwright.stop()
                self.logger.debug("Playwright stopped successfully")
            except Exception as e:
                self.logger.warning(
                    "Error stopping playwright", 
                    error=str(e),
                    exception_class=e.__class__.__name__
                )
            finally:
                self._playwright = None
        
        self._initialized = False
        self.logger.debug("Browser cleanup completed")
    
    async def __aenter__(self):
        """
        Async context manager entry point.
        """
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Async context manager exit point.
        """
        await self.close() 