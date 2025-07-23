"""
Configuration for E2E tests.

This module provides fixtures and configuration for end-to-end tests
that use real browser automation.
"""

import pytest
import asyncio
from api.logic import jobs


@pytest.fixture(autouse=True)
def clear_jobs():
    """Clear jobs before each E2E test to avoid interference."""
    jobs.clear()
    yield
    jobs.clear()


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


def pytest_configure(config):
    """Configure pytest for E2E tests."""
    # Add custom markers if not already defined
    if not hasattr(config.option, 'markexpr'):
        return
    
    # Skip E2E tests by default unless explicitly requested
    if not config.getoption("-m"):
        config.option.markexpr = "not e2e"


def pytest_collection_modifyitems(config, items):
    """Modify test collection to handle E2E test markers."""
    # Skip E2E tests if running in CI or if browser is not available
    skip_e2e = pytest.mark.skip(reason="E2E tests require real browser and network access")
    
    for item in items:
        if "e2e" in item.keywords:
            # Add warning about slow tests
            item.add_marker(pytest.mark.slow)
            
            # Skip if running in CI environment
            import os
            if os.getenv("CI") or os.getenv("GITHUB_ACTIONS"):
                item.add_marker(skip_e2e)
