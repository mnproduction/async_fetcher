import structlog

def setup_logger():
    """Configures structlog for JSON output."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ],
        logger_factory=structlog.PrintLoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(min_level=0), # Change min_level as needed (DEBUG=0, INFO=1)
        cache_logger_on_first_use=True,
    )
    return structlog.get_logger()

def get_logger(name: str = None):
    """Get a configured logger instance."""
    if name:
        return structlog.get_logger(name)
    return structlog.get_logger()

# Initialize the logger configuration
logger = setup_logger() 