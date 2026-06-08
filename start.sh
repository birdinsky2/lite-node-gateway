#!/usr/bin/env bash
set -euo pipefail

BUILD=0
SKIP_HELPER=0
SKIP_DOCKER=0
HELPER_PORT="${SYSTEM_PROXY_HELPER_PORT:-18089}"
HELPER_WAIT_SECONDS="${HELPER_WAIT_SECONDS:-8}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --build)
      BUILD=1
      ;;
    --skip-helper)
      SKIP_HELPER=1
      ;;
    --skip-docker)
      SKIP_DOCKER=1
      ;;
    --helper-port)
      shift
      HELPER_PORT="${1:?--helper-port requires a value}"
      ;;
    --helper-wait-seconds)
      shift
      HELPER_WAIT_SECONDS="${1:?--helper-wait-seconds requires a value}"
      ;;
    -h|--help)
      cat <<'EOF'
Usage: ./start.sh [--build] [--skip-helper] [--skip-docker]

Starts the host system-proxy helper, then runs docker compose up -d.
EOF
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
  shift
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$ROOT/docker-compose.yml"
HELPER_SCRIPT="$ROOT/scripts/system_proxy_helper.py"
LOG_DIR="$ROOT/data/logs"
HELPER_OUT_LOG="$LOG_DIR/system-proxy-helper.out.log"
HELPER_ERR_LOG="$LOG_DIR/system-proxy-helper.err.log"
HELPER_URL="http://127.0.0.1:$HELPER_PORT/api/system-proxy"

helper_health() {
  python3 - "$HELPER_URL" <<'PY' >/dev/null 2>&1
import json
import sys
import urllib.request

try:
    with urllib.request.urlopen(sys.argv[1], timeout=2) as response:
        body = json.loads(response.read().decode("utf-8") or "{}")
    raise SystemExit(0 if "ok" in body else 1)
except Exception:
    raise SystemExit(1)
PY
}

listener_pids() {
  if command -v ss >/dev/null 2>&1; then
    ss -ltnp "sport = :$HELPER_PORT" 2>/dev/null | awk 'NR > 1 { print }'
  elif command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$HELPER_PORT" -sTCP:LISTEN 2>/dev/null || true
  else
    return 0
  fi
}

start_helper() {
  if [[ ! -f "$HELPER_SCRIPT" ]]; then
    echo "System proxy helper script was not found: $HELPER_SCRIPT" >&2
    exit 1
  fi
  if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 was not found in PATH." >&2
    exit 1
  fi

  if helper_health; then
    echo "System proxy helper is already running: $HELPER_URL"
    return
  fi

  local listeners
  listeners="$(listener_pids || true)"
  if [[ -n "$listeners" ]]; then
    echo "Port $HELPER_PORT is already listening, but helper health check failed:" >&2
    echo "$listeners" >&2
    exit 1
  fi

  mkdir -p "$LOG_DIR"
  echo "Starting system proxy helper with python3 ..."
  (
    cd "$ROOT"
    SYSTEM_PROXY_HELPER_PORT="$HELPER_PORT" nohup python3 "$HELPER_SCRIPT" >"$HELPER_OUT_LOG" 2>"$HELPER_ERR_LOG" &
    echo $! >"$LOG_DIR/system-proxy-helper.pid"
  )

  local deadline=$((SECONDS + HELPER_WAIT_SECONDS))
  while (( SECONDS < deadline )); do
    if helper_health; then
      echo "System proxy helper started. PID: $(cat "$LOG_DIR/system-proxy-helper.pid")"
      return
    fi
    sleep 0.3
  done

  echo "System proxy helper did not become healthy within ${HELPER_WAIT_SECONDS}s." >&2
  echo "stdout: $HELPER_OUT_LOG" >&2
  echo "stderr: $HELPER_ERR_LOG" >&2
  tail -n 20 "$HELPER_ERR_LOG" 2>/dev/null >&2 || true
  exit 1
}

if [[ "$SKIP_HELPER" -eq 0 ]]; then
  start_helper
fi

if [[ "$SKIP_DOCKER" -eq 0 ]]; then
  if ! command -v docker >/dev/null 2>&1; then
    echo "docker was not found in PATH." >&2
    exit 1
  fi

  echo "Starting Docker services ..."
  compose_args=(compose -f "$COMPOSE_FILE" up -d --remove-orphans)
  if [[ "$BUILD" -eq 1 ]]; then
    compose_args+=(--build)
  fi
  docker "${compose_args[@]}"
fi

cat <<EOF

Ready.
Manager:      http://127.0.0.1:8089
Main proxy:   http://127.0.0.1:7896
Helper:       $HELPER_URL
EOF
