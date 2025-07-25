"""
Simplified FastAPI application for Cloudflare-protected content fetching.

This application provides a clean, simple API for fetching content from
Cloudflare-protected sites using FlareSolverr cookie extraction + aiohttp.
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Import simplified models
from .models import (
    SingleFetchRequest, BatchFetchRequest, FetchResult,
    BatchFetchResponse, HealthResponse
)

# Import the simplified fetcher
from toolkit.simple_fetcher import SimpleFetcher

# Import logger
from settings.logger import get_logger

# Initialize logger
logger = get_logger("api.main")

# Global fetcher instance
fetcher: SimpleFetcher = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global fetcher

    # Startup
    logger.info("Simplified Fetcher Service starting up")

    # Initialize the fetcher
    flaresolverr_url = os.getenv("FLARESOLVERR_URL", "http://localhost:8191")
    fetcher = SimpleFetcher(flaresolverr_url=flaresolverr_url)

    # Test FlareSolverr connection
    try:
        health = await fetcher.health_check()
        if health["flaresolverr_healthy"]:
            logger.info("FlareSolverr connection verified")
        else:
            logger.warning("FlareSolverr service not available at startup")
    except Exception as e:
        logger.error(f"Failed to check FlareSolverr health: {str(e)}")

    yield

    # Shutdown
    logger.info("Simplified Fetcher Service shutting down")
    if fetcher:
        await fetcher.close()


# Create simplified FastAPI application
app = FastAPI(
    title="Simplified Content Fetcher",
    description="""
    A simplified service for fetching content from Cloudflare-protected sites.

    ## Features

    * **FlareSolverr Integration**: Bypasses Cloudflare protection using FlareSolverr
    * **Cookie Caching**: Efficient cookie management with automatic refresh
    * **Fast HTTP Requests**: Uses aiohttp for high-performance requests
    * **Batch Processing**: Supports concurrent fetching of multiple URLs
    * **Simple API**: Clean, minimal API focused on core functionality

    ## Use Cases

    * Fetching content from Cloudflare-protected sites
    * Periodic content monitoring (like tem.fi)
    * Batch content extraction
    * Link checking and validation

    ## Requirements

    * FlareSolverr service running on port 8191
    * Target sites must be accessible via FlareSolverr
    """,
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# API ENDPOINTS
# =============================================================================

@app.post("/fetch", response_model=FetchResult)
async def fetch_single_url(request: SingleFetchRequest):
    """
    Fetch content from a single URL using FlareSolverr + aiohttp.

    This endpoint fetches content from Cloudflare-protected sites by:
    1. Using cached cookies if available and valid
    2. Refreshing cookies via FlareSolverr if needed
    3. Making fast HTTP requests with aiohttp

    Args:
        request: Single fetch request with URL and options

    Returns:
        FetchResult with content, timing, and status information
    """
    if not fetcher:
        raise HTTPException(status_code=503, detail="Fetcher service not initialized")

    try:
        result = await fetcher.fetch_single(
            url=request.url,
            force_refresh_cookies=request.force_refresh_cookies
        )

        # Convert SimpleFetcher result to API model
        return FetchResult(
            url=result.url,
            success=result.success,
            status_code=result.status_code,
            content=result.content,
            content_length=result.content_length,
            execution_time=result.execution_time,
            error=result.error,
            used_cookies=result.used_cookies,
            cookies_refreshed=result.cookies_refreshed
        )

    except Exception as e:
        logger.error(f"Error fetching single URL {request.url}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.post("/fetch/batch", response_model=BatchFetchResponse)
async def fetch_multiple_urls(request: BatchFetchRequest):
    """
    Fetch content from multiple URLs concurrently.

    This endpoint processes multiple URLs efficiently by:
    1. Using shared cookie sessions across requests
    2. Processing URLs concurrently with configurable limits
    3. Providing detailed results for each URL

    Args:
        request: Batch fetch request with URLs and options

    Returns:
        BatchFetchResponse with results for all URLs
    """
    if not fetcher:
        raise HTTPException(status_code=503, detail="Fetcher service not initialized")

    try:
        results = await fetcher.fetch_batch(
            urls=request.urls,
            max_concurrent=request.max_concurrent,
            force_refresh_cookies=request.force_refresh_cookies
        )

        # Convert results to API models
        api_results = []
        successful_count = 0
        total_time = 0.0

        for result in results:
            api_result = FetchResult(
                url=result.url,
                success=result.success,
                status_code=result.status_code,
                content=result.content,
                content_length=result.content_length,
                execution_time=result.execution_time,
                error=result.error,
                used_cookies=result.used_cookies,
                cookies_refreshed=result.cookies_refreshed
            )
            api_results.append(api_result)

            if result.success:
                successful_count += 1
            total_time = max(total_time, result.execution_time)

        return BatchFetchResponse(
            results=api_results,
            total_urls=len(request.urls),
            successful_urls=successful_count,
            failed_urls=len(request.urls) - successful_count,
            total_execution_time=total_time
        )

    except Exception as e:
        logger.error(f"Error in batch fetch: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Check the health of the fetcher service.

    Returns information about:
    - Overall service status
    - FlareSolverr connectivity
    - Cached cookie sessions
    - Any issues or errors

    Returns:
        HealthResponse with detailed health information
    """
    if not fetcher:
        return HealthResponse(
            service="SimpleFetcher",
            status="unhealthy",
            flaresolverr_healthy=False,
            cached_domains=0,
            timestamp=0.0,
            error="Fetcher service not initialized"
        )

    try:
        health = await fetcher.health_check()

        return HealthResponse(
            service=health["service"],
            status=health["status"],
            flaresolverr_healthy=health["flaresolverr_healthy"],
            cached_domains=health["cached_domains"],
            cookie_sessions=health.get("cookie_sessions", {}),
            timestamp=health["timestamp"],
            issues=health.get("issues"),
            error=health.get("error")
        )

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return HealthResponse(
            service="SimpleFetcher",
            status="unhealthy",
            flaresolverr_healthy=False,
            cached_domains=0,
            timestamp=0.0,
            error=str(e)
        )

@app.post("/cleanup", response_model=dict)
async def cleanup_stale_cookies():
    """
    Clean up stale cookie sessions.

    This endpoint removes old, unused cookie sessions to free up memory
    and maintain optimal performance.

    Returns:
        dict: Number of sessions cleaned up
    """
    if not fetcher:
        raise HTTPException(status_code=503, detail="Fetcher service not initialized")

    try:
        cleaned_count = await fetcher.cleanup_stale_cookies()
        logger.info(f"Cleaned up {cleaned_count} stale cookie sessions")

        return {
            "message": "Cleanup completed",
            "sessions_cleaned": cleaned_count
        }

    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")


@app.get("/cookies/info", response_model=dict)
async def get_cookie_info():
    """
    Get information about cached cookie sessions.

    Returns detailed information about all cached cookie sessions,
    including creation time, expiration, and usage statistics.

    Returns:
        dict: Cookie session information
    """
    if not fetcher:
        raise HTTPException(status_code=503, detail="Fetcher service not initialized")

    try:
        cookie_info = await fetcher.get_cookie_info()
        return {
            "cached_domains": len(cookie_info),
            "sessions": cookie_info
        }

    except Exception as e:
        logger.error(f"Error getting cookie info: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get cookie info: {str(e)}")



@app.get("/")
async def root():
    """
    Root endpoint with service information.

    Returns:
        dict: Service information and available endpoints
    """
    return {
        "service": "Simplified Content Fetcher",
        "version": "2.0.0",
        "description": "A simplified service for fetching content from Cloudflare-protected sites using FlareSolverr",
        "endpoints": {
            "health": "/health",
            "fetch_single": "/fetch",
            "fetch_batch": "/fetch/batch",
            "cleanup": "/cleanup",
            "cookie_info": "/cookies/info",
            "docs": "/docs"
        },
        "features": [
            "FlareSolverr integration for Cloudflare bypass",
            "Cookie caching with automatic refresh",
            "Fast HTTP requests with aiohttp",
            "Batch processing with concurrency control",
            "Simple, focused API"
        ]
    }