#!/usr/bin/env python3
"""
Server startup script that properly configures the event loop policy for Windows.

This script ensures that the correct event loop policy is set before any other
asyncio code runs, which is critical for subprocess support on Windows.
"""

import platform
import asyncio
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def setup_event_loop_policy():
    """Set up the appropriate event loop policy for the current platform."""
    if platform.system() == "Windows":
        # On Windows, we must use WindowsProactorEventLoopPolicy for subprocess support
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        print("INFO: Windows Proactor event loop policy installed for subprocess support.")
    else:
        # On Unix systems, try to use uvloop for better performance
        try:
            import uvloop
            uvloop.install()
            print("INFO: uvloop installed for better performance on Unix systems.")
        except ImportError:
            print("INFO: uvloop not found, using default event loop policy.")

def main():
    """Main entry point for the server."""
    # Set up event loop policy first
    setup_event_loop_policy()
    
    # Import uvicorn after setting up the event loop policy
    import uvicorn
    
    # Start the server without reload to avoid subprocess issues
    print("Starting Async Web Fetching Service...")
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )

if __name__ == "__main__":
    main()
