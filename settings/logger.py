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

# Import from the new centralized logging configuration
from .logging_config import (
    configure_logging,
    get_logger,
    log_request_context,
    clear_request_context,
    get_current_context
)


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