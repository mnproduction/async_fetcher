# Use a browser-ready base image
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# Install UV
RUN pip install uv

# Copy and install dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen
RUN uv run patchright install chromium

# Copy application code
COPY . .

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]