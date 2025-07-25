# Use lightweight Python base image
FROM python:3.13-slim

WORKDIR /app

# Install UV
RUN pip install uv

# Copy and install dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

# Copy application code
COPY . .

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]