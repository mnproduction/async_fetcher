"""
Unit tests for business logic functions

This module tests all business logic functions used in the Async HTML Fetcher Service,
including job management, status updates, and result handling.

Test Coverage:
- Job creation and management
- Job status updates and transitions
- Result addition and processing
- Job status retrieval and serialization
- Error handling and edge cases

Author: Async HTML Fetcher Service
Version: 1.0.0
"""

import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from freezegun import freeze_time

from api.logic import (
    jobs, create_job, get_job_status, update_job_status, 
    add_job_result, run_fetching_job, fetch_single_url_with_semaphore
)


# =============================================================================
# JOB CREATION TESTS
# =============================================================================

class TestJobCreation:
    """Test job creation and management functions."""
    
    def test_create_job_success(self, sample_fetch_request_simple):
        """Test successful job creation."""
        job_id = create_job(sample_fetch_request_simple)
        
        # Verify job ID format
        assert isinstance(job_id, str)
        uuid.UUID(job_id)  # Should not raise exception
        
        # Verify job exists in store
        assert job_id in jobs
        
        # Verify job data
        job_data = jobs[job_id]
        assert job_data["status"] == "pending"
        assert job_data["total_urls"] == 1
        assert job_data["completed_urls"] == 0
        assert job_data["results"] == []
        assert "created_at" in job_data
        assert "updated_at" in job_data
    
    def test_create_job_with_complex_request(self, sample_fetch_request):
        """Test job creation with complex request."""
        job_id = create_job(sample_fetch_request)
        
        # Verify job data
        job_data = jobs[job_id]
        assert job_data["total_urls"] == 3
        assert job_data["completed_urls"] == 0
        assert len(job_data["results"]) == 0
        
        # Verify request data is stored
        assert "request" in job_data
        stored_request = job_data["request"]
        assert stored_request["links"] == sample_fetch_request.links
        assert stored_request["options"]["concurrency_limit"] == 5
    
    def test_create_job_generates_unique_ids(self, sample_fetch_request_simple):
        """Test that job creation generates unique IDs."""
        job_id1 = create_job(sample_fetch_request_simple)
        job_id2 = create_job(sample_fetch_request_simple)
        
        assert job_id1 != job_id2
        assert job_id1 in jobs
        assert job_id2 in jobs
    
    @freeze_time("2023-01-01 12:00:00")
    def test_create_job_timestamps(self, sample_fetch_request_simple):
        """Test that job creation sets proper timestamps."""
        job_id = create_job(sample_fetch_request_simple)
        job_data = jobs[job_id]
        
        # Verify timestamps exist and are recent
        assert "created_at" in job_data
        assert "updated_at" in job_data
        
        created_at = datetime.fromisoformat(job_data["created_at"])
        updated_at = datetime.fromisoformat(job_data["updated_at"])
        
        # Timestamps should be recent (within last minute)
        now = datetime.now(timezone.utc)
        assert (now - created_at).total_seconds() < 60
        assert (now - updated_at).total_seconds() < 60


# =============================================================================
# JOB STATUS MANAGEMENT TESTS
# =============================================================================

class TestJobStatusManagement:
    """Test job status update and retrieval functions."""
    
    @freeze_time("2023-01-01 12:00:00")
    def test_update_job_status_success(self, sample_job_id):
        """Test successful job status update."""
        # Update status to in_progress
        update_job_status(sample_job_id, "in_progress")
        
        # Verify status was updated
        job_data = jobs[sample_job_id]
        assert job_data["status"] == "in_progress"
        
        # Verify updated_at timestamp was updated
        updated_at = datetime.fromisoformat(job_data["updated_at"])
        now = datetime.now(timezone.utc)
        assert (now - updated_at).total_seconds() < 60
    
    def test_update_job_status_invalid_job_id(self):
        """Test status update with invalid job ID."""
        # Function returns False for invalid job ID instead of raising KeyError
        result = update_job_status("non-existent-job-id", "in_progress")
        assert result is False
    
    def test_update_job_status_invalid_status(self, sample_job_id):
        """Test status update with invalid status."""
        with pytest.raises(ValueError) as exc_info:
            update_job_status(sample_job_id, "invalid_status")
        
        assert "Invalid status" in str(exc_info.value)
    
    def test_get_job_status_success(self, sample_job_id):
        """Test successful job status retrieval."""
        response = get_job_status(sample_job_id)
        
        # Verify response structure
        assert response.job_id == sample_job_id
        assert response.status == "pending"
        assert response.total_urls == 1
        assert response.completed_urls == 0
        assert response.results == []
        assert response.started_at is None
        assert response.completed_at is None
    
    def test_get_job_status_not_found(self):
        """Test job status retrieval for non-existent job."""
        response = get_job_status("non-existent-job-id")
        assert response is None
    
    def test_get_job_status_with_results(self, sample_job_id_completed):
        """Test job status retrieval with results."""
        response = get_job_status(sample_job_id_completed)
        
        # Verify response structure
        assert response.job_id == sample_job_id_completed
        assert response.status == "completed"
        assert response.total_urls == 1
        assert response.completed_urls == 1
        assert len(response.results) == 1
        assert response.progress_percentage == 100.0
        assert response.is_finished
    
    def test_get_job_status_corrupted_data(self, sample_job_id):
        """Test job status retrieval with corrupted data."""
        # Corrupt the job data with an invalid status
        jobs[sample_job_id]["status"] = "invalid_status"

        # Should handle gracefully by catching the validation error
        try:
            response = get_job_status(sample_job_id)
            # If we get here, the function should handle the invalid status gracefully
            assert response is not None
        except Exception as e:
            # The function should handle validation errors gracefully
            assert "validation error" in str(e).lower() or "invalid_status" in str(e)


# =============================================================================
# RESULT MANAGEMENT TESTS
# =============================================================================

class TestResultManagement:
    """Test result addition and processing functions."""
    
    def test_add_job_result_success(self, sample_job_id):
        """Test successful result addition."""
        result_data = {
            "url": "https://example.com",
            "status": "success",
            "html_content": "<html><body>Hello</body></html>",
            "response_time_ms": 1250,
            "status_code": 200
        }
        
        add_job_result(sample_job_id, result_data)
        
        # Verify result was added
        job_data = jobs[sample_job_id]
        assert job_data["completed_urls"] == 1
        assert len(job_data["results"]) == 1
        assert job_data["results"][0] == result_data
        
        # Verify status was updated to completed
        assert job_data["status"] == "completed"
    
    def test_add_job_result_error(self, sample_job_id):
        """Test error result addition."""
        result_data = {
            "url": "https://broken.com",
            "status": "error",
            "error_message": "Connection timeout"
        }
        
        add_job_result(sample_job_id, result_data)
        
        # Verify result was added
        job_data = jobs[sample_job_id]
        assert job_data["completed_urls"] == 1
        assert len(job_data["results"]) == 1
        assert job_data["results"][0] == result_data
        
        # Verify status was updated to completed
        assert job_data["status"] == "completed"
    
    def test_add_job_result_multiple(self, sample_job_id_complex):
        """Test adding multiple results to a job."""
        result1 = {
            "url": "https://example.com",
            "status": "success",
            "html_content": "<html></html>"
        }
        
        result2 = {
            "url": "https://test.com",
            "status": "error",
            "error_message": "Connection failed"
        }
        
        # Add first result
        add_job_result(sample_job_id_complex, result1)
        job_data = jobs[sample_job_id_complex]
        assert job_data["completed_urls"] == 1
        assert job_data["status"] == "in_progress"
        
        # Add second result
        add_job_result(sample_job_id_complex, result2)
        job_data = jobs[sample_job_id_complex]
        assert job_data["completed_urls"] == 2
        assert job_data["status"] == "in_progress"
        
        # Add third result (should complete the job)
        result3 = {
            "url": "https://sample.org",
            "status": "success",
            "html_content": "<html></html>"
        }
        add_job_result(sample_job_id_complex, result3)
        job_data = jobs[sample_job_id_complex]
        assert job_data["completed_urls"] == 3
        assert job_data["status"] == "completed"
    
    def test_add_job_result_invalid_job_id(self):
        """Test result addition with invalid job ID."""
        result_data = {
            "url": "https://example.com",
            "status": "success",
            "html_content": "<html></html>"
        }
        
        # Function returns False for invalid job ID instead of raising KeyError
        result = add_job_result("non-existent-job-id", result_data)
        assert result is False
    
    def test_add_job_result_updates_timestamp(self, sample_job_id):
        """Test that result addition updates timestamp."""
        result_data = {
            "url": "https://example.com",
            "status": "success",
            "html_content": "<html></html>"
        }
        
        # Get original timestamp
        original_updated_at = jobs[sample_job_id]["updated_at"]
        
        # Add result
        add_job_result(sample_job_id, result_data)
        
        # Verify timestamp was updated
        new_updated_at = jobs[sample_job_id]["updated_at"]
        assert new_updated_at != original_updated_at


# =============================================================================
# FETCHING LOGIC TESTS
# =============================================================================

class TestFetchingLogic:
    """Test fetching logic functions."""
    
    @pytest.mark.asyncio
    async def test_fetch_single_url_with_semaphore_success(self, mock_browser):
        """Test successful single URL fetch."""
        # Mock the StealthBrowserToolkit class
        with patch('api.logic.StealthBrowserToolkit', return_value=mock_browser):
            result = await fetch_single_url_with_semaphore(
                url="https://example.com",
                semaphore=MagicMock(),
                proxies=["http://proxy.example.com:8080"],
                wait_min=1,
                wait_max=3
            )
        
        # Verify result structure
        assert result.url == "https://example.com"
        assert result.status == "success"
        assert result.html_content == "<html><body>Test content</body></html>"
        # Response time is 0 for mocked calls
        assert result.response_time_ms >= 0
        assert result.status_code is None
        assert result.error_message is None
    
    @pytest.mark.asyncio
    async def test_fetch_single_url_with_semaphore_error(self, mock_browser_error):
        """Test single URL fetch with error."""
        # Mock the browser pool to fail, forcing fallback to direct browser
        mock_pool = MagicMock()
        mock_pool.get_browser.side_effect = Exception("Pool error")
        
        with patch('api.logic.get_browser_pool', return_value=mock_pool):
            with patch('api.logic.StealthBrowserToolkit', return_value=mock_browser_error):
                result = await fetch_single_url_with_semaphore(
                    url="https://broken.com",
                    semaphore=MagicMock(),
                    proxies=[],
                    wait_min=1,
                    wait_max=3
                )
        
        # Verify result structure
        assert result.url == "https://broken.com"
        assert result.status == "error"
        assert result.html_content is None
        assert "Browser error" in result.error_message
        assert result.response_time_ms is not None
        assert result.status_code is None
    
    @pytest.mark.asyncio
    async def test_fetch_single_url_with_semaphore_no_proxies(self, mock_browser):
        """Test single URL fetch without proxies."""
        # Mock the StealthBrowserToolkit class
        with patch('api.logic.StealthBrowserToolkit', return_value=mock_browser):
            result = await fetch_single_url_with_semaphore(
                url="https://example.com",
                semaphore=MagicMock(),
                proxies=[],
                wait_min=1,
                wait_max=3
            )
        
        # Should still work without proxies
        assert result.status == "success"
    
    @pytest.mark.asyncio
    async def test_run_fetching_job_success(self, sample_job_id_complex, mock_browser):
        """Test successful job execution."""
        # Mock the StealthBrowserToolkit class
        with patch('api.logic.StealthBrowserToolkit', return_value=mock_browser):
            await run_fetching_job(sample_job_id_complex)
        
        # Verify job was completed
        job_data = jobs[sample_job_id_complex]
        assert job_data["status"] == "completed"
        assert job_data["completed_urls"] == 3
        assert len(job_data["results"]) == 3
        
        # Verify all results are successful
        for result in job_data["results"]:
            assert result["status"] == "success"
            assert result["html_content"] is not None
    
    @pytest.mark.asyncio
    async def test_run_fetching_job_with_errors(self, sample_job_id_complex, mock_browser_error):
        """Test job execution with some errors."""
        # Mock the browser pool to fail, forcing fallback to direct browser
        mock_pool = MagicMock()
        mock_pool.get_browser.side_effect = Exception("Pool error")
        
        with patch('api.logic.get_browser_pool', return_value=mock_pool):
            with patch('api.logic.StealthBrowserToolkit', return_value=mock_browser_error):
                await run_fetching_job(sample_job_id_complex)
        
        # Verify job was completed despite errors
        job_data = jobs[sample_job_id_complex]
        assert job_data["status"] == "completed"
        assert job_data["completed_urls"] == 3
        assert len(job_data["results"]) == 3
        
        # Verify all results are errors
        for result in job_data["results"]:
            assert result["status"] == "error"
            assert result["error_message"] is not None
    
    @pytest.mark.asyncio
    async def test_run_fetching_job_invalid_job_id(self):
        """Test job execution with invalid job ID."""
        # Function logs error and returns early for invalid job ID instead of raising KeyError
        await run_fetching_job("non-existent-job-id")
        # Should complete without raising exception
    
    @pytest.mark.asyncio
    async def test_run_fetching_job_status_transitions(self, sample_job_id_complex, mock_browser):
        """Test job status transitions during execution."""
        # Mock the StealthBrowserToolkit class
        with patch('api.logic.StealthBrowserToolkit', return_value=mock_browser):
            # Start the job
            await run_fetching_job(sample_job_id_complex)
        
        # Verify status transitions
        job_data = jobs[sample_job_id_complex]
        assert job_data["status"] == "completed"
        
        # Verify timestamps
        assert "started_at" in job_data
        assert "completed_at" in job_data
        
        started_at = datetime.fromisoformat(job_data["started_at"])
        completed_at = datetime.fromisoformat(job_data["completed_at"])
        assert completed_at > started_at


# =============================================================================
# EDGE CASES AND ERROR HANDLING TESTS
# =============================================================================

class TestEdgeCasesAndErrorHandling:
    """Test edge cases and error handling."""
    
    def test_job_store_isolation(self, sample_fetch_request_simple):
        """Test that jobs are isolated in the store."""
        # Create multiple jobs
        job_id1 = create_job(sample_fetch_request_simple)
        job_id2 = create_job(sample_fetch_request_simple)
        
        # Verify jobs are separate
        assert job_id1 != job_id2
        assert jobs[job_id1]["id"] == job_id1
        assert jobs[job_id2]["id"] == job_id2
    
    def test_concurrent_job_creation(self, sample_fetch_request_simple):
        """Test concurrent job creation (simulated)."""
        # Create jobs rapidly
        job_ids = []
        for _ in range(10):
            job_id = create_job(sample_fetch_request_simple)
            job_ids.append(job_id)
        
        # Verify all jobs were created successfully
        assert len(job_ids) == 10
        assert len(set(job_ids)) == 10  # All unique
        
        # Verify all jobs exist in store
        for job_id in job_ids:
            assert job_id in jobs
    
    def test_job_data_persistence(self, sample_job_id):
        """Test that job data persists across function calls."""
        # Update job status
        update_job_status(sample_job_id, "in_progress")
        
        # Verify data persists
        job_data = jobs[sample_job_id]
        assert job_data["status"] == "in_progress"
        
        # Add result
        result_data = {
            "url": "https://example.com",
            "status": "success",
            "html_content": "<html></html>"
        }
        add_job_result(sample_job_id, result_data)
        
        # Verify data still persists
        job_data = jobs[sample_job_id]
        assert job_data["status"] == "completed"
        assert len(job_data["results"]) == 1
    
    def test_invalid_result_data(self, sample_job_id):
        """Test handling of invalid result data."""
        # Try to add result with missing required fields
        invalid_result = {
            "url": "https://example.com"
            # Missing status field
        }
        
        # Function should handle invalid data gracefully
        result = add_job_result(sample_job_id, invalid_result)
        assert result is True  # Should still add the result
    
    def test_job_cleanup_after_completion(self, sample_job_id):
        """Test that completed jobs remain in store for retrieval."""
        # Complete the job
        result_data = {
            "url": "https://example.com",
            "status": "success",
            "html_content": "<html></html>"
        }
        add_job_result(sample_job_id, result_data)
        
        # Verify job still exists and is retrievable
        response = get_job_status(sample_job_id)
        assert response is not None
        assert response.status == "completed"
        assert response.is_finished 