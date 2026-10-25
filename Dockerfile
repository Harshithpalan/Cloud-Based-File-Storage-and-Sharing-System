# Multi-stage / optimized Dockerfile for Cloud File Share
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    FLASK_ENV=production

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Create uploads directory
RUN mkdir -p uploads

# Expose container port
EXPOSE 8080

# Run with Gunicorn WSGI server
CMD exec gunicorn --bind :$PORT --workers 2 --threads 4 --timeout 60 "app:create_app('production')"
