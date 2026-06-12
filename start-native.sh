#!/usr/bin/env bash
set -euo pipefail

BUILD_FRONTEND=0
SKIP_FRONTEND_BUILD=0
SKIP_HELPER=0
NO_BROWSER=0
SKIP_MIHOMO_DOWNLOAD=0
RUN_SECONDS=0
MANAGER_PORT=8089
PROXY_PORT=7896
CONTROLLER_PORT=9090
HELPER_PORT="${SYSTEM_PROXY_HELPER_PORT:-18089}"
WAIT_SECONDS=35
DATA_DIR=""
MIHOMO_VERSION="v1.19.26"

usage() {
  cat <<'EOF'
Usage: ./start-native.sh [options]

Starts Lite Node Gateway directly on the host without Docker.

Options:
  --build-frontend          Force npm frontend build before starting.
  --skip-frontend-build     Do not build frontend; require manager/static to exist.
  --skip-helper             Do not start the host system-proxy helper.
  --no-browser              Do not open the Manager page automatically.
  --skip-mihomo-download    Require vendor/mihomo/linux-amd64/mihomo to exist.
  --run-seconds N           Stop automatically after N seconds, for smoke tests.
  --manager-port N          Manager port. Default: 8089.
  --proxy-port N            Main proxy port. Default: 7896.
  --controller-port N       Mihomo control API port. Default: 9090.
  --helper-port N           System proxy helper port. Default: 18089.
  --data-dir PATH           Runtime data directory. Default: ./data.
  --mihomo-version VERSION  Mihomo release version. Default: v1.19.26.
  -h, --help                Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --build-frontend) BUILD_FRONTEND=1 ;;
    --skip-frontend-build) SKIP_FRONTEND_BUILD=1 ;;
    --skip-helper) SKIP_HELPER=1 ;;
    --no-browser) NO_BROWSER=1 ;;
    --skip-mihomo-download) SKIP_MIHOMO_DOWNLOAD=1 ;;
    --run-seconds) shift; RUN_SECONDS="${1:?--run-seconds requires a value}" ;;
    --manager-port) shift; MANAGER_PORT="${1:?--manager-port requires a value}" ;;
    --proxy-port) shift; PROXY_PORT="${1:?--proxy-port requires a value}" ;;
    --controller-port) shift; CONTROLLER_PORT="${1:?--controller-port requires a value}" ;;
    --helper-port) shift; HELPER_PORT="${1:?--helper-port requires a value}" ;;
    --data-dir) shift; DATA_DIR="${1:?--data-dir requires a value}" ;;
    --mihomo-version) shift; MIHOMO_VERSION="${1:?--mihomo-version requires a value}" ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANAGER_DIR="$ROOT/manager"
FRONTEND_DIR="$MANAGER_DIR/frontend"
STATIC_DIR="$MANAGER_DIR/static"
REQUIREMENTS_FILE="$MANAGER_DIR/requirements.txt"
HELPER_SCRIPT="$ROOT/scripts/system_proxy_helper.py"
VENV_DIR="$ROOT/.venv-linux"
VENV_PYTHON="$VENV_DIR/bin/python"
VENDOR_MIHOMO_DIR="$ROOT/vendor/mihomo/linux-amd64"
MIHOMO_BIN="$VENDOR_MIHOMO_DIR/mihomo"
BUILD_DIR="$ROOT/build/native"

if [[ -z "$DATA_DIR" ]]; then
  DATA_DIR="$ROOT/data"
fi
mkdir -p "$DATA_DIR"
DATA_DIR="$(cd "$DATA_DIR" && pwd)"
LOG_DIR="$DATA_DIR/logs"
CONFIG_FILE="$DATA_DIR/config.yaml"
MANAGER_URL="http://127.0.0.1:$MANAGER_PORT"
CONTROLLER_URL="http://127.0.0.1:$CONTROLLER_PORT"
HELPER_URL="http://127.0.0.1:$HELPER_PORT/api/system-proxy"
PIDS=()

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "$1 was not found in PATH." >&2
    return 1
  fi
}

python3_works() {
  command -v python3 >/dev/null 2>&1 && python3 - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
}

python_venv_install_hint() {
  local version
  version="$(python3 - <<'PY' 2>/dev/null || true
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
PY
)"
  if [[ -n "$version" ]]; then
    echo "Debian/Ubuntu/Deepin: sudo apt install python${version}-venv python3-pip"
  else
    echo "Debian/Ubuntu/Deepin: sudo apt install python3-venv python3-pip"
  fi
}

remove_venv_dir() {
  if [[ -d "$VENV_DIR" && "$VENV_DIR" == "$ROOT/.venv-linux" ]]; then
    rm -rf "$VENV_DIR"
  fi
}

venv_has_pip() {
  [[ -x "$VENV_PYTHON" ]] && "$VENV_PYTHON" -m pip --version >/dev/null 2>&1
}

create_python_venv() {
  echo "Creating Python virtual environment ..."
  if ! python3 -m venv "$VENV_DIR"; then
    echo "Could not create a virtual environment." >&2
    echo "$(python_venv_install_hint)" >&2
    if [[ -d "$VENV_DIR" ]] && ! venv_has_pip; then
      echo "Removing incomplete virtual environment: $VENV_DIR" >&2
      remove_venv_dir
    fi
    exit 1
  fi

  if venv_has_pip; then
    return
  fi

  echo "The virtual environment was created without pip. Trying ensurepip ..." >&2
  if "$VENV_PYTHON" -m ensurepip --upgrade >/dev/null 2>&1 && venv_has_pip; then
    echo "Bootstrapped pip in the virtual environment."
    return
  fi

  echo "Could not bootstrap pip in the virtual environment." >&2
  echo "$(python_venv_install_hint)" >&2
  echo "Removing incomplete virtual environment: $VENV_DIR" >&2
  remove_venv_dir
  exit 1
}

frontend_static_exists() {
  [[ -f "$STATIC_DIR/index.html" ]] && find "$STATIC_DIR/assets" -maxdepth 1 -type f \( -name '*.js' -o -name '*.css' \) 2>/dev/null | grep -q .
}

build_frontend_if_needed() {
  if [[ "$SKIP_FRONTEND_BUILD" -eq 1 ]] && ! frontend_static_exists; then
    echo "manager/static is missing. Rerun without --skip-frontend-build or build the frontend first." >&2
    exit 1
  fi
  if [[ "$BUILD_FRONTEND" -eq 0 ]] && frontend_static_exists; then
    echo "Using existing frontend build: $STATIC_DIR"
    return
  fi

  need_cmd npm || {
    echo "Install Node.js/npm, then rerun this script. Debian/Ubuntu: sudo apt install nodejs npm" >&2
    exit 1
  }
  echo "Building frontend ..."
  (
    cd "$FRONTEND_DIR"
    if [[ ! -d node_modules ]]; then
      npm ci
    fi
    npm run build
  )
}

ensure_python_env() {
  python3_works || {
    echo "Install Python 3.11+ and rerun this script." >&2
    echo "Debian/Ubuntu/Deepin: sudo apt install python3 python3-venv python3-pip" >&2
    exit 1
  }
  if [[ -d "$VENV_DIR" && ! -x "$VENV_PYTHON" ]]; then
    echo "Detected incomplete Python virtual environment: $VENV_DIR"
    echo "Recreating Python virtual environment ..."
    remove_venv_dir
  fi
  if [[ ! -x "$VENV_PYTHON" ]]; then
    create_python_venv
  elif ! venv_has_pip; then
    echo "Detected broken Python virtual environment: $VENV_DIR"
    if "$VENV_PYTHON" -m ensurepip --upgrade >/dev/null 2>&1 && venv_has_pip; then
      echo "Repaired pip in the existing Python virtual environment."
    else
      echo "Recreating Python virtual environment ..."
      remove_venv_dir
      create_python_venv
    fi
  fi

  if "$VENV_PYTHON" -c "import yaml, requests" >/dev/null 2>&1; then
    echo "Using existing Python dependencies: $VENV_DIR"
    return
  fi

  echo "Installing Python dependencies ..."
  "$VENV_PYTHON" -m pip install --upgrade pip
  "$VENV_PYTHON" -m pip install -r "$REQUIREMENTS_FILE"
}

download_file() {
  local out_file="$1"
  shift
  mkdir -p "$(dirname "$out_file")"
  for url in "$@"; do
    echo "Downloading $url"
    if command -v curl >/dev/null 2>&1; then
      curl -L --retry 3 --retry-delay 2 --connect-timeout 20 --max-time 240 -o "$out_file" "$url" || true
    elif command -v wget >/dev/null 2>&1; then
      wget -O "$out_file" "$url" || true
    else
      echo "curl or wget is required to download mihomo." >&2
      exit 1
    fi
    if [[ -s "$out_file" ]] && [[ "$(wc -c <"$out_file")" -gt 1000000 ]]; then
      return
    fi
    rm -f "$out_file"
  done
  echo "Could not download mihomo $MIHOMO_VERSION." >&2
  exit 1
}

ensure_mihomo() {
  if [[ -x "$MIHOMO_BIN" ]]; then
    echo "Using existing mihomo: $MIHOMO_BIN"
    return
  fi
  if [[ "$SKIP_MIHOMO_DOWNLOAD" -eq 1 ]]; then
    echo "mihomo was not found. Place it at $MIHOMO_BIN or rerun without --skip-mihomo-download." >&2
    exit 1
  fi

  local gz_path="$BUILD_DIR/mihomo-linux.gz"
  download_file "$gz_path" \
    "https://downloads.sourceforge.net/project/mihomo.mirror/$MIHOMO_VERSION/mihomo-linux-amd64-v1-$MIHOMO_VERSION.gz" \
    "https://downloads.sourceforge.net/project/mihomo.mirror/$MIHOMO_VERSION/mihomo-linux-amd64-compatible-$MIHOMO_VERSION.gz" \
    "https://downloads.sourceforge.net/project/mihomo.mirror/$MIHOMO_VERSION/mihomo-linux-amd64-$MIHOMO_VERSION.gz" \
    "https://github.com/MetaCubeX/mihomo/releases/download/$MIHOMO_VERSION/mihomo-linux-amd64-v1-$MIHOMO_VERSION.gz" \
    "https://github.com/MetaCubeX/mihomo/releases/download/$MIHOMO_VERSION/mihomo-linux-amd64-compatible-$MIHOMO_VERSION.gz" \
    "https://github.com/MetaCubeX/mihomo/releases/download/$MIHOMO_VERSION/mihomo-linux-amd64-$MIHOMO_VERSION.gz"
  mkdir -p "$VENDOR_MIHOMO_DIR"
  gzip -dc "$gz_path" >"$MIHOMO_BIN"
  chmod +x "$MIHOMO_BIN"
}

ensure_initial_config() {
  mkdir -p "$DATA_DIR/subscriptions" "$LOG_DIR"
  if [[ -f "$CONFIG_FILE" ]]; then
    return
  fi

  cat >"$CONFIG_FILE" <<EOF
mixed-port: $PROXY_PORT
allow-lan: true
bind-address: "*"
mode: rule
log-level: info
external-controller: 127.0.0.1:$CONTROLLER_PORT
secret: ""
unified-delay: true
tcp-concurrent: true
profile:
  store-selected: true
  store-fake-ip: true
dns:
  enable: true
  ipv6: false
  enhanced-mode: fake-ip
  fake-ip-range: 198.18.0.1/16
  default-nameserver:
    - 223.5.5.5
    - 119.29.29.29
  nameserver:
    - https://dns.alidns.com/dns-query
    - https://doh.pub/dns-query
proxies: []
proxy-groups:
  - name: AUTO
    type: select
    proxies:
      - DIRECT
  - name: NODE
    type: select
    proxies:
      - DIRECT
listeners: []
rules:
  - DOMAIN,localhost,DIRECT
  - DOMAIN-SUFFIX,local,DIRECT
  - IP-CIDR,127.0.0.0/8,DIRECT,no-resolve
  - IP-CIDR,10.0.0.0/8,DIRECT,no-resolve
  - IP-CIDR,172.16.0.0/12,DIRECT,no-resolve
  - IP-CIDR,192.168.0.0/16,DIRECT,no-resolve
  - IP-CIDR,169.254.0.0/16,DIRECT,no-resolve
  - IP-CIDR6,::1/128,DIRECT,no-resolve
  - IP-CIDR6,fc00::/7,DIRECT,no-resolve
  - IP-CIDR6,fe80::/10,DIRECT,no-resolve
  - MATCH,NODE
EOF
}

http_ready() {
  "$VENV_PYTHON" - "$1" <<'PY' >/dev/null 2>&1
import sys
import urllib.request

try:
    with urllib.request.urlopen(sys.argv[1], timeout=2) as response:
        raise SystemExit(0 if response.status < 500 else 1)
except Exception:
    raise SystemExit(1)
PY
}

wait_http() {
  local name="$1"
  local url="$2"
  local deadline=$((SECONDS + WAIT_SECONDS))
  while (( SECONDS < deadline )); do
    if http_ready "$url"; then
      return
    fi
    sleep 0.35
  done
  echo "$name did not become ready at $url." >&2
  exit 1
}

is_http_ready() {
  http_ready "$1"
}

wait_http_down() {
  local name="$1"
  local url="$2"
  local deadline=$((SECONDS + 8))
  while (( SECONDS < deadline )); do
    if ! http_ready "$url"; then
      return
    fi
    sleep 0.35
  done
  echo "$name is still responding at $url." >&2
  exit 1
}

port_listener_pids() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -t -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | sort -u || true
  elif command -v ss >/dev/null 2>&1; then
    ss -ltnp "sport = :$port" 2>/dev/null | sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p' | sort -u || true
  elif command -v fuser >/dev/null 2>&1; then
    fuser -n tcp "$port" 2>/dev/null | tr ' ' '\n' | grep -E '^[0-9]+$' | sort -u || true
  fi
}

stop_port_listeners() {
  local name="$1"
  local port="$2"
  local pids=()
  local pid
  mapfile -t pids < <(port_listener_pids "$port")
  if [[ "${#pids[@]}" -eq 0 ]]; then
    echo "$name is responding, but no listener PID could be found for port $port." >&2
    exit 1
  fi

  echo "Stopping existing $name on port $port ..."
  for pid in "${pids[@]}"; do
    kill "$pid" >/dev/null 2>&1 || true
  done

  local deadline=$((SECONDS + 8))
  while (( SECONDS < deadline )); do
    local still_running=0
    for pid in "${pids[@]}"; do
      if kill -0 "$pid" >/dev/null 2>&1; then
        still_running=1
      fi
    done
    if [[ "$still_running" -eq 0 ]]; then
      return
    fi
    sleep 0.35
  done

  echo "Existing $name did not stop gracefully; forcing stop ..."
  for pid in "${pids[@]}"; do
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill -9 "$pid" >/dev/null 2>&1 || true
    fi
  done
}

start_logged_process() {
  local name="$1"
  shift
  echo "Starting $name ..."
  "$@" >"$LOG_DIR/$name.out.log" 2>"$LOG_DIR/$name.err.log" &
  STARTED_PID="$!"
  PIDS+=("$STARTED_PID")
}

stop_managed_pid() {
  local pid="${1:-}"
  if [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1; then
    kill "$pid" >/dev/null 2>&1 || true
    sleep 0.35
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill -9 "$pid" >/dev/null 2>&1 || true
    fi
  fi
}

start_mihomo() {
  start_logged_process mihomo "$MIHOMO_BIN" -d "$DATA_DIR" -f "$CONFIG_FILE"
  MIHOMO_PID="$STARTED_PID"
  wait_http mihomo "$CONTROLLER_URL/version"
}

start_system_proxy_helper() {
  start_logged_process system-proxy-helper "$VENV_PYTHON" "$HELPER_SCRIPT"
  HELPER_PID="$STARTED_PID"
  wait_http system-proxy-helper "$HELPER_URL"
}

start_manager() {
  start_logged_process manager "$VENV_PYTHON" "$MANAGER_DIR/app.py"
  MANAGER_PID="$STARTED_PID"
  wait_http manager "$MANAGER_URL/api/health"
}

ensure_mihomo_running() {
  # 托管进程仍在运行 → 绝不重启。即使 Core API 暂时探不通（可能正忙），
  # 也不能把活着的进程杀掉，否则会掐断正在处理的请求。
  if [[ -n "${MIHOMO_PID:-}" ]] && kill -0 "$MIHOMO_PID" >/dev/null 2>&1; then
    return
  fi
  # 没有托管的存活进程：可能是外部已有监听者，或进程已退出。
  if is_http_ready "$CONTROLLER_URL/version"; then
    return
  fi
  echo "mihomo is not running; starting ..."
  stop_managed_pid "${MIHOMO_PID:-}"
  start_mihomo
}

ensure_system_proxy_helper_running() {
  if [[ "$SKIP_HELPER" -eq 1 ]]; then
    return
  fi
  # 托管进程仍在运行 → 绝不重启（即使 Helper API 暂时探不通）。
  if [[ -n "${HELPER_PID:-}" ]] && kill -0 "$HELPER_PID" >/dev/null 2>&1; then
    return
  fi
  # 没有托管的存活进程：可能是外部已有监听者，或进程已退出。
  if is_http_ready "$HELPER_URL"; then
    return
  fi
  echo "System proxy helper is not running; starting ..."
  stop_managed_pid "${HELPER_PID:-}"
  start_system_proxy_helper
}

ensure_manager_running() {
  # 托管进程仍在运行 → 绝不重启。一键测速等耗时操作期间 /api/health 可能短暂
  # 探不通，但进程是活的，绝不能杀，否则会掐断正在处理的请求（表现为前端 Failed to fetch）。
  if [[ -n "${MANAGER_PID:-}" ]] && kill -0 "$MANAGER_PID" >/dev/null 2>&1; then
    return
  fi
  # 没有托管的存活进程：可能是外部已有监听者，或进程已退出。
  if is_http_ready "$MANAGER_URL/api/health"; then
    return
  fi
  echo "manager is not running; starting ..."
  stop_managed_pid "${MANAGER_PID:-}"
  start_manager
}

watchdog_once() {
  ensure_mihomo_running
  ensure_system_proxy_helper_running
  ensure_manager_running
}

sync_manager_config() {
  if "$VENV_PYTHON" - "$MANAGER_URL/api/rebuild" <<'PY' >/dev/null 2>&1
import sys
import urllib.request

request = urllib.request.Request(
    sys.argv[1],
    data=b"{}",
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(request, timeout=20) as response:
    raise SystemExit(0 if response.status < 500 else 1)
PY
  then
    echo "Synced Mihomo config through manager."
  else
    echo "Manager config sync failed. Open the Manager and click rebuild if nodes look stale." >&2
  fi
}

cleanup() {
  local pid
  for (( idx=${#PIDS[@]}-1; idx>=0; idx-- )); do
    pid="${PIDS[$idx]}"
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
    fi
  done
}
trap cleanup EXIT INT TERM

build_frontend_if_needed
ensure_python_env
ensure_mihomo
ensure_initial_config

export GATEWAY_DATA_DIR="$DATA_DIR"
export MIHOMO_API_URL="$CONTROLLER_URL"
export MIHOMO_CONFIG_IN_CORE="$CONFIG_FILE"
export MIHOMO_MIXED_PORT="$PROXY_PORT"
export MIHOMO_EXTERNAL_CONTROLLER="127.0.0.1:$CONTROLLER_PORT"
export SYSTEM_PROXY_HELPER_URL="http://127.0.0.1:$HELPER_PORT"
export SYSTEM_PROXY_SERVER="127.0.0.1:$PROXY_PORT"
export SYSTEM_PROXY_TEST_PROXY="http://127.0.0.1:$PROXY_PORT"
export PORT_PROBE_PROXY_HOST="127.0.0.1"
export MANAGER_HOST="127.0.0.1"
export MANAGER_PORT="$MANAGER_PORT"
export SYSTEM_PROXY_HELPER_HOST="127.0.0.1"
export SYSTEM_PROXY_HELPER_PORT="$HELPER_PORT"

if is_http_ready "$CONTROLLER_URL/version"; then
  echo "mihomo is already running: $CONTROLLER_URL"
else
  start_mihomo
fi

if [[ "$SKIP_HELPER" -eq 0 ]]; then
  if is_http_ready "$HELPER_URL"; then
    echo "System proxy helper is already running: $HELPER_URL"
  else
    start_system_proxy_helper
  fi
fi

if [[ "$BUILD_FRONTEND" -eq 1 ]] && is_http_ready "$MANAGER_URL/api/health"; then
  echo "Frontend was rebuilt; restarting existing manager at $MANAGER_URL"
  stop_port_listeners manager "$MANAGER_PORT"
  wait_http_down manager "$MANAGER_URL/api/health"
  MANAGER_RESTARTED=1
fi

if is_http_ready "$MANAGER_URL/api/health"; then
  echo "manager is already running: $MANAGER_URL"
else
  start_manager
fi
sync_manager_config

if [[ "${MANAGER_RESTARTED:-0}" -eq 1 ]]; then
  sleep 1.2
  ensure_mihomo_running
  ensure_system_proxy_helper_running
fi

cat <<EOF

Ready.
Manager:      $MANAGER_URL
Main proxy:   http://127.0.0.1:$PROXY_PORT
Core API:     $CONTROLLER_URL
EOF
if [[ "$SKIP_HELPER" -eq 0 ]]; then
  echo "Helper:       $HELPER_URL"
fi
cat <<'EOF'

Keep this terminal open while using the gateway. Press Ctrl+C to stop.
EOF

if [[ "$NO_BROWSER" -eq 0 ]] && command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$MANAGER_URL" >/dev/null 2>&1 || true
fi

if [[ "$RUN_SECONDS" -gt 0 ]]; then
  deadline=$((SECONDS + RUN_SECONDS))
  while (( SECONDS < deadline )); do
    watchdog_once
    sleep 1
  done
  echo "Timed run finished."
else
  while true; do
    watchdog_once
    sleep 1
  done
fi
