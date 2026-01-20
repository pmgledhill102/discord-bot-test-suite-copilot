# Build stage
FROM python:3.13-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libffi-dev \
        && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt

# Runtime stage
FROM python:3.13-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY app.py .

# Update PATH to include user site-packages
ENV PATH=/root/.local/bin:$PATH

# Expose port
EXPOSE 8080

# Run with gunicorn for production
RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host files.pythonhosted.org gunicorn==23.0.0

# Use gunicorn with proper worker configuration
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "2", "--timeout", "60", "--preload", "app:app"]
