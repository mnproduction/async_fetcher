import time
import uuid
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

# Import models to verify they work correctly
from .models import FetchRequest, FetchResponse, JobStatusResponse, FetchResult, FetchOptions

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


@app.get("/")
async def root():
    """
    Root endpoint returning API information.
    
    Returns basic API information and confirms the service is running.
    """
    logger.info("Root endpoint accessed", endpoint="/", action="get_api_info")
    return {"message": "Async Web Fetching Service API"}


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