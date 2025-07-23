import asyncio
import random
from typing import Dict, List, Optional, Union, Any

from settings.logger import get_logger

# Import the correct async API from patchright
from patchright.async_api import async_playwright


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
    
    async def initialize(self) -> None:
        """
        Initialize the browser instance using patchright's async API.
        
        This method sets up the playwright instance and launches the browser
        with stealth configuration to avoid detection.
        """
        if self._initialized:
            return
            
        self.logger.info("Initializing stealth browser", headless=self.headless)
        
        try:
            # Initialize playwright using patchright's async API
            self._playwright = await async_playwright().start()
            
            # Launch browser with stealth settings
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                # Use chrome channel for better undetection
                channel="chrome" if not self.headless else None,
                # Additional stealth arguments
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-web-security",
                    "--disable-features=VizDisplayCompositor"
                ]
            )
            
            self._initialized = True
            self.logger.info("Stealth browser initialized successfully")
            
        except Exception as e:
            self.logger.error("Failed to initialize browser", error=str(e))
            await self.close()
            raise
    
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
        
        try:
            context = await self._browser.new_context(**context_options)
            self.logger.debug("Browser context created successfully", proxy=proxy is not None)
            return context
            
        except Exception as e:
            self.logger.error("Failed to create browser context", error=str(e), proxy=proxy)
            raise
    
    async def fetch_url(self, url: str, proxy: Optional[str] = None, wait_time: int = 2) -> Dict[str, Union[str, bool, None]]:
        """
        Fetch a URL using a stealth browser context and return the HTML content.
        
        Args:
            url: The URL to fetch
            proxy: Optional proxy URL
            wait_time: Time to wait after page load (default: 2 seconds)
            
        Returns:
            Dictionary containing fetch result with keys: url, success, html, error
        """
        result = {
            "url": url,
            "success": False,
            "html": None,
            "error": None
        }
        
        context = None
        page = None
        
        try:
            self.logger.info("Fetching URL", url=url, proxy=proxy is not None)
            
            # Create stealth context
            context = await self.create_context(proxy)
            page = await context.new_page()
            
            # Navigate to the URL with stealth settings
            response = await page.goto(
                url, 
                wait_until="networkidle",
                timeout=30000  # 30 second timeout
            )
            
            if not response or response.status >= 400:
                result["error"] = f"Failed to load page: HTTP {response.status if response else 'unknown'}"
                self.logger.warning("HTTP error during fetch", url=url, status=response.status if response else 'unknown')
                return result
            
            # Wait for additional time to ensure page is fully loaded
            await asyncio.sleep(wait_time)
            
            # Get the HTML content
            html = await page.content()
            result["html"] = html
            result["success"] = True
            
            self.logger.info("Successfully fetched URL", url=url, content_length=len(html))
            return result
            
        except Exception as e:
            error_message = str(e)
            self.logger.error("Error fetching URL", url=url, error=error_message)
            result["error"] = error_message
            return result
            
        finally:
            # Clean up resources
            if page:
                try:
                    await page.close()
                except Exception as e:
                    self.logger.warning("Error closing page", error=str(e))
            
            if context:
                try:
                    await context.close()
                except Exception as e:
                    self.logger.warning("Error closing context", error=str(e))
    
    async def close(self) -> None:
        """
        Close the browser instance and free resources.
        """
        if self._browser:
            self.logger.info("Closing browser")
            try:
                await self._browser.close()
            except Exception as e:
                self.logger.warning("Error closing browser", error=str(e))
            finally:
                self._browser = None
        
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception as e:
                self.logger.warning("Error stopping playwright", error=str(e))
            finally:
                self._playwright = None
        
        self._initialized = False
    
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