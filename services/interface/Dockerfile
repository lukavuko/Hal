FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN adduser -u 5678 --disabled-password --gecos "" appuser && \
    chown -R appuser /app

# Create data directory for calibration persistence
RUN mkdir -p /app/data && chown appuser /app/data

USER appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

ENV PYTHONUNBUFFERED=1
ENV API_PORT=5050

EXPOSE 8000 5050

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/_stcore/health || exit 1

CMD ["streamlit", "run", "src/app.py", "--server.port=8000", "--server.address=0.0.0.0"]
