"""
End-to-end tests with real browser automation.

These tests use actual browser instances and should be run separately
from unit and integration tests due to their slower execution time.
Run with: pytest -m e2e
"""

import pytest
import asyncio
from httpx import AsyncClient

from api.main import app

# Mark all tests in this file as e2e tests
pytestmark = [pytest.mark.e2e, pytest.mark.slow, pytest.mark.browser, pytest.mark.network]


@pytest.fixture
async def async_client():
    """Create async HTTP client for testing."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def real_urls():
    """Provide real URLs for E2E testing."""
    return [
        "https://httpbin.org/html",
        "https://httpbin.org/json",
        "https://example.com"
    ]


class TestRealBrowserAutomation:
    """Test real browser automation for E2E scenarios."""
    
    @pytest.mark.asyncio
    async def test_real_browser_fetch_success(self, async_client, real_urls):
        """Test actual browser automation with real URLs."""
        request_data = {
            "links": real_urls[:1],  # Start with just one URL
            "options": {
                "proxies": [],
                "wait_min": 1,
                "wait_max": 2,
                "concurrency_limit": 1
            }
        }
        
        response = await async_client.post("/fetch/start", json=request_data)
        assert response.status_code == 200
        
        data = response.json()
        job_id = data["job_id"]
        
        # Wait for job to complete (real browser takes time)
        max_wait = 30  # 30 seconds max
        wait_interval = 1
        
        for _ in range(max_wait):
            status_response = await async_client.get(f"/fetch/status/{job_id}")
            status_data = status_response.json()
            
            if status_data["status"] == "completed":
                break
                
            await asyncio.sleep(wait_interval)
        
        # Verify job completed successfully
        assert status_data["status"] == "completed"
        assert status_data["completed_urls"] == 1
        assert len(status_data["results"]) == 1
        
        # Verify we got actual HTML content
        result = status_data["results"][0]
        assert result["status"] == "success"
        assert result["content"] is not None
        assert len(result["content"]) > 0
        assert "<html" in result["content"].lower()
    
    @pytest.mark.asyncio
    async def test_real_browser_multiple_urls(self, async_client, real_urls):
        """Test real browser automation with multiple URLs."""
        request_data = {
            "links": real_urls,
            "options": {
                "proxies": [],
                "wait_min": 1,
                "wait_max": 2,
                "concurrency_limit": 2
            }
        }
        
        response = await async_client.post("/fetch/start", json=request_data)
        assert response.status_code == 200
        
        data = response.json()
        job_id = data["job_id"]
        
        # Wait for job to complete
        max_wait = 60  # 60 seconds for multiple URLs
        wait_interval = 2
        
        for _ in range(max_wait // wait_interval):
            status_response = await async_client.get(f"/fetch/status/{job_id}")
            status_data = status_response.json()
            
            if status_data["status"] == "completed":
                break
                
            await asyncio.sleep(wait_interval)
        
        # Verify job completed
        assert status_data["status"] == "completed"
        assert status_data["completed_urls"] == len(real_urls)
        assert len(status_data["results"]) == len(real_urls)
        
        # Verify all results have content
        for result in status_data["results"]:
            if result["status"] == "success":
                assert result["content"] is not None
                assert len(result["content"]) > 0
    
    @pytest.mark.asyncio
    async def test_real_browser_error_handling(self, async_client):
        """Test real browser error handling with invalid URLs."""
        invalid_urls = [
            "https://this-domain-does-not-exist-12345.com",
            "https://httpbin.org/status/404"
        ]
        
        request_data = {
            "links": invalid_urls,
            "options": {
                "proxies": [],
                "wait_min": 1,
                "wait_max": 2,
                "concurrency_limit": 1
            }
        }
        
        response = await async_client.post("/fetch/start", json=request_data)
        assert response.status_code == 200
        
        data = response.json()
        job_id = data["job_id"]
        
        # Wait for job to complete
        max_wait = 30
        wait_interval = 1
        
        for _ in range(max_wait):
            status_response = await async_client.get(f"/fetch/status/{job_id}")
            status_data = status_response.json()
            
            if status_data["status"] == "completed":
                break
                
            await asyncio.sleep(wait_interval)
        
        # Verify job completed with errors
        assert status_data["status"] == "completed"
        assert status_data["completed_urls"] == len(invalid_urls)
        
        # Check that we have error results
        error_count = sum(1 for result in status_data["results"] if result["status"] == "error")
        assert error_count > 0
