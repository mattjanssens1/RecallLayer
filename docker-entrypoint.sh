#!/bin/sh
# Entrypoint for RecallLayer sidecar container.
# Builds the uvicorn command, adding TLS flags only when cert+key are provided.
set -e

TLS_ARGS=""
if [ -n "${RECALLLAYER_TLS_CERT}" ] && [ -n "${RECALLLAYER_TLS_KEY}" ]; then
    TLS_ARGS="--ssl-certfile ${RECALLLAYER_TLS_CERT} --ssl-keyfile ${RECALLLAYER_TLS_KEY}"
fi

exec uvicorn recalllayer.api.recalllayer_sidecar_app:app \
    --host "${RECALLLAYER_HOST:-0.0.0.0}" \
    --port "${RECALLLAYER_PORT:-8765}" \
    --log-level "${RECALLLAYER_LOG_LEVEL:-info}" \
    ${TLS_ARGS}
