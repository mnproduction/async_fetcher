#!/usr/bin/env python3
"""
Test the exact original curl command that was requested.
"""

import asyncio
import httpx
import json

async def test_original_curl():
    """Test the exact original curl command."""
    print("🎯 Testing Original Curl Command")
    print("="*60)
    
    # Exact request from the original curl command
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
    
    print("Original curl command equivalent:")
    print("curl -X 'POST' \\")
    print("  'http://localhost:8000/fetch/start' \\")
    print("  -H 'accept: application/json' \\")
    print("  -H 'Content-Type: application/json' \\")
    print("  -d '{")
    print('  "links": [')
    print('    "https://example.com"')
    print('  ],')
    print('  "options": {')
    print('    "proxies": [],')
    print('    "wait_min": 1,')
    print('    "wait_max": 15,')
    print('    "concurrency_limit": 5,')
    print('    "retry_count": 2')
    print('  }')
    print("}'")
    
    print(f"\nRequest body: {json.dumps(request_body, indent=2)}")
    print("\n" + "="*60)
    
    async with httpx.AsyncClient() as client:
        try:
            print("Sending POST request...")
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
            
            if response.status_code == 200:
                result = response.json()
                job_id = result.get('job_id')
                status_url = result.get('status_url')
                
                print(f"✅ Job created successfully!")
                print(f"Job ID: {job_id}")
                print(f"Status URL: {status_url}")
                
                print(f"\nMonitoring job progress...")
                for i in range(20):  # Monitor for up to 40 seconds
                    await asyncio.sleep(2)
                    
                    status_response = await client.get(f"http://localhost:8000/fetch/status/{job_id}")
                    status_data = status_response.json()
                    
                    status = status_data.get('status')
                    progress = status_data.get('progress_percentage', 0)
                    
                    print(f"  Check {i+1:2d}: {status:12s} | Progress: {progress:3.0f}%")
                    
                    if status in ['completed', 'failed']:
                        print(f"\n🎉 Job finished with status: {status}")
                        
                        results = status_data.get('results', [])
                        print(f"\nResults ({len(results)} URLs):")
                        
                        for idx, result in enumerate(results, 1):
                            url = result.get('url')
                            result_status = result.get('status')
                            response_time = result.get('response_time_ms', 0)
                            
                            print(f"  {idx}. {url}")
                            print(f"     Status: {result_status}")
                            print(f"     Response Time: {response_time}ms")
                            
                            if result_status == 'success':
                                html_length = len(result.get('html_content', ''))
                                print(f"     ✅ HTML Content: {html_length} characters")
                                
                                # Show a snippet of the content
                                content = result.get('html_content', '')
                                if content:
                                    snippet = content[:200] + "..." if len(content) > 200 else content
                                    print(f"     Content snippet: {snippet}")
                                    
                            elif result_status == 'error':
                                error_msg = result.get('error_message', 'No error message')
                                error_type = result.get('error_type', 'Unknown')
                                print(f"     ❌ Error Type: {error_type}")
                                print(f"     Error Message: {error_msg}")
                        
                        # Show job summary
                        total_urls = status_data.get('total_urls', 0)
                        completed_urls = status_data.get('completed_urls', 0)
                        success_rate = (completed_urls / total_urls * 100) if total_urls > 0 else 0
                        
                        print(f"\n📊 Job Summary:")
                        print(f"     Total URLs: {total_urls}")
                        print(f"     Completed: {completed_urls}")
                        print(f"     Success Rate: {success_rate:.1f}%")
                        
                        if status == 'completed' and success_rate == 100:
                            print(f"\n🎉 SUCCESS! Original curl command works perfectly!")
                            return True
                        else:
                            print(f"\n⚠️  Job completed but with issues.")
                            return False
                        
                        break
                else:
                    print(f"\n⏰ Job still running after 40 seconds")
                    return False
                    
            else:
                print(f"❌ Request failed: {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = asyncio.run(test_original_curl())
    if success:
        print("\n🎉 All tests passed! The original curl command works perfectly!")
    else:
        print("\n❌ Test failed.")
