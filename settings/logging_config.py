"""
Centralized Logging Configuration

This module provides a centralized logging configuration system that can be
easily customized and extended. It supports both development and production
environments with different log formats and levels.

Features:
- Environment-based configuration (dev/prod)
- Configurable log levels and formats
- File and console handlers
- Request ID tracking
- Performance metrics logging
- Structured JSON logging for production
- Human-readable logging for development
"""

import json
import logging
import logging.config
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import structlog


class LoggingConfig:
    """Centralized logging configuration manager."""
    
    def __init__(self):
        self.config = {}
        self.environment = os.getenv("ENVIRONMENT", "development")
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.log_format = os.getenv("LOG_FORMAT", "json" if self.environment == "production" else "text")
        
    def get_development_config(self) -> Dict[str, Any]:
        """Get logging configuration for development environment."""
        return {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "detailed": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S"
                },
                "simple": {
                    "format": "%(levelname)s - %(message)s"
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": self.log_level,
                    "formatter": "detailed",
                    "stream": "ext://sys.stdout"
                },
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "level": self.log_level,
                    "formatter": "detailed",
                    "filename": "logs/app.log",
                    "maxBytes": 10485760,  # 10MB
                    "backupCount": 5
                }
            },
            "loggers": {
                "": {  # Root logger
                    "level": self.log_level,
                    "handlers": ["console", "file"],
                    "propagate": False
                },
                "api": {
                    "level": self.log_level,
                    "handlers": ["console", "file"],
                    "propagate": False
                },
                "toolkit": {
                    "level": self.log_level,
                    "handlers": ["console", "file"],
                    "propagate": False
                },
                "settings": {
                    "level": self.log_level,
                    "handlers": ["console", "file"],
                    "propagate": False
                }
            }
        }
    
    def get_production_config(self) -> Dict[str, Any]:
        """Get logging configuration for production environment."""
        return {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {
                    "class": "structlog.stdlib.ProcessorFormatter",
                    "processor": structlog.processors.JSONRenderer()
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": self.log_level,
                    "formatter": "json",
                    "stream": "ext://sys.stdout"
                },
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "level": self.log_level,
                    "formatter": "json",
                    "filename": "logs/app.log",
                    "maxBytes": 10485760,  # 10MB
                    "backupCount": 10
                }
            },
            "loggers": {
                "": {  # Root logger
                    "level": self.log_level,
                    "handlers": ["console", "file"],
                    "propagate": False
                },
                "api": {
                    "level": self.log_level,
                    "handlers": ["console", "file"],
                    "propagate": False
                },
                "toolkit": {
                    "level": self.log_level,
                    "handlers": ["console", "file"],
                    "propagate": False
                },
                "settings": {
                    "level": self.log_level,
                    "handlers": ["console", "file"],
                    "propagate": False
                }
            }
        }
    
    def configure_structlog(self) -> None:
        """Configure structlog for structured logging."""
        processors = [
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
        ]
        
        # Add appropriate renderer based on environment
        if self.environment == "production" or self.log_format == "json":
            processors.append(structlog.processors.JSONRenderer())
        else:
            processors.append(structlog.dev.ConsoleRenderer())
        
        structlog.configure(
            processors=processors,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
    
    def setup_logging(self) -> None:
        """Set up the complete logging configuration."""
        # Create logs directory if it doesn't exist
        Path("logs").mkdir(exist_ok=True)
        
        # Configure structlog first
        self.configure_structlog()
        
        # Get appropriate config based on environment
        if self.environment == "production":
            self.config = self.get_production_config()
        else:
            self.config = self.get_development_config()
        
        # Apply the configuration
        logging.config.dictConfig(self.config)
        
        # Log the configuration
        logger = structlog.get_logger(__name__)
        logger.info(
            "Logging configured",
            environment=self.environment,
            log_level=self.log_level,
            log_format=self.log_format
        )
    
    def get_logger(self, name: str) -> structlog.stdlib.BoundLogger:
        """Get a structured logger with the given name."""
        return structlog.get_logger(name)
    
    def log_request_context(self, request_id: str, user_agent: Optional[str] = None) -> None:
        """Add request context to all log entries within this context."""
        # Clear any existing context variables to prevent pollution
        structlog.contextvars.clear_contextvars()
        
        # Bind new context variables for this request
        context_vars = {"request_id": request_id}
        if user_agent:
            context_vars["user_agent"] = user_agent
            
        structlog.contextvars.bind_contextvars(**context_vars)
    
    def clear_request_context(self) -> None:
        """Clear all request context variables."""
        structlog.contextvars.clear_contextvars()
    
    def get_current_context(self) -> Dict[str, Any]:
        """Get the current context variables as a dictionary."""
        # Get a temporary logger to access current context
        temp_logger = structlog.get_logger()
        return getattr(temp_logger, '_context', {})


# Create global instance
logging_config = LoggingConfig()


def configure_logging() -> None:
    """Configure logging for the application."""
    logging_config.setup_logging()


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger with the given name."""
    return logging_config.get_logger(name)


def log_request_context(request_id: str, user_agent: Optional[str] = None) -> None:
    """Add request context to all log entries within this context."""
    logging_config.log_request_context(request_id, user_agent)


def clear_request_context() -> None:
    """Clear all request context variables."""
    logging_config.clear_request_context()


def get_current_context() -> Dict[str, Any]:
    """Get the current context variables as a dictionary."""
    return logging_config.get_current_context()


# Export main interface
__all__ = [
    'configure_logging',
    'get_logger',
    'log_request_context', 
    'clear_request_context',
    'get_current_context',
    'LoggingConfig'
] 