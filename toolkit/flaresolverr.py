import asyncio
import aiohttp
import json
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse

from settings.logger import get_logger


class FlareSolverrError(Exception):
    """Base exception for FlareSolverr-related errors."""
    pass


class FlareSolverrTimeoutError(FlareSolverrError):
    """Raised when FlareSolverr request times out."""
    pass


class FlareSolverrChallengeError(FlareSolverrError):
    """Raised when FlareSolverr fails to solve the challenge."""
    pass


class FlareSolverrConnectionError(FlareSolverrError):
    """Raised when unable to connect to FlareSolverr service."""
    pass


class FlareSolverrClient:
    """
    Async client for interacting with FlareSolverr service to bypass Cloudflare protection.
    
    This client provides both direct proxy usage and cookie extraction capabilities
    for bypassing Cloudflare v3 protection including Turnstile CAPTCHAs.
    """
    
    def __init__(
        self,
        flaresolverr_url: str = "http://localhost:8191",
        default_timeout: int = 60000,
        session_ttl: int = 600000  # 10 minutes
    ):
        """
        Initialize FlareSolverr client.
        
        Args:
            flaresolverr_url: URL of the FlareSolverr service
            default_timeout: Default timeout for challenge solving in milliseconds
            session_ttl: Session time-to-live in milliseconds
        """
        self.flaresolverr_url = flaresolverr_url.rstrip('/')
        self.api_endpoint = f"{self.flaresolverr_url}/v1"
        self.default_timeout = default_timeout
        self.session_ttl = session_ttl
        self.logger = get_logger("toolkit.flaresolverr")
        
        # Session management
        self.sessions: Dict[str, Dict[str, Any]] = {}
        
    async def health_check(self) -> bool:
        """
        Check if FlareSolverr service is running and accessible.
        
        Returns:
            bool: True if service is healthy, False otherwise
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.flaresolverr_url,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if "FlareSolverr is ready!" in data.get("msg", ""):
                            self.logger.info(
                                "FlareSolverr health check passed",
                                version=data.get("version"),
                                user_agent=data.get("userAgent", "")[:50] + "..."
                            )
                            return True
                    return False
        except Exception as e:
            self.logger.error(f"FlareSolverr health check failed: {str(e)}")
            return False
    
    async def create_session(self, session_id: str) -> bool:
        """
        Create a new browser session in FlareSolverr.
        
        Args:
            session_id: Unique identifier for the session
            
        Returns:
            bool: True if session created successfully
        """
        payload = {
            "cmd": "sessions.create",
            "session": session_id,
            "maxTimeout": self.session_ttl
        }
        
        try:
            result = await self._make_request(payload)
            if result.get("status") == "ok":
                self.sessions[session_id] = {
                    "created_at": asyncio.get_event_loop().time(),
                    "last_used": asyncio.get_event_loop().time()
                }
                self.logger.info(f"Created FlareSolverr session: {session_id}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Failed to create session {session_id}: {str(e)}")
            return False
    
    async def destroy_session(self, session_id: str) -> bool:
        """
        Destroy a browser session in FlareSolverr.
        
        Args:
            session_id: Session identifier to destroy
            
        Returns:
            bool: True if session destroyed successfully
        """
        payload = {
            "cmd": "sessions.destroy",
            "session": session_id
        }
        
        try:
            result = await self._make_request(payload)
            if result.get("status") == "ok":
                self.sessions.pop(session_id, None)
                self.logger.info(f"Destroyed FlareSolverr session: {session_id}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Failed to destroy session {session_id}: {str(e)}")
            return False
    
    async def solve_challenge(
        self,
        url: str,
        session_id: Optional[str] = None,
        timeout: Optional[int] = None,
        headers: Optional[Dict[str, str]] = None,
        cookies: Optional[List[Dict[str, Any]]] = None,
        return_only_cookies: bool = False
    ) -> Dict[str, Any]:
        """
        Solve Cloudflare challenge for a given URL.
        
        Args:
            url: Target URL to access
            session_id: Optional session ID to use
            timeout: Timeout in milliseconds (uses default if None)
            headers: Optional custom headers
            cookies: Optional initial cookies
            return_only_cookies: If True, only return cookies without full HTML
            
        Returns:
            Dict containing solution data (HTML, cookies, user-agent, etc.)
            
        Raises:
            FlareSolverrError: Various FlareSolverr-related errors
        """
        payload = {
            "cmd": "request.get",
            "url": url,
            "maxTimeout": timeout or self.default_timeout,
            "returnOnlyCookies": return_only_cookies
        }
        
        if session_id:
            payload["session"] = session_id
            # Update session last used time
            if session_id in self.sessions:
                self.sessions[session_id]["last_used"] = asyncio.get_event_loop().time()
        
        if headers:
            payload["headers"] = headers
            
        if cookies:
            payload["cookies"] = cookies
        
        self.logger.info(
            "Solving Cloudflare challenge",
            url=url,
            session_id=session_id,
            timeout=timeout or self.default_timeout,
            return_only_cookies=return_only_cookies
        )
        
        try:
            result = await self._make_request(payload)
            
            if result.get("status") != "ok":
                error_msg = result.get("message", "Unknown error")
                self.logger.error(f"Challenge solving failed: {error_msg}")
                raise FlareSolverrChallengeError(f"Failed to solve challenge: {error_msg}")
            
            solution = result.get("solution", {})
            self.logger.info(
                "Challenge solved successfully",
                url=url,
                final_url=solution.get("url"),
                status_code=solution.get("status"),
                cookies_count=len(solution.get("cookies", [])),
                content_length=len(solution.get("response", "")) if not return_only_cookies else 0
            )
            
            return solution
            
        except FlareSolverrError:
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error during challenge solving: {str(e)}")
            raise FlareSolverrError(f"Unexpected error: {str(e)}") from e
    
    async def get_cookies_for_domain(
        self,
        url: str,
        session_id: Optional[str] = None,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get valid Cloudflare cookies for a domain by solving the challenge.
        
        This method is optimized for cookie extraction and can be used
        with other HTTP clients like aiohttp or requests.
        
        Args:
            url: Target URL to get cookies for
            session_id: Optional session ID
            timeout: Timeout in milliseconds
            
        Returns:
            Dict containing cookies, user-agent, and domain info
        """
        solution = await self.solve_challenge(
            url=url,
            session_id=session_id,
            timeout=timeout,
            return_only_cookies=True
        )
        
        # Convert cookies list to dict format for easy use with HTTP clients
        cookies_list = solution.get("cookies", [])
        cookies_dict = {cookie["name"]: cookie["value"] for cookie in cookies_list}
        
        # Extract domain from URL
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        
        return {
            "cookies_dict": cookies_dict,
            "cookies_list": cookies_list,
            "user_agent": solution.get("userAgent", ""),
            "domain": domain,
            "final_url": solution.get("url", url),
            "status_code": solution.get("status", 200)
        }
    
    async def _make_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make HTTP request to FlareSolverr API.
        
        Args:
            payload: Request payload
            
        Returns:
            Response data as dict
            
        Raises:
            FlareSolverrConnectionError: Connection issues
            FlareSolverrTimeoutError: Request timeout
            FlareSolverrError: Other errors
        """
        headers = {"Content-Type": "application/json"}
        
        try:
            timeout = aiohttp.ClientTimeout(
                total=payload.get("maxTimeout", self.default_timeout) / 1000 + 30
            )
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_endpoint,
                    json=payload,
                    headers=headers,
                    timeout=timeout
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise FlareSolverrConnectionError(
                            f"HTTP {response.status}: {error_text}"
                        )
                    
                    return await response.json()
                    
        except asyncio.TimeoutError as e:
            raise FlareSolverrTimeoutError("Request to FlareSolverr timed out") from e
        except aiohttp.ClientError as e:
            raise FlareSolverrConnectionError(f"Connection error: {str(e)}") from e
        except json.JSONDecodeError as e:
            raise FlareSolverrError(f"Invalid JSON response: {str(e)}") from e
    
    async def cleanup_old_sessions(self, max_age_seconds: int = 600) -> int:
        """
        Clean up old sessions that haven't been used recently.
        
        Args:
            max_age_seconds: Maximum age for sessions in seconds
            
        Returns:
            Number of sessions cleaned up
        """
        current_time = asyncio.get_event_loop().time()
        old_sessions = []
        
        for session_id, session_info in self.sessions.items():
            if current_time - session_info["last_used"] > max_age_seconds:
                old_sessions.append(session_id)
        
        cleaned_count = 0
        for session_id in old_sessions:
            if await self.destroy_session(session_id):
                cleaned_count += 1
        
        if cleaned_count > 0:
            self.logger.info(f"Cleaned up {cleaned_count} old FlareSolverr sessions")
        
        return cleaned_count
