#!/usr/bin/env python3
"""
Test the API with debug logging to see what's happening.
"""

import asyncio
import httpx
import json

async def test_api_debug():
    """Test the API with debug logging."""
    print("🔍 Testing API with Debug Logging")
    print("="*60)
    
    request_body = {
        "links": ["https://example.com"],
        "options": {
            "proxies": [],
            "wait_min": 1,
            "wait_max": 3,
            "concurrency_limit": 1,
            "retry_count": 1
        }
    }
    
    print(f"Request: {json.dumps(request_body, indent=2)}")
    
    async with httpx.AsyncClient() as client:
        try:
            print("\n1. Sending request...")
            response = await client.post(
                "http://localhost:8000/fetch/start",
                json=request_body,
                timeout=30.0
            )
            
            print(f"Response Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                job_id = result.get('job_id')
                print(f"Job ID: {job_id}")
                
                print("\n2. Monitoring job (with detailed status)...")
                for i in range(15):
                    await asyncio.sleep(2)
                    
                    status_response = await client.get(f"http://localhost:8000/fetch/status/{job_id}")
                    status_data = status_response.json()
                    
                    status = status_data.get('status')
                    progress = status_data.get('progress_percentage', 0)
                    
                    print(f"   Check {i+1:2d}: {status:12s} | Progress: {progress:3.0f}%")
                    
                    if status in ['completed', 'failed']:
                        print(f"\n3. Job finished with status: {status}")
                        
                        results = status_data.get('results', [])
                        for idx, result in enumerate(results, 1):
                            print(f"\n   Result {idx}:")
                            print(f"     URL: {result.get('url')}")
                            print(f"     Status: {result.get('status')}")
                            print(f"     Response Time: {result.get('response_time_ms')}ms")
                            
                            if result.get('status') == 'error':
                                print(f"     Error Type: {result.get('error_type')}")
                                print(f"     Error Message: {result.get('error_message')}")
                            elif result.get('status') == 'success':
                                html_length = len(result.get('html_content', ''))
                                print(f"     HTML Length: {html_length} characters")
                        
                        break
                else:
                    print("\n⏰ Job still running after 30 seconds")
                    
            else:
                print(f"❌ Request failed: {response.status_code}")
                print(f"Response: {response.text}")
                
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_api_debug())
