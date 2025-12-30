FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    fswebcam v4l-utils \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user with video group access
RUN adduser -u 5678 --disabled-password --gecos "" appuser && \
    adduser appuser video && \
    chown -R appuser /app

# Create data and models directories
RUN mkdir -p /app/data /app/models && \
    chown -R appuser /app/data /app/models

USER appuser

# Add user's local bin to PATH for pip-installed executables
ENV PATH="/home/appuser/.local/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src
ENV PORT=5000
ENV PIPER_CACHE=/app/models
ENV CONFIG_PATH=src/models.yml

EXPOSE 5000
EXPOSE 5678

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/health', timeout=5)" || exit 1

CMD ["python", "src/app.py"]
