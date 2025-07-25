import asyncio
import time
from typing import Dict, Any
from urllib.parse import urlparse
from dataclasses import dataclass, asdict
import json

from toolkit.flaresolverr import FlareSolverrClient, FlareSolverrError
from settings.logger import get_logger


@dataclass
class CookieSession:
    """Represents a cached cookie session for a domain."""
    domain: str
    cookies_dict: Dict[str, str]
    cookies_list: list
    user_agent: str
    created_at: float
    expires_at: float
    last_used: float
    
    def is_expired(self) -> bool:
        """Check if the cookie session has expired."""
        return time.time() > self.expires_at
    
    def is_stale(self, max_age_seconds: int = 1800) -> bool:
        """Check if the session is stale (hasn't been used recently)."""
        return time.time() - self.last_used > max_age_seconds
    
    def touch(self):
        """Update the last_used timestamp."""
        self.last_used = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CookieSession':
        """Create from dictionary."""
        return cls(**data)


class CookieManager:
    """
    Manages Cloudflare cookies with automatic refresh and caching.
    
    This manager handles:
    - Cookie extraction via FlareSolverr
    - Automatic expiration and refresh
    - Domain-based cookie storage
    - Performance optimization through caching
    """
    
    def __init__(
        self,
        flaresolverr_client: FlareSolverrClient,
        default_ttl_seconds: int = 1800,  # 30 minutes
        max_stale_seconds: int = 3600,    # 1 hour
        auto_refresh: bool = True
    ):
        """
        Initialize cookie manager.
        
        Args:
            flaresolverr_client: FlareSolverr client instance
            default_ttl_seconds: Default cookie TTL in seconds
            max_stale_seconds: Maximum time to keep unused cookies
            auto_refresh: Whether to automatically refresh expired cookies
        """
        self.flaresolverr = flaresolverr_client
        self.default_ttl = default_ttl_seconds
        self.max_stale = max_stale_seconds
        self.auto_refresh = auto_refresh
        self.logger = get_logger("toolkit.cookie_manager")
        
        # Domain -> CookieSession mapping
        self._sessions: Dict[str, CookieSession] = {}
        
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()
    
    async def get_session(self, url: str, force_refresh: bool = False) -> CookieSession:
        """
        Get a valid cookie session for the given URL.
        
        Args:
            url: Target URL
            force_refresh: Force refresh even if cookies are valid
            
        Returns:
            Valid CookieSession
            
        Raises:
            FlareSolverrError: If cookie extraction fails
        """
        domain = self._extract_domain(url)
        
        async with self._lock:
            # Check if we have a valid cached session
            if not force_refresh and domain in self._sessions:
                session = self._sessions[domain]
                
                if not session.is_expired():
                    session.touch()
                    self.logger.debug(f"Using cached cookies for {domain}")
                    return session
                else:
                    self.logger.info(f"Cookies expired for {domain}, refreshing...")
            
            # Need to get fresh cookies
            self.logger.info(f"Extracting fresh cookies for {domain}")
            session = await self._extract_cookies(url, domain)
            self._sessions[domain] = session
            
            return session
    
    async def get_cookies_dict(self, url: str, force_refresh: bool = False) -> Dict[str, str]:
        """
        Get cookies dictionary for the URL.
        
        Args:
            url: Target URL
            force_refresh: Force refresh even if cookies are valid
            
        Returns:
            Dictionary of cookie name -> value
        """
        session = await self.get_session(url, force_refresh)
        return session.cookies_dict
    
    async def get_headers(self, url: str, force_refresh: bool = False) -> Dict[str, str]:
        """
        Get HTTP headers including User-Agent for the URL.
        
        Args:
            url: Target URL
            force_refresh: Force refresh even if cookies are valid
            
        Returns:
            Dictionary of HTTP headers
        """
        session = await self.get_session(url, force_refresh)
        return {
            "User-Agent": session.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Cache-Control": "max-age=0"
        }
    
    async def invalidate_domain(self, url: str):
        """
        Invalidate cached cookies for a domain.
        
        Args:
            url: URL whose domain cookies should be invalidated
        """
        domain = self._extract_domain(url)
        async with self._lock:
            if domain in self._sessions:
                del self._sessions[domain]
                self.logger.info(f"Invalidated cookies for {domain}")
    
    async def cleanup_stale_sessions(self) -> int:
        """
        Remove stale cookie sessions.
        
        Returns:
            Number of sessions cleaned up
        """
        async with self._lock:
            stale_domains = []
            
            for domain, session in self._sessions.items():
                if session.is_stale(self.max_stale):
                    stale_domains.append(domain)
            
            for domain in stale_domains:
                del self._sessions[domain]
            
            if stale_domains:
                self.logger.info(f"Cleaned up {len(stale_domains)} stale cookie sessions")
            
            return len(stale_domains)
    
    async def get_session_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all cached sessions.
        
        Returns:
            Dictionary of domain -> session info
        """
        async with self._lock:
            info = {}
            current_time = time.time()
            
            for domain, session in self._sessions.items():
                info[domain] = {
                    "created_at": session.created_at,
                    "expires_at": session.expires_at,
                    "last_used": session.last_used,
                    "is_expired": session.is_expired(),
                    "is_stale": session.is_stale(self.max_stale),
                    "age_seconds": current_time - session.created_at,
                    "cookies_count": len(session.cookies_dict),
                    "user_agent": session.user_agent[:50] + "..." if len(session.user_agent) > 50 else session.user_agent
                }
            
            return info
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        parsed = urlparse(url)
        return parsed.netloc
    
    async def _extract_cookies(self, url: str, domain: str) -> CookieSession:
        """
        Extract cookies from FlareSolverr for a domain.
        
        Args:
            url: Target URL
            domain: Domain name
            
        Returns:
            New CookieSession
            
        Raises:
            FlareSolverrError: If extraction fails
        """
        try:
            # Use FlareSolverr to get cookies
            cookie_data = await self.flaresolverr.get_cookies_for_domain(url)
            
            current_time = time.time()
            expires_at = current_time + self.default_ttl
            
            session = CookieSession(
                domain=domain,
                cookies_dict=cookie_data["cookies_dict"],
                cookies_list=cookie_data["cookies_list"],
                user_agent=cookie_data["user_agent"],
                created_at=current_time,
                expires_at=expires_at,
                last_used=current_time
            )
            
            self.logger.info(
                f"Extracted cookies for {domain}",
                cookies_count=len(session.cookies_dict),
                ttl_seconds=self.default_ttl,
                user_agent=session.user_agent[:50] + "..."
            )
            
            return session
            
        except Exception as e:
            self.logger.error(f"Failed to extract cookies for {domain}: {str(e)}")
            raise FlareSolverrError(f"Cookie extraction failed for {domain}: {str(e)}") from e
    
    async def save_sessions_to_file(self, filepath: str):
        """
        Save current sessions to a JSON file.
        
        Args:
            filepath: Path to save the sessions
        """
        async with self._lock:
            data = {
                domain: session.to_dict() 
                for domain, session in self._sessions.items()
            }
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            
            self.logger.info(f"Saved {len(data)} sessions to {filepath}")
    
    async def load_sessions_from_file(self, filepath: str) -> int:
        """
        Load sessions from a JSON file.
        
        Args:
            filepath: Path to load sessions from
            
        Returns:
            Number of sessions loaded
        """
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            async with self._lock:
                loaded_count = 0

                for domain, session_data in data.items():
                    session = CookieSession.from_dict(session_data)

                    # Only load non-expired sessions
                    if not session.is_expired():
                        self._sessions[domain] = session
                        loaded_count += 1
                    else:
                        self.logger.debug(f"Skipped expired session for {domain}")

                self.logger.info(f"Loaded {loaded_count} valid sessions from {filepath}")
                return loaded_count

        except FileNotFoundError:
            self.logger.info(f"Session file {filepath} not found, starting fresh")
            return 0
        except Exception as e:
            self.logger.error(f"Failed to load sessions from {filepath}: {str(e)}")
            return 0
