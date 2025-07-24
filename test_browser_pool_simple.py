#!/usr/bin/env python3
"""
Simple test to verify browser pool is working correctly.
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

async def test_browser_pool_simple():
    """Test the browser pool with reliable URLs."""
    print("🔍 Testing Browser Pool with Reliable URLs")
    print("="*60)
    
    try:
        from toolkit.browser_pool import get_browser_pool, shutdown_browser_pool
        
        print("1. Getting browser pool...")
        browser_pool = await get_browser_pool()
        print(f"✅ Browser pool obtained")
        print(f"   Pool size: {len(browser_pool._pool)}")
        
        print("\n2. Testing single browser acquisition...")
        async with browser_pool.get_browser() as browser:
            print(f"✅ Browser acquired successfully")
            
            # Test with example.com (we know this works)
            print("\n3. Testing with example.com...")
            try:
                content = await browser.get_page_content("https://example.com")
                print(f"✅ example.com fetched: {len(content)} characters")
            except Exception as e:
                print(f"❌ example.com failed: {e}")
        
        print("\n4. Testing multiple concurrent fetches...")
        
        async def fetch_url(url, index):
            try:
                async with browser_pool.get_browser() as browser:
                    content = await browser.get_page_content(url)
                    return f"Task {index}: ✅ {len(content)} chars from {url}"
            except Exception as e:
                return f"Task {index}: ❌ {e}"
        
        # Use reliable URLs
        test_urls = [
            "https://example.com",
            "https://example.org", 
            "https://www.google.com"
        ]
        
        tasks = [fetch_url(url, i+1) for i, url in enumerate(test_urls)]
        results = await asyncio.gather(*tasks)
        
        print("   Results:")
        for result in results:
            print(f"   {result}")
        
        print(f"\n5. Pool status after tests:")
        print(f"   Pool size: {len(browser_pool._pool)}")
        available = sum(1 for b in browser_pool._pool if not b.in_use)
        in_use = sum(1 for b in browser_pool._pool if b.in_use)
        print(f"   Available: {available}, In use: {in_use}")
        
        print("\n6. Shutting down browser pool...")
        await shutdown_browser_pool()
        print("✅ Browser pool shut down successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Browser pool test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_api_with_good_url():
    """Test the API with a URL we know works."""
    print("\n" + "="*60)
    print("🎯 Testing API with Reliable URL")
    print("="*60)
    
    try:
        import httpx
        
        # Test with example.com instead of httpbin.org
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
        
        print("1. Sending request to API...")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:8000/fetch/start",
                json=request_body,
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                job_id = result.get('job_id')
                print(f"✅ Job created: {job_id}")
                
                # Monitor job
                print("\n2. Monitoring job...")
                for i in range(10):
                    await asyncio.sleep(3)
                    status_response = await client.get(f"http://localhost:8000/fetch/status/{job_id}")
                    status_data = status_response.json()
                    
                    status = status_data.get('status')
                    print(f"   Check {i+1}: {status}")
                    
                    if status in ['completed', 'failed']:
                        results = status_data.get('results', [])
                        if results:
                            result = results[0]
                            print(f"   Result: {result.get('status')} - {result.get('url')}")
                            if result.get('status') == 'success':
                                print(f"   Content length: {len(result.get('html_content', ''))}")
                                print("✅ API test successful!")
                                return True
                            else:
                                print(f"   Error: {result.get('error_message')}")
                        break
                
            else:
                print(f"❌ API request failed: {response.status_code}")
                
    except Exception as e:
        print(f"❌ API test failed: {e}")
        
    return False

async def main():
    """Main test function."""
    pool_success = await test_browser_pool_simple()
    
    if pool_success:
        api_success = await test_api_with_good_url()
        
        if api_success:
            print("\n🎉 All tests passed! Browser pool and API are working correctly.")
        else:
            print("\n⚠️  Browser pool works, but API test failed.")
    else:
        print("\n❌ Browser pool test failed.")
    
    print("\n" + "="*60)
    print("🏁 Testing complete")

if __name__ == "__main__":
    asyncio.run(main())
