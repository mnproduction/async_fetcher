"""
Browser instance pooling for improved performance.

This module provides a browser pool to reuse browser instances
instead of creating new ones for each request, significantly
improving performance for high-volume operations.
"""

import asyncio
import time
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager
from dataclasses import dataclass

from settings.logger import get_logger
from toolkit.browser import StealthBrowserToolkit

logger = get_logger("toolkit.browser_pool")


@dataclass
class BrowserInstance:
    """Represents a browser instance in the pool."""
    toolkit: StealthBrowserToolkit
    created_at: float
    last_used: float
    in_use: bool = False
    use_count: int = 0


class BrowserPool:
    """
    Pool of browser instances for reuse.
    
    This class manages a pool of browser instances to avoid the overhead
    of creating and destroying browsers for each request.
    """
    
    def __init__(
        self,
        min_size: int = 2,
        max_size: int = 10,
        max_age_seconds: int = 300,  # 5 minutes
        max_uses: int = 100,
        cleanup_interval: int = 60  # 1 minute
    ):
        """
        Initialize the browser pool.
        
        Args:
            min_size: Minimum number of browsers to keep in pool
            max_size: Maximum number of browsers in pool
            max_age_seconds: Maximum age of a browser before replacement
            max_uses: Maximum uses of a browser before replacement
            cleanup_interval: Interval between cleanup runs (seconds)
        """
        self.min_size = min_size
        self.max_size = max_size
        self.max_age_seconds = max_age_seconds
        self.max_uses = max_uses
        self.cleanup_interval = cleanup_interval
        
        self._pool: List[BrowserInstance] = []
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._shutdown = False
    
    async def start(self):
        """Start the browser pool and initialize minimum browsers."""
        logger.info("Starting browser pool", min_size=self.min_size, max_size=self.max_size)
        
        # Pre-create minimum number of browsers
        for _ in range(self.min_size):
            await self._create_browser()
        
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info("Browser pool started", browsers=len(self._pool))
    
    async def stop(self):
        """Stop the browser pool and close all browsers."""
        logger.info("Stopping browser pool")
        self._shutdown = True
        
        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Close all browsers
        async with self._lock:
            for instance in self._pool:
                try:
                    await instance.toolkit.close()
                except Exception as e:
                    logger.warning("Error closing browser", error=str(e))
            
            self._pool.clear()
        
        logger.info("Browser pool stopped")
    
    @asynccontextmanager
    async def get_browser(self):
        """
        Get a browser instance from the pool.
        
        Returns:
            Context manager yielding a StealthBrowserToolkit instance
        """
        instance = await self._acquire_browser()
        try:
            yield instance.toolkit
        finally:
            await self._release_browser(instance)
    
    async def _acquire_browser(self) -> BrowserInstance:
        """Acquire a browser instance from the pool."""
        async with self._lock:
            # Find available browser
            for instance in self._pool:
                if not instance.in_use and self._is_browser_healthy(instance):
                    instance.in_use = True
                    instance.last_used = time.time()
                    instance.use_count += 1
                    logger.debug("Acquired browser from pool", use_count=instance.use_count)
                    return instance
            
            # No available browser, create new one if under limit
            if len(self._pool) < self.max_size:
                instance = await self._create_browser()
                instance.in_use = True
                instance.last_used = time.time()
                instance.use_count += 1
                logger.debug("Created new browser for pool", pool_size=len(self._pool))
                return instance
            
            # Pool is full, wait for available browser
            logger.warning("Browser pool exhausted, waiting for available browser")
        
        # Wait for browser to become available
        while True:
            await asyncio.sleep(0.1)
            async with self._lock:
                for instance in self._pool:
                    if not instance.in_use and self._is_browser_healthy(instance):
                        instance.in_use = True
                        instance.last_used = time.time()
                        instance.use_count += 1
                        logger.debug("Acquired browser after wait", use_count=instance.use_count)
                        return instance
    
    async def _release_browser(self, instance: BrowserInstance):
        """Release a browser instance back to the pool."""
        async with self._lock:
            instance.in_use = False
            logger.debug("Released browser to pool", use_count=instance.use_count)
    
    async def _create_browser(self) -> BrowserInstance:
        """Create a new browser instance."""
        toolkit = StealthBrowserToolkit(headless=True)
        
        if not await toolkit.initialize():
            raise RuntimeError("Failed to initialize browser for pool")
        
        instance = BrowserInstance(
            toolkit=toolkit,
            created_at=time.time(),
            last_used=time.time()
        )
        
        self._pool.append(instance)
        return instance
    
    def _is_browser_healthy(self, instance: BrowserInstance) -> bool:
        """Check if a browser instance is healthy and can be reused."""
        now = time.time()
        
        # Check age
        if now - instance.created_at > self.max_age_seconds:
            return False
        
        # Check usage count
        if instance.use_count >= self.max_uses:
            return False
        
        return True
    
    async def _cleanup_loop(self):
        """Background task to clean up old/overused browsers."""
        while not self._shutdown:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_browsers()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in browser pool cleanup", error=str(e))
    
    async def _cleanup_browsers(self):
        """Remove old or overused browsers from the pool."""
        async with self._lock:
            to_remove = []
            
            for instance in self._pool:
                if instance.in_use:
                    continue
                
                if not self._is_browser_healthy(instance):
                    to_remove.append(instance)
            
            # Remove unhealthy browsers
            for instance in to_remove:
                try:
                    await instance.toolkit.close()
                    self._pool.remove(instance)
                    logger.debug("Removed unhealthy browser from pool", age=time.time() - instance.created_at, uses=instance.use_count)
                except Exception as e:
                    logger.warning("Error removing browser from pool", error=str(e))
            
            # Ensure minimum pool size
            while len(self._pool) < self.min_size and not self._shutdown:
                try:
                    await self._create_browser()
                    logger.debug("Added browser to maintain minimum pool size")
                except Exception as e:
                    logger.error("Error creating browser for minimum pool size", error=str(e))
                    break
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        total_browsers = len(self._pool)
        in_use = sum(1 for instance in self._pool if instance.in_use)
        available = total_browsers - in_use
        
        return {
            "total_browsers": total_browsers,
            "in_use": in_use,
            "available": available,
            "min_size": self.min_size,
            "max_size": self.max_size
        }


# Global browser pool instance
_browser_pool: Optional[BrowserPool] = None


async def get_browser_pool() -> BrowserPool:
    """Get the global browser pool instance."""
    global _browser_pool
    
    if _browser_pool is None:
        _browser_pool = BrowserPool()
        await _browser_pool.start()
    
    return _browser_pool


async def shutdown_browser_pool():
    """Shutdown the global browser pool."""
    global _browser_pool
    
    if _browser_pool:
        await _browser_pool.stop()
        _browser_pool = None
