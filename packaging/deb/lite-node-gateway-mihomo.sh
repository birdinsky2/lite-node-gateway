#!/usr/bin/env bash
set -euo pipefail

DATA_DIR="${GATEWAY_DATA_DIR:-/var/lib/lite-node-gateway}"
CONFIG_FILE="${MIHOMO_CONFIG_FILE:-$DATA_DIR/config.yaml}"
PROXY_PORT="${MIHOMO_MIXED_PORT:-7896}"
CONTROLLER="${MIHOMO_EXTERNAL_CONTROLLER:-127.0.0.1:9090}"
MIHOMO_BIN="${MIHOMO_BIN:-/opt/lite-node-gateway/bin/mihomo}"

mkdir -p "$DATA_DIR/subscriptions"

if [[ ! -f "$CONFIG_FILE" ]]; then
  cat >"$CONFIG_FILE" <<EOF
mixed-port: $PROXY_PORT
allow-lan: true
bind-address: "*"
mode: rule
log-level: info
external-controller: $CONTROLLER
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
  - MATCH,NODE
EOF
fi

exec "$MIHOMO_BIN" -d "$DATA_DIR" -f "$CONFIG_FILE"
