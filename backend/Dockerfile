# Production Dockerfile for TitleTrust Backend
# Optimized for Google Cloud Run

FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app
# Crucial: Add the current directory to Python's search path
ENV PYTHONPATH="${PYTHONPATH}:/app"

# Install system dependencies required for Python packages
# OpenCV dependencies for newer Debian versions
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Update certificates
RUN update-ca-certificates

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY . .

# DEBUG: Verify content of main.py in the image
RUN echo "--- CHECKING MAIN.PY CONTENT ---" && cat main.py | head -n 15 && echo "--- END CHECK ---"

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Force standard SSL certificate paths for requests/google-auth
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

# Cloud Run will inject PORT environment variable (usually 8080)
# We configure gunicorn to listen on $PORT
ENV PORT=8080

# Expose the port (documentation only, Cloud Run uses $PORT)
EXPOSE 8080

# Use gunicorn with uvicorn workers for production performance
# --bind 0.0.0.0:$PORT binds to the Cloud Run injected port
# --workers 1 is recommended for Cloud Run (auto-scaling handles concurrency)
# --worker-class uvicorn.workers.UvicornWorker for async FastAPI support
# --timeout 330 for long-running requests (adjust as needed)
CMD exec gunicorn --bind 0.0.0.0:$PORT --workers 1 --worker-class uvicorn.workers.UvicornWorker --timeout 600 --graceful-timeout 600 main:app
