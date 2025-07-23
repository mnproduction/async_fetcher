"""
Advanced Structured Logging Configuration using structlog

This module provides production-ready structured logging with:
- JSON formatted output for log aggregation
- Request context tracking with request_id and user_agent
- Comprehensive processor chain for detailed log information
- Integration with Python's standard logging library
- Context variable management for request tracing

Usage:
    from settings.logger import get_logger, log_request_context
    
    logger = get_logger("my.module")
    logger.info("Something happened", extra_field="value")
    
    # In request handlers:
    log_request_context("request-123", "Mozilla/5.0...")
"""

import logging
import sys
import time
from typing import Any, Dict, Optional

import structlog


def configure_logging() -> None:
    """
    Configure structlog for JSON formatted logging with comprehensive processors.
    
    This setup provides:
    - JSON output for structured log aggregation
    - ISO timestamp formatting
    - Context variable merging for request tracking
    - Stack trace and exception formatting
    - Integration with Python's standard logging
    """
    # Configure standard logging to work with structlog
    logging.basicConfig(
        format="%(message)s", 
        stream=sys.stdout, 
        level=logging.INFO
    )

    # Configure structlog with comprehensive processor chain
    structlog.configure(
        processors=[
            # Merge context variables (request_id, user_agent, etc.)
            structlog.contextvars.merge_contextvars,
            
            # Filter by log level from stdlib logging
            structlog.stdlib.filter_by_level,
            
            # Add logger name to log entries
            structlog.stdlib.add_logger_name,
            
            # Add log level to log entries
            structlog.stdlib.add_log_level,
            
            # Handle positional arguments like stdlib logging
            structlog.stdlib.PositionalArgumentsFormatter(),
            
            # Add ISO formatted timestamps
            structlog.processors.TimeStamper(fmt="iso"),
            
            # Include stack traces when available
            structlog.processors.StackInfoRenderer(),
            
            # Format exception information
            structlog.processors.format_exc_info,
            
            # Ensure all strings are properly encoded
            structlog.processors.UnicodeDecoder(),
            
            # Output as JSON for structured log parsing
            structlog.processors.JSONRenderer()
        ],
        
        # Use stdlib logger factory for integration
        logger_factory=structlog.stdlib.LoggerFactory(),
        
        # Use stdlib bound logger for consistent interface
        wrapper_class=structlog.stdlib.BoundLogger,
        
        # Cache loggers for performance
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger with the given name.
    
    Args:
        name: Logger name, typically module name (e.g., "api.main")
        
    Returns:
        Configured structlog BoundLogger instance
        
    Example:
        ```python
        logger = get_logger("api.endpoints")
        logger.info("Processing request", user_id=123, action="login")
        ```
    """
    return structlog.get_logger(name)


def log_request_context(request_id: str, user_agent: Optional[str] = None) -> None:
    """
    Add request context to all log entries within this context.
    
    This function sets context variables that will be automatically
    included in all log messages within the current request scope.
    
    Args:
        request_id: Unique identifier for the request (typically UUID)
        user_agent: Client user agent string from request headers
        
    Example:
        ```python
        # At the start of request processing:
        log_request_context("req-abc123", "Mozilla/5.0...")
        
        # All subsequent logs in this context will include:
        # {"request_id": "req-abc123", "user_agent": "Mozilla/5.0...", ...}
        ```
        
    Note:
        Context variables persist until explicitly cleared or overwritten.
        They are automatically included in all log entries made with
        loggers obtained from get_logger().
    """
    # Clear any existing context variables to prevent pollution
    structlog.contextvars.clear_contextvars()
    
    # Bind new context variables for this request
    context_vars = {"request_id": request_id}
    if user_agent:
        context_vars["user_agent"] = user_agent
        
    structlog.contextvars.bind_contextvars(**context_vars)


def clear_request_context() -> None:
    """
    Clear all request context variables.
    
    Useful for cleanup or when context variables should not
    persist beyond the current request scope.
    """
    structlog.contextvars.clear_contextvars()


def get_current_context() -> Dict[str, Any]:
    """
    Get the current context variables as a dictionary.
    
    Returns:
        Dictionary of current context variables
        
    Useful for debugging or inspecting current request context.
    """
    # Get a temporary logger to access current context
    temp_logger = structlog.get_logger()
    return getattr(temp_logger, '_context', {})


# Initialize logging configuration when module is imported
configure_logging()

# Export main interface
__all__ = [
    'get_logger',
    'log_request_context', 
    'clear_request_context',
    'get_current_context',
    'configure_logging'
] 