### Product Specifications Document (PRD): Async HTML Fetcher Service (Version 3)

#### **# Overview**

The Async Fetcher is a high-performance, standalone FastAPI microservice for asynchronous HTML fetching. It solves the problem of efficiently and reliably scraping content from modern, dynamic, and protected websites that often employ anti-bot measures. The service is designed for internal systems that need to fetch HTML content from a list of URLs without handling the complexities of browser automation, proxy management, and concurrency.

#### **# Core Features**

*   **Stealth Browser Automation**: Exclusively utilizes **Patchright**, a stealth-focused browser automation library, via the `StealthBrowserToolkit` to render JavaScript and bypass common anti-bot mechanisms.
*   **Asynchronous Job Processing**: Employs a non-blocking, job-based workflow. Clients submit a list of links and receive a `job_id` instantly, polling for results later.
*   **Configurable Concurrency**: Allows users to specify the number of parallel browser instances to balance speed against server resource consumption.
*   **Proxy Rotation**: Supports a list of proxies, which are assigned randomly to each URL request to prevent IP-based blocking.
*   **Robust Error Reporting**: Captures and reports errors on a per-URL basis without crashing the entire job, providing clear feedback on failures.
*   **Standardized JSON Output**: Delivers structured, predictable JSON responses for easy integration with other services, powered by Pydantic models.
*   **Structured Logging**: Provides detailed, machine-readable JSON logs for tracking job progress and debugging issues, powered by **structlog**.
*   **Resource Management**: Ensures each browser task runs in an isolated context and cleans up resources automatically to prevent memory leaks.

#### **# User Experience**

The service targets internal developers and services that need to:
- Scrape HTML content from JavaScript-heavy or protected websites.
- Submit large lists of URLs for fetching without blocking their own processes.
- Customize scraping behavior (e.g., wait times, proxies) on a per-request basis.

**Key user flows are API-driven:**
1.  **Job Submission:** An internal service sends a `POST` request to `/fetch/start` with a list of links and optional configurations.
2.  **Job Acceptance:** The service validates the request, accepts the job, and immediately returns a `202 Accepted` response with a unique `job_id`.
3.  **Status Polling:** The client service uses the `job_id` to periodically send `GET` requests to the `/fetch/status/{job_id}` endpoint.
4.  **Result Retrieval:** The status endpoint returns the current job status (`pending`, `running`, `completed`). Once completed, the response includes the full list of fetch results.

#### **# Technical Architecture**

##### **System Components**
*   **FastAPI Application (`api/main.py`)**: The main entry point. Defines API endpoints, handles request validation, and manages background tasks.
*   **Job & Task Logic (`api/logic.py`)**:
    *   **Job Store:** A simple in-memory dictionary for managing the state and results of all jobs.
    *   **Job Runner:** The `run_fetching_job` function orchestrates the entire fetching process.
    *   **Concurrency Manager:** An `asyncio.Semaphore` to enforce the user-defined concurrency limit.
*   **Browser Engine (`toolkit/browser.py`)**: The `StealthBrowserToolkit` class, which manages the lifecycle of **Patchright** browser instances.
*   **Structured Logging (`settings/logger.py`)**: A `structlog`-based logger configured to output JSON for easy parsing by log aggregators.

##### **Data Models (`api/models.py`)**
*   **`FetchRequest`**: Pydantic model defining the input structure, including `links` and `options`.
*   **`FetchOptions`**: Pydantic model for user-configurable settings.
*   **`FetchResponse`**: Pydantic model for the final job status and results.
*   **`FetchResult`**: Pydantic model for the outcome of a single URL fetch.

##### **APIs and Integrations**
*   **Web Framework**: **FastAPI**.
*   **Browser Automation**: **Patchright**.
*   **Data Validation**: **Pydantic**.
*   **Logging**: **structlog**.

##### **Infrastructure Requirements**
*   **Python 3.13+**
*   FastAPI and Uvicorn.
*   **Patchright** and its browser dependencies (`patchright install`).
*   **Optional Future Upgrade**: Redis for a persistent, distributed job store.

#### **# Development Roadmap**

##### **Phase 1: Core Foundation (MVP)**
-   [x] Set up the FastAPI project structure.
-   [x] Decouple and integrate the `StealthBrowserToolkit` using **Patchright**.
-   [x] Configure **structlog** for JSON-formatted, structured logging.
-   [x] Implement the `/fetch/start` and `/fetch/status/{job_id}` endpoints.
-   [x] Implement the in-memory dictionary for job state management.
-   [x] Use FastAPI's `BackgroundTasks` to run jobs asynchronously.
-   [x] Implement `asyncio.Semaphore` for user-configurable concurrency limiting.
-   [x] Implement random proxy rotation.
-   [x] Create unit tests for API endpoints and core logic.

##### **Phase 2: Robustness & Usability**
-   [ ] Replace the in-memory job store with a **Redis** backend for persistence.
-   [ ] Add a `/jobs` endpoint to list recent jobs and their statuses.
-   [ ] Implement an optional `webhook_url` in `FetchOptions` to notify a client service when a job is complete.

##### **Phase 3: Enterprise Features**
-   [ ] Implement simple API key authentication for security.
-   [ ] Integrate with Prometheus for exporting performance metrics.
-   [ ] Add a `/fetch/cancel/{job_id}` endpoint to terminate a running job.

#### **# Code Implementation Plan**

Here is the updated code for each file, now reflecting the use of **Patchright** and **structlog**.

#### `async_fetcher/requirements.txt`

```
fastapi
uvicorn[standard]
# Use patchright instead of playwright
patchright
fake-useragent
# Use structlog instead of loguru
structlog
pydantic
```

#### `async_fetcher/settings/logger.py`

```python
import sys
import structlog

def setup_logger():
    """Configures structlog for JSON output."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ],
        logger_factory=structlog.PrintLoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(min_level=0), # Change min_level as needed (DEBUG=0, INFO=1)
        cache_logger_on_first_use=True,
    )
    return structlog.get_logger()

logger = setup_logger()
```

#### `async_fetcher/toolkit/browser.py`
*(This is the `StealthBrowserToolkit` adapted for Patchright and structlog)*

```python
import asyncio
import random
from typing import Dict, Any, Optional

try:
    # Use Patchright as the primary import
    from patchright.async_api import async_patchright, Browser, Page
except ImportError:
    raise ImportError("Patchright is not installed. Please install it with: pip install patchright")

from fake_useragent import UserAgent
from settings.logger import logger

class StealthBrowserToolkit:
    """A streamlined toolkit for browser automation with stealth capabilities using Patchright."""

    def __init__(
        self,
        headless: bool = True,
        user_agent: str = None,
        proxy: Dict[str, Any] = None,
        wait_min: int = 1,
        wait_max: int = 3,
        timeout: int = 60000
    ):
        self.headless = headless
        self.proxy = proxy
        self.wait_min = wait_min
        self.wait_max = wait_max
        self.timeout = timeout
        self.user_agent = self._get_user_agent(user_agent)
        self.patchright = None
        self.browser = None
        self.log = logger.bind(service="StealthBrowserToolkit")

    def _get_user_agent(self, user_agent: str) -> str:
        if user_agent:
            return user_agent
        try:
            return UserAgent().random
        except Exception as e:
            self.log.warning("get_user_agent_failed", error=str(e))
            return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

    async def init_browser(self) -> bool:
        try:
            self.patchright = await async_patchright().start()
            launch_options = {
                "headless": self.headless,
                "channel": "chrome",
                "args": ["--disable-blink-features=AutomationControlled"]
            }
            self.browser: Browser = await self.patchright.chromium.launch(**launch_options)
            self.log.info("browser_initialized")
            return True
        except Exception as e:
            self.log.error("browser_launch_error", error=str(e))
            return False

    async def get_page_content(self, url: str) -> Optional[str]:
        if not self.browser:
            raise RuntimeError("Browser is not initialized. Call init_browser() first.")

        context = None
        try:
            context_options = {"user_agent": self.user_agent}
            if self.proxy:
                context_options["proxy"] = self.proxy

            context = await self.browser.new_context(**context_options)
            page: Page = await context.new_page()
            await page.goto(url, timeout=self.timeout, wait_until='domcontentloaded')

            await asyncio.sleep(random.uniform(self.wait_min, self.wait_max))
            
            content = await page.content()
            if await self._is_challenge_page(page, content):
                 self.log.warning("challenge_page_detected", url=url)
                 await asyncio.sleep(10) # Wait for JS challenges
                 content = await page.content() # Get content again
                 if await self._is_challenge_page(page, content):
                     raise RuntimeError(f"CAPTCHA or challenge page detected at {url} that could not be bypassed.")

            return content
        finally:
            if context:
                await context.close()

    async def _is_challenge_page(self, page: Page, content: str) -> bool:
        title = (await page.title() or "").lower()
        content_lower = content.lower()
        challenge_keywords = ["just a moment", "checking your browser", "cloudflare", "challenge-running", "ddos protection", "captcha"]
        if any(keyword in title for keyword in challenge_keywords) or any(keyword in content_lower for keyword in challenge_keywords):
            return True
        return False

    async def close(self):
        if self.browser:
            await self.browser.close()
        if self.patchright:
            await self.patchright.stop()
```

#### Other Files (`api/logic.py`, `api/main.py`)
The code for `api/logic.py` and `api/main.py` remains the same as in the previous version, but now it will correctly use the **Patchright**-based `StealthBrowserToolkit` and log messages using **structlog**. The logger calls `logger.info(...)` will now produce structured JSON logs.

#### Setup and Run Instructions (Updated)

1.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Install Patchright Browsers:**
    ```bash
    patchright install
    ```

3.  **Run the API Server:**
    ```bash
    uvicorn api.main:app --reload
    ```
