# Structured Logging Documentation

## Overview

The Async HTML Fetcher Service uses [structlog](https://www.structlog.org/) for production-ready structured logging. All logs are output in JSON format for easy parsing by log aggregation systems like ELK Stack, Splunk, or cloud logging services.

## Features

- **JSON-formatted output** for machine parsing
- **Request context tracking** with unique request IDs
- **Automatic HTTP request logging** with timing metrics
- **Context variable propagation** across async operations
- **Integration with Python's standard logging**
- **Production-ready configuration**

## Usage

### Basic Logging

```python
from settings.logger import get_logger

# Get a logger for your module
logger = get_logger("my.module")

# Log with structured data
logger.info("User action completed", 
           user_id=123, 
           action="login", 
           success=True)

logger.error("Database connection failed",
            error_code="DB_CONN_TIMEOUT",
            retry_count=3,
            database="primary")
```

### Request Context Tracking

```python
from settings.logger import get_logger, log_request_context

logger = get_logger("api.endpoint")

# In request handlers (done automatically by middleware)
log_request_context("req-abc123", "Mozilla/5.0...")

# All subsequent logs will include request context
logger.info("Processing user request", user_id=456)
# Output: {"user_id": 456, "request_id": "req-abc123", "user_agent": "Mozilla/5.0...", ...}
```

### Context Management

```python
from settings.logger import clear_request_context, get_current_context

# Clear context when needed
clear_request_context()

# Inspect current context for debugging
current_context = get_current_context()
print(f"Current context: {current_context}")
```

## Log Structure

All logs follow a consistent JSON structure:

### Standard Fields

Every log entry contains these fields:

```json
{
  "event": "Human-readable log message",
  "logger": "module.name",
  "level": "info|debug|warning|error|critical",
  "timestamp": "2025-07-23T11:54:45.369416Z"
}
```

### Request Context Fields

When request context is active, these fields are automatically added:

```json
{
  "request_id": "d0452ff5-c20a-4cea-8039-55c6fb4e2293",
  "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}
```

### HTTP Request Fields

The middleware automatically adds these fields for HTTP requests:

```json
{
  "path": "/api/fetch/start",
  "method": "POST",
  "status_code": 200,
  "process_time_ms": 1.23,
  "content_length": "256",
  "query_params": "limit=10&offset=0",
  "client_ip": "192.168.1.100"
}
```

### Custom Fields

Add your own structured data:

```json
{
  "user_id": 123,
  "action": "login",
  "success": true,
  "metadata": {
    "source": "web",
    "feature_flag": "new_ui"
  }
}
```

## HTTP Request Logging

The FastAPI middleware automatically logs all HTTP requests with the following lifecycle:

1. **Request Started**: Logged when request is received
2. **Endpoint Logs**: Business logic logs with request context
3. **Request Completed**: Logged when response is sent

### Example Request Log Flow

```json
// 1. Request started
{
  "event": "Request started",
  "path": "/api/fetch/start",
  "method": "POST",
  "request_id": "req-123",
  "user_agent": "curl/7.68.0",
  "timestamp": "2025-07-23T10:00:00.000Z"
}

// 2. Business logic logs (your code)
{
  "event": "Starting fetch job",
  "job_id": "job-456",
  "url_count": 5,
  "request_id": "req-123",
  "timestamp": "2025-07-23T10:00:00.100Z"
}

// 3. Request completed
{
  "event": "Request completed",
  "path": "/api/fetch/start",
  "method": "POST",
  "status_code": 202,
  "process_time_ms": 150.5,
  "request_id": "req-123",
  "timestamp": "2025-07-23T10:00:00.150Z"
}
```

## Configuration

### Environment Variables

No environment variables required - all configuration is done programmatically.

### Log Levels

Set log level via Python's standard logging:

```python
import logging
logging.getLogger().setLevel(logging.DEBUG)  # Show debug logs
logging.getLogger().setLevel(logging.WARNING)  # Only warnings and errors
```

### Production Configuration

The logger is pre-configured for production with:

- JSON output for log aggregation
- ISO timestamp formatting
- Context variable merging
- Exception formatting
- Stack trace inclusion
- Unicode handling

## Integration with Log Aggregation

### ELK Stack (Elasticsearch, Logstash, Kibana)

The JSON format works directly with ELK:

```yaml
# logstash.conf
input {
  file {
    path => "/var/log/async-fetcher/*.log"
    start_position => "beginning"
    codec => "json"
  }
}

filter {
  # Logs are already in JSON format, minimal processing needed
  if ![timestamp] {
    drop { }
  }
}

output {
  elasticsearch {
    hosts => ["elasticsearch:9200"]
    index => "async-fetcher-%{+YYYY.MM.dd}"
  }
}
```

### Kubernetes/Docker Logging

Logs go to stdout and are automatically collected:

```yaml
# docker-compose.yml
version: '3.8'
services:
  app:
    build: .
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
```

## Troubleshooting

### Common Issues

#### 1. Context Not Propagating

**Problem**: Request context (request_id) not appearing in logs

**Solution**: Ensure `log_request_context()` is called before other log statements:

```python
# ❌ Wrong order
logger.info("Processing request")  # No context
log_request_context("req-123")

# ✅ Correct order  
log_request_context("req-123")
logger.info("Processing request")  # Has context
```

#### 2. Malformed JSON Logs

**Problem**: Logs are not valid JSON

**Solutions**:
- Check for unescaped quotes in log messages
- Avoid logging complex objects directly - serialize first
- Use structured fields instead of string formatting

```python
# ❌ Avoid
logger.info(f"User {user_dict} performed action")

# ✅ Better
logger.info("User performed action", user=user_dict, action="login")
```

#### 3. Missing Request IDs

**Problem**: HTTP requests not getting unique request IDs

**Solution**: Verify middleware is properly registered in FastAPI:

```python
# Should be in main.py
@app.middleware("http")
async def log_requests(request: Request, call_next):
    # ... middleware code ...
```

#### 4. Performance Issues

**Problem**: Logging impacting application performance

**Solutions**:
- Use appropriate log levels (avoid DEBUG in production)
- Structure data efficiently
- Consider async logging for high-throughput scenarios

### Debugging Tips

#### View Current Context

```python
from settings.logger import get_current_context
print(f"Current context: {get_current_context()}")
```

#### Test Logger Configuration

```python
from settings.logger import get_logger

logger = get_logger("test")
logger.debug("Debug message")
logger.info("Info message", key="value")
logger.warning("Warning message")
logger.error("Error message", error_code=500)
```

#### Validate JSON Output

```bash
# Pipe logs through jq to validate JSON
python -m api.main 2>&1 | head -10 | jq .
```

### Log Analysis Queries

#### Find Slow Requests (> 1000ms)

```bash
# Using jq
cat app.log | jq 'select(.process_time_ms > 1000)'

# Using grep + jq
grep "Request completed" app.log | jq 'select(.process_time_ms > 1000)'
```

#### Trace Specific Request

```bash
# Find all logs for a specific request_id
cat app.log | jq 'select(.request_id == "d0452ff5-c20a-4cea-8039-55c6fb4e2293")'
```

#### Error Rate Analysis

```bash
# Count errors by hour
cat app.log | jq -r 'select(.level == "error") | .timestamp[0:13]' | sort | uniq -c
```

## Best Practices

### 1. Use Meaningful Event Messages

```python
# ❌ Vague
logger.info("Processing")

# ✅ Descriptive
logger.info("Processing fetch job", job_id="job-123", url_count=5)
```

### 2. Structure Data Consistently

```python
# ✅ Consistent field names across modules
logger.info("User action", user_id=123, action="login")
logger.info("User error", user_id=123, error="invalid_password")
```

### 3. Include Context for Debugging

```python
# ✅ Rich context for troubleshooting
logger.error("Database query failed", 
            table="users", 
            query_type="SELECT",
            timeout_seconds=30,
            retry_count=3)
```

### 4. Use Appropriate Log Levels

- **DEBUG**: Detailed diagnostic information
- **INFO**: General operational messages
- **WARNING**: Something unexpected but not an error
- **ERROR**: Error occurred but application continues
- **CRITICAL**: Serious error, application may abort

### 5. Avoid Logging Sensitive Data

```python
# ❌ Don't log passwords, tokens, etc.
logger.info("User login", password=user_password)

# ✅ Log safely
logger.info("User login", user_id=user.id, login_method="password")
```

## Performance Considerations

- JSON serialization has minimal overhead
- Context variables are cached for performance
- Logger instances are cached automatically
- Structured logging is faster than string formatting
- Use log levels to control verbosity in production

## Support

For issues with structured logging:

1. Check the troubleshooting section above
2. Validate JSON output with `jq`
3. Verify middleware registration
4. Test with minimal examples
5. Check structlog documentation: https://www.structlog.org/

---

**Last Updated**: 2025-07-23  
**Version**: 1.0.0 