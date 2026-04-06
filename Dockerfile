FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
  && rm -rf /var/lib/apt/lists/*

# Install Python dependencies before copying source so layers are cached.
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[postgres]"

# Copy source
COPY src/ src/

# Re-run install to pick up the actual source package.
RUN pip install --no-cache-dir -e ".[postgres]"

# Data directory — mount a volume here for durable segment storage.
RUN mkdir -p /data/recalllayer
ENV RECALLLAYER_SIDECAR_ROOT_DIR=/data/recalllayer

# Sane defaults — override via environment variables at runtime.
ENV RECALLLAYER_COLLECTION_ID=default
ENV RECALLLAYER_HOST_REPOSITORY=inmemory
ENV RECALLLAYER_HOST=0.0.0.0
ENV RECALLLAYER_PORT=8765
ENV RECALLLAYER_LOG_LEVEL=info

EXPOSE 8765

# Health check — hits /healthz every 10s with a 5s timeout, 3 retries.
HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${RECALLLAYER_PORT}/healthz')"

CMD uvicorn recalllayer.api.recalllayer_sidecar_app:app \
      --host "${RECALLLAYER_HOST}" \
      --port "${RECALLLAYER_PORT}" \
      --log-level "${RECALLLAYER_LOG_LEVEL}"
