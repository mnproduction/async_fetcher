# Simplified Cloudflare Fetcher Service

A lightweight FastAPI service for fetching content from Cloudflare-protected sites using FlareSolverr cookie extraction + aiohttp. Built with Python 3.13, FastAPI, and optimized for periodic content monitoring.

## Features

- **FlareSolverr Integration**: Uses FlareSolverr for Cloudflare challenge solving
- **Fast HTTP Requests**: aiohttp for high-performance HTTP requests with cached cookies
- **Cookie Management**: Automatic cookie caching and refresh for optimal performance
- **Asynchronous Processing**: Concurrent URL fetching with configurable limits
- **Simple API**: Clean, focused endpoints for single and batch fetching
- **Health Monitoring**: Built-in health checks and service monitoring
- **Docker Support**: Lightweight Docker deployment without browser dependencies

## Quick Start

### Using Docker Compose (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd async_fetcher

# Build and start the services (includes FlareSolverr)
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the services
docker-compose down
```

The API will be available at http://localhost:8000.
FlareSolverr will be available at http://localhost:8191.

### Using Docker Directly

```bash
# Build the Docker image
docker build -t cloudflare-fetcher .

# Run the container (requires FlareSolverr service)
docker run -p 8000:8000 -e FLARESOLVERR_URL=http://flaresolverr:8191 cloudflare-fetcher
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

### 1. Fetch Single URL

```bash
curl -X POST "http://localhost:8000/fetch" \
     -H "Content-Type: application/json" \
     -d '{
       "url": "https://example.com",
       "force_refresh_cookies": false
     }'
```

Response:
```json
{
  "url": "https://example.com",
  "success": true,
  "content": "<html><head><title>Example</title></head><body>...</body></html>",
  "content_length": 1256,
  "status_code": 200,
  "execution_time": 2.5,
  "used_cookies": true,
  "cookies_refreshed": false,
  "error": null
}
```

### 2. Fetch Multiple URLs

```bash
curl -X POST "http://localhost:8000/fetch/batch" \
     -H "Content-Type: application/json" \
     -d '{
       "urls": [
         "https://httpbin.org/html",
         "https://example.com"
       ],
       "max_concurrent": 2,
       "force_refresh_cookies": false
     }'
```

Response:
```json
{
  "total_urls": 2,
  "successful_urls": 2,
  "failed_urls": 0,
  "success_rate": 100.0,
  "total_execution_time": 4.2,
  "results": [
    {
      "url": "https://httpbin.org/html",
      "success": true,
      "content": "<html>...</html>",
      "content_length": 1024,
      "status_code": 200,
      "execution_time": 2.1,
      "used_cookies": false,
      "cookies_refreshed": false,
      "error": null
    }
  ]
}
```

### 3. Check Service Health

```bash
curl -X GET "http://localhost:8000/health"
```

Response:
```json
{
  "service": "SimpleFetcher",
  "status": "healthy",
  "flaresolverr_healthy": true,
  "cached_domains": 3,
  "timestamp": 1640995200.0,
  "error": null
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
# FlareSolverr Configuration
FLARESOLVERR_URL=http://localhost:8191

# Logging
LOG_LEVEL=INFO

# Cookie Management
COOKIE_MAX_STALE_SECONDS=1800
```

### Docker Environment Variables

For Docker deployment, you can set environment variables in the `docker-compose.yml`:

```yaml
environment:
  - PYTHONPATH=/app
  - LOG_LEVEL=INFO
  - FLARESOLVERR_URL=http://flaresolverr:8191
  - COOKIE_MAX_STALE_SECONDS=1800
```

### Additional Endpoints

#### Cookie Information
```bash
curl -X GET "http://localhost:8000/cookies/info"
```

#### Cleanup Stale Cookies
```bash
curl -X POST "http://localhost:8000/cleanup"
```

## Error Handling

The service handles various error types:

- **Connection Errors**: Network connectivity issues
- **Timeout Errors**: Request timeout issues
- **Cloudflare Errors**: Challenge solving failures
- **HTTP Errors**: Server response errors

## Development

### Project Structure

```
async_fetcher/
├── api/                    # FastAPI application
│   ├── main.py            # Main application entry point
│   └── models.py          # Pydantic data models
├── toolkit/               # Core fetching toolkit
│   ├── simple_fetcher.py  # Main fetcher service
│   ├── flaresolverr.py    # FlareSolverr client
│   ├── cookie_manager.py  # Cookie management
│   └── sanitization.py   # Input sanitization
├── settings/              # Application settings
│   └── logger.py          # Structured logging
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

The current Dockerfile is optimized for the simplified FlareSolverr + aiohttp architecture and doesn't require browser dependencies. The service relies on an external FlareSolverr service for Cloudflare bypass.

**Production Setup:**

1. **Use the provided docker-compose.yml** (recommended)
2. **Or deploy separately** with FlareSolverr service available
3. **Configure FLARESOLVERR_URL** environment variable

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

## CI/CD Pipeline

This project includes a comprehensive CI/CD pipeline using GitHub Actions.

### Automated Workflows

#### CI Pipeline (`.github/workflows/ci.yml`)
Runs on every push and pull request to `main` and `develop` branches:

- **Code Quality & Linting**: Uses Ruff for code formatting and linting
- **Unit Tests**: Fast tests with mocked dependencies
- **Integration Tests**: API endpoint tests with mocked FlareSolverr
- **E2E Tests**: Full system tests with real FlareSolverr service
- **Docker Build**: Validates Docker image builds
- **Security Scan**: Checks for known vulnerabilities

#### Deployment Pipeline (`.github/workflows/deploy.yml`)
Triggered on releases or manual dispatch:

- **Build & Push**: Creates Docker images for multiple architectures
- **Deploy to Staging**: Manual deployment to staging environment
- **Deploy to Production**: Automatic deployment on releases
- **Notifications**: Success/failure notifications

### Development Scripts

Use the `scripts/dev.py` utility for common development tasks:

```bash
# Setup development environment
python scripts/dev.py setup

# Code formatting and linting
python scripts/dev.py format
python scripts/dev.py lint

# Running tests
python scripts/dev.py test          # All tests
python scripts/dev.py test-unit     # Unit tests only
python scripts/dev.py test-int      # Integration tests only
python scripts/dev.py test-e2e      # E2E tests only
python scripts/dev.py coverage      # Tests with coverage report

# Cleanup
python scripts/dev.py clean
```

### Test Categories

Tests are organized with pytest markers:

- `unit`: Fast, isolated tests with mocked dependencies
- `integration`: API tests with mocked external services
- `e2e`: Full system tests requiring real FlareSolverr
- `slow`: Tests that take longer than 5 seconds
- `network`: Tests requiring network access
- `cloudflare`: Tests with real Cloudflare-protected sites

### Code Quality Standards

- **Linting**: Ruff with strict rules for code quality
- **Formatting**: Consistent code style with Ruff formatter
- **Type Hints**: Full type annotation coverage
- **Test Coverage**: Minimum 75% coverage requirement
- **Security**: Automated vulnerability scanning

### Dependency Management

- **Dependabot**: Automated dependency updates
- **Security**: Regular security scans
- **Pinned Versions**: Controlled dependency updates

## License

[Add your license information here]

## Support

For issues and questions:
- Create an issue in the repository
- Check the API documentation at `/docs`
- Review the troubleshooting section above
