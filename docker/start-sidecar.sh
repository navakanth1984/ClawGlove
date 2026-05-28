#!/bin/bash
# start-sidecar.sh — ClawGlove sidecar process supervisor
# Starts HTTP proxy + TCP daemon. If either exits, kills the other and returns the exit code.
# This ensures the container fails (and Docker restarts it) if either component dies.

set -e

echo "[ClawGlove] Starting HTTP proxy on :8080 ..."
python -m clawglove.sidecar.http_proxy --policies policies/ --port 8080 --kafka "${KAFKA_BROKER:-localhost:9092}" &
HTTP_PID=$!

echo "[ClawGlove] Starting governance daemon on :50051 ..."
python -m clawglove.sidecar.daemon --policies policies/ --port 50051 --kafka "${KAFKA_BROKER:-localhost:9092}" --otlp "${OTEL_EXPORTER_OTLP_ENDPOINT:-http://localhost:4317}" &
DAEMON_PID=$!

echo "[ClawGlove] Both processes running (HTTP_PID=$HTTP_PID, DAEMON_PID=$DAEMON_PID)"

# Trap SIGTERM/SIGINT — clean shutdown
_shutdown() {
    echo "[ClawGlove] Shutdown signal received. Stopping processes..."
    kill "$HTTP_PID" "$DAEMON_PID" 2>/dev/null || true
    wait "$HTTP_PID" "$DAEMON_PID" 2>/dev/null || true
    echo "[ClawGlove] Shutdown complete."
    exit 0
}
trap _shutdown SIGTERM SIGINT

# Wait for the first process to exit. Either one exiting is a fatal condition.
wait -n "$HTTP_PID" "$DAEMON_PID"
EXIT_CODE=$?

echo "[ClawGlove] A component exited (code=$EXIT_CODE). Terminating sidecar."
kill "$HTTP_PID" "$DAEMON_PID" 2>/dev/null || true
exit "$EXIT_CODE"
