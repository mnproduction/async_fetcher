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

import sys
import structlog
from typing import Optional, Dict, Any

# Shared processors for all environments
_shared_processors = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.StackInfoRenderer(),
    structlog.dev.set_exc_info,
    structlog.processors.format_exc_info,
    structlog.processors.UnicodeDecoder(),
]

def configure_logging(log_level: str = "INFO", force_json: bool = False):
    """
    Configure structlog for either development (console) or production (JSON).
    """
    is_prod = force_json or (sys.stdout.isatty() is False)
    
    processors = _shared_processors + [
        structlog.processors.JSONRenderer() if is_prod else structlog.dev.ConsoleRenderer(colors=True)
    ]

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    # Set the root logger level
    import logging
    logging.basicConfig(level=log_level.upper(), stream=sys.stdout, format="%(message)s")


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger with the given name."""
    return structlog.get_logger(name)
        
# --- Context Management Functions ---
def log_request_context(request_id: str, **kwargs: Any):
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id, **kwargs)

def clear_request_context():
    structlog.contextvars.clear_contextvars()

def get_current_context() -> Dict[str, Any]:
    return structlog.contextvars.get_contextvars()

# Initial configuration on import
configure_logging() 