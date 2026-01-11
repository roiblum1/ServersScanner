# ============================================================================
# Server Scanner Dashboard - Dockerfile
# Multi-stage build for production-ready container
# ============================================================================

# Build stage
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# ============================================================================
# Runtime stage
FROM python:3.11-slim

# Set metadata
LABEL maintainer="Server Scanner Dashboard"
LABEL description="FastAPI-based server monitoring dashboard"
LABEL version="1.0.0"

# Create non-root user (using default UID)
RUN useradd -m -s /bin/bash scanner && \
    mkdir -p /app && \
    chown -R scanner:scanner /app

# Set working directory
WORKDIR /app

# Add local bin to PATH (before switching user)
ENV PATH=/home/scanner/.local/bin:$PATH

# Copy Python dependencies from builder
COPY --from=builder /root/.local /home/scanner/.local

# Copy application code
COPY --chown=scanner:scanner . .

# Switch to non-root user
USER scanner

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/cache/status').read()"

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Run application directly with Python (web_ui.py has uvicorn.run() built-in)
CMD ["python", "src/web_ui.py", "--host", "0.0.0.0", "--port", "8000"]
