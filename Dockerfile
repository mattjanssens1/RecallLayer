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

# TLS: set both to enable HTTPS termination inside the container.
# Mount your cert/key into the container and point these vars at the paths.
# Leave empty (the default) to run plain HTTP (recommended behind a TLS proxy).
ENV RECALLLAYER_TLS_CERT=
ENV RECALLLAYER_TLS_KEY=

EXPOSE 8765

# Health check — hits /healthz every 10s with a 5s timeout, 3 retries.
# Uses https:// automatically when TLS is configured.
HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
  CMD python -c " \
import os, urllib.request, ssl; \
scheme = 'https' if os.getenv('RECALLLAYER_TLS_CERT') else 'http'; \
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE; \
urllib.request.urlopen(f\"{scheme}://localhost:{os.getenv('RECALLLAYER_PORT', 8765)}/healthz\", context=ctx if scheme=='https' else None) \
"

# Entrypoint script resolves TLS flags at runtime so the CMD stays readable.
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
