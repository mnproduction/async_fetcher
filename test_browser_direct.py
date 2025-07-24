#!/usr/bin/env python3
"""
Direct test of Patchright browser functionality to isolate the issue.
"""

import asyncio
import platform
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

async def test_patchright_direct():
    """Test Patchright directly without our wrapper."""
    print("Testing Patchright directly...")
    print(f"Platform: {platform.system()}")
    print(f"Python version: {sys.version}")
    
    try:
        # Test 1: Import patchright
        print("\n1. Testing patchright import...")
        from patchright.async_api import async_playwright
        print("✅ Patchright imported successfully")
        
        # Test 2: Start playwright
        print("\n2. Testing playwright startup...")
        playwright = await async_playwright().start()
        print("✅ Playwright started successfully")
        
        # Test 3: Launch browser with minimal options
        print("\n3. Testing browser launch (minimal options)...")
        try:
            browser = await playwright.chromium.launch(headless=True)
            print("✅ Browser launched successfully with minimal options")
            await browser.close()
        except Exception as e:
            print(f"❌ Browser launch failed with minimal options: {e}")
            print(f"Error type: {type(e).__name__}")
            
        # Test 4: Launch browser with our stealth args
        print("\n4. Testing browser launch (with stealth args)...")
        stealth_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-setuid-sandbox",
            "--disable-infobars",
            "--disable-popup-blocking",
            "--disable-notifications",
            "--disable-web-security",
        ]
        
        try:
            browser = await playwright.chromium.launch(
                headless=True,
                args=stealth_args
            )
            print("✅ Browser launched successfully with stealth args")
            
            # Test 5: Create context and page
            print("\n5. Testing context and page creation...")
            context = await browser.new_context()
            page = await context.new_page()
            print("✅ Context and page created successfully")
            
            # Test 6: Navigate to a simple page
            print("\n6. Testing navigation...")
            await page.goto("https://example.com", timeout=30000)
            title = await page.title()
            print(f"✅ Navigation successful. Page title: {title}")
            
            # Test 7: Get page content
            print("\n7. Testing content extraction...")
            content = await page.content()
            print(f"✅ Content extracted. Length: {len(content)} characters")
            
            await context.close()
            await browser.close()
            
        except Exception as e:
            print(f"❌ Browser launch failed with stealth args: {e}")
            print(f"Error type: {type(e).__name__}")
            import traceback
            traceback.print_exc()
            
        # Test 8: Check browser installation
        print("\n8. Testing browser installation...")
        try:
            # Try to get browser executable path
            browser_path = playwright.chromium.executable_path
            print(f"✅ Browser executable path: {browser_path}")
        except Exception as e:
            print(f"❌ Could not get browser path: {e}")
            
        await playwright.stop()
        print("✅ Playwright stopped successfully")
        
    except ImportError as e:
        print(f"❌ Failed to import patchright: {e}")
        print("Try: pip install patchright")
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

async def test_our_browser_wrapper():
    """Test our browser wrapper."""
    print("\n" + "="*60)
    print("Testing our browser wrapper...")
    
    try:
        from toolkit.browser import StealthBrowserToolkit
        
        print("\n1. Creating StealthBrowserToolkit instance...")
        browser = StealthBrowserToolkit(headless=True)
        print("✅ StealthBrowserToolkit created")
        
        print("\n2. Initializing browser...")
        success = await browser.initialize()
        print(f"✅ Browser initialization result: {success}")
        
        if success:
            print("\n3. Testing page content fetch...")
            try:
                content = await browser.get_page_content("https://example.com")
                print(f"✅ Content fetched. Length: {len(content)} characters")
            except Exception as e:
                print(f"❌ Content fetch failed: {e}")
                import traceback
                traceback.print_exc()
        
        print("\n4. Closing browser...")
        await browser.close()
        print("✅ Browser closed successfully")
        
    except Exception as e:
        print(f"❌ Browser wrapper test failed: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """Main test function."""
    print("🔍 Investigating Patchright Browser Issues")
    print("="*60)
    
    await test_patchright_direct()
    await test_our_browser_wrapper()
    
    print("\n" + "="*60)
    print("🏁 Browser investigation complete")

if __name__ == "__main__":
    asyncio.run(main())
