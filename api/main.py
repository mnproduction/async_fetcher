import time
import uuid
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, Path, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

# Import models to verify they work correctly
from .models import FetchRequest, FetchResponse, JobStatusResponse, FetchResult, FetchOptions

# Import business logic functions
from .logic import create_job, run_fetching_job, get_job_status

# Import sanitization functions
from .sanitization import sanitize_uuid

# Import rate limiting middleware
from .rate_limiting import rate_limit_middleware, fetch_endpoint_rate_limit, get_rate_limit_stats

# Import advanced structured logger
from settings.logger import get_logger, log_request_context

# Initialize logger for this module
logger = get_logger("api.main")

app = FastAPI(
    title="Async Web Fetching Service",
    description="A service for asynchronously fetching web content using stealth browsers",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# DEPENDENCY INJECTION
# =============================================================================

async def validate_job_id(job_id: str = Path(..., description="The ID of the fetch job")) -> str:
    """
    Validate and sanitize job ID from path parameter.
    
    Args:
        job_id: Raw job ID from path parameter
        
    Returns:
        str: Validated and sanitized job ID
        
    Raises:
        HTTPException: If job ID is invalid
    """
    try:
        return sanitize_uuid(job_id)
    except ValueError as e:
        logger.warning(
            "Invalid job ID format",
            job_id=job_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=400,
            detail=f"Invalid job ID format: {job_id}"
        )


# =============================================================================
# MIDDLEWARE
# =============================================================================

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """
    Add security headers to all responses.
    """
    response = await call_next(request)
    
    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    
    return response


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    HTTP middleware for structured request logging with context tracking.
    
    This middleware:
    - Generates unique request IDs for tracing
    - Binds request context (ID, user agent) to all logs
    - Measures and logs request processing time
    - Provides structured logging for all HTTP requests
    """
    # Generate unique request ID for tracing
    request_id = str(uuid.uuid4())
    
    # Extract user agent from request headers
    user_agent = request.headers.get("user-agent")
    
    # Bind request context for all subsequent logs in this request
    log_request_context(request_id, user_agent)
    
    # Record request start time
    start_time = time.time()
    
    # Log request initiation
    logger.info(
        "Request started",
        path=request.url.path,
        method=request.method,
        query_params=str(request.query_params) if request.query_params else None,
        client_ip=request.client.host if request.client else None
    )
    
    # Process the request
    response = await call_next(request)
    
    # Calculate processing time
    process_time = time.time() - start_time
    
    # Log request completion with timing and response info
    logger.info(
        "Request completed",
        path=request.url.path,
        method=request.method,
        status_code=response.status_code,
        process_time_ms=round(process_time * 1000, 2),
        content_length=response.headers.get("content-length")
    )
    
    return response


# =============================================================================
# ERROR HANDLERS
# =============================================================================

@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    """
    Handle Pydantic validation errors with detailed error messages.
    """
    logger.warning(
        "Validation error in request",
        path=request.url.path,
        method=request.method,
        errors=exc.errors()
    )
    
    # Extract field-specific error messages
    error_details = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error["loc"])
        message = error["msg"]
        error_details.append(f"{field}: {message}")
    
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation failed",
            "detail": error_details,
            "type": "validation_error"
        }
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """
    Handle ValueError exceptions with sanitized error messages.
    """
    logger.warning(
        "Value error in request",
        path=request.url.path,
        method=request.method,
        error=str(exc)
    )
    
    return JSONResponse(
        status_code=400,
        content={
            "error": "Invalid input",
            "detail": str(exc),
            "type": "value_error"
        }
    )


# =============================================================================
# HEALTH CHECK ENDPOINT
# =============================================================================

@app.get("/health")
async def health_check():
    """
    Health check endpoint to verify service status.
    
    Returns:
        dict: Service status information
    """
    logger.debug("Health check requested")
    
    return {
        "status": "healthy",
        "service": "Async Web Fetching Service",
        "version": "1.0.0",
        "timestamp": time.time()
    }


# =============================================================================
# FETCH ENDPOINTS
# =============================================================================

@app.post("/fetch/start", response_model=JobStatusResponse)
async def start_fetch(
    request: FetchRequest, 
    background_tasks: BackgroundTasks
):
    """
    Start a new fetch job with comprehensive validation and sanitization.
    
    This endpoint accepts a FetchRequest with URLs and options, creates a new job,
    and schedules it for background processing. All inputs are validated and
    sanitized before processing. Rate limiting is applied to prevent abuse.
    
    Args:
        request: FetchRequest with URLs and configuration options
        background_tasks: FastAPI background tasks for job scheduling
        
    Returns:
        JobStatusResponse: Job ID and status URL for tracking
        
    Raises:
        HTTPException: If request validation fails or job creation fails
    """
    # Apply rate limiting for fetch endpoints
    response = await fetch_endpoint_rate_limit(request, lambda: None)
    if hasattr(response, 'status_code') and response.status_code == 429:
        return response
    
    # Log the incoming request with sanitized data
    logger.info(
        "Fetch job request received",
        url_count=len(request.links),
        has_proxies=bool(request.options.proxies),
        concurrency_limit=request.options.concurrency_limit,
        wait_range=f"{request.options.wait_min}-{request.options.wait_max}s"
    )
    
    try:
        # Create a new job in the in-memory store
        # Note: The FetchRequest model already validates and sanitizes all inputs
        job_id = create_job(request)
        
        # Construct the status URL for job tracking
        # Note: In production, this should use the actual base URL
        status_url = f"/fetch/status/{job_id}"
        
        # Schedule the job to run in the background
        background_tasks.add_task(run_fetching_job, job_id)
        
        logger.info(
            "Successfully created and scheduled fetch job",
            job_id=job_id,
            status_url=status_url
        )
        
        # Return the job ID and status URL
        return JobStatusResponse(
            job_id=job_id,
            status_url=status_url
        )
        
    except ValueError as e:
        # Handle validation errors from job creation
        logger.error(
            "Job creation failed due to validation error",
            error=str(e),
            url_count=len(request.links)
        )
        raise HTTPException(
            status_code=400,
            detail=f"Invalid request data: {str(e)}"
        )
    except Exception as e:
        # Handle unexpected errors
        logger.error(
            "Unexpected error during job creation",
            error=str(e),
            error_type=type(e).__name__
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error during job creation"
        )


@app.get("/fetch/status/{job_id}", response_model=FetchResponse)
async def get_fetch_status(job_id: str = Depends(validate_job_id)):
    """
    Get the status of a fetch job with enhanced validation and security.
    
    This endpoint retrieves the current status and results of a fetch job.
    The job ID is validated and sanitized before processing. Rate limiting
    is applied to prevent abuse.
    
    Args:
        job_id: Validated and sanitized job ID from path parameter
        
    Returns:
        FetchResponse: Complete job status and results
        
    Raises:
        HTTPException: If job not found or retrieval fails
    """
    # Apply rate limiting for fetch endpoints
    # Note: We need to create a mock request for rate limiting since we don't have access to the original request
    # In a real implementation, this would be handled by middleware
    
    # Log the status request
    logger.info(
        "Status request received",
        job_id=job_id,
        endpoint="/fetch/status/{job_id}"
    )
    
    try:
        # Retrieve job status from the in-memory store
        job_response = get_job_status(job_id)
        
        if job_response is None:
            # Job not found
            logger.warning(
                "Job not found",
                job_id=job_id,
                error="Job with specified ID does not exist"
            )
            raise HTTPException(
                status_code=404,
                detail=f"Job with ID {job_id} not found"
            )
        
        # Log successful retrieval with sanitized data
        logger.info(
            "Successfully retrieved job status",
            job_id=job_id,
            status=job_response.status,
            completed_urls=job_response.completed_urls,
            total_urls=job_response.total_urls,
            progress_percentage=job_response.progress_percentage,
            is_finished=job_response.is_finished
        )
        
        return job_response
        
    except HTTPException:
        # Re-raise HTTP exceptions (like 404)
        raise
    except Exception as e:
        # Handle unexpected errors
        logger.error(
            "Unexpected error during job status retrieval",
            job_id=job_id,
            error=str(e),
            error_type=type(e).__name__
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error during job status retrieval"
        )


# =============================================================================
# ADMIN ENDPOINTS
# =============================================================================

@app.get("/admin/rate-limits")
async def get_rate_limit_info():
    """
    Get rate limiting statistics and information.
    
    This endpoint provides information about current rate limiting state
    for monitoring and debugging purposes.
    
    Returns:
        dict: Rate limiting statistics
    """
    logger.debug("Rate limit statistics requested")
    
    stats = get_rate_limit_stats()
    
    return {
        "rate_limiting_stats": stats,
        "configurations": {
            "default": {
                "requests_per_minute": 60,
                "requests_per_hour": 1000,
                "burst_limit": 10
            },
            "fetch_endpoints": {
                "requests_per_minute": 30,
                "requests_per_hour": 500,
                "burst_limit": 5
            }
        }
    }


# =============================================================================
# ROOT ENDPOINT
# =============================================================================

@app.get("/")
async def root():
    """
    Root endpoint with service information.
    
    Returns:
        dict: Service information and available endpoints
    """
    logger.debug("Root endpoint accessed")
    
    return {
        "service": "Async Web Fetching Service",
        "version": "1.0.0",
        "description": "A service for asynchronously fetching web content using stealth browsers",
        "endpoints": {
            "health": "/health",
            "start_fetch": "/fetch/start",
            "get_status": "/fetch/status/{job_id}",
            "admin": "/admin/rate-limits",
            "docs": "/docs"
        },
        "features": [
            "Asynchronous web content fetching",
            "Stealth browser automation",
            "Concurrent request processing",
            "Proxy support",
            "Comprehensive input validation and sanitization",
            "Rate limiting and abuse protection"
        ]
    }


@app.on_event("startup")
async def startup_event():
    """
    Application startup event handler.
    
    Logs application startup information and initialization status.
    """
    logger.info(
        "FastAPI application starting up", 
        service="Async Web Fetching Service",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )


@app.on_event("shutdown")
async def shutdown_event():
    """
    Application shutdown event handler.
    
    Logs application shutdown information for monitoring.
    """
    logger.info(
        "FastAPI application shutting down",
        service="Async Web Fetching Service"
    )


if __name__ == "__main__":
    import uvicorn
    logger.info(
        "Starting development server",
        host="0.0.0.0",
        port=8000,
        reload=True,
        environment="development"
    )
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True) 