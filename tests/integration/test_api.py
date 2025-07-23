"""
Integration tests for the Async HTML Fetcher API endpoints.

This module contains comprehensive integration tests for the API endpoints,
testing end-to-end functionality including job creation, status retrieval,
and error handling scenarios.
"""

import pytest
import uuid
from httpx import AsyncClient
import asyncio
from unittest.mock import patch, AsyncMock

from api.main import app
from api.models import FetchRequest, FetchOptions, FetchResult
from api.logic import jobs, create_job, update_job_status, add_job_result


class TestFetchStartEndpoint:
    """Test cases for the POST /fetch/start endpoint."""

    @pytest.mark.asyncio
    async def test_start_fetch_success(self, async_client, sample_fetch_request):
        """Test successful job creation with valid request."""
        response = await async_client.post(
            "/fetch/start",
            json=sample_fetch_request.model_dump()
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "job_id" in data
        assert "status_url" in data
        
        # Verify job_id is a valid UUID
        job_id = data["job_id"]
        assert uuid.UUID(job_id)  # Should not raise ValueError
        
        # Verify status_url format
        expected_status_url = f"http://test/fetch/status/{job_id}"
        assert data["status_url"] == expected_status_url
        
        # Verify job was created in memory
        assert job_id in jobs
        assert jobs[job_id]["status"] == "pending"
        assert jobs[job_id]["total_urls"] == len(sample_fetch_request.links)
        assert jobs[job_id]["completed_urls"] == 0

    @pytest.mark.asyncio
    async def test_start_fetch_simple_request(self, async_client, sample_fetch_request_simple):
        """Test job creation with minimal request."""
        response = await async_client.post(
            "/fetch/start",
            json=sample_fetch_request_simple.model_dump()
        )
        
        assert response.status_code == 200
        data = response.json()
        
        job_id = data["job_id"]
        assert job_id in jobs
        assert jobs[job_id]["total_urls"] == 1
        assert jobs[job_id]["completed_urls"] == 0

    @pytest.mark.asyncio
    async def test_start_fetch_multiple_urls(self, async_client, sample_urls):
        """Test job creation with multiple URLs."""
        request_data = {
            "links": sample_urls,
            "options": {
                "proxies": [],
                "wait_min": 1,
                "wait_max": 3,
                "concurrency_limit": 3
            }
        }
        
        response = await async_client.post("/fetch/start", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        job_id = data["job_id"]
        assert jobs[job_id]["total_urls"] == len(sample_urls)
        assert jobs[job_id]["completed_urls"] == 0

    @pytest.mark.asyncio
    async def test_start_fetch_with_proxies(self, async_client, sample_proxies):
        """Test job creation with proxy configuration."""
        request_data = {
            "links": ["https://example.com"],
            "options": {
                "proxies": sample_proxies,
                "wait_min": 1,
                "wait_max": 3,
                "concurrency_limit": 5
            }
        }
        
        response = await async_client.post("/fetch/start", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        job_id = data["job_id"]
        assert jobs[job_id]["options"]["proxies"] == sample_proxies

    @pytest.mark.asyncio
    async def test_start_fetch_invalid_request_empty_links(self, async_client):
        """Test job creation with empty links list."""
        request_data = {
            "links": [],
            "options": {}
        }
        
        response = await async_client.post("/fetch/start", json=request_data)
        
        assert response.status_code == 422  # Validation error
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_start_fetch_invalid_request_no_links(self, async_client):
        """Test job creation without links field."""
        request_data = {
            "options": {}
        }
        
        response = await async_client.post("/fetch/start", json=request_data)
        
        assert response.status_code == 422  # Validation error
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_start_fetch_invalid_urls(self, async_client, invalid_urls):
        """Test job creation with invalid URLs."""
        request_data = {
            "links": invalid_urls,
            "options": {}
        }
        
        response = await async_client.post("/fetch/start", json=request_data)
        
        assert response.status_code == 422  # Validation error
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_start_fetch_invalid_proxies(self, async_client, invalid_proxies):
        """Test job creation with invalid proxy URLs."""
        request_data = {
            "links": ["https://example.com"],
            "options": {
                "proxies": invalid_proxies
            }
        }
        
        response = await async_client.post("/fetch/start", json=request_data)
        
        assert response.status_code == 422  # Validation error
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_start_fetch_invalid_wait_times(self, async_client):
        """Test job creation with invalid wait time configuration."""
        request_data = {
            "links": ["https://example.com"],
            "options": {
                "wait_min": 5,
                "wait_max": 1  # wait_min > wait_max
            }
        }
        
        response = await async_client.post("/fetch/start", json=request_data)
        
        assert response.status_code == 422  # Validation error
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_start_fetch_invalid_concurrency_limit(self, async_client):
        """Test job creation with invalid concurrency limit."""
        request_data = {
            "links": ["https://example.com"],
            "options": {
                "concurrency_limit": 0  # Must be > 0
            }
        }
        
        response = await async_client.post("/fetch/start", json=request_data)
        
        assert response.status_code == 422  # Validation error
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_start_fetch_malformed_json(self, async_client):
        """Test job creation with malformed JSON."""
        response = await async_client.post(
            "/fetch/start",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_start_fetch_missing_content_type(self, async_client):
        """Test job creation without Content-Type header."""
        request_data = {
            "links": ["https://example.com"],
            "options": {}
        }
        
        response = await async_client.post(
            "/fetch/start",
            json=request_data,
            headers={}  # No Content-Type
        )
        
        # FastAPI should still process this correctly
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_start_fetch_large_request(self, async_client):
        """Test job creation with a large number of URLs."""
        large_url_list = [f"https://example{i}.com" for i in range(100)]
        
        request_data = {
            "links": large_url_list,
            "options": {
                "concurrency_limit": 10
            }
        }
        
        response = await async_client.post("/fetch/start", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        job_id = data["job_id"]
        assert jobs[job_id]["total_urls"] == 100
        assert jobs[job_id]["options"]["concurrency_limit"] == 10


class TestFetchStatusEndpoint:
    """Test cases for the GET /fetch/status/{job_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_status_existing_job(self, async_client, sample_job_id):
        """Test status retrieval for existing job."""
        response = await async_client.get(f"/fetch/status/{sample_job_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "job_id" in data
        assert "status" in data
        assert "results" in data
        assert "total_urls" in data
        assert "completed_urls" in data
        assert "started_at" in data
        assert "completed_at" in data
        
        # Verify data values
        assert data["job_id"] == sample_job_id
        assert data["status"] == "pending"
        assert isinstance(data["results"], list)
        assert data["total_urls"] == 1
        assert data["completed_urls"] == 0

    @pytest.mark.asyncio
    async def test_get_status_completed_job(self, async_client, sample_job_id_completed):
        """Test status retrieval for completed job."""
        response = await async_client.get(f"/fetch/status/{sample_job_id_completed}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "completed"
        assert data["completed_urls"] == data["total_urls"]
        assert len(data["results"]) > 0

    @pytest.mark.asyncio
    async def test_get_status_in_progress_job(self, async_client, sample_job_id_in_progress):
        """Test status retrieval for job in progress."""
        response = await async_client.get(f"/fetch/status/{sample_job_id_in_progress}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "in_progress"
        assert data["completed_urls"] < data["total_urls"]

    @pytest.mark.asyncio
    async def test_get_status_complex_job(self, async_client, sample_job_id_complex):
        """Test status retrieval for job with multiple URLs."""
        response = await async_client.get(f"/fetch/status/{sample_job_id_complex}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_urls"] > 1
        assert isinstance(data["results"], list)

    @pytest.mark.asyncio
    async def test_get_status_nonexistent_job(self, async_client):
        """Test status retrieval for non-existent job."""
        fake_job_id = str(uuid.uuid4())
        response = await async_client.get(f"/fetch/status/{fake_job_id}")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_status_invalid_uuid(self, async_client):
        """Test status retrieval with invalid UUID format."""
        response = await async_client.get("/fetch/status/invalid-uuid")
        
        assert response.status_code == 422  # Validation error
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_get_status_empty_uuid(self, async_client):
        """Test status retrieval with empty UUID."""
        response = await async_client.get("/fetch/status/")
        
        assert response.status_code == 404  # Route not found

    @pytest.mark.asyncio
    async def test_get_status_with_results(self, async_client, sample_job_id):
        """Test status retrieval after adding results."""
        # Add a result to the job
        result = {
            "url": "https://example.com",
            "status": "success",
            "html_content": "<html><body>Test content</body></html>",
            "error_message": None
        }
        add_job_result(sample_job_id, result)
        
        response = await async_client.get(f"/fetch/status/{sample_job_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "completed"
        assert data["completed_urls"] == 1
        assert len(data["results"]) == 1
        assert data["results"][0]["url"] == result["url"]
        assert data["results"][0]["status"] == result["status"]

    @pytest.mark.asyncio
    async def test_get_status_with_error_results(self, async_client, sample_job_id):
        """Test status retrieval with error results."""
        # Add an error result to the job
        error_result = {
            "url": "https://example.com",
            "status": "error",
            "html_content": None,
            "error_message": "Connection timeout"
        }
        add_job_result(sample_job_id, error_result)
        
        response = await async_client.get(f"/fetch/status/{sample_job_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "completed"
        assert data["completed_urls"] == 1
        assert len(data["results"]) == 1
        assert data["results"][0]["status"] == "error"
        assert data["results"][0]["error_message"] == "Connection timeout"

    @pytest.mark.asyncio
    async def test_get_status_timestamp_fields(self, async_client, sample_job_id):
        """Test that timestamp fields are present and valid."""
        response = await async_client.get(f"/fetch/status/{sample_job_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify timestamp fields exist
        assert "started_at" in data
        assert "completed_at" in data
        
        # Verify timestamps are strings (ISO format) or None
        assert data["started_at"] is None or isinstance(data["started_at"], str)
        assert data["completed_at"] is None or isinstance(data["completed_at"], str)

    @pytest.mark.asyncio
    async def test_get_status_results_structure(self, async_client, sample_job_id_completed):
        """Test that results have the correct structure."""
        response = await async_client.get(f"/fetch/status/{sample_job_id_completed}")
        
        assert response.status_code == 200
        data = response.json()
        
        if data["results"]:
            result = data["results"][0]
            
            # Verify result structure
            assert "url" in result
            assert "status" in result
            assert "html_content" in result
            assert "error_message" in result
            
            # Verify data types
            assert isinstance(result["url"], str)
            assert isinstance(result["status"], str)
            assert result["html_content"] is None or isinstance(result["html_content"], str)
            assert result["error_message"] is None or isinstance(result["error_message"], str)


class TestAPIErrorHandling:
    """Test cases for API error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_api_health_check(self, async_client):
        """Test that the API is running and responding."""
        response = await async_client.get("/")
        
        # Should return 200 for root path (root endpoint is defined)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_api_method_not_allowed(self, async_client):
        """Test that unsupported HTTP methods return 405."""
        # Try GET on POST-only endpoint
        response = await async_client.get("/fetch/start")
        assert response.status_code == 405
        
        # Try POST on GET-only endpoint
        fake_job_id = str(uuid.uuid4())
        response = await async_client.post(f"/fetch/status/{fake_job_id}")
        assert response.status_code == 405

    @pytest.mark.asyncio
    async def test_api_large_payload(self, async_client):
        """Test handling of large request payloads."""
        # Create a large request with many URLs
        large_url_list = [f"https://example{i}.com" for i in range(1000)]
        
        request_data = {
            "links": large_url_list,
            "options": {
                "proxies": [],
                "wait_min": 1,
                "wait_max": 3,
                "concurrency_limit": 10
            }
        }
        
        response = await async_client.post("/fetch/start", json=request_data)
        
        # Should handle large payloads gracefully
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data

    @pytest.mark.asyncio
    async def test_api_concurrent_requests(self, async_client):
        """Test handling of concurrent requests."""
        request_data = {
            "links": ["https://example.com"],
            "options": {}
        }
        
        # Create multiple concurrent requests
        tasks = []
        for _ in range(10):
            task = async_client.post("/fetch/start", json=request_data)
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks)
        
        # Verify all requests succeeded
        assert all(response.status_code == 200 for response in responses)

    @pytest.mark.asyncio
    async def test_api_response_headers(self, async_client, sample_fetch_request):
        """Test that API responses include proper headers."""
        response = await async_client.post(
            "/fetch/start",
            json=sample_fetch_request.model_dump()
        )
        
        assert response.status_code == 200
        
        # Verify content type
        assert "application/json" in response.headers.get("content-type", "")
        
        # Verify other headers
        assert "content-length" in response.headers

    @pytest.mark.asyncio
    async def test_api_cors_headers(self, async_client, sample_fetch_request):
        """Test CORS headers for cross-origin requests."""
        response = await async_client.post(
            "/fetch/start",
            json=sample_fetch_request.model_dump(),
            headers={"Origin": "https://example.com"}
        )
        
        assert response.status_code == 200
        
        # FastAPI should handle CORS if configured
        # This test verifies the API doesn't break with Origin header


class TestAsyncAPIEndpoints:
    """Test cases for async API functionality."""

    @pytest.mark.asyncio
    async def test_async_fetch_start(self, async_client, sample_fetch_request):
        """Test async job creation."""
        response = await async_client.post(
            "/fetch/start",
            json=sample_fetch_request.model_dump()
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "job_id" in data
        assert "status_url" in data
        
        job_id = data["job_id"]
        assert job_id in jobs

    @pytest.mark.asyncio
    async def test_async_fetch_status(self, async_client, sample_job_id):
        """Test async status retrieval."""
        response = await async_client.get(f"/fetch/status/{sample_job_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["job_id"] == sample_job_id
        assert data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_async_concurrent_requests(self, async_client):
        """Test multiple concurrent async requests."""
        request_data = {
            "links": ["https://example.com"],
            "options": {}
        }
        
        # Create multiple concurrent requests
        tasks = []
        for _ in range(5):
            task = async_client.post("/fetch/start", json=request_data)
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks)
        
        # Verify all requests succeeded
        assert all(response.status_code == 200 for response in responses)
        
        # Verify all jobs were created
        job_ids = [response.json()["job_id"] for response in responses]
        assert all(job_id in jobs for job_id in job_ids)


class TestAPIValidation:
    """Test cases for API input validation."""

    @pytest.mark.asyncio
    async def test_validate_url_schemes(self, async_client):
        """Test validation of different URL schemes."""
        valid_schemes = [
            "https://example.com",
            "http://example.com",
            "https://subdomain.example.com",
            "https://example.com:8080",
            "https://example.com/path",
            "https://example.com/path?param=value"
        ]
        
        for url in valid_schemes:
            request_data = {
                "links": [url],
                "options": {}
            }
            
            response = await async_client.post("/fetch/start", json=request_data)
            assert response.status_code == 200, f"Failed for URL: {url}"

    @pytest.mark.asyncio
    async def test_validate_invalid_url_schemes(self, async_client):
        """Test validation of invalid URL schemes."""
        invalid_schemes = [
            "ftp://example.com",
            "file:///path/to/file",
            "mailto:user@example.com",
            "tel:+1234567890"
        ]
        
        for url in invalid_schemes:
            request_data = {
                "links": [url],
                "options": {}
            }
            
            response = await async_client.post("/fetch/start", json=request_data)
            assert response.status_code == 422, f"Should fail for URL: {url}"

    @pytest.mark.asyncio
    async def test_validate_proxy_formats(self, async_client):
        """Test validation of different proxy formats."""
        valid_proxies = [
            "http://proxy.example.com:8080",
            "https://proxy.example.com:8443",
            "http://user:pass@proxy.example.com:8080"
        ]
        
        for proxy in valid_proxies:
            request_data = {
                "links": ["https://example.com"],
                "options": {
                    "proxies": [proxy]
                }
            }
            
            response = await async_client.post("/fetch/start", json=request_data)
            assert response.status_code == 200, f"Failed for proxy: {proxy}"

    @pytest.mark.asyncio
    async def test_validate_invalid_proxy_formats(self, async_client):
        """Test validation of invalid proxy formats."""
        invalid_proxies = [
            "invalid-proxy",
            "proxy.example.com",
            "ftp://proxy.example.com:8080"
        ]
        
        for proxy in invalid_proxies:
            request_data = {
                "links": ["https://example.com"],
                "options": {
                    "proxies": [proxy]
                }
            }
            
            response = await async_client.post("/fetch/start", json=request_data)
            assert response.status_code == 422, f"Should fail for proxy: {proxy}"

    @pytest.mark.asyncio
    async def test_validate_wait_time_constraints(self, async_client):
        """Test validation of wait time constraints."""
        # Test valid wait times
        valid_configs = [
            {"wait_min": 1, "wait_max": 3},
            {"wait_min": 0, "wait_max": 5},
            {"wait_min": 2, "wait_max": 2}
        ]
        
        for config in valid_configs:
            request_data = {
                "links": ["https://example.com"],
                "options": config
            }
            
            response = await async_client.post("/fetch/start", json=request_data)
            assert response.status_code == 200, f"Failed for config: {config}"

    @pytest.mark.asyncio
    async def test_validate_invalid_wait_times(self, async_client):
        """Test validation of invalid wait times."""
        invalid_configs = [
            {"wait_min": 3, "wait_max": 1},  # min > max
            {"wait_min": -1, "wait_max": 3},  # negative min
            {"wait_max": -1}  # negative max
        ]
        
        for config in invalid_configs:
            request_data = {
                "links": ["https://example.com"],
                "options": config
            }
            
            response = await async_client.post("/fetch/start", json=request_data)
            assert response.status_code == 422, f"Should fail for config: {config}"

    @pytest.mark.asyncio
    async def test_validate_concurrency_limits(self, async_client):
        """Test validation of concurrency limits."""
        # Test valid concurrency limits
        valid_limits = [1, 5, 10, 50, 100]
        
        for limit in valid_limits:
            request_data = {
                "links": ["https://example.com"],
                "options": {
                    "concurrency_limit": limit
                }
            }
            
            response = await async_client.post("/fetch/start", json=request_data)
            assert response.status_code == 200, f"Failed for limit: {limit}"

    @pytest.mark.asyncio
    async def test_validate_invalid_concurrency_limits(self, async_client):
        """Test validation of invalid concurrency limits."""
        invalid_limits = [0, -1, -5]
        
        for limit in invalid_limits:
            request_data = {
                "links": ["https://example.com"],
                "options": {
                    "concurrency_limit": limit
                }
            }
            
            response = await async_client.post("/fetch/start", json=request_data)
            assert response.status_code == 422, f"Should fail for limit: {limit}" 