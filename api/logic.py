"""
Business Logic for Job Management and Fetching Operations

This module provides the core business logic for the Async HTML Fetcher Service,
including job lifecycle management, result tracking, and coordination between
the API layer and the browser toolkit.

Key Components:
- In-memory job store for tracking job states and results
- Job creation and lifecycle management functions
- Result aggregation and status updates
- Comprehensive logging and error handling
- Fetch job runner with concurrency control

The job store uses a thread-safe in-memory dictionary to track all active jobs,
providing fast access to job status and results while maintaining data consistency.

Author: Async HTML Fetcher Service
Version: 1.0.0
"""

import asyncio
import random
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Union

from settings.logger import get_logger
from api.models import FetchRequest, FetchResponse, FetchResult, JobStatusResponse
from toolkit.browser import StealthBrowserToolkit

# Initialize logger for this module
logger = get_logger("api.logic")

# =============================================================================
# IN-MEMORY JOB STORE
# =============================================================================

# Global in-memory job store
# Structure: {job_id: job_data_dict}
jobs: Dict[str, Dict[str, Any]] = {}


# =============================================================================
# JOB DATA STRUCTURE DESIGN
# =============================================================================

"""
Job Data Structure Schema:

Each job in the in-memory store follows this structure:

{
    "id": str,                    # Unique job identifier (UUID)
    "status": str,                # Current status: "pending", "in_progress", "completed", "failed"
    "created_at": str,            # ISO format timestamp when job was created
    "updated_at": str,            # ISO format timestamp of last update
    "started_at": Optional[str],  # ISO format timestamp when processing started
    "completed_at": Optional[str], # ISO format timestamp when job completed
    "request": Dict,              # Serialized FetchRequest data
    "results": List[Dict],        # List of serialized FetchResult objects
    "total_urls": int,            # Total number of URLs to process
    "completed_urls": int,        # Number of URLs processed so far
    "error_message": Optional[str] # Job-level error message (if failed)
}

Key Features:
- Thread-safe operations (single-threaded async context)
- Automatic timestamp management
- Progress tracking with counters
- Serialized model data for persistence
- Comprehensive error tracking
"""


# =============================================================================
# JOB CREATION AND MANAGEMENT FUNCTIONS
# =============================================================================

def create_job(request: FetchRequest) -> str:
    """
    Create a new job and return its unique identifier.
    
    This function initializes a new job entry in the in-memory store with
    all required fields and default values. The job starts in "pending" status
    and will be updated as processing progresses.
    
    Args:
        request: FetchRequest object containing URLs and options
        
    Returns:
        str: Unique job identifier (UUID)
        
    Raises:
        ValueError: If request validation fails
        
    Example:
        ```python
        request = FetchRequest(links=["https://example.com"])
        job_id = create_job(request)
        print(f"Created job: {job_id}")
        ```
    """
    # Generate unique job ID
    job_id = str(uuid.uuid4())
    
    # Get current timestamp
    now = datetime.utcnow().isoformat()
    
    # Create job data structure
    job_data = {
        "id": job_id,
        "status": "pending",
        "created_at": now,
        "updated_at": now,
        "started_at": None,
        "completed_at": None,
        "request": request.model_dump(),  # Serialize request to dict
        "results": [],
        "total_urls": len(request.links),
        "completed_urls": 0,
        "error_message": None
    }
    
    # Store job in memory
    jobs[job_id] = job_data
    
    logger.info(
        "Created new job",
        job_id=job_id,
        total_urls=len(request.links),
        concurrency_limit=request.options.concurrency_limit,
        has_proxies=len(request.options.proxies) > 0
    )
    
    return job_id


def get_job_status(job_id: str) -> Optional[FetchResponse]:
    """
    Retrieve the current status and results of a job.
    
    This function converts the internal job data structure to a FetchResponse
    object that can be returned to API clients. It handles missing jobs gracefully
    by returning None.
    
    Args:
        job_id: Unique job identifier
        
    Returns:
        Optional[FetchResponse]: Job status and results, or None if job not found
        
    Example:
        ```python
        response = get_job_status("550e8400-e29b-41d4-a716-446655440000")
        if response:
            print(f"Job status: {response.status}")
            print(f"Progress: {response.progress_percentage}%")
        ```
    """
    if job_id not in jobs:
        logger.warning("Job not found", job_id=job_id)
        return None
    
    job = jobs[job_id]
    
    # Convert serialized results back to FetchResult objects
    results = []
    for result_data in job["results"]:
        try:
            result = FetchResult(**result_data)
            results.append(result)
        except Exception as e:
            logger.error("Failed to deserialize result", job_id=job_id, error=str(e))
            # Create error result for corrupted data
            results.append(FetchResult(
                url=result_data.get("url", "unknown"),
                status="error",
                error_message=f"Failed to deserialize result: {str(e)}"
            ))
    
    # Parse timestamps
    started_at = None
    completed_at = None
    
    if job["started_at"]:
        try:
            started_at = datetime.fromisoformat(job["started_at"])
        except ValueError:
            logger.warning("Invalid started_at timestamp", job_id=job_id)
    
    if job["completed_at"]:
        try:
            completed_at = datetime.fromisoformat(job["completed_at"])
        except ValueError:
            logger.warning("Invalid completed_at timestamp", job_id=job_id)
    
    # Create and return FetchResponse
    response = FetchResponse(
        job_id=job_id,
        status=job["status"],
        results=results,
        total_urls=job["total_urls"],
        completed_urls=job["completed_urls"],
        started_at=started_at,
        completed_at=completed_at
    )
    
    logger.debug(
        "Retrieved job status",
        job_id=job_id,
        status=job["status"],
        completed_urls=job["completed_urls"],
        total_urls=job["total_urls"]
    )
    
    return response


def update_job_status(job_id: str, status: str, error_message: Optional[str] = None) -> bool:
    """
    Update the status of a job and optionally set an error message.
    
    This function updates the job status and handles status-specific logic
    such as setting timestamps for job lifecycle events.
    
    Args:
        job_id: Unique job identifier
        status: New status ("pending", "in_progress", "completed", "failed")
        error_message: Optional error message for failed jobs
        
    Returns:
        bool: True if job was updated successfully, False if job not found
        
    Raises:
        ValueError: If status is invalid
        
    Example:
        ```python
        success = update_job_status("job123", "in_progress")
        if not success:
            print("Job not found")
        ```
    """
    if job_id not in jobs:
        logger.warning("Cannot update status - job not found", job_id=job_id, status=status)
        return False
    
    # Validate status
    valid_statuses = ["pending", "in_progress", "completed", "failed"]
    if status not in valid_statuses:
        raise ValueError(f"Invalid status: {status}. Must be one of: {valid_statuses}")
    
    job = jobs[job_id]
    old_status = job["status"]
    
    # Update status and timestamp
    job["status"] = status
    job["updated_at"] = datetime.utcnow().isoformat()
    
    # Handle status-specific logic
    if status == "in_progress" and old_status == "pending":
        # Job is starting - set started_at timestamp
        job["started_at"] = datetime.utcnow().isoformat()
        logger.info("Job started processing", job_id=job_id)
    
    elif status in ["completed", "failed"]:
        # Job is finishing - set completed_at timestamp
        job["completed_at"] = datetime.utcnow().isoformat()
        if status == "completed":
            logger.info("Job completed successfully", job_id=job_id)
        else:
            logger.info("Job failed", job_id=job_id, error_message=error_message)
    
    # Set error message if provided
    if error_message:
        job["error_message"] = error_message
    
    logger.info(
        "Updated job status",
        job_id=job_id,
        old_status=old_status,
        new_status=status,
        error_message=error_message
    )
    
    return True


def add_job_result(job_id: str, result: Union[FetchResult, Dict[str, Any]]) -> bool:
    """
    Add a result to a job and update completion counters.

    This function adds a new fetch result to the job and automatically
    updates the completion counter. It also checks if the job should be
    marked as completed when all URLs have been processed.

    Args:
        job_id: Unique job identifier
        result: FetchResult object or dict containing the fetch outcome

    Returns:
        bool: True if result was added successfully, False if job not found

    Example:
        ```python
        result = FetchResult(
            url="https://example.com",
            status="success",
            html_content="<html>...</html>"
        )
        success = add_job_result("job123", result)
        ```
    """
    if job_id not in jobs:
        # Handle both FetchResult objects and dicts
        url = result.url if hasattr(result, 'url') else result.get('url', 'unknown')
        logger.warning("Cannot add result - job not found", job_id=job_id, url=url)
        return False
    
    job = jobs[job_id]
    
    # Serialize result for storage
    if isinstance(result, FetchResult):
        result_data = result.model_dump()
    else:
        result_data = result
    
    # Add result to job
    job["results"].append(result_data)
    job["completed_urls"] += 1
    job["updated_at"] = datetime.utcnow().isoformat()
    
    # Check if job is complete
    if job["completed_urls"] >= job["total_urls"]:
        # All URLs processed - mark job as completed
        update_job_status(job_id, "completed")
    else:
        # Ensure job is in progress if it was pending
        if job["status"] == "pending":
            update_job_status(job_id, "in_progress")
    
            # Get URL and status for logging
        url = result.url if hasattr(result, 'url') else result.get('url', 'unknown')
        status = result.status if hasattr(result, 'status') else result.get('status', 'unknown')
        
        logger.info(
            "Added job result",
            job_id=job_id,
            url=url,
            status=status,
            completed_urls=job["completed_urls"],
            total_urls=job["total_urls"],
            progress_percentage=round((job["completed_urls"] / job["total_urls"]) * 100, 1)
        )
    
    return True


def delete_job(job_id: str) -> bool:
    """
    Remove a job from the in-memory store.
    
    This function permanently removes a job and all its data from memory.
    Use with caution as this operation cannot be undone.
    
    Args:
        job_id: Unique job identifier
        
    Returns:
        bool: True if job was deleted successfully, False if job not found
        
    Example:
        ```python
        success = delete_job("job123")
        if success:
            print("Job deleted successfully")
        ```
    """
    if job_id not in jobs:
        logger.warning("Cannot delete - job not found", job_id=job_id)
        return False
    
    job_status = jobs[job_id]["status"]
    del jobs[job_id]
    
    logger.info("Deleted job", job_id=job_id, status=job_status)
    return True


def get_all_jobs() -> List[Dict[str, Any]]:
    """
    Get a list of all jobs in the store.
    
    This function returns a list of all jobs with their basic information.
    Useful for monitoring and debugging purposes.
    
    Returns:
        List[Dict]: List of job summaries with basic information
        
    Example:
        ```python
        all_jobs = get_all_jobs()
        for job in all_jobs:
            print(f"Job {job['id']}: {job['status']}")
        ```
    """
    job_summaries = []
    
    for job_id, job_data in jobs.items():
        summary = {
            "id": job_id,
            "status": job_data["status"],
            "created_at": job_data["created_at"],
            "updated_at": job_data["updated_at"],
            "total_urls": job_data["total_urls"],
            "completed_urls": job_data["completed_urls"],
            "progress_percentage": round((job_data["completed_urls"] / job_data["total_urls"]) * 100, 1) if job_data["total_urls"] > 0 else 0
        }
        job_summaries.append(summary)
    
    logger.debug("Retrieved all jobs", count=len(job_summaries))
    return job_summaries


def cleanup_completed_jobs(max_age_hours: int = 24) -> int:
    """
    Remove completed jobs older than the specified age.
    
    This function helps manage memory usage by removing old completed jobs.
    Only jobs with "completed" or "failed" status are considered for cleanup.
    
    Args:
        max_age_hours: Maximum age in hours for completed jobs (default: 24)
        
    Returns:
        int: Number of jobs removed
        
    Example:
        ```python
        removed_count = cleanup_completed_jobs(max_age_hours=12)
        print(f"Removed {removed_count} old jobs")
        ```
    """
    cutoff_time = datetime.utcnow().timestamp() - (max_age_hours * 3600)
    jobs_to_remove = []
    
    for job_id, job_data in jobs.items():
        if job_data["status"] in ["completed", "failed"]:
            try:
                completed_at = datetime.fromisoformat(job_data["completed_at"])
                if completed_at.timestamp() < cutoff_time:
                    jobs_to_remove.append(job_id)
            except (ValueError, TypeError):
                # Invalid timestamp - remove the job
                jobs_to_remove.append(job_id)
    
    # Remove old jobs
    for job_id in jobs_to_remove:
        del jobs[job_id]
    
    if jobs_to_remove:
        logger.info(
            "Cleaned up old completed jobs",
            removed_count=len(jobs_to_remove),
            max_age_hours=max_age_hours
        )
    
    return len(jobs_to_remove)


# =============================================================================
# PROXY SELECTION HELPER FUNCTIONS
# =============================================================================

def select_random_proxy(proxies: List[str]) -> Optional[str]:
    """
    Select a random proxy from the provided list.
    
    This function encapsulates the proxy selection logic, making it easier
    to test and potentially enhance with more sophisticated selection
    strategies in the future.
    
    Args:
        proxies: List of available proxy URLs
        
    Returns:
        Optional[str]: Selected proxy URL or None if no proxies available
        
    Example:
        ```python
        proxies = ["http://proxy1:8080", "http://proxy2:8080"]
        proxy = select_random_proxy(proxies)
        ```
    """
    try:
        if not proxies:
            logger.debug("No proxies available, using direct connection")
            return None
        
        if len(proxies) == 1:
            logger.debug("Single proxy available", proxy=proxies[0])
            return proxies[0]
        
        selected_proxy = random.choice(proxies)
        logger.debug("Selected random proxy", proxy=selected_proxy, total_proxies=len(proxies))
        return selected_proxy
        
    except Exception as e:
        logger.error("Error selecting proxy", error=str(e), proxies_count=len(proxies) if proxies else 0)
        return None


# =============================================================================
# FETCHING FUNCTIONS
# =============================================================================

async def fetch_single_url_with_semaphore(
    url: str,
    semaphore: asyncio.Semaphore,
    proxies: List[str],
    wait_min: int,
    wait_max: int,
    retry_count: int = 1
) -> FetchResult:
    """
    Fetch a single URL with semaphore-controlled concurrency and proxy rotation.
    
    This function acquires a semaphore to limit concurrent fetches, selects
    a random proxy for each attempt, waits for a random interval, and fetches
    the URL using the StealthBrowserToolkit. It includes retry logic with
    different proxies for each attempt.
    
    Args:
        url: The URL to fetch
        semaphore: asyncio.Semaphore to control concurrency
        proxies: List of available proxy URLs
        wait_min: Minimum wait time in seconds
        wait_max: Maximum wait time in seconds
        retry_count: Number of retry attempts (default: 1)
        
    Returns:
        FetchResult: The result of the fetch operation
        
    Example:
        ```python
        semaphore = asyncio.Semaphore(5)
        result = await fetch_single_url_with_semaphore(
            "https://example.com", semaphore, ["http://proxy1:8080"], 1, 3, 2
        )
        ```
    """
    async with semaphore:
        # Try different proxies if retries are needed
        for attempt in range(retry_count + 1):
            # Select a random proxy if available
            # For retries, we want to ensure we don't use the same proxy twice in a row
            if attempt > 0 and len(proxies) > 1:
                # For retries, exclude the previously used proxy if possible
                previous_proxy = proxy if 'proxy' in locals() else None
                available_proxies = [p for p in proxies if p != previous_proxy]
                proxy = select_random_proxy(available_proxies) if available_proxies else select_random_proxy(proxies)
            else:
                proxy = select_random_proxy(proxies)
            
            # Calculate random wait time within range
            wait_time = random.randint(wait_min, wait_max)
            
            logger.info(
                "Fetching URL with semaphore", 
                url=url, 
                proxy=proxy, 
                wait_time=wait_time,
                attempt=attempt + 1,
                max_attempts=retry_count + 1
            )
            
            start_time = datetime.utcnow()
            
            try:
                # Use the StealthBrowserToolkit to fetch the URL
                async with StealthBrowserToolkit(headless=True) as browser:
                    result = await browser.fetch_url(url, proxy, wait_time)
                
                # Validate the result structure
                if not isinstance(result, dict):
                    raise ValueError(f"Invalid result type: {type(result)}")
                
                if "success" not in result:
                    raise ValueError("Result missing 'success' field")
                
                # Calculate response time
                end_time = datetime.utcnow()
                response_time_ms = int((end_time - start_time).total_seconds() * 1000)
                
                # If successful or this is the last attempt, return the result
                if result["success"] or attempt == retry_count:
                    # Log the final result
                    if result["success"]:
                        logger.info(
                            "Fetch completed successfully",
                            url=url,
                            proxy=proxy,
                            response_time_ms=response_time_ms,
                            status_code=result.get("status_code"),
                            attempt=attempt + 1,
                            max_attempts=retry_count + 1
                        )
                        return FetchResult(
                            url=url,
                            status="success",
                            html_content=result["html"],
                            response_time_ms=response_time_ms,
                            status_code=result.get("status_code")
                        )
                    else:
                        logger.error(
                            "Fetch failed after all attempts",
                            url=url,
                            proxy=proxy,
                            error=result["error"],
                            response_time_ms=response_time_ms,
                            status_code=result.get("status_code"),
                            attempts=retry_count + 1
                        )
                        return FetchResult(
                            url=url,
                            status="error",
                            error_message=result["error"],
                            response_time_ms=response_time_ms,
                            status_code=result.get("status_code")
                        )
                
                # If we get here, the fetch failed but we have more retries
                logger.warning(
                    "Fetch failed, retrying with different proxy", 
                    url=url, 
                    error=result["error"],
                    attempt=attempt + 1,
                    max_attempts=retry_count + 1
                )
                
                # Wait before retrying with exponential backoff
                retry_wait = wait_time * (2 ** attempt)  # Exponential backoff
                logger.info(
                    "Waiting before retry",
                    url=url,
                    wait_time=retry_wait,
                    attempt=attempt + 1,
                    max_attempts=retry_count + 1
                )
                await asyncio.sleep(retry_wait)
            
            except Exception as e:
                # Calculate response time for failed requests
                end_time = datetime.utcnow()
                response_time_ms = int((end_time - start_time).total_seconds() * 1000)
                
                # If this is the last attempt, return the error result
                if attempt == retry_count:
                    logger.error(
                        "All fetch attempts failed", 
                        url=url, 
                        error=str(e),
                        attempts=retry_count + 1
                    )
                    
                    return FetchResult(
                        url=url,
                        status="error",
                        error_message=f"All fetch attempts failed: {str(e)}",
                        response_time_ms=response_time_ms
                    )
                
                # Otherwise, log and continue to the next attempt
                logger.warning(
                    "Fetch attempt failed, retrying", 
                    url=url, 
                    error=str(e),
                    attempt=attempt + 1,
                    max_attempts=retry_count + 1
                )
                
                # Wait before retrying with exponential backoff
                retry_wait = wait_time * (2 ** attempt)  # Exponential backoff
                logger.info(
                    "Waiting before retry",
                    url=url,
                    wait_time=retry_wait,
                    attempt=attempt + 1,
                    max_attempts=retry_count + 1
                )
                await asyncio.sleep(retry_wait)


async def run_fetching_job(job_id: str) -> None:
    """
    Run a fetching job as a background task with concurrency control.
    
    This function orchestrates the concurrent fetching of URLs for a specific job.
    It extracts job options, creates a semaphore for concurrency control,
    processes URLs concurrently, and updates job status and results.
    
    Args:
        job_id: Unique job identifier
        
    Example:
        ```python
        # Start job processing in background
        asyncio.create_task(run_fetching_job("job123"))
        ```
    """
    if job_id not in jobs:
        logger.error("Job not found for processing", job_id=job_id)
        return
    
    # Update job status to in_progress
    update_job_status(job_id, "in_progress")
    
    job = jobs[job_id]
    request_data = job["request"]
    
    try:
        # Extract options from the request
        links = request_data["links"]
        options = request_data["options"]
        
        proxies = options.get("proxies", [])
        wait_min = max(0, options.get("wait_min", 1))
        wait_max = max(wait_min, options.get("wait_max", 3))
        concurrency_limit = min(20, max(1, options.get("concurrency_limit", 5)))
        retry_count = max(0, min(5, options.get("retry_count", 2)))  # Limit retries to 0-5
        
        logger.info(
            "Starting job processing",
            job_id=job_id,
            total_urls=len(links),
            concurrency_limit=concurrency_limit,
            wait_range=f"{wait_min}-{wait_max}s",
            proxy_count=len(proxies),
            retry_count=retry_count
        )
        
        # Create a semaphore to limit concurrency
        semaphore = asyncio.Semaphore(concurrency_limit)
        
        # Create tasks for each URL with retry logic
        tasks = [
            fetch_single_url_with_semaphore(url, semaphore, proxies, wait_min, wait_max, retry_count=retry_count)
            for url in links
        ]
        
        # Process URLs concurrently with controlled concurrency
        for task in asyncio.as_completed(tasks):
            try:
                result = await task
                add_job_result(job_id, result)
            except Exception as e:
                logger.error(
                    "Error processing URL task",
                    job_id=job_id,
                    error=str(e)
                )
                # Add a generic error result if we can't determine which URL failed
                error_result = FetchResult(
                    url="unknown",
                    status="error",
                    error_message=f"Task processing error: {str(e)}"
                )
                add_job_result(job_id, error_result)
    
    except Exception as e:
        logger.error(
            "Error running job",
            job_id=job_id,
            error=str(e)
        )
        update_job_status(job_id, "failed", str(e))


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_job_count() -> Dict[str, int]:
    """
    Get counts of jobs by status.
    
    Returns:
        Dict[str, int]: Count of jobs for each status
        
    Example:
        ```python
        counts = get_job_count()
        print(f"Pending: {counts['pending']}, In Progress: {counts['in_progress']}")
        ```
    """
    counts = {
        "pending": 0,
        "in_progress": 0,
        "completed": 0,
        "failed": 0,
        "total": len(jobs)
    }
    
    for job_data in jobs.values():
        status = job_data["status"]
        if status in counts:
            counts[status] += 1
    
    return counts


def is_job_finished(job_id: str) -> bool:
    """
    Check if a job is in a terminal state (completed or failed).
    
    Args:
        job_id: Unique job identifier
        
    Returns:
        bool: True if job is completed or failed, False otherwise
    """
    if job_id not in jobs:
        return False
    
    return jobs[job_id]["status"] in ["completed", "failed"]


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'create_job',
    'get_job_status',
    'update_job_status',
    'add_job_result',
    'delete_job',
    'get_all_jobs',
    'cleanup_completed_jobs',
    'get_job_count',
    'is_job_finished',
    'fetch_single_url_with_semaphore',
    'run_fetching_job'
] 