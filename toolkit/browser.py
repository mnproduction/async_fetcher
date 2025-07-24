import asyncio
import random
import re
import platform
from typing import Dict, Any, Optional
from urllib.parse import urlparse

from settings.logger import get_logger

# Try to import fake_useragent, fall back to static user agent if not available
try:
    from fake_useragent import UserAgent
except ImportError:
    UserAgent = None

# Import the correct async API from patchright
try:
    from patchright.async_api import async_playwright, Browser, BrowserContext, Page
except ImportError:
    raise ImportError("Patchright is not installed. Please install it with: uv add patchright")


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
    An enhanced toolkit for stealth browser automation using Patchright.
    
    This class provides advanced anti-detection capabilities, sophisticated
    challenge detection, and robust error handling for web scraping.
    """
    
    def __init__(
        self, 
        headless: bool = True,
        user_agent: str = None,
        proxy: Dict[str, Any] = None,
        wait_min: int = 1,
        wait_max: int = 3,
        timeout: int = 60000
    ):
        """
        Initialize the enhanced stealth browser toolkit.
        
        Args:
            headless: Whether to run the browser in headless mode
            user_agent: Custom user agent string, or None to generate randomly
            proxy: Proxy configuration dict with 'server' key, optional 'username' and 'password'
            wait_min: Minimum wait time between actions in seconds
            wait_max: Maximum wait time between actions in seconds
            timeout: Default timeout for navigation in milliseconds
        """
        self.headless = headless
        self.proxy = proxy
        self.wait_min = wait_min
        self.wait_max = wait_max
        self.timeout = timeout
        self.user_agent = self._get_user_agent(user_agent)
        self.logger = get_logger("toolkit.browser")
        
        # Will be initialized during startup
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
    
    def _get_user_agent(self, user_agent: str) -> str:
        """Get user agent string, generating one if none provided."""
        if user_agent:
            return user_agent
            
        if UserAgent:
            try:
                ua = UserAgent()
                return ua.random
            except Exception as e:
                self.logger.warning(f"Error generating random user agent: {str(e)}")
        
        # Fallback to a realistic static user agent
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    
    async def initialize(self) -> bool:
        """
        Initialize browser with enhanced stealth configuration.
        
        Returns:
            bool: True if initialization was successful, False otherwise
        """
        try:
            self.logger.info("Initializing stealth browser", headless=self.headless)
            
            # Initialize playwright
            self.playwright = await async_playwright().start()

            # Enhanced stealth arguments
            stealth_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-setuid-sandbox",
                "--disable-infobars",
                "--disable-popup-blocking",
                "--disable-notifications",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--disable-field-trial-config",
                "--disable-back-forward-cache",
                "--disable-default-apps",
                "--disable-extensions",
                "--disable-component-extensions-with-background-pages",
                "--disable-background-networking",
                "--no-default-browser-check",
                "--no-first-run",
                "--disable-hang-monitor",
                "--disable-prompt-on-repost",
                "--disable-client-side-phishing-detection",
                "--disable-component-update",
                "--disable-domain-reliability"
            ]

            # Platform-specific arguments
            if platform.system() == "Linux":
                stealth_args.extend([
                    "--disable-gpu",
                    "--disable-software-rasterizer"
                ])

            # Configure and launch browser
            launch_options = {
                "headless": self.headless,
                "args": stealth_args
            }

            # Try to use chrome channel for better stealth
            try:
                launch_options["channel"] = "chrome"
                self.browser = await self.playwright.chromium.launch(**launch_options)
            except Exception as channel_error:
                self.logger.warning(f"Failed to launch with chrome channel: {channel_error}")
                # Fallback: launch without specific channel
                del launch_options["channel"]
                self.browser = await self.playwright.chromium.launch(**launch_options)

            self.logger.info(
                "Stealth browser initialized successfully",
                headless=self.headless,
                browser_type="chromium",
                platform=platform.system()
            )
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize browser: {str(e)}")
            await self.close()
            raise BrowserError(f"Failed to launch browser: {e}") from e
    
    def _get_context_options(self) -> Dict[str, Any]:
        """Get enhanced browser context options including proxy if configured."""
        options = {
            "user_agent": self.user_agent,
            "viewport": {"width": 1920, "height": 1080},
            "locale": "en-US",
            "timezone_id": "America/New_York",
            "ignore_https_errors": True,
            "java_script_enabled": True,
            "bypass_csp": True,
            "has_touch": False,
            "is_mobile": False,
            # Additional stealth headers
            "extra_http_headers": {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        }
        
        if self.proxy:
            self.logger.info("Configuring proxy", proxy_server=self.proxy.get("server", "unknown"))
            options["ignore_https_errors"] = True
            
            # Parse proxy URL to separate credentials if embedded
            if "server" in self.proxy:
                parsed = urlparse(self.proxy["server"])
                
                if '@' in parsed.netloc:
                    auth, host = parsed.netloc.split('@')
                    username, password = auth.split(':')
                    server_url = f"{parsed.scheme}://{host}"
                    
                    options["proxy"] = {
                        "server": server_url,
                        "username": username,
                        "password": password,
                        "bypass": "<-loopback>"
                    }
                else:
                    options["proxy"] = self.proxy
            else:
                options["proxy"] = self.proxy
            
        return options
    
    async def _test_proxy_connection(self, page: Page) -> bool:
        """
        Test proxy connection with multiple fallback URLs.
        
        Args:
            page: The page to use for testing
            
        Returns:
            bool: True if the proxy connection works, False otherwise
        """
        test_urls = [
            'https://httpbin.org/ip',
            'https://api.ipify.org?format=json',
            'https://ip.seeip.org/json',
            'http://checkip.amazonaws.com'
        ]
        
        for url in test_urls:
            try:
                self.logger.debug(f"Testing proxy connection with {url}")
                
                response = await page.goto(url, timeout=10000)  # 10 second timeout
                
                if response and response.ok:
                    try:
                        content = await page.content()
                        self.logger.info(f"Proxy test successful with {url}")
                        self.logger.debug(f"Proxy response content: {content[:200]}")
                        return True
                    except Exception as content_error:
                        self.logger.debug(f"Could not read content from {url}: {content_error}")
                        continue
                else:
                    status = response.status if response else 'No response'
                    self.logger.warning(f"Proxy test failed with {url}. Status: {status}")
                    
            except Exception as e:
                error_msg = str(e).lower()
                self.logger.warning(f"Proxy test failed with {url}: {error_msg}")
                
                if "proxy" in error_msg or "connection" in error_msg:
                    self.logger.error("Proxy connection failed")
                elif "timeout" in error_msg:
                    self.logger.error("Proxy connection timed out")
                continue
                
        return False
    
    async def get_page_content(self, url: str) -> Optional[str]:
        """
        High-level method to get content from a URL with enhanced stealth and error handling.
        
        Args:
            url: The URL to fetch content from
            
        Returns:
            str: HTML content of the page or None if fetching failed
            
        Raises:
            FetchError: Base class for all fetch-related errors
            TimeoutError: When navigation times out
            NavigationError: When navigation fails
            CaptchaError: When captcha is detected
            ProxyError: When proxy connection fails
            BrowserError: When browser initialization fails
        """
        if not self.browser:
            await self.initialize()
        
        context = None
        page = None
        
        try:
            self.logger.info(
                "Starting URL fetch", 
                url=url, 
                proxy=self.proxy is not None,
                wait_time=f"{self.wait_min}-{self.wait_max}s",
                headless=self.headless
            )
            
            # Create enhanced stealth context
            context_options = self._get_context_options()
            context = await self.browser.new_context(**context_options)
            page = await context.new_page()
            
            # Set timeouts
            page.set_default_navigation_timeout(self.timeout)
            page.set_default_timeout(self.timeout)
            
            # Test proxy if configured
            if self.proxy and not await self._test_proxy_connection(page):
                raise ProxyError("Proxy connection test failed")
            
            # Enhanced navigation strategy
            self.logger.debug("Starting navigation", url=url)
            
            # Add pre-navigation delay for HTTPS requests
            if url.startswith('https://'):
                await asyncio.sleep(random.uniform(1, 2))
            
            try:
                response = await page.goto(
                    url, 
                    wait_until="domcontentloaded",
                    timeout=self.timeout
                )
            except Exception as e:
                self._categorize_and_raise_error(e, url)
            
            if not response:
                raise NavigationError("No response received from the server")
            
            self.logger.info(
                "Navigation complete", 
                url=url, 
                status_code=response.status,
                content_type=response.headers.get("content-type", "unknown")
            )
            
            # Check for HTTP errors
            if response.status >= 400:
                self.logger.warning("HTTP error response", url=url, status_code=response.status)
                raise NavigationError(f"HTTP error: {response.status}")
            
            # Wait for multiple load states to ensure dynamic content loads
            try:
                await page.wait_for_load_state('load', timeout=self.timeout // 2)
                self.logger.debug("Reached 'load' state")
                await page.wait_for_load_state('networkidle', timeout=self.timeout // 2)
                self.logger.debug("Reached 'networkidle' state")
            except Exception as load_error:
                self.logger.warning(f"Not all load states reached: {load_error}")
            
            # Human-like delay
            wait_time = random.uniform(self.wait_min, self.wait_max)
            self.logger.debug(f"Adding human-like delay: {wait_time:.2f}s")
            await asyncio.sleep(wait_time)
            
            # Get page content
            content = await page.content()
            
            # Enhanced challenge detection
            if await self._is_challenge_page(page, content):
                self.logger.warning(f"Challenge page detected at {url}")
                # Wait longer for challenge to resolve
                await asyncio.sleep(random.uniform(5, 10))
                # Refresh content after waiting
                content = await page.content()
                
                # Check again after waiting
                if await self._is_challenge_page(page, content):
                    raise CaptchaError("Persistent captcha/challenge page detected")
            
            self.logger.info(
                "Successfully fetched URL", 
                url=url, 
                content_length=len(content),
                status_code=response.status
            )
            return content
            
        except Exception as e:
            if isinstance(e, FetchError):
                raise e  # Re-raise our custom errors
            self._categorize_and_raise_error(e, url)
            
        finally:
            # Clean up resources
            self.logger.debug("Cleaning up browser resources", url=url)
            
            if page:
                try:
                    await page.close()
                    self.logger.debug("Page closed successfully")
                except Exception as e:
                    self.logger.warning(f"Error closing page: {str(e)}")
            
            if context:
                try:
                    await context.close()
                    self.logger.debug("Context closed successfully")
                except Exception as e:
                    self.logger.warning(f"Error closing context: {str(e)}")
    
    async def _is_challenge_page(self, page: Page, content: str) -> bool:
        """
        Enhanced challenge detection for Cloudflare and other protection services.
        
        Args:
            page: The page to check
            content: The page content
            
        Returns:
            bool: True if a challenge is detected, False otherwise
        """
        try:
            # 1. Check content for challenge markers
            content_lower = content.lower()
            challenge_markers = [
                "just a moment",
                "checking your browser",
                "cloudflare",
                "challenge-running",
                "ddos protection",
                "security check",
                "please wait",
                "checking if the site connection is secure",
                "attention required",
                "verify you are human",
                "captcha",
                "robot verification",
                "access denied",
                "blocked"
            ]
            
            for marker in challenge_markers:
                if marker in content_lower:
                    self.logger.debug(f"Detected challenge marker: {marker}")
                    return True
            
            # 2. Check for common challenge elements
            challenge_selectors = [
                'div#cf-challenge-wrapper',
                'div#challenge-container', 
                'iframe[src*="challenges.cloudflare.com"]',
                'iframe[src*="turnstile"]',
                'div[class*="cf-"]',
                'form[id*="challenge-form"]',
                '.captcha-container',
                '#captcha',
                '.recaptcha'
            ]
            
            for selector in challenge_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        self.logger.debug(f"Found challenge element: {selector}")
                        return True
                except Exception:
                    continue
            
            # 3. Check for challenge text with JavaScript evaluation
            try:
                has_challenge_text = await page.evaluate("""
                () => {
                    if (!document.body) return false;
                    const bodyText = document.body.innerText || '';
                    const challengePatterns = [
                        /cloudflare/i,
                        /ddos protection/i,
                        /checking your browser/i,
                        /security check/i,
                        /just a moment/i,
                        /please wait/i,
                        /verify you are human/i,
                        /captcha/i,
                        /attention required/i
                    ];
                    return challengePatterns.some(pattern => pattern.test(bodyText));
                }
                """)
                
                if has_challenge_text:
                    self.logger.debug("Detected challenge text via JavaScript evaluation")
                    return True
            except Exception as e:
                self.logger.debug(f"Error checking for challenge text: {str(e)}")
            
            # 4. Check page title
            try:
                title = await page.title()
                if title:
                    title_patterns = [
                        r'cloudflare',
                        r'security check',
                        r'attention required',
                        r'just a moment',
                        r'access denied',
                        r'blocked'
                    ]
                    for pattern in title_patterns:
                        if re.search(pattern, title, re.IGNORECASE):
                            self.logger.debug(f"Detected challenge in page title: {title}")
                            return True
            except Exception as e:
                self.logger.debug(f"Error checking page title: {str(e)}")
            
            return False
            
        except Exception as e:
            self.logger.warning(f"Challenge detection error: {str(e)}")
            return False
    
    def _categorize_and_raise_error(self, error: Exception, url: str):
        """
        Categorize a Playwright/Patchright exception into a custom FetchError.
        
        Args:
            error: The original exception
            url: The URL being fetched
            
        Raises:
            Appropriate FetchError subclass based on the error type
        """
        error_str = str(error).lower()
        
        if "timeout" in error_str:
            raise TimeoutError(f"Navigation timed out for {url}: {error}") from error
        elif "proxy" in error_str or "connection" in error_str:
            raise ProxyError(f"Proxy error for {url}: {error}") from error
        elif isinstance(error, (CaptchaError, NavigationError, ProxyError, TimeoutError)):
            raise error  # Re-raise already categorized errors
        else:
            raise NavigationError(f"Navigation failed for {url}: {error}") from error
    
    async def close(self) -> None:
        """
        Close the browser instance and free resources.
        """
        self.logger.debug("Starting browser cleanup")
        
        if self.browser:
            self.logger.info("Closing browser instance")
            try:
                await self.browser.close()
                self.logger.debug("Browser closed successfully")
            except Exception as e:
                self.logger.warning(f"Error closing browser: {str(e)}")
            finally:
                self.browser = None
        
        if self.playwright:
            self.logger.debug("Stopping playwright instance")
            try:
                await self.playwright.stop()
                self.logger.debug("Playwright stopped successfully")
            except Exception as e:
                self.logger.warning(f"Error stopping playwright: {str(e)}")
            finally:
                self.playwright = None
        
        self.logger.debug("Browser cleanup completed")
    
    async def __aenter__(self):
        """Async context manager entry point."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit point."""
        await self.close() 