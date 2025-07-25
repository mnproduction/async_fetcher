# Test Suite for Simplified Content Fetcher

This directory contains comprehensive tests for the Simplified Content Fetcher, organized into different categories based on scope and dependencies. The test suite is designed for the simplified FlareSolverr + aiohttp architecture.

## Test Structure

```
tests/
├── unit/                           # Unit tests (fast, isolated)
│   ├── test_flaresolverr.py       # FlareSolverr client tests
│   ├── test_cookie_manager.py     # Cookie management tests
│   ├── test_simple_fetcher.py     # Simple fetcher tests
│   └── test_models.py             # Data model tests
├── integration/                   # Integration tests (API endpoints)
│   └── test_api_endpoints.py     # API endpoint tests with mocked dependencies
├── e2e/                          # End-to-end tests (full system)
│   └── test_real_flaresolverr.py # Real FlareSolverr integration tests
├── conftest.py                   # Shared test fixtures
└── README.md                     # This file
```

## Test Categories

### Unit Tests (`pytest -m unit`)
- **Fast execution** (< 1 second per test)
- **Isolated components** with mocked dependencies
- **High coverage** of individual functions and classes
- **No external dependencies** (no network, no FlareSolverr)

**Components tested:**
- FlareSolverr client (mocked HTTP requests)
- Cookie manager (session storage and validation)
- Simple fetcher (fetch logic with mocked dependencies)
- Data models (Pydantic validation)

### Integration Tests (`pytest -m integration`)
- **API endpoint testing** with mocked FlareSolverr
- **Request/response validation**
- **Error handling scenarios**
- **FastAPI application behavior**

**Endpoints tested:**
- `/health` - Service health check
- `/` - Service information
- `/fetch` - Single URL fetch
- `/fetch/batch` - Batch URL fetch
- `/cookies/info` - Cookie session information
- `/cleanup` - Expired cookie cleanup

### End-to-End Tests (`pytest -m e2e`)
- **Full system testing** with real FlareSolverr service
- **Actual Cloudflare bypass** scenarios
- **Real network requests**
- **Slower execution** (may take minutes)

**Scenarios tested:**
- FlareSolverr health checks
- Simple challenge solving
- Cloudflare challenge solving (tem.fi)
- Complete cookie session lifecycle
- Real network fetching

## Running Tests

### Quick Tests (Unit + Integration)
```bash
# Run fast tests only (recommended for development)
pytest -m "not e2e and not slow"

# With coverage report
pytest -m "not e2e and not slow" --cov=api --cov=toolkit --cov=settings --cov-report=term-missing --cov-report=html:htmlcov --cov-fail-under=75
```

### All Tests
```bash
# Run all tests (including slow E2E tests)
pytest

# Run with verbose output
pytest -v
```

### Specific Test Categories
```bash
# Unit tests only
pytest -m unit

# Integration tests only
pytest -m integration

# E2E tests only (requires FlareSolverr service)
pytest -m e2e

# Fast tests only
pytest -m fast

# Slow tests only
pytest -m slow
```

### FlareSolverr-specific Tests
```bash
# Tests requiring FlareSolverr service
pytest -m flaresolverr

# Cloudflare bypass tests
pytest -m cloudflare

# Network-dependent tests
pytest -m network
```

## Test Markers

The test suite uses pytest markers to categorize tests:

- `unit`: Unit tests for individual components (fast, mocked)
- `integration`: Integration tests for API endpoints (mocked FlareSolverr)
- `e2e`: End-to-end tests with real FlareSolverr service (slow)
- `slow`: Tests that take longer to run (>5 seconds)
- `flaresolverr`: Tests that require FlareSolverr service
- `fast`: Tests that run quickly (under 1 second)
- `network`: Tests that require network access
- `mock`: Tests that use mocked dependencies
- `cloudflare`: Tests that interact with Cloudflare-protected sites

## Prerequisites

### For Unit and Integration Tests
- No external dependencies required
- All dependencies are mocked

### For E2E Tests
- **FlareSolverr service** must be running:
  ```bash
  docker-compose up flaresolverr
  ```
- **Network access** for real HTTP requests
- **Longer timeouts** for Cloudflare challenges

## Test Configuration

Test configuration is defined in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
addopts = "-v"
testpaths = ["tests"]
python_files = "test_*.py"
python_classes = "Test*"
python_functions = "test_*"
asyncio_mode = "strict"
```

## Test Fixtures

### Shared Fixtures (`conftest.py`)
- `test_client`: FastAPI TestClient for API testing
- `async_client`: Async HTTP client for testing
- `mock_flaresolverr_client`: Mock FlareSolverr client
- `mock_cookie_manager`: Mock cookie manager
- `mock_simple_fetcher`: Mock simple fetcher
- `sample_fetch_requests`: Sample request data
- `sample_fetch_results`: Sample result data

## Writing Tests

### Unit Test Example
```python
import pytest
from unittest.mock import AsyncMock

@pytest.mark.unit
@pytest.mark.fast
@pytest.mark.mock
async def test_flaresolverr_health_check(mock_flaresolverr_client):
    mock_flaresolverr_client.health_check.return_value = {"status": "ok"}
    result = await mock_flaresolverr_client.health_check()
    assert result["status"] == "ok"
```

### Integration Test Example
```python
import pytest

@pytest.mark.integration
@pytest.mark.fast
@pytest.mark.mock
def test_health_endpoint(test_client):
    response = test_client.get("/health")
    assert response.status_code == 200
    assert "service" in response.json()
```

### E2E Test Example
```python
import pytest

@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.flaresolverr
async def test_real_flaresolverr_health(flaresolverr_client):
    result = await flaresolverr_client.health_check()
    assert result["status"] == "ok"
```

## Test Data

### Sample URLs for Testing
- `https://httpbin.org/html` - Simple HTML content
- `https://httpbin.org/json` - JSON response
- `https://httpbin.org/status/404` - Error scenarios
- `https://tem.fi` - Cloudflare-protected site (E2E only)

## Coverage Requirements

- **Minimum coverage**: 75%
- **Unit tests**: Should cover all business logic
- **Integration tests**: Should cover all API endpoints
- **E2E tests**: Should cover critical Cloudflare bypass scenarios

## Best Practices

### For Development
1. Use fast tests (`pytest -m "not e2e and not slow"`) for rapid feedback
2. Run E2E tests only when testing Cloudflare bypass functionality
3. Focus on unit and integration test coverage

### For CI/CD
1. Run fast tests on every commit
2. Run E2E tests on release branches or nightly
3. Use parallel test execution for large suites

### Writing New Tests
1. **Unit tests**: Mock all external dependencies (FlareSolverr, aiohttp)
2. **Integration tests**: Test API behavior with mocked services
3. **E2E tests**: Use real FlareSolverr only for critical bypass scenarios

## Troubleshooting

### Common Issues

1. **FlareSolverr tests failing**: Ensure FlareSolverr service is running
   ```bash
   docker-compose up flaresolverr
   ```

2. **Async tests hanging**: Check event loop configuration in `conftest.py`

3. **Import errors**: Ensure PYTHONPATH includes project root

4. **Coverage too low**: Add tests for uncovered code paths

5. **Slow tests**: Use `-m "not slow"` for development

### E2E Test Requirements

- FlareSolverr service running on `localhost:8191`
- Network connectivity for real HTTP requests
- Longer timeouts for Cloudflare challenges (30-60 seconds)

### Getting Help

- Check test output for specific error messages
- Review test fixtures in `conftest.py`
- Consult pytest documentation for advanced features
- Use `pytest --collect-only` to see available tests
