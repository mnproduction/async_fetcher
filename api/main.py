from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import models to verify they work correctly

# Import and test structured logger
from settings.logger import get_logger

logger = get_logger("api.main")

app = FastAPI(
    title="Async Web Fetching Service",
    description="A service for asynchronously fetching web content using stealth browsers",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    logger.info("Root endpoint accessed", endpoint="/", method="GET")
    return {"message": "Async Web Fetching Service API"}

@app.on_event("startup")
async def startup_event():
    logger.info("FastAPI application starting up", service="Async Web Fetching Service")

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting development server", host="0.0.0.0", port=8000)
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True) 