FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 curl \
    build-essential curl git \
    && rm -rf /var/lib/apt/lists/*
# software-properties-common

# Create non-root user
RUN adduser -u 5678 --disabled-password --gecos "" appuser && \
    chown -R appuser /app

# Create data directory for calibration persistence
RUN mkdir -p /app/data && chown appuser /app/data

USER appuser

# Add user's local bin to PATH for pip-installed executables
ENV PATH="/home/appuser/.local/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

ENV PYTHONUNBUFFERED=1
ENV API_PORT=5050

EXPOSE 8501 5050

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "src/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
