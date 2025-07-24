#!/usr/bin/env python3
"""
Test the browser pool specifically to isolate any issues.
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

async def test_browser_pool():
    """Test the browser pool functionality."""
    print("🔍 Testing Browser Pool Functionality")
    print("="*60)
    
    try:
        from toolkit.browser_pool import get_browser_pool, shutdown_browser_pool
        
        print("1. Getting browser pool...")
        browser_pool = await get_browser_pool()
        print(f"✅ Browser pool obtained: {browser_pool}")
        print(f"   Available browsers: {len(browser_pool.available_browsers)}")
        print(f"   In-use browsers: {len(browser_pool.in_use_browsers)}")
        
        print("\n2. Testing browser acquisition...")
        async with browser_pool.get_browser() as browser:
            print(f"✅ Browser acquired: {browser}")
            print(f"   Browser type: {type(browser).__name__}")
            
            print("\n3. Testing browser functionality...")
            try:
                # Test with a simple, fast-loading page
                content = await browser.get_page_content("https://httpbin.org/html")
                print(f"✅ Content fetched successfully. Length: {len(content)} characters")
                
                # Extract some content to verify it's real
                if "Herman Melville" in content:
                    print("✅ Content verification passed (found expected text)")
                else:
                    print("⚠️  Content verification failed (expected text not found)")
                    
            except Exception as e:
                print(f"❌ Browser functionality test failed: {e}")
                import traceback
                traceback.print_exc()
        
        print("\n4. Testing multiple browser acquisitions...")
        tasks = []
        
        async def fetch_url(url, index):
            try:
                async with browser_pool.get_browser() as browser:
                    print(f"   Task {index}: Acquired browser")
                    content = await browser.get_page_content(url)
                    print(f"   Task {index}: Fetched {len(content)} characters from {url}")
                    return len(content)
            except Exception as e:
                print(f"   Task {index}: Failed - {e}")
                return 0
        
        # Test with multiple fast URLs
        test_urls = [
            "https://httpbin.org/html",
            "https://httpbin.org/json", 
            "https://httpbin.org/xml"
        ]
        
        for i, url in enumerate(test_urls, 1):
            tasks.append(fetch_url(url, i))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        print(f"✅ Multiple fetch results: {results}")
        
        print("\n5. Browser pool status after tests...")
        print(f"   Available browsers: {len(browser_pool.available_browsers)}")
        print(f"   In-use browsers: {len(browser_pool.in_use_browsers)}")
        
        print("\n6. Shutting down browser pool...")
        await shutdown_browser_pool()
        print("✅ Browser pool shut down successfully")
        
    except Exception as e:
        print(f"❌ Browser pool test failed: {e}")
        import traceback
        traceback.print_exc()

async def test_example_com_specifically():
    """Test example.com specifically since that's what failed."""
    print("\n" + "="*60)
    print("🎯 Testing example.com specifically")
    print("="*60)
    
    try:
        from toolkit.browser import StealthBrowserToolkit
        
        print("1. Testing example.com with different timeouts...")
        
        # Test with different timeout values
        timeouts = [30000, 60000, 90000]  # 30s, 60s, 90s
        
        for timeout in timeouts:
            print(f"\n   Testing with {timeout/1000}s timeout...")
            browser = StealthBrowserToolkit(headless=True, timeout=timeout)
            
            try:
                await browser.initialize()
                start_time = asyncio.get_event_loop().time()
                content = await browser.get_page_content("https://example.com")
                end_time = asyncio.get_event_loop().time()
                
                duration = end_time - start_time
                print(f"   ✅ Success with {timeout/1000}s timeout. Duration: {duration:.2f}s")
                print(f"   Content length: {len(content)} characters")
                break
                
            except Exception as e:
                print(f"   ❌ Failed with {timeout/1000}s timeout: {e}")
                
            finally:
                await browser.close()
        
        print("\n2. Testing alternative URLs...")
        test_urls = [
            "https://httpbin.org/html",
            "https://httpbin.org/json",
            "https://www.google.com",
            "https://example.org"  # Alternative to example.com
        ]
        
        browser = StealthBrowserToolkit(headless=True, timeout=60000)
        await browser.initialize()
        
        for url in test_urls:
            try:
                print(f"\n   Testing {url}...")
                start_time = asyncio.get_event_loop().time()
                content = await browser.get_page_content(url)
                end_time = asyncio.get_event_loop().time()
                
                duration = end_time - start_time
                print(f"   ✅ Success: {len(content)} chars in {duration:.2f}s")
                
            except Exception as e:
                print(f"   ❌ Failed: {e}")
        
        await browser.close()
        
    except Exception as e:
        print(f"❌ Example.com test failed: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """Main test function."""
    await test_browser_pool()
    await test_example_com_specifically()
    
    print("\n" + "="*60)
    print("🏁 Browser pool investigation complete")

if __name__ == "__main__":
    asyncio.run(main())
