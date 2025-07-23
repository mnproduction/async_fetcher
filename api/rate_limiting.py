"""
Rate Limiting Middleware for Async HTML Fetcher Service

This module provides comprehensive rate limiting functionality to protect
the API from abuse and ensure fair resource usage.

Features:
- Per-client rate limiting based on IP address
- Configurable limits for different endpoints
- Sliding window rate limiting algorithm
- Automatic cleanup of expired entries
- Detailed logging and monitoring

Author: Async HTML Fetcher Service
Version: 1.0.0
"""

import time
import asyncio
from collections import defaultdict, deque
from typing import Dict, Deque, Optional, Tuple
from dataclasses import dataclass
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse

from settings.logger import get_logger

# Initialize logger for this module
logger = get_logger("api.rate_limiting")


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting rules."""
    
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_limit: int = 10
    window_size_seconds: int = 60


class RateLimiter:
    """
    Rate limiter implementation using sliding window algorithm.
    
    This class provides rate limiting functionality with:
    - Per-client tracking based on IP address
    - Sliding window algorithm for accurate rate calculation
    - Automatic cleanup of expired entries
    - Configurable limits and windows
    """
    
    def __init__(self, config: RateLimitConfig):
        """
        Initialize the rate limiter.
        
        Args:
            config: Rate limiting configuration
        """
        self.config = config
        self.clients: Dict[str, Deque[float]] = defaultdict(deque)
        self.lock = asyncio.Lock()
        self._cleanup_task = None
        
        # Start cleanup task only if there's a running event loop
        try:
            self._cleanup_task = asyncio.create_task(self._cleanup_expired_entries())
        except RuntimeError:
            # No running event loop, cleanup will be started when needed
            pass
    
    async def is_allowed(self, client_id: str) -> Tuple[bool, Dict[str, int]]:
        """
        Check if a client is allowed to make a request.
        
        Args:
            client_id: Unique identifier for the client (usually IP address)
            
        Returns:
            Tuple[bool, Dict]: (allowed, rate_limit_info)
        """
        # Start cleanup task if not already started
        if self._cleanup_task is None:
            try:
                self._cleanup_task = asyncio.create_task(self._cleanup_expired_entries())
            except RuntimeError:
                # Still no running event loop, skip cleanup for now
                pass
        
        async with self.lock:
            current_time = time.time()
            
            # Get client's request history
            client_requests = self.clients[client_id]
            
            # Remove expired requests (older than window_size_seconds)
            cutoff_time = current_time - self.config.window_size_seconds
            while client_requests and client_requests[0] < cutoff_time:
                client_requests.popleft()
            
            # Check burst limit
            if len(client_requests) >= self.config.burst_limit:
                logger.warning(
                    "Rate limit exceeded (burst)",
                    client_id=client_id,
                    request_count=len(client_requests),
                    burst_limit=self.config.burst_limit
                )
                return False, {
                    "limit": self.config.burst_limit,
                    "remaining": 0,
                    "reset_time": int(cutoff_time + self.config.window_size_seconds)
                }
            
            # Add current request
            client_requests.append(current_time)
            
            # Calculate remaining requests
            remaining = max(0, self.config.requests_per_minute - len(client_requests))
            
            return True, {
                "limit": self.config.requests_per_minute,
                "remaining": remaining,
                "reset_time": int(current_time + self.config.window_size_seconds)
            }
    
    async def _cleanup_expired_entries(self):
        """Periodically cleanup expired client entries."""
        while True:
            try:
                await asyncio.sleep(300)  # Cleanup every 5 minutes
                
                async with self.lock:
                    current_time = time.time()
                    cutoff_time = current_time - self.config.window_size_seconds
                    
                    # Remove clients with no recent requests
                    expired_clients = []
                    for client_id, requests in self.clients.items():
                        # Remove expired requests
                        while requests and requests[0] < cutoff_time:
                            requests.popleft()
                        
                        # Remove client if no requests remain
                        if not requests:
                            expired_clients.append(client_id)
                    
                    # Remove expired clients
                    for client_id in expired_clients:
                        del self.clients[client_id]
                    
                    if expired_clients:
                        logger.debug(
                            "Cleaned up expired rate limit entries",
                            expired_clients=len(expired_clients),
                            active_clients=len(self.clients)
                        )
                        
            except Exception as e:
                logger.error(
                    "Error during rate limit cleanup",
                    error=str(e),
                    error_type=type(e).__name__
                )


# =============================================================================
# RATE LIMITING CONFIGURATIONS
# =============================================================================

# Default rate limiting configuration
DEFAULT_RATE_LIMIT = RateLimitConfig(
    requests_per_minute=60,
    requests_per_hour=1000,
    burst_limit=10,
    window_size_seconds=60
)

# Strict rate limiting for fetch endpoints
FETCH_RATE_LIMIT = RateLimitConfig(
    requests_per_minute=30,  # More restrictive for resource-intensive operations
    requests_per_hour=500,
    burst_limit=5,
    window_size_seconds=60
)

# Create rate limiter instances
default_limiter = RateLimiter(DEFAULT_RATE_LIMIT)
fetch_limiter = RateLimiter(FETCH_RATE_LIMIT)


# =============================================================================
# CLIENT IDENTIFICATION
# =============================================================================

def get_client_id(request: Request) -> str:
    """
    Extract client identifier from request.
    
    Args:
        request: FastAPI request object
        
    Returns:
        str: Client identifier (IP address)
    """
    # Try to get real IP from various headers
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP in the chain
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # Fallback to client host
    if request.client:
        return request.client.host
    
    # Last resort
    return "unknown"


# =============================================================================
# RATE LIMITING MIDDLEWARE
# =============================================================================

async def rate_limit_middleware(
    request: Request,
    call_next,
    limiter: RateLimiter = default_limiter
):
    """
    Rate limiting middleware for FastAPI.
    
    Args:
        request: FastAPI request object
        call_next: Next middleware/endpoint function
        limiter: Rate limiter instance to use
        
    Returns:
        Response: FastAPI response object
        
    Raises:
        HTTPException: If rate limit is exceeded
    """
    client_id = get_client_id(request)
    
    # Check rate limit
    allowed, rate_info = await limiter.is_allowed(client_id)
    
    if not allowed:
        logger.warning(
            "Rate limit exceeded",
            client_id=client_id,
            path=request.url.path,
            method=request.method,
            rate_info=rate_info
        )
        
        return JSONResponse(
            status_code=429,
            content={
                "error": "Rate limit exceeded",
                "detail": "Too many requests. Please try again later.",
                "retry_after": rate_info["reset_time"] - int(time.time()),
                "rate_limit_info": rate_info
            },
            headers={
                "X-RateLimit-Limit": str(rate_info["limit"]),
                "X-RateLimit-Remaining": str(rate_info["remaining"]),
                "X-RateLimit-Reset": str(rate_info["reset_time"]),
                "Retry-After": str(rate_info["reset_time"] - int(time.time()))
            }
        )
    
    # Add rate limit headers to response
    response = await call_next(request)
    
    response.headers["X-RateLimit-Limit"] = str(rate_info["limit"])
    response.headers["X-RateLimit-Remaining"] = str(rate_info["remaining"])
    response.headers["X-RateLimit-Reset"] = str(rate_info["reset_time"])
    
    return response


# =============================================================================
# ENDPOINT-SPECIFIC RATE LIMITING
# =============================================================================

async def fetch_endpoint_rate_limit(request: Request, call_next):
    """
    Rate limiting middleware specifically for fetch endpoints.
    
    Uses stricter rate limits for resource-intensive fetch operations.
    """
    return await rate_limit_middleware(request, call_next, fetch_limiter)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_rate_limit_stats() -> Dict[str, int]:
    """
    Get current rate limiting statistics.
    
    Returns:
        Dict: Statistics about current rate limiting state
    """
    return {
        "default_clients": len(default_limiter.clients),
        "fetch_clients": len(fetch_limiter.clients),
        "total_clients": len(default_limiter.clients) + len(fetch_limiter.clients)
    }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'RateLimiter',
    'RateLimitConfig',
    'DEFAULT_RATE_LIMIT',
    'FETCH_RATE_LIMIT',
    'default_limiter',
    'fetch_limiter',
    'rate_limit_middleware',
    'fetch_endpoint_rate_limit',
    'get_client_id',
    'get_rate_limit_stats'
] 