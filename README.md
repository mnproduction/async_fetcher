# Async Web Fetching Service

A high-performance FastAPI service for asynchronously fetching web content using stealth browser technology. Built with Python 3.13, FastAPI, and Patchright for undetectable web scraping.

## Features

- **Asynchronous Fetching**: Process multiple URLs concurrently with configurable limits
- **Stealth Browser Technology**: Uses Patchright/Playwright for undetectable web scraping
- **Proxy Rotation**: Support for multiple proxy servers with automatic rotation
- **Error Handling**: Comprehensive error categorization and reporting
- **Job Management**: Track and monitor fetch jobs with real-time status updates
- **Performance Monitoring**: Built-in performance metrics and logging
- **Rate Limiting**: Configurable rate limiting to prevent abuse
- **Docker Support**: Easy deployment with Docker and Docker Compose

## Quick Start

### Using Docker Compose (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd async_fetcher

# Build and start the service
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the service
docker-compose down
```

The API will be available at http://localhost:8000.

### Using Docker Directly

```bash
# Build the Docker image
docker build -t async-web-fetcher .

# Run the container
docker run -p 8000:8000 async-web-fetcher
```

### Local Development

```bash
# Install UV (Python package manager)
pip install uv

# Clone the repository
git clone <repository-url>
cd async_fetcher

# Install dependencies
uv sync

# Run the development server
uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

## API Usage

### 1. Start a Fetch Job

```bash
curl -X POST "http://localhost:8000/fetch/start" \
     -H "Content-Type: application/json" \
     -d '{
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
     }'
```

Response:
```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status_url": "/fetch/status/123e4567-e89b-12d3-a456-426614174000"
}
```

### 2. Check Job Status

```bash
curl -X GET "http://localhost:8000/fetch/status/123e4567-e89b-12d3-a456-426614174000"
```

Response:
```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "completed",
  "results": [
    {
      "url": "https://httpbin.org/html",
      "status": "success",
      "html_content": "<html><head><title>Herman Melville - Moby-Dick</title></head><body><h1>Moby-Dick</h1><p>Call me Ishmael...</p></body></html>",
      "error_message": null,
      "error_type": null,
      "response_time_ms": 1250,
      "status_code": 200
    }
  ],
  "total_urls": 3,
  "completed_urls": 3,
  "progress_percentage": 100.0,
  "is_finished": true
}
```

### 3. Health Check

```bash
curl -X GET "http://localhost:8000/health"
```

Response:
```json
{
  "status": "healthy",
  "service": "Async Web Fetching Service",
  "version": "1.0.0",
  "timestamp": 1640995200.0
}
```

## API Documentation

- **Interactive Documentation**: http://localhost:8000/docs (Swagger UI)
- **ReDoc Documentation**: http://localhost:8000/redoc
- **OpenAPI Schema**: http://localhost:8000/openapi.json

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
# Logging
LOG_LEVEL=INFO

# Rate Limiting
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_REQUESTS_PER_HOUR=1000
RATE_LIMIT_BURST_LIMIT=10

# Fetch Endpoint Rate Limiting
FETCH_RATE_LIMIT_REQUESTS_PER_MINUTE=30
FETCH_RATE_LIMIT_REQUESTS_PER_HOUR=500
FETCH_RATE_LIMIT_BURST_LIMIT=5
```

### Docker Environment Variables

For Docker deployment, you can set environment variables in the `docker-compose.yml`:

```yaml
environment:
  - PYTHONPATH=/app
  - LOG_LEVEL=INFO
  - RATE_LIMIT_REQUESTS_PER_MINUTE=60
```

## Rate Limiting

The API implements configurable rate limiting:

- **Default endpoints**: 60 requests/minute, 1000 requests/hour
- **Fetch endpoints**: 30 requests/minute, 500 requests/hour
- **Burst protection**: Configurable burst limits

## Error Handling

The service categorizes errors into different types:

- **NetworkError**: Connection or network-related issues
- **TimeoutError**: Request timeout issues
- **NavigationError**: Browser navigation failures
- **CaptchaError**: CAPTCHA detection
- **ProxyError**: Proxy-related issues

## Monitoring

### Performance Metrics

```bash
curl -X GET "http://localhost:8000/admin/performance"
```

### Rate Limiting Statistics

```bash
curl -X GET "http://localhost:8000/admin/rate-limits"
```

## Development

### Project Structure

```
async_fetcher/
├── api/                    # FastAPI application
│   ├── main.py            # Main application entry point
│   ├── models.py          # Pydantic data models
│   ├── logic.py           # Business logic
│   ├── sanitization.py    # Input sanitization
│   └── rate_limiting.py   # Rate limiting middleware
├── toolkit/               # Browser automation toolkit
│   ├── browser.py         # StealthBrowserToolkit
│   └── browser_pool.py    # Browser pool management
├── settings/              # Application settings
│   ├── logger.py          # Structured logging
│   └── performance_metrics.py # Performance monitoring
├── tests/                 # Test suite
│   ├── unit/             # Unit tests
│   ├── integration/      # Integration tests
│   └── e2e/              # End-to-end tests
├── Dockerfile            # Docker configuration
├── docker-compose.yml    # Docker Compose configuration
├── pyproject.toml        # Project dependencies
└── README.md             # This file
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run unit tests only
uv run pytest tests/unit/

# Run integration tests
uv run pytest tests/integration/

# Run with coverage
uv run pytest --cov=api --cov=toolkit --cov=settings
```

### Code Quality

```bash
# Run linting
uv run ruff check .

# Run formatting
uv run ruff format .

# Run type checking
uv run mypy api/ toolkit/ settings/
```

## Docker Deployment

### Production Deployment

For production deployment with full browser functionality, you'll need to include browser dependencies. The current Dockerfile is optimized for development and testing.

**For Production with Browser Support:**

1. **Option 1: Use a browser-enabled base image**
```dockerfile
# Use a base image with browser dependencies
FROM mcr.microsoft.com/playwright/python:v1.40.0-focal

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen
RUN uv run pip install patchright && uv run patchright install
COPY . .
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

2. **Option 2: Add browser dependencies to current Dockerfile**
```dockerfile
# Add these packages to the apt-get install command:
libglib2.0-0 libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 \
libexpat1 libatspi2.0-0 libx11-6 libxcomposite1 libxdamage1 libxext6 \
libxfixes3 libxrandr2 libgbm1 libxcb1 libxkbcommon0 libasound2 \
fonts-liberation libdrm2 libgtk-3-0 libxss1 xdg-utils
```

**Current Development Setup:**
- ✅ Perfect for API development and testing
- ✅ Graceful handling of missing browser dependencies
- ✅ Fast build times and small image size
- ✅ All API endpoints work correctly
- No development dependencies

For a minimal image without browser dependencies (development/testing):
```dockerfile
# Use multi-stage build for smaller image
FROM python:3.13-slim as builder

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen

FROM python:3.13-slim
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY . .

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose for Production

```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - LOG_LEVEL=INFO
      - RATE_LIMIT_REQUESTS_PER_MINUTE=60
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Optional: Add Redis for job persistence
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    restart: unless-stopped

volumes:
  redis-data:
```

## Troubleshooting

### Common Issues

1. **Browser initialization fails**: Ensure Patchright is properly installed
2. **Rate limiting errors**: Check rate limit configuration
3. **Proxy connection issues**: Verify proxy URLs and credentials
4. **Memory issues**: Adjust concurrency limits for your system

### Logs

The service uses structured JSON logging. Check logs for detailed error information:

```bash
# Docker logs
docker-compose logs -f api

# Local logs
tail -f logs/app.log
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## License

[Add your license information here]

## Support

For issues and questions:
- Create an issue in the repository
- Check the API documentation at `/docs`
- Review the troubleshooting section above
