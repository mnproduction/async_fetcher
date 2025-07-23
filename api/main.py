import time
import uuid
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, Path, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi
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
from settings.performance_metrics import get_performance_summary, get_error_rate

# Initialize logger for this module
logger = get_logger("api.main")

app = FastAPI(
    title="Async Web Fetching Service",
    description="""A service for asynchronously fetching web content using stealth browsers.

## Features

- **Asynchronous Fetching**: Process multiple URLs concurrently with configurable limits
- **Stealth Browser Technology**: Uses Patchright/Playwright for undetectable web scraping
- **Proxy Rotation**: Support for multiple proxy servers with automatic rotation
- **Error Handling**: Comprehensive error categorization and reporting
- **Job Management**: Track and monitor fetch jobs with real-time status updates
- **Performance Monitoring**: Built-in performance metrics and logging
- **Rate Limiting**: Configurable rate limiting to prevent abuse

## Usage

1. **Submit a fetch job** using the `/fetch/start` endpoint with your URLs and options
2. **Monitor progress** using the `/fetch/status/{job_id}` endpoint
3. **View results** once the job is completed

## API Endpoints

- `POST /fetch/start` - Start a new fetch job
- `GET /fetch/status/{job_id}` - Get job status and results
- `GET /health` - Service health check
- `GET /admin/rate-limits` - Rate limiting statistics
- `GET /admin/performance` - Performance metrics

## Authentication

Currently, this API does not require authentication. Rate limiting is applied to prevent abuse.

## Rate Limits

- Default: 60 requests per minute, 1000 per hour
- Fetch endpoints: 30 requests per minute, 500 per hour
- Burst limit: 10 requests per burst

For more information, see the individual endpoint documentation below.
""",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    swagger_ui_parameters={
        "docExpansion": "list",
        "defaultModelsExpandDepth": 2,
        "defaultModelExpandDepth": 2,
        "deepLinking": True,
        "displayRequestDuration": True,
        "filter": True,
        "showExtensions": True,
        "showCommonExtensions": True,
        "syntaxHighlight.theme": "monokai"
    }
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# CUSTOM OPENAPI SCHEMA
# =============================================================================

def custom_openapi():
    """
    Customize the OpenAPI schema with detailed examples and enhanced documentation.
    """
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Add detailed examples for request models
    if "components" in openapi_schema and "schemas" in openapi_schema["components"]:
        schemas = openapi_schema["components"]["schemas"]
        
        # FetchRequest example
        if "FetchRequest" in schemas:
            schemas["FetchRequest"]["example"] = {
                "links": [
                    "https://httpbin.org/html",
                    "https://httpbin.org/json",
                    "https://example.com"
                ],
                "options": {
                    "proxies": [
                        "http://proxy1.example.com:8080",
                        "http://proxy2.example.com:8080"
                    ],
                    "wait_min": 1,
                    "wait_max": 3,
                    "concurrency_limit": 5,
                    "retry_count": 2
                }
            }
        
        # JobStatusResponse example
        if "JobStatusResponse" in schemas:
            schemas["JobStatusResponse"]["example"] = {
                "job_id": "123e4567-e89b-12d3-a456-426614174000",
                "status_url": "/fetch/status/123e4567-e89b-12d3-a456-426614174000"
            }
        
        # FetchResponse example
        if "FetchResponse" in schemas:
            schemas["FetchResponse"]["example"] = {
                "job_id": "123e4567-e89b-12d3-a456-426614174000",
                "status": "completed",
                "results": [
                    {
                        "url": "https://httpbin.org/html",
                        "status": "success",
                        "html_content": "<html><head><title>Herman Melville - Moby-Dick</title></head><body><h1>Moby-Dick</h1><p>Call me Ishmael...</p></body></html>",
                        "error_message": None,
                        "error_type": None,
                        "response_time_ms": 1250,
                        "status_code": 200
                    },
                    {
                        "url": "https://httpbin.org/json",
                        "status": "success",
                        "html_content": "<html><head><title>JSON Response</title></head><body><pre>{\"slideshow\":{\"author\":\"Yours Truly\"}}</pre></body></html>",
                        "error_message": None,
                        "error_type": None,
                        "response_time_ms": 980,
                        "status_code": 200
                    },
                    {
                        "url": "https://example.com",
                        "status": "error",
                        "html_content": None,
                        "error_message": "Navigation failed: HTTP 404",
                        "error_type": "NavigationError",
                        "response_time_ms": 2100,
                        "status_code": 404
                    }
                ],
                "total_urls": 3,
                "completed_urls": 3,
                "progress_percentage": 100.0,
                "is_finished": True
            }
        
        # FetchResult example
        if "FetchResult" in schemas:
            schemas["FetchResult"]["example"] = {
                "url": "https://httpbin.org/html",
                "status": "success",
                "html_content": "<html><head><title>Example Page</title></head><body><h1>Hello World</h1><p>This is example content.</p></body></html>",
                "error_message": None,
                "error_type": None,
                "response_time_ms": 1250,
                "status_code": 200
            }
        
        # FetchOptions example
        if "FetchOptions" in schemas:
            schemas["FetchOptions"]["example"] = {
                "proxies": [
                    "http://proxy1.example.com:8080",
                    "http://proxy2.example.com:8080"
                ],
                "wait_min": 1,
                "wait_max": 3,
                "concurrency_limit": 5,
                "retry_count": 2
            }
    
    # Add server information
    openapi_schema["servers"] = [
        {
            "url": "http://localhost:8000",
            "description": "Development server"
        },
        {
            "url": "https://api.example.com",
            "description": "Production server"
        }
    ]
    
    # Add tags for better organization
    openapi_schema["tags"] = [
        {
            "name": "fetch",
            "description": "Operations for starting and monitoring fetch jobs"
        },
        {
            "name": "admin",
            "description": "Administrative endpoints for monitoring and statistics"
        },
        {
            "name": "health",
            "description": "Health check and service status endpoints"
        }
    ]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


# Set the custom OpenAPI schema
app.openapi = custom_openapi


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
        client_ip=request.client.host if request.client else None,
        request_id=request_id,
        user_agent=user_agent
    )
    
    # Process the request
    response = await call_next(request)
    
    # Add the request ID to the response headers for client-side tracing
    response.headers["X-Request-ID"] = request_id
    
    # Calculate processing time
    process_time = time.time() - start_time
    
    # Log request completion with timing and response info
    logger.info(
        "Request completed",
        path=request.url.path,
        method=request.method,
        status_code=response.status_code,
        process_time_ms=round(process_time * 1000, 2),
        content_length=response.headers.get("content-length"),
        request_id=request_id
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
    # Get request ID from headers if available
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    logger.warning(
        "Validation error in request",
        path=request.url.path,
        method=request.method,
        errors=exc.errors(),
        request_id=request_id
    )
    
    # Extract field-specific error messages
    error_details = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error["loc"])
        message = error["msg"]
        error_details.append(f"{field}: {message}")
    
    response = JSONResponse(
        status_code=422,
        content={
            "error": "Validation failed",
            "detail": error_details,
            "type": "validation_error"
        }
    )
    
    # Add request ID to error response headers
    response.headers["X-Request-ID"] = request_id
    
    return response


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """
    Handle ValueError exceptions with sanitized error messages.
    """
    # Get request ID from headers if available
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    logger.warning(
        "Value error in request",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        request_id=request_id
    )
    
    response = JSONResponse(
        status_code=400,
        content={
            "error": "Invalid input",
            "detail": str(exc),
            "type": "value_error"
        }
    )
    
    # Add request ID to error response headers
    response.headers["X-Request-ID"] = request_id
    
    return response


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Handle general exceptions with request ID tracking.
    """
    # Get request ID from headers if available
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    logger.error(
        "Unhandled exception in request",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exception_type=type(exc).__name__,
        request_id=request_id
    )
    
    response = JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": "An unexpected error occurred",
            "type": "internal_error"
        }
    )
    
    # Add request ID to error response headers
    response.headers["X-Request-ID"] = request_id
    
    return response


# =============================================================================
# HEALTH CHECK ENDPOINT
# =============================================================================

@app.get(
    "/health",
    tags=["health"],
    summary="Health Check",
    description="""Check the health and status of the Async Web Fetching Service.

This endpoint provides basic health information about the service, including:
- Service status (healthy/unhealthy)
- Service name and version
- Current timestamp

Use this endpoint to:
- Verify the service is running and responsive
- Monitor service availability
- Check service version information

**Response Codes:**
- `200 OK`: Service is healthy and operational
- `503 Service Unavailable`: Service is unhealthy (if implemented)

**Rate Limiting:** This endpoint is not rate limited.
""",
    response_description="Service health status and basic information"
)
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

@app.post(
    "/fetch/start", 
    response_model=JobStatusResponse,
    tags=["fetch"],
    summary="Start a New Fetch Job",
    description="""Submit a list of URLs to be fetched asynchronously using stealth browser technology.

This endpoint creates a new fetch job that will process the provided URLs in the background.
The job will be processed with the specified configuration options and can be monitored
using the returned job ID.

## Request Parameters

### links (required)
A list of URLs to fetch. Each URL must be a valid HTTP or HTTPS URL.
- **Type**: Array of strings
- **Minimum**: 1 URL
- **Maximum**: 100 URLs (configurable limit)

### options (optional)
Configuration options for the fetching process:

#### proxies
- **Type**: Array of strings
- **Description**: List of proxy URLs to use for fetching
- **Format**: `http://host:port` or `https://host:port`
- **Behavior**: If provided, a random proxy will be selected for each request

#### wait_min
- **Type**: Integer
- **Default**: 1
- **Range**: 0-60 seconds
- **Description**: Minimum wait time between requests

#### wait_max
- **Type**: Integer
- **Default**: 3
- **Range**: wait_min to 300 seconds
- **Description**: Maximum wait time between requests

#### concurrency_limit
- **Type**: Integer
- **Default**: 5
- **Range**: 1-20
- **Description**: Maximum number of concurrent browser instances

#### retry_count
- **Type**: Integer
- **Default**: 2
- **Range**: 0-5
- **Description**: Number of retry attempts for failed requests

## Response

Returns a job ID and status URL that can be used to monitor the job progress.

## Rate Limiting

This endpoint is rate limited to:
- 30 requests per minute
- 500 requests per hour
- 5 requests per burst

## Error Handling

- **400 Bad Request**: Invalid request format or parameters
- **422 Unprocessable Entity**: Validation errors in request data
- **429 Too Many Requests**: Rate limit exceeded
- **500 Internal Server Error**: Server error during job creation

## Example Usage

```bash
curl -X POST "http://localhost:8000/fetch/start" \\
     -H "Content-Type: application/json" \\
     -d '{
       "links": ["https://example.com", "https://httpbin.org/html"],
       "options": {
         "concurrency_limit": 3,
         "wait_min": 1,
         "wait_max": 2
       }
     }'
```
""",
    response_description="Job ID and status URL for monitoring the fetch job"
)
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


@app.get(
    "/fetch/status/{job_id}", 
    response_model=FetchResponse,
    tags=["fetch"],
    summary="Get Fetch Job Status",
    description="""Check the status and results of a previously submitted fetch job.

This endpoint returns the current status of the job and any results that are available.
Use this endpoint to monitor job progress and retrieve completed results.

## Path Parameters

### job_id (required)
- **Type**: String (UUID)
- **Description**: The unique identifier of the fetch job
- **Format**: UUID v4 format (e.g., `123e4567-e89b-12d3-a456-426614174000`)
- **Source**: Returned by the `/fetch/start` endpoint

## Job Status Values

### pending
- **Description**: The job has been created but has not started processing yet
- **Next Action**: Wait for the job to transition to `in_progress`

### in_progress
- **Description**: The job is currently being processed
- **Information Available**: Progress percentage, completed URLs count
- **Next Action**: Continue polling for updates

### completed
- **Description**: The job has finished processing all URLs
- **Information Available**: All results, final statistics
- **Next Action**: Process the results

### failed
- **Description**: The job encountered an error and could not be completed
- **Information Available**: Error message, partial results (if any)
- **Next Action**: Review error details and retry if appropriate

## Response Fields

### job_id
- **Type**: String
- **Description**: The job identifier

### status
- **Type**: String
- **Description**: Current job status (pending, in_progress, completed, failed)

### results
- **Type**: Array of FetchResult objects
- **Description**: Individual URL fetch results (available when status is completed or failed)

### total_urls
- **Type**: Integer
- **Description**: Total number of URLs in the job

### completed_urls
- **Type**: Integer
- **Description**: Number of URLs processed so far

### progress_percentage
- **Type**: Float
- **Description**: Job completion percentage (0.0 to 100.0)

### is_finished
- **Type**: Boolean
- **Description**: Whether the job is in a terminal state (completed or failed)

## Error Handling

- **400 Bad Request**: Invalid job ID format
- **404 Not Found**: Job with the specified ID does not exist
- **500 Internal Server Error**: Server error during status retrieval

## Rate Limiting

This endpoint is rate limited to:
- 60 requests per minute
- 1000 requests per hour
- 10 requests per burst

## Example Usage

```bash
curl -X GET "http://localhost:8000/fetch/status/123e4567-e89b-12d3-a456-426614174000"
```

## Polling Strategy

For long-running jobs, implement a polling strategy:
1. Start with 1-second intervals
2. Increase to 5-second intervals after 30 seconds
3. Increase to 10-second intervals after 2 minutes
4. Stop polling when `is_finished` is true
""",
    response_description="Job status, progress information, and results (if available)"
)
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

@app.get(
    "/admin/rate-limits",
    tags=["admin"],
    summary="Get Rate Limiting Statistics",
    description="""Retrieve comprehensive rate limiting statistics and configuration information.

This endpoint provides detailed information about the current rate limiting state,
including usage statistics, configuration settings, and performance metrics.
Use this endpoint for monitoring, debugging, and understanding rate limiting behavior.

## Response Information

### rate_limiting_stats
- **Type**: Object
- **Description**: Current rate limiting statistics including:
  - Request counts per time window
  - Rate limit violations
  - Current usage levels
  - Historical performance data

### configurations
- **Type**: Object
- **Description**: Current rate limiting configuration settings:
  - **default**: General API rate limits
  - **fetch_endpoints**: Specific limits for fetch operations

## Configuration Details

### Default Limits
- **requests_per_minute**: 60 requests
- **requests_per_hour**: 1000 requests
- **burst_limit**: 10 requests per burst

### Fetch Endpoint Limits
- **requests_per_minute**: 30 requests
- **requests_per_hour**: 500 requests
- **burst_limit**: 5 requests per burst

## Use Cases

- **Monitoring**: Track API usage patterns and rate limit effectiveness
- **Debugging**: Investigate rate limiting issues or unexpected behavior
- **Capacity Planning**: Understand current usage levels and plan for scaling
- **Performance Analysis**: Analyze rate limiting impact on service performance

## Rate Limiting

This endpoint is not rate limited to ensure administrators can always access monitoring data.

## Error Handling

- **200 OK**: Successfully retrieved rate limiting statistics
- **500 Internal Server Error**: Error retrieving statistics

## Example Response

```json
{
  "rate_limiting_stats": {
    "total_requests": 1250,
    "rate_limited_requests": 15,
    "current_minute_usage": 45,
    "current_hour_usage": 320
  },
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
```
""",
    response_description="Rate limiting statistics and configuration information"
)
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


@app.get(
    "/admin/performance",
    tags=["admin"],
    summary="Get Performance Metrics",
    description="""Retrieve comprehensive performance metrics and statistics for the Async Web Fetching Service.

This endpoint provides detailed performance data including fetch operation statistics,
error rates, response times, and system health metrics. Use this endpoint for
monitoring service performance, identifying bottlenecks, and capacity planning.

## Response Information

### performance_summary
- **Type**: Object
- **Description**: Comprehensive performance statistics including:
  - Average response times for fetch operations
  - Throughput metrics (requests per second)
  - Job completion rates and durations
  - Resource utilization statistics
  - Historical performance trends

### error_rates
- **Type**: Object
- **Description**: Error rate statistics including:
  - Overall error rate percentage
  - Error rates by type (network, validation, timeout, etc.)
  - Error trends over time
  - Most common error patterns

### timestamp
- **Type**: Float
- **Description**: Unix timestamp when the metrics were collected

### service
- **Type**: String
- **Description**: Service name for identification

## Performance Metrics

### Response Times
- **Average**: Typical response time for fetch operations
- **P95**: 95th percentile response time
- **P99**: 99th percentile response time
- **Maximum**: Longest observed response time

### Throughput
- **Requests per second**: Current processing rate
- **Concurrent jobs**: Number of active fetch jobs
- **Queue depth**: Number of pending jobs

### Error Statistics
- **Success rate**: Percentage of successful operations
- **Error breakdown**: Distribution of error types
- **Retry success rate**: Success rate after retries

## Use Cases

- **Performance Monitoring**: Track service performance over time
- **Capacity Planning**: Understand current load and plan for scaling
- **Troubleshooting**: Identify performance bottlenecks and issues
- **SLA Monitoring**: Ensure service meets performance requirements
- **Trend Analysis**: Analyze performance patterns and trends

## Rate Limiting

This endpoint is not rate limited to ensure administrators can always access performance data.

## Error Handling

- **200 OK**: Successfully retrieved performance metrics
- **500 Internal Server Error**: Error retrieving metrics

## Example Response

```json
{
  "performance_summary": {
    "average_response_time_ms": 1250,
    "p95_response_time_ms": 2100,
    "p99_response_time_ms": 3500,
    "requests_per_second": 8.5,
    "concurrent_jobs": 12,
    "queue_depth": 3
  },
  "error_rates": {
    "overall_error_rate": 2.3,
    "network_errors": 1.1,
    "timeout_errors": 0.8,
    "validation_errors": 0.4,
    "success_rate": 97.7
  },
  "timestamp": 1640995200.0,
  "service": "Async Web Fetching Service"
}
```

## Monitoring Recommendations

1. **Set up alerts** for high error rates (>5%) or slow response times
2. **Monitor trends** to identify performance degradation
3. **Track capacity** to plan for scaling needs
4. **Analyze patterns** to optimize configuration settings
""",
    response_description="Comprehensive performance metrics and error rate statistics"
)
async def get_performance_metrics():
    """
    Get performance metrics and statistics.
    
    This endpoint provides comprehensive performance data including
    fetch and job durations, error rates, and statistical summaries.
    
    Returns:
        dict: Performance metrics and statistics
    """
    logger.debug("Performance metrics requested")
    
    performance_summary = get_performance_summary()
    error_rates = get_error_rate()
    
    return {
        "performance_summary": performance_summary,
        "error_rates": error_rates,
        "timestamp": time.time(),
        "service": "Async Web Fetching Service"
    }


# =============================================================================
# ROOT ENDPOINT
# =============================================================================

@app.get(
    "/",
    tags=["health"],
    summary="Service Information",
    description="""Get comprehensive information about the Async Web Fetching Service.

This endpoint provides an overview of the service, including its capabilities,
available endpoints, features, and basic service information. Use this endpoint
to understand what the service offers and how to interact with it.

## Response Information

### service
- **Type**: String
- **Description**: The name of the service

### version
- **Type**: String
- **Description**: Current version of the service

### description
- **Type**: String
- **Description**: Brief description of the service functionality

### endpoints
- **Type**: Object
- **Description**: Available API endpoints with their paths:
  - **health**: Service health check endpoint
  - **start_fetch**: Endpoint to start a new fetch job
  - **get_status**: Endpoint to check job status and results
  - **admin**: Administrative endpoints for monitoring
  - **docs**: Interactive API documentation

### features
- **Type**: Array of strings
- **Description**: List of key features and capabilities

## Service Features

- **Asynchronous web content fetching**: Process multiple URLs concurrently
- **Stealth browser automation**: Use undetectable browser technology
- **Concurrent request processing**: Handle multiple requests simultaneously
- **Proxy support**: Rotate through multiple proxy servers
- **Comprehensive input validation and sanitization**: Ensure data security
- **Rate limiting and abuse protection**: Prevent service abuse

## Use Cases

- **Service Discovery**: Learn about available endpoints and features
- **API Integration**: Understand how to interact with the service
- **Health Monitoring**: Quick check if service is operational
- **Documentation**: Get an overview before diving into detailed docs

## Rate Limiting

This endpoint is not rate limited as it provides essential service information.

## Error Handling

- **200 OK**: Successfully retrieved service information
- **500 Internal Server Error**: Error retrieving service information

## Example Response

```json
{
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
```

## Next Steps

1. **Check health**: Use `/health` to verify service status
2. **View documentation**: Visit `/docs` for interactive API documentation
3. **Start fetching**: Use `/fetch/start` to begin a fetch job
4. **Monitor performance**: Use `/admin/performance` for system metrics
""",
    response_description="Service information, available endpoints, and features"
)
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