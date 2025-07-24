#!/usr/bin/env python3
"""
Test script to replicate the exact curl request you provided.
"""

import asyncio
import httpx
import json

async def test_exact_curl_request():
    """Test the exact curl request provided."""
    
    # Exact request body from your curl command
    request_body = {
        "links": [
            "https://example.com"
        ],
        "options": {
            "proxies": [],
            "wait_min": 1,
            "wait_max": 15,
            "concurrency_limit": 5,
            "retry_count": 2
        }
    }
    
    print("Testing exact curl request...")
    print(f"Request body: {json.dumps(request_body, indent=2)}")
    print("\n" + "="*60)
    
    async with httpx.AsyncClient() as client:
        try:
            # Start the fetch job
            print("Sending POST request to /fetch/start...")
            response = await client.post(
                "http://localhost:8000/fetch/start",
                json=request_body,
                headers={
                    "accept": "application/json",
                    "Content-Type": "application/json"
                },
                timeout=30.0
            )
            
            print(f"Response Status: {response.status_code}")
            print(f"Response Headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"Response Body: {json.dumps(result, indent=2)}")
                
                job_id = result.get('job_id')
                if job_id:
                    print(f"\n✅ Job created successfully!")
                    print(f"Job ID: {job_id}")
                    print(f"Status: {result.get('status')}")
                    print(f"Details: {result.get('details')}")
                    
                    # Monitor the job status
                    print(f"\n📊 Monitoring job progress...")
                    for i in range(15):  # Check up to 15 times (30 seconds)
                        await asyncio.sleep(2)
                        
                        status_response = await client.get(f"http://localhost:8000/fetch/status/{job_id}")
                        status_data = status_response.json()
                        
                        status = status_data.get('status', 'unknown')
                        progress = status_data.get('progress_percentage', 0)
                        completed = status_data.get('completed_urls', 0)
                        total = status_data.get('total_urls', 0)
                        
                        print(f"  Check {i+1:2d}: {status:12s} | Progress: {progress:3.0f}% | URLs: {completed}/{total}")
                        
                        if status in ['completed', 'failed']:
                            print(f"\n🎉 Job finished with status: {status}")
                            
                            # Show results
                            results = status_data.get('results', [])
                            print(f"\nResults ({len(results)} URLs):")
                            for idx, result in enumerate(results, 1):
                                url = result.get('url', 'unknown')
                                result_status = result.get('status', 'unknown')
                                response_time = result.get('response_time_ms', 0)
                                
                                print(f"  {idx}. {url}")
                                print(f"     Status: {result_status}")
                                print(f"     Response Time: {response_time}ms")
                                
                                if result_status == 'success':
                                    html_length = len(result.get('html_content', ''))
                                    print(f"     HTML Content: {html_length} characters")
                                elif result_status == 'error':
                                    error_msg = result.get('error_message', 'No error message')
                                    error_type = result.get('error_type', 'Unknown')
                                    print(f"     Error Type: {error_type}")
                                    print(f"     Error Message: {error_msg}")
                                print()
                            
                            break
                    else:
                        print(f"\n⏰ Job still running after 30 seconds")
                        
                else:
                    print(f"❌ No job_id in response")
            else:
                print(f"❌ Request failed with status {response.status_code}")
                print(f"Response: {response.text}")
                
        except Exception as e:
            print(f"❌ Error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(test_exact_curl_request())
