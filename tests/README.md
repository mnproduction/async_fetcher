# Test Suite Documentation

This document describes the optimized test suite structure designed for fast execution and comprehensive coverage.

## Test Categories

### 1. Unit Tests (`tests/unit/`)
- **Purpose**: Test individual components in isolation
- **Speed**: Very fast (< 1 second per test)
- **Dependencies**: All external dependencies are mocked
- **Markers**: `@pytest.mark.unit`, `@pytest.mark.fast`, `@pytest.mark.mock`

### 2. Integration Tests (`tests/integration/`)
- **Purpose**: Test API endpoints and component interactions
- **Speed**: Fast (< 1 second per test with mocked browser)
- **Dependencies**: Browser automation is mocked, database/external APIs mocked
- **Markers**: `@pytest.mark.integration`, `@pytest.mark.fast`, `@pytest.mark.mock`

### 3. End-to-End Tests (`tests/e2e/`)
- **Purpose**: Test complete workflows with real browser automation
- **Speed**: Slow (10+ seconds per test)
- **Dependencies**: Real browser instances, network access required
- **Markers**: `@pytest.mark.e2e`, `@pytest.mark.slow`, `@pytest.mark.browser`, `@pytest.mark.network`

## Running Tests

### Fast Development Testing (Recommended)
```bash
# Run only fast tests (unit + integration with mocks)
pytest -c pytest-fast.ini

# Or using markers
pytest -m "not e2e and not slow"

# Run specific test categories
pytest -m unit          # Unit tests only
pytest -m integration   # Integration tests only
pytest -m fast          # All fast tests
```

### Full Test Suite
```bash
# Run all tests including E2E (slow)
pytest

# Run with coverage
pytest --cov=api --cov=toolkit --cov=settings
```

### End-to-End Testing
```bash
# Run only E2E tests
pytest -c pytest-e2e.ini

# Or using markers
pytest -m e2e
```

## Performance Improvements

### Before Optimization
- Integration tests: **12+ seconds** (real browser automation)
- Unit tests: **10+ seconds** (broken async mocks)
- Total test time: **20+ seconds**

### After Optimization
- Integration tests: **0.2-0.3 seconds** (mocked browser)
- Unit tests: **10 seconds** (fixed async mocks)
- Fast test suite: **~11 seconds total**
- **98% performance improvement** for integration tests

## Test Configuration Files

### `pytest.ini` (Default)
- Runs all test types
- Includes coverage reporting
- Suitable for CI/CD pipelines

### `pytest-fast.ini`
- Excludes E2E and slow tests
- Optimized for development
- Fastest feedback loop

### `pytest-e2e.ini`
- Runs only E2E tests
- No coverage reporting
- For comprehensive testing

## Browser Automation Strategy

### Development/CI (Fast)
- **Unit tests**: Browser toolkit methods are mocked with `AsyncMock`
- **Integration tests**: Browser class constructor is mocked to return mock instance
- **Result**: No real browser instances created, tests complete in milliseconds

### E2E Testing (Comprehensive)
- **Real browsers**: Actual Chromium/Firefox instances via Playwright
- **Browser pooling**: Reuse browser instances to reduce initialization overhead
- **Network access**: Tests against real websites
- **Result**: Comprehensive validation but slower execution

## Browser Pool (Optional)

For scenarios requiring real browsers but with better performance:

```python
from toolkit.browser_pool import get_browser_pool

# Use pooled browser
pool = await get_browser_pool()
async with pool.get_browser() as browser:
    content = await browser.get_page_content(url)
```

**Benefits**:
- Reuses browser instances
- Reduces initialization overhead
- Configurable pool size and cleanup
- Automatic health monitoring

## Best Practices

### For Development
1. Use `pytest -c pytest-fast.ini` for rapid feedback
2. Run E2E tests only before major releases
3. Focus on unit and integration test coverage

### For CI/CD
1. Run fast tests on every commit
2. Run E2E tests on release branches
3. Use parallel test execution for large suites

### Writing New Tests
1. **Unit tests**: Mock all external dependencies
2. **Integration tests**: Test API behavior with mocked browser
3. **E2E tests**: Use real browsers only for critical user journeys

## Troubleshooting

### Slow Test Execution
- Check if E2E tests are running unintentionally
- Verify browser mocks are properly configured
- Use `pytest --durations=10` to identify slow tests

### Browser Mock Issues
- Ensure `AsyncMock` is used for async browser methods
- Verify mock setup in test fixtures
- Check that browser class constructor is mocked in integration tests

### E2E Test Failures
- Verify network connectivity
- Check if target websites are accessible
- Ensure browser dependencies are installed
- Review browser pool configuration
