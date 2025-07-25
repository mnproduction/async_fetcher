import asyncio
import aiohttp
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from toolkit.flaresolverr import FlareSolverrClient, FlareSolverrError
from toolkit.cookie_manager import CookieManager
from settings.logger import get_logger


@dataclass
class FetchResult:
    """Result of a fetch operation."""
    url: str
    success: bool
    status_code: Optional[int] = None
    content: Optional[str] = None
    content_length: int = 0
    execution_time: float = 0.0
    error: Optional[str] = None
    used_cookies: bool = False
    cookies_refreshed: bool = False


class SimpleFetcher:
    """
    Simplified fetcher service using FlareSolverr cookies + aiohttp.
    
    This service is optimized for periodic content checking scenarios where:
    - You need to fetch content from Cloudflare-protected sites
    - You want fast subsequent requests after initial cookie extraction
    - You need automatic cookie refresh when they expire
    """
    
    def __init__(
        self,
        flaresolverr_url: str = "http://localhost:8191",
        cookie_ttl_seconds: int = 1800,  # 30 minutes
        request_timeout: int = 30,
        max_retries: int = 2,
        retry_delay: float = 1.0
    ):
        """
        Initialize the simplified fetcher.
        
        Args:
            flaresolverr_url: URL of FlareSolverr service
            cookie_ttl_seconds: How long to cache cookies
            request_timeout: HTTP request timeout in seconds
            max_retries: Maximum retry attempts for failed requests
            retry_delay: Delay between retries in seconds
        """
        self.flaresolverr_url = flaresolverr_url
        self.request_timeout = request_timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.logger = get_logger("toolkit.simple_fetcher")
        
        # Initialize components
        self.flaresolverr_client = FlareSolverrClient(flaresolverr_url)
        self.cookie_manager = CookieManager(
            self.flaresolverr_client,
            default_ttl_seconds=cookie_ttl_seconds
        )
        
        # HTTP session will be created when needed
        self._http_session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_http_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def _ensure_http_session(self):
        """Ensure HTTP session is created."""
        if self._http_session is None or self._http_session.closed:
            timeout = aiohttp.ClientTimeout(total=self.request_timeout)
            connector = aiohttp.TCPConnector(
                limit=100,  # Total connection pool size
                limit_per_host=10,  # Per-host connection limit
                ttl_dns_cache=300,  # DNS cache TTL
                use_dns_cache=True,
            )
            
            self._http_session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                }
            )
    
    async def fetch_single(self, url: str, force_refresh_cookies: bool = False) -> FetchResult:
        """
        Fetch content from a single URL.
        
        Args:
            url: URL to fetch
            force_refresh_cookies: Force cookie refresh even if cached cookies are valid
            
        Returns:
            FetchResult with the outcome
        """
        start_time = time.time()
        result = FetchResult(url=url, success=False)
        
        try:
            await self._ensure_http_session()
            
            # Check if FlareSolverr is healthy
            if not await self.flaresolverr_client.health_check():
                result.error = "FlareSolverr service is not available"
                return result
            
            # Try to fetch with cached cookies first
            if not force_refresh_cookies:
                fetch_result = await self._fetch_with_cookies(url)
                if fetch_result.success:
                    fetch_result.execution_time = time.time() - start_time
                    return fetch_result
                
                # If cookies failed, we'll refresh them below
                self.logger.info(f"Cached cookies failed for {url}, refreshing...")
                result.cookies_refreshed = True
            
            # Get fresh cookies and try again
            try:
                await self.cookie_manager.invalidate_domain(url)
                fresh_result = await self._fetch_with_cookies(url)
                fresh_result.cookies_refreshed = result.cookies_refreshed or force_refresh_cookies
                fresh_result.execution_time = time.time() - start_time
                return fresh_result
                
            except FlareSolverrError as e:
                result.error = f"FlareSolverr error: {str(e)}"
                return result
        
        except Exception as e:
            result.error = f"Unexpected error: {str(e)}"
            self.logger.error(f"Unexpected error fetching {url}: {str(e)}")
            return result
        
        finally:
            result.execution_time = time.time() - start_time
    
    async def fetch_batch(
        self, 
        urls: List[str], 
        max_concurrent: int = 5,
        force_refresh_cookies: bool = False
    ) -> List[FetchResult]:
        """
        Fetch content from multiple URLs concurrently.
        
        Args:
            urls: List of URLs to fetch
            max_concurrent: Maximum concurrent requests
            force_refresh_cookies: Force cookie refresh for all URLs
            
        Returns:
            List of FetchResults
        """
        if not urls:
            return []
        
        self.logger.info(f"Starting batch fetch of {len(urls)} URLs")
        
        # Create semaphore to limit concurrency
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def fetch_with_semaphore(url: str) -> FetchResult:
            async with semaphore:
                return await self.fetch_single(url, force_refresh_cookies)
        
        # Execute all fetches concurrently
        tasks = [fetch_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions that occurred
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(FetchResult(
                    url=urls[i],
                    success=False,
                    error=f"Task exception: {str(result)}"
                ))
            else:
                final_results.append(result)
        
        # Log summary
        successful = sum(1 for r in final_results if r.success)
        self.logger.info(f"Batch fetch completed: {successful}/{len(urls)} successful")
        
        return final_results
    
    async def _fetch_with_cookies(self, url: str) -> FetchResult:
        """
        Fetch URL using cached cookies.
        
        Args:
            url: URL to fetch
            
        Returns:
            FetchResult
        """
        result = FetchResult(url=url, success=False, used_cookies=True)
        
        try:
            # Get cookies and headers
            cookies = await self.cookie_manager.get_cookies_dict(url)
            headers = await self.cookie_manager.get_headers(url)
            
            # Make the request with retries
            for attempt in range(self.max_retries + 1):
                try:
                    async with self._http_session.get(
                        url,
                        headers=headers,
                        cookies=cookies,
                        allow_redirects=True
                    ) as response:
                        result.status_code = response.status
                        
                        if response.status == 200:
                            content = await response.text()
                            result.content = content
                            result.content_length = len(content)
                            result.success = True
                            
                            self.logger.debug(
                                f"Successfully fetched {url}",
                                status_code=response.status,
                                content_length=result.content_length,
                                attempt=attempt + 1
                            )
                            return result
                        
                        elif response.status in [403, 429]:
                            # Likely cookie/rate limit issue
                            result.error = f"HTTP {response.status} - cookies may be invalid"
                            self.logger.warning(f"HTTP {response.status} for {url}, cookies may be invalid")
                            return result
                        
                        else:
                            result.error = f"HTTP {response.status}"
                            if attempt < self.max_retries:
                                self.logger.warning(f"HTTP {response.status} for {url}, retrying...")
                                await asyncio.sleep(self.retry_delay)
                                continue
                            return result
                
                except asyncio.TimeoutError:
                    if attempt < self.max_retries:
                        self.logger.warning(f"Timeout for {url}, retrying...")
                        await asyncio.sleep(self.retry_delay)
                        continue
                    result.error = "Request timeout"
                    return result
                
                except Exception as e:
                    if attempt < self.max_retries:
                        self.logger.warning(f"Request error for {url}: {str(e)}, retrying...")
                        await asyncio.sleep(self.retry_delay)
                        continue
                    result.error = f"Request error: {str(e)}"
                    return result
            
            return result
        
        except Exception as e:
            result.error = f"Cookie/header error: {str(e)}"
            return result
    
    async def get_cookie_info(self) -> Dict[str, Any]:
        """
        Get information about cached cookies.
        
        Returns:
            Dictionary with cookie session information
        """
        return await self.cookie_manager.get_session_info()
    
    async def cleanup_stale_cookies(self) -> int:
        """
        Clean up stale cookie sessions.
        
        Returns:
            Number of sessions cleaned up
        """
        return await self.cookie_manager.cleanup_stale_sessions()
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check the health of the fetcher service.
        
        Returns:
            Health status information
        """
        health = {
            "service": "SimpleFetcher",
            "status": "healthy",
            "flaresolverr_healthy": False,
            "http_session_active": self._http_session is not None and not self._http_session.closed,
            "cached_domains": 0,
            "timestamp": time.time()
        }
        
        try:
            # Check FlareSolverr
            health["flaresolverr_healthy"] = await self.flaresolverr_client.health_check()
            
            # Get cookie info
            cookie_info = await self.get_cookie_info()
            health["cached_domains"] = len(cookie_info)
            health["cookie_sessions"] = cookie_info
            
            if not health["flaresolverr_healthy"]:
                health["status"] = "degraded"
                health["issues"] = ["FlareSolverr service unavailable"]
        
        except Exception as e:
            health["status"] = "unhealthy"
            health["error"] = str(e)
        
        return health
    
    async def close(self):
        """Close the fetcher and clean up resources."""
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()
            self.logger.debug("HTTP session closed")
        
        # Clean up any FlareSolverr sessions if needed
        await self.flaresolverr_client.cleanup_old_sessions()
        self.logger.debug("SimpleFetcher closed")
