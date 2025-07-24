#!/usr/bin/env python3
"""
Simple test script to verify the API is working correctly.
"""

import asyncio
import httpx
import json

async def test_health():
    """Test the health endpoint."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8000/health")
        print(f"Health check: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200

async def test_fetch():
    """Test the fetch endpoint."""
    async with httpx.AsyncClient() as client:
        # Start a fetch job
        fetch_request = {
            "links": ["https://httpbin.org/html", "https://httpbin.org/json"],
            "options": {
                "concurrency_limit": 2,
                "wait_min": 1,
                "wait_max": 2
            }
        }
        
        print("Starting fetch job...")
        response = await client.post(
            "http://localhost:8000/fetch/start",
            json=fetch_request,
            timeout=30.0
        )
        
        print(f"Fetch start: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"Job ID: {result['job_id']}")
            print(f"Status URL: {result['status_url']}")
            
            # Check job status
            job_id = result['job_id']
            print(f"\nChecking job status...")
            
            for i in range(10):  # Check up to 10 times
                await asyncio.sleep(2)
                status_response = await client.get(f"http://localhost:8000/fetch/status/{job_id}")
                status_data = status_response.json()
                
                print(f"Attempt {i+1}: Status = {status_data['status']}, Progress = {status_data.get('progress_percentage', 0)}%")

                # Check if job is finished (completed or failed)
                is_finished = status_data['status'] in ['completed', 'failed']
                if is_finished:
                    print(f"Job completed!")
                    print(f"Results: {len(status_data['results'])} URLs processed")
                    for result in status_data['results']:
                        print(f"  - {result['url']}: {result['status']}")
                        if result['status'] == 'success':
                            print(f"    HTML length: {len(result['html_content'])} characters")
                    break
            
            return True
        else:
            print(f"Error: {response.text}")
            return False

async def main():
    """Main test function."""
    print("Testing Async Web Fetching Service...")
    
    # Test health endpoint
    health_ok = await test_health()
    if not health_ok:
        print("Health check failed!")
        return
    
    print("\n" + "="*50)
    
    # Test fetch endpoint
    fetch_ok = await test_fetch()
    if fetch_ok:
        print("\nAll tests passed!")
    else:
        print("\nFetch test failed!")

if __name__ == "__main__":
    asyncio.run(main())
