from __future__ import annotations

import base64
import concurrent.futures
import copy
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import secrets
import shutil
import threading
import traceback
import urllib.parse
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import requests
import yaml


class QuotedString(str):
    pass


class GatewayYamlDumper(yaml.SafeDumper):
    pass


def quoted_string_representer(dumper: yaml.SafeDumper, value: QuotedString) -> yaml.nodes.ScalarNode:
    return dumper.represent_scalar("tag:yaml.org,2002:str", str(value), style='"')


GatewayYamlDumper.add_representer(QuotedString, quoted_string_representer)


def quote_reality_yaml_scalars(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        prefix, value, suffix = match.groups()
        stripped = value.strip()
        if not stripped or stripped[0] in {"'", '"', "|", ">", "[", "{"}:
            return match.group(0)
        escaped = stripped.replace("\\", "\\\\").replace('"', '\\"')
        return f'{prefix}"{escaped}"{suffix}'

    return re.sub(r"^(\s*(?:public-key|short-id):\s*)([^#\r\n]*?)(\s*(?:#.*)?)$", replace, text, flags=re.MULTILINE)


APP_DIR = pathlib.Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
DATA_DIR = pathlib.Path(os.environ.get("GATEWAY_DATA_DIR", APP_DIR.parent / "data")).resolve()
SUB_DIR = DATA_DIR / "subscriptions"
STATE_FILE = DATA_DIR / "manager-state.json"
CONFIG_FILE = DATA_DIR / "config.yaml"
BACKUP_FILE = DATA_DIR / "config.yaml.before-manager"

MIHOMO_API_URL = os.environ.get("MIHOMO_API_URL", "http://127.0.0.1:9090").rstrip("/")
MIHOMO_SECRET = os.environ.get("MIHOMO_SECRET", "")
MIHOMO_CONFIG_IN_CORE = os.environ.get("MIHOMO_CONFIG_IN_CORE", "/root/.config/mihomo/config.yaml")
MIHOMO_MIXED_PORT = int(os.environ.get("MIHOMO_MIXED_PORT", "7897"))
MIHOMO_EXTERNAL_CONTROLLER = os.environ.get("MIHOMO_EXTERNAL_CONTROLLER", "0.0.0.0:9090")
NODE_DELAY_TEST_URL = os.environ.get("NODE_DELAY_TEST_URL", "http://www.gstatic.com/generate_204")
NODE_DELAY_TIMEOUT_MS = int(os.environ.get("NODE_DELAY_TIMEOUT_MS", "5000"))
NODE_DELAY_WORKERS = int(os.environ.get("NODE_DELAY_WORKERS", "8"))
SYSTEM_PROXY_HELPER_URL = os.environ.get("SYSTEM_PROXY_HELPER_URL", "http://host.docker.internal:18089").rstrip("/")
SYSTEM_PROXY_SERVER = os.environ.get("SYSTEM_PROXY_SERVER", "127.0.0.1:7896")
SYSTEM_PROXY_TEST_URL = os.environ.get("SYSTEM_PROXY_TEST_URL", "https://ipinfo.io/json")
SYSTEM_PROXY_TEST_PROXY = os.environ.get("SYSTEM_PROXY_TEST_PROXY", "http://mihomo:7897")
PORT_PROBE_PROXY_HOST = os.environ.get("PORT_PROBE_PROXY_HOST", "mihomo")

PORT_MIN = int(os.environ.get("PORT_MIN", "7900"))
PORT_MAX = int(os.environ.get("PORT_MAX", "7999"))
MANAGER_HOST = os.environ.get("MANAGER_HOST", "0.0.0.0")
MANAGER_PORT = int(os.environ.get("MANAGER_PORT", "8080"))

BUILTIN_TARGETS = {"DIRECT", "REJECT", "GLOBAL", "AUTO", "NODE"}
STATE_LOCK = threading.RLock()

DEFAULT_SYSTEM_PROXY_BYPASS_RULES = [
    "localhost",
    "127.*",
    "::1",
    "10.*",
    "172.16.*",
    "172.17.*",
    "172.18.*",
    "172.19.*",
    "172.20.*",
    "172.21.*",
    "172.22.*",
    "172.23.*",
    "172.24.*",
    "172.25.*",
    "172.26.*",
    "172.27.*",
    "172.28.*",
    "172.29.*",
    "172.30.*",
    "172.31.*",
    "192.168.*",
    "*.local",
    "<local>",
]


DEFAULT_DNS = {
    "enable": True,
    "ipv6": False,
    "enhanced-mode": "fake-ip",
    "fake-ip-range": "198.18.0.1/16",
    "default-nameserver": ["223.5.5.5", "119.29.29.29"],
    "nameserver": ["https://dns.alidns.com/dns-query", "https://doh.pub/dns-query"],
}


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().replace(microsecond=0).isoformat()


def empty_state() -> dict[str, Any]:
    return {
        "version": 1,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "subscriptions": [],
        "bindings": [],
        "system_proxy": empty_system_proxy_state(),
    }


def default_system_proxy_host_port() -> tuple[str, int]:
    server = SYSTEM_PROXY_SERVER.strip()
    if ":" in server:
        host, port_text = server.rsplit(":", 1)
        try:
            port = int(port_text)
            if 1 <= port <= 65535:
                return host.strip() or "127.0.0.1", port
        except ValueError:
            pass
    return "127.0.0.1", 7896


def default_system_proxy_port() -> int:
    return default_system_proxy_host_port()[1]


def default_system_proxy_bypass_text() -> str:
    return "\n".join(DEFAULT_SYSTEM_PROXY_BYPASS_RULES)


def normalize_bypass_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        raw = "\n".join(str(item) for item in value)
    else:
        raw = str(value)
    rules: list[str] = []
    seen: set[str] = set()
    for item in re.split(r"[;\r\n]+", raw):
        rule = item.strip()
        if not rule or rule in seen:
            continue
        seen.add(rule)
        rules.append(rule)
    return "\n".join(rules)


def bypass_text_to_override(value: Any) -> str:
    text = normalize_bypass_text(value)
    return ";".join(line.strip() for line in text.splitlines() if line.strip())


def empty_system_proxy_state() -> dict[str, Any]:
    return {
        "enabled": False,
        "server_port": default_system_proxy_port(),
        "bypass": None,
        "selected_subscription_id": None,
        "selected_node_id": None,
        "updated_at": None,
    }


def normalize_system_proxy_state(proxy_state: dict[str, Any]) -> dict[str, Any]:
    defaults = empty_system_proxy_state()
    for key, value in defaults.items():
        proxy_state.setdefault(key, value)
    try:
        port = int(proxy_state.get("server_port") or default_system_proxy_port())
    except (TypeError, ValueError):
        port = default_system_proxy_port()
    proxy_state["server_port"] = port if 1 <= port <= 65535 else default_system_proxy_port()
    if proxy_state.get("bypass") is not None:
        proxy_state["bypass"] = normalize_bypass_text(proxy_state.get("bypass"))
    return proxy_state


def system_proxy_server(state: dict[str, Any]) -> str:
    proxy_state = normalize_system_proxy_state(state.setdefault("system_proxy", empty_system_proxy_state()))
    host, _ = default_system_proxy_host_port()
    return f"{host}:{proxy_state['server_port']}"


def configured_bypass_text(proxy_state: dict[str, Any], helper: dict[str, Any] | None = None) -> str:
    saved = proxy_state.get("bypass")
    if saved is not None:
        return normalize_bypass_text(saved)
    helper_override = helper.get("override") if helper else None
    if helper_override:
        return normalize_bypass_text(helper_override)
    return default_system_proxy_bypass_text()


def read_json(path: pathlib.Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: pathlib.Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def read_yaml_file(path: pathlib.Path) -> Any:
    if not path.exists():
        return None
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return yaml.safe_load(quote_reality_yaml_scalars(data.decode(encoding))) or {}
        except UnicodeDecodeError:
            continue
    return yaml.safe_load(quote_reality_yaml_scalars(data.decode("utf-8", errors="replace"))) or {}


def write_yaml_file(path: pathlib.Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(yaml.dump(value, Dumper=GatewayYamlDumper, allow_unicode=True, sort_keys=False), encoding="utf-8")
    tmp.replace(path)


def init_state_from_existing_config() -> dict[str, Any]:
    state = empty_state()
    config = read_yaml_file(CONFIG_FILE) or {}
    listeners = config.get("listeners") if isinstance(config, dict) else []
    groups = {
        str(group.get("name"))
        for group in (config.get("proxy-groups") or [])
        if isinstance(group, dict) and group.get("name")
    }
    bindings: list[dict[str, Any]] = []
    if isinstance(listeners, list):
        for item in listeners:
            if not isinstance(item, dict):
                continue
            port = item.get("port")
            target = str(item.get("proxy") or "").strip()
            if not isinstance(port, int) or not target:
                continue
            if PORT_MIN <= port <= PORT_MAX and (target in BUILTIN_TARGETS or target in groups):
                bindings.append(
                    {
                        "port": port,
                        "mode": "builtin",
                        "target": target,
                        "listen": str(item.get("listen") or "0.0.0.0"),
                        "enabled": True,
                        "created_at": now_iso(),
                        "updated_at": now_iso(),
                    }
                )
    state["bindings"] = sorted(bindings, key=lambda item: item["port"])
    return state


def load_state() -> dict[str, Any]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SUB_DIR.mkdir(parents=True, exist_ok=True)
    if STATE_FILE.exists():
        state = read_json(STATE_FILE, empty_state())
    else:
        state = init_state_from_existing_config()
        write_json(STATE_FILE, state)
    state.setdefault("subscriptions", [])
    state.setdefault("bindings", [])
    normalize_system_proxy_state(state.setdefault("system_proxy", empty_system_proxy_state()))
    return state


def save_state(state: dict[str, Any]) -> None:
    state["updated_at"] = now_iso()
    write_json(STATE_FILE, state)


def headers_for_core() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if MIHOMO_SECRET:
        headers["Authorization"] = f"Bearer {MIHOMO_SECRET}"
    return headers


def mihomo_request(method: str, path: str, **kwargs: Any) -> requests.Response:
    return requests.request(
        method,
        f"{MIHOMO_API_URL}{path}",
        headers=headers_for_core(),
        timeout=kwargs.pop("timeout", 12),
        **kwargs,
    )


def core_status() -> dict[str, Any]:
    try:
        response = mihomo_request("GET", "/version", timeout=5)
        return {
            "ok": response.ok,
            "status": response.status_code,
            "body": response.json() if response.text else {},
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def latest_proxy_delay(proxy: dict[str, Any]) -> int | None:
    history = proxy.get("history")
    if isinstance(history, list):
        for item in reversed(history):
            if isinstance(item, dict):
                delay = item.get("delay")
                if isinstance(delay, (int, float)) and delay > 0:
                    return int(delay)
    extra = proxy.get("extra")
    if isinstance(extra, dict):
        for value in extra.values():
            if isinstance(value, dict):
                delay = latest_proxy_delay(value)
                if delay is not None:
                    return delay
    return None


def test_mihomo_proxy_delay(proxy_name: str) -> dict[str, Any]:
    try:
        response = mihomo_request(
            "GET",
            f"/proxies/{urllib.parse.quote(proxy_name, safe='')}/delay",
            params={"timeout": NODE_DELAY_TIMEOUT_MS, "url": NODE_DELAY_TEST_URL},
            timeout=max(3, NODE_DELAY_TIMEOUT_MS / 1000 + 2),
        )
        if response.status_code >= 400:
            return {"ok": False, "alive": False, "delay_ms": None, "error": response.text[:180] or f"HTTP {response.status_code}"}
        body = response.json() if response.text else {}
        delay = body.get("delay") if isinstance(body, dict) else None
        if isinstance(delay, (int, float)) and delay > 0:
            return {"ok": True, "alive": True, "delay_ms": int(delay)}
        return {"ok": False, "alive": False, "delay_ms": None, "error": "timeout"}
    except Exception as exc:
        return {"ok": False, "alive": False, "delay_ms": None, "error": str(exc)}


def test_node_delays(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    workers = max(1, min(NODE_DELAY_WORKERS, len(nodes) or 1))
    results: dict[str, dict[str, Any]] = {}
    started = now_iso()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {
            executor.submit(test_mihomo_proxy_delay, node["proxy_name"]): node
            for node in nodes
            if node.get("proxy_name")
        }
        for future in concurrent.futures.as_completed(future_map):
            node = future_map[future]
            try:
                result = future.result()
            except Exception as exc:
                result = {"ok": False, "alive": False, "delay_ms": None, "error": str(exc)}
            results[node["id"]] = {
                "node_id": node["id"],
                "name": node["name"],
                "subscription_id": node["subscription_id"],
                "subscription_name": node["subscription_name"],
                "tested_at": started,
                **result,
            }
    return [results.get(node["id"], {"node_id": node["id"], "ok": False, "alive": False, "delay_ms": None, "error": "missing proxy name", "tested_at": started}) for node in nodes]


def decode_response_text(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def try_yaml(text: str) -> Any:
    try:
        return yaml.safe_load(quote_reality_yaml_scalars(text))
    except Exception:
        return None


def try_base64_text(text: str) -> str | None:
    cleaned = re.sub(r"\s+", "", text.strip())
    if len(cleaned) < 16:
        return None
    padding = "=" * ((4 - len(cleaned) % 4) % 4)
    for decoder in (base64.b64decode, base64.urlsafe_b64decode):
        try:
            decoded = decoder(cleaned + padding)
            return decode_response_text(decoded)
        except Exception:
            continue
    return None


def uri_display_name(parsed: urllib.parse.SplitResult, fallback: str) -> str:
    name = urllib.parse.unquote(parsed.fragment or "").strip()
    return name or fallback


def first_query_value(query: dict[str, list[str]], *names: str) -> str | None:
    for name in names:
        values = query.get(name)
        if values is None:
            continue
        for value in values:
            if value is not None:
                return value
    return None


def query_flag(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def normalize_mihomo_proxy(proxy: dict[str, Any]) -> dict[str, Any]:
    item = copy.deepcopy(proxy)
    reality_opts = item.get("reality-opts")
    if isinstance(reality_opts, dict):
        for key in ("public-key", "short-id"):
            if reality_opts.get(key) is not None:
                reality_opts[key] = QuotedString(str(reality_opts[key]))
    return item


def parse_ss_uri(line: str, index: int) -> dict[str, Any] | None:
    parsed = urllib.parse.urlsplit(line)
    name = uri_display_name(parsed, f"ss-{index}")
    raw = line[5:].split("#", 1)[0]
    if "@" in raw:
        userinfo, hostpart = raw.rsplit("@", 1)
        decoded_userinfo = urllib.parse.unquote(userinfo)
        if ":" not in decoded_userinfo:
            decoded_userinfo = decode_response_text(base64.urlsafe_b64decode(userinfo + "=" * ((4 - len(userinfo) % 4) % 4)))
        method, password = decoded_userinfo.split(":", 1)
        host = urllib.parse.urlsplit(f"//{hostpart}").hostname
        port = urllib.parse.urlsplit(f"//{hostpart}").port
    else:
        decoded = decode_response_text(base64.urlsafe_b64decode(raw + "=" * ((4 - len(raw) % 4) % 4)))
        if "@" not in decoded:
            return None
        userinfo, hostpart = decoded.rsplit("@", 1)
        method, password = userinfo.split(":", 1)
        host = urllib.parse.urlsplit(f"//{hostpart}").hostname
        port = urllib.parse.urlsplit(f"//{hostpart}").port
    if not host or not port:
        return None
    return {"name": name, "type": "ss", "server": host, "port": port, "cipher": method, "password": password, "udp": True}


def parse_trojan_uri(line: str, index: int) -> dict[str, Any] | None:
    parsed = urllib.parse.urlsplit(line)
    if not parsed.hostname or not parsed.port or not parsed.username:
        return None
    query = urllib.parse.parse_qs(parsed.query)
    proxy: dict[str, Any] = {
        "name": uri_display_name(parsed, f"trojan-{index}"),
        "type": "trojan",
        "server": parsed.hostname,
        "port": parsed.port,
        "password": urllib.parse.unquote(parsed.username),
        "udp": True,
    }
    if query.get("sni"):
        proxy["sni"] = query["sni"][0]
    if query.get("security", [""])[0] == "tls":
        proxy["skip-cert-verify"] = query.get("allowInsecure", ["0"])[0] in {"1", "true", "True"}
    return proxy


def parse_vmess_uri(line: str, index: int) -> dict[str, Any] | None:
    raw = line[len("vmess://") :]
    decoded = decode_response_text(base64.urlsafe_b64decode(raw + "=" * ((4 - len(raw) % 4) % 4)))
    data = json.loads(decoded)
    server = data.get("add")
    port = int(data.get("port") or 0)
    uuid = data.get("id")
    if not server or not port or not uuid:
        return None
    proxy: dict[str, Any] = {
        "name": str(data.get("ps") or f"vmess-{index}"),
        "type": "vmess",
        "server": server,
        "port": port,
        "uuid": uuid,
        "alterId": int(data.get("aid") or 0),
        "cipher": data.get("scy") or "auto",
        "udp": True,
    }
    if data.get("tls"):
        proxy["tls"] = True
        if data.get("sni"):
            proxy["servername"] = data.get("sni")
    if data.get("net") == "ws":
        proxy["network"] = "ws"
        headers: dict[str, str] = {}
        if data.get("host"):
            headers["Host"] = data["host"]
        proxy["ws-opts"] = {"path": data.get("path") or "/", "headers": headers}
    return proxy


def parse_vless_uri(line: str, index: int) -> dict[str, Any] | None:
    parsed = urllib.parse.urlsplit(line)
    if not parsed.hostname or not parsed.port or not parsed.username:
        return None
    query = urllib.parse.parse_qs(parsed.query)
    security = (first_query_value(query, "security") or "").lower()
    network = (first_query_value(query, "type", "network") or "").lower()
    proxy: dict[str, Any] = {
        "name": uri_display_name(parsed, f"vless-{index}"),
        "type": "vless",
        "server": parsed.hostname,
        "port": parsed.port,
        "uuid": urllib.parse.unquote(parsed.username),
        "udp": True,
    }

    flow = first_query_value(query, "flow")
    if flow:
        proxy["flow"] = flow

    if security in {"tls", "reality"}:
        proxy["tls"] = True
        servername = first_query_value(query, "sni", "servername", "peer")
        if servername:
            proxy["servername"] = servername
        fingerprint = first_query_value(query, "fp", "fingerprint", "client-fingerprint")
        if fingerprint:
            proxy["client-fingerprint"] = fingerprint
        allow_insecure = first_query_value(query, "allowInsecure", "allow-insecure", "skip-cert-verify")
        if allow_insecure is not None:
            proxy["skip-cert-verify"] = query_flag(allow_insecure)
        alpn = first_query_value(query, "alpn")
        if alpn:
            proxy["alpn"] = [item.strip() for item in alpn.split(",") if item.strip()]

    if security == "reality":
        reality_opts: dict[str, Any] = {}
        public_key = first_query_value(query, "pbk", "public-key", "publicKey")
        short_id = first_query_value(query, "sid", "short-id", "shortId")
        if public_key:
            reality_opts["public-key"] = public_key
        if short_id is not None:
            reality_opts["short-id"] = short_id
        if reality_opts:
            proxy["reality-opts"] = reality_opts

    if network == "ws":
        headers: dict[str, str] = {}
        host = first_query_value(query, "host")
        if host:
            headers["Host"] = host
        proxy["network"] = "ws"
        proxy["ws-opts"] = {"path": first_query_value(query, "path") or "/", "headers": headers}
    elif network == "grpc":
        proxy["network"] = "grpc"
        service_name = first_query_value(query, "serviceName", "service-name", "grpc-service-name")
        grpc_opts: dict[str, Any] = {}
        if service_name:
            grpc_opts["grpc-service-name"] = service_name
        grpc_mode = first_query_value(query, "mode")
        if grpc_mode:
            grpc_opts["grpc-mode"] = grpc_mode
        if grpc_opts:
            proxy["grpc-opts"] = grpc_opts
    elif network in {"h2", "http"}:
        proxy["network"] = "h2"
        h2_opts: dict[str, Any] = {}
        host = first_query_value(query, "host")
        path = first_query_value(query, "path")
        if host:
            h2_opts["host"] = [item.strip() for item in host.split(",") if item.strip()]
        if path:
            h2_opts["path"] = path
        if h2_opts:
            proxy["h2-opts"] = h2_opts
    return proxy


def parse_uri_lines(text: str) -> list[dict[str, Any]]:
    proxies: list[dict[str, Any]] = []
    for index, line in enumerate([item.strip() for item in text.splitlines() if item.strip()], start=1):
        try:
            if line.startswith("ss://"):
                item = parse_ss_uri(line, index)
            elif line.startswith("trojan://"):
                item = parse_trojan_uri(line, index)
            elif line.startswith("vmess://"):
                item = parse_vmess_uri(line, index)
            elif line.startswith("vless://"):
                item = parse_vless_uri(line, index)
            else:
                item = None
            if item:
                proxies.append(item)
        except Exception:
            continue
    return proxies


def normalize_proxies(proxies: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if not isinstance(proxies, list):
        return normalized
    for index, proxy in enumerate(proxies, start=1):
        if not isinstance(proxy, dict):
            continue
        item = copy.deepcopy(proxy)
        name = str(item.get("name") or f"node-{index}").strip() or f"node-{index}"
        item["name"] = name
        normalized.append(item)
    return normalized


def parse_subscription_payload(text: str) -> tuple[list[dict[str, Any]], str | None]:
    parsed = try_yaml(text)
    if isinstance(parsed, dict) and isinstance(parsed.get("proxies"), list):
        return normalize_proxies(parsed["proxies"]), parsed.get("name") or parsed.get("profile", {}).get("name")
    decoded = try_base64_text(text)
    if decoded:
        parsed = try_yaml(decoded)
        if isinstance(parsed, dict) and isinstance(parsed.get("proxies"), list):
            return normalize_proxies(parsed["proxies"]), parsed.get("name") or parsed.get("profile", {}).get("name")
        uri_proxies = parse_uri_lines(decoded)
        if uri_proxies:
            return normalize_proxies(uri_proxies), None
    uri_proxies = parse_uri_lines(text)
    if uri_proxies:
        return normalize_proxies(uri_proxies), None
    raise ValueError("订阅内容里没有找到可用节点。当前支持 Clash/Mihomo YAML，以及常见 ss/trojan/vmess/vless 链接订阅。")


def fetch_subscription(url: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    response = requests.get(
        url,
        headers={
            "User-Agent": "clash.meta",
            "Accept": "text/yaml, application/yaml, text/plain, */*",
        },
        timeout=35,
    )
    response.raise_for_status()
    text = decode_response_text(response.content)
    proxies, profile_name = parse_subscription_payload(text)
    if not proxies:
        raise ValueError("订阅返回成功，但没有解析到节点。")
    metadata = {
        "profile_name": profile_name,
        "content_type": response.headers.get("Content-Type", ""),
        "subscription_userinfo": response.headers.get("Subscription-Userinfo", ""),
        "fetched_at": now_iso(),
    }
    return proxies, metadata


def subscription_path(subscription_id: str) -> pathlib.Path:
    return SUB_DIR / f"{subscription_id}.yaml"


def save_subscription_nodes(subscription_id: str, proxies: list[dict[str, Any]], metadata: dict[str, Any]) -> None:
    write_yaml_file(subscription_path(subscription_id), {"metadata": metadata, "proxies": [normalize_mihomo_proxy(proxy) for proxy in proxies]})


def load_subscription_nodes(subscription_id: str) -> list[dict[str, Any]]:
    data = read_yaml_file(subscription_path(subscription_id)) or {}
    return normalize_proxies(data.get("proxies") or [])


def masked_url(url: str) -> str:
    try:
        parsed = urllib.parse.urlsplit(url)
        query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        masked_query = []
        for key, value in query:
            if re.search(r"token|key|secret|password|pwd", key, re.I):
                masked_query.append((key, "****"))
            else:
                masked_query.append((key, value))
        return urllib.parse.urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(masked_query), "")
        )
    except Exception:
        return "****"


def make_node_id(proxy: dict[str, Any], index: int) -> str:
    signature = {
        "index": index,
        "name": str(proxy.get("name") or ""),
        "type": str(proxy.get("type") or ""),
        "server": str(proxy.get("server") or ""),
        "port": str(proxy.get("port") or ""),
    }
    return hashlib.sha1(json.dumps(signature, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def unique_name(base: str, used: set[str]) -> str:
    value = base.strip() or "node"
    if value not in used:
        used.add(value)
        return value
    suffix = 2
    while f"{value} #{suffix}" in used:
        suffix += 1
    final = f"{value} #{suffix}"
    used.add(final)
    return final


def subscription_nodes(subscription: dict[str, Any], used_names: set[str] | None = None) -> list[dict[str, Any]]:
    proxies = load_subscription_nodes(subscription["id"])
    nodes: list[dict[str, Any]] = []
    local_ids: set[str] = set()
    for index, proxy in enumerate(proxies, start=1):
        node_id = make_node_id(proxy, index)
        if node_id in local_ids:
            node_id = hashlib.sha1(f"{node_id}:{index}".encode("utf-8")).hexdigest()[:16]
        local_ids.add(node_id)
        original_name = str(proxy.get("name") or f"node-{index}")
        if used_names is None:
            proxy_name = ""
        else:
            proxy_name = unique_name(f"{subscription['name']} / {original_name}", used_names)
        safe_proxy = copy.deepcopy(proxy)
        if proxy_name:
            safe_proxy["name"] = proxy_name
        safe_proxy = normalize_mihomo_proxy(safe_proxy)
        nodes.append(
            {
                "id": node_id,
                "name": original_name,
                "type": str(proxy.get("type") or ""),
                "server": str(proxy.get("server") or ""),
                "port": proxy.get("port"),
                "subscription_id": subscription["id"],
                "subscription_name": subscription["name"],
                "proxy_name": proxy_name,
                "proxy": safe_proxy,
            }
        )
    return nodes


def collect_nodes(state: dict[str, Any], only_enabled: bool) -> tuple[list[dict[str, Any]], dict[tuple[str, str], dict[str, Any]]]:
    used = set(BUILTIN_TARGETS)
    nodes: list[dict[str, Any]] = []
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for subscription in state.get("subscriptions", []):
        if only_enabled and not subscription.get("enabled", True):
            continue
        for node in subscription_nodes(subscription, used):
            nodes.append(node)
            by_key[(node["subscription_id"], node["id"])] = node
    return nodes, by_key


def helper_status() -> dict[str, Any]:
    try:
        response = requests.get(f"{SYSTEM_PROXY_HELPER_URL}/api/system-proxy", timeout=4)
        body = response.json() if response.text else {}
        if response.status_code >= 400:
            return {"ok": False, "status": response.status_code, "error": str(body.get("error") or response.text[:200])}
        return {"ok": True, "status": response.status_code, **body}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def update_helper_system_proxy(enabled: bool, server: str, bypass: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"enabled": enabled, "server": server}
    if bypass is not None:
        payload["override"] = bypass_text_to_override(bypass)
    try:
        response = requests.post(
            f"{SYSTEM_PROXY_HELPER_URL}/api/system-proxy",
            json=payload,
            timeout=8,
        )
        body = response.json() if response.text else {}
        if response.status_code >= 400 or body.get("ok") is False:
            raise ApiError(response.status_code if response.status_code >= 400 else 502, str(body.get("error") or response.text[:200]))
        return {"ok": True, "status": response.status_code, **body}
    except ApiError:
        raise
    except Exception as exc:
        raise ApiError(502, f"System proxy helper unavailable: {exc}") from exc


def node_label(node: dict[str, Any]) -> str:
    return f"{node['subscription_name']} / {node['name']}"


def find_node_for_system_proxy(
    state: dict[str, Any],
    subscription_id: str | None = None,
    node_id: str | None = None,
    allow_first: bool = False,
) -> dict[str, Any]:
    nodes, by_key = collect_nodes(state, only_enabled=True)
    if subscription_id and node_id:
        node = by_key.get((subscription_id, node_id))
        if not node:
            raise ApiError(400, "Node does not exist or the subscription is disabled.")
        return node

    proxy_state = state.setdefault("system_proxy", empty_system_proxy_state())
    saved_subscription_id = str(proxy_state.get("selected_subscription_id") or "")
    saved_node_id = str(proxy_state.get("selected_node_id") or "")
    if saved_subscription_id and saved_node_id:
        node = by_key.get((saved_subscription_id, saved_node_id))
        if node:
            return node

    if allow_first and nodes:
        return nodes[0]
    raise ApiError(400, "Please select a node before enabling the system proxy.")


def select_mihomo_node(node: dict[str, Any]) -> dict[str, Any]:
    response = mihomo_request(
        "PUT",
        f"/proxies/{urllib.parse.quote('NODE', safe='')}",
        json={"name": node["proxy_name"]},
        timeout=10,
    )
    if response.status_code >= 400:
        raise ApiError(502, f"Mihomo node switch failed: HTTP {response.status_code} {response.text[:240]}")
    try:
        body = response.json() if response.text else {}
    except Exception:
        body = {"text": response.text}
    return {"ok": True, "status": response.status_code, "body": body}


def public_system_proxy(state: dict[str, Any]) -> dict[str, Any]:
    proxy_state = normalize_system_proxy_state(state.setdefault("system_proxy", empty_system_proxy_state()))
    _, by_key = collect_nodes(state, only_enabled=True)
    selected_subscription_id = proxy_state.get("selected_subscription_id")
    selected_node_id = proxy_state.get("selected_node_id")
    selected_node = None
    if selected_subscription_id and selected_node_id:
        selected_node = by_key.get((str(selected_subscription_id), str(selected_node_id)))
    helper = helper_status()
    helper_enabled = bool(helper.get("enabled")) if "enabled" in helper else bool(proxy_state.get("enabled"))
    bypass = configured_bypass_text(proxy_state, helper)
    return {
        "enabled": helper_enabled,
        "desired_enabled": bool(proxy_state.get("enabled")),
        "server": system_proxy_server(state),
        "server_port": int(proxy_state["server_port"]),
        "bypass": bypass,
        "default_bypass": default_system_proxy_bypass_text(),
        "helper_ok": bool(helper.get("ok")),
        "helper": helper,
        "selected_subscription_id": selected_subscription_id,
        "selected_node_id": selected_node_id,
        "selected_label": node_label(selected_node) if selected_node else None,
        "selected_resolved": bool(selected_node),
        "updated_at": proxy_state.get("updated_at"),
    }


def read_existing_dns() -> dict[str, Any]:
    config = read_yaml_file(CONFIG_FILE)
    if isinstance(config, dict) and isinstance(config.get("dns"), dict):
        return config["dns"]
    return copy.deepcopy(DEFAULT_DNS)


def build_mihomo_config(state: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    nodes, node_by_key = collect_nodes(state, only_enabled=True)
    proxy_names = [node["proxy_name"] for node in nodes]
    proxies = [node["proxy"] for node in nodes]

    if proxy_names:
        auto_group = {
            "name": "AUTO",
            "type": "url-test",
            "proxies": proxy_names,
            "url": "http://www.gstatic.com/generate_204",
            "interval": 600,
            "tolerance": 50,
        }
        node_group = {"name": "NODE", "type": "select", "proxies": ["AUTO", *proxy_names, "DIRECT"]}
    else:
        auto_group = {"name": "AUTO", "type": "select", "proxies": ["DIRECT"]}
        node_group = {"name": "NODE", "type": "select", "proxies": ["DIRECT"]}

    listeners: list[dict[str, Any]] = []
    resolved_bindings: list[dict[str, Any]] = []
    for binding in sorted(state.get("bindings", []), key=lambda item: int(item.get("port") or 0)):
        if not binding.get("enabled", True):
            continue
        port = int(binding.get("port") or 0)
        if not (PORT_MIN <= port <= PORT_MAX):
            continue
        target = None
        label = None
        if binding.get("mode") == "builtin":
            target = str(binding.get("target") or "").strip()
            if target not in BUILTIN_TARGETS:
                target = None
            label = target
        elif binding.get("mode") == "node":
            node = node_by_key.get((str(binding.get("subscription_id")), str(binding.get("node_id"))))
            if node:
                target = node["proxy_name"]
                label = f"{node['subscription_name']} / {node['name']}"
        if not target:
            resolved_bindings.append({**binding, "resolved": False, "reason": "节点不存在或订阅已停用"})
            continue
        listeners.append(
            {
                "name": f"port-{port}",
                "type": "mixed",
                "listen": str(binding.get("listen") or "0.0.0.0"),
                "port": port,
                "proxy": target,
                "udp": True,
            }
        )
        resolved_bindings.append({**binding, "resolved": True, "target": target, "label": label})

    config = {
        "mixed-port": MIHOMO_MIXED_PORT,
        "allow-lan": True,
        "bind-address": "*",
        "mode": "rule",
        "log-level": "info",
        "external-controller": MIHOMO_EXTERNAL_CONTROLLER,
        "secret": MIHOMO_SECRET,
        "unified-delay": True,
        "tcp-concurrent": True,
        "profile": {"store-selected": True, "store-fake-ip": True},
        "dns": read_existing_dns(),
        "proxies": proxies,
        "proxy-groups": [auto_group, node_group],
        "listeners": listeners,
        "rules": ["MATCH,NODE"],
    }
    return config, resolved_bindings


def reload_core() -> dict[str, Any]:
    response = mihomo_request(
        "PUT",
        "/configs",
        json={"path": MIHOMO_CONFIG_IN_CORE, "force": True},
        timeout=15,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Mihomo reload failed: HTTP {response.status_code} {response.text[:300]}")
    try:
        body = response.json()
    except Exception:
        body = {"text": response.text}
    return {"ok": True, "status": response.status_code, "body": body}


def rebuild_and_reload(state: dict[str, Any], reload: bool = True) -> dict[str, Any]:
    if CONFIG_FILE.exists() and not BACKUP_FILE.exists():
        shutil.copy2(CONFIG_FILE, BACKUP_FILE)
    config, resolved = build_mihomo_config(state)
    write_yaml_file(CONFIG_FILE, config)
    result: dict[str, Any] = {"config_written": True, "resolved_bindings": resolved}
    if reload:
        result["reload"] = reload_core()
        cleared_errors = 0
        for subscription in state.get("subscriptions", []):
            last_error = str(subscription.get("last_error") or "")
            if last_error.startswith("Mihomo reload failed"):
                subscription["last_error"] = None
                subscription["updated_at"] = now_iso()
                cleared_errors += 1
        if cleared_errors:
            save_state(state)
            result["cleared_reload_errors"] = cleared_errors
    return result


def public_state() -> dict[str, Any]:
    state = load_state()
    _, node_by_key = collect_nodes(state, only_enabled=False)
    subscriptions = []
    for item in state.get("subscriptions", []):
        node_count = len(load_subscription_nodes(item["id"]))
        subscriptions.append(
            {
                "id": item["id"],
                "name": item["name"],
                "enabled": item.get("enabled", True),
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
                "last_error": item.get("last_error"),
                "node_count": node_count,
                "url_masked": masked_url(item.get("url", "")),
            }
        )
    bindings = []
    for binding in sorted(state.get("bindings", []), key=lambda row: int(row.get("port") or 0)):
        public = {
            "port": binding.get("port"),
            "mode": binding.get("mode"),
            "enabled": binding.get("enabled", True),
            "listen": binding.get("listen") or "0.0.0.0",
            "updated_at": binding.get("updated_at"),
            "host_proxy": f"http://127.0.0.1:{binding.get('port')}",
            "container_proxy": f"http://host.docker.internal:{binding.get('port')}",
        }
        if binding.get("mode") == "builtin":
            public["target"] = binding.get("target")
            public["label"] = binding.get("target")
            public["resolved"] = True
        else:
            key = (str(binding.get("subscription_id")), str(binding.get("node_id")))
            node = node_by_key.get(key)
            public["subscription_id"] = binding.get("subscription_id")
            public["node_id"] = binding.get("node_id")
            public["resolved"] = bool(node)
            public["label"] = f"{node['subscription_name']} / {node['name']}" if node else "节点不存在或订阅已删除"
        bindings.append(public)
    return {
        "port_min": PORT_MIN,
        "port_max": PORT_MAX,
        "subscriptions": subscriptions,
        "bindings": bindings,
        "system_proxy": public_system_proxy(state),
        "core": core_status(),
    }


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class ManagerHandler(SimpleHTTPRequestHandler):
    server_version = "LiteNodeGatewayManager/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[manager] {self.address_string()} - {format % args}")

    def send_json(self, value: Any, status: int = HTTPStatus.OK) -> None:
        payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def read_body_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            value = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ApiError(400, f"JSON 格式错误：{exc}")
        if not isinstance(value, dict):
            raise ApiError(400, "请求体必须是 JSON 对象。")
        return value

    def handle_api(self, method: str) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path
        try:
            with STATE_LOCK:
                if method == "GET" and path == "/api/health":
                    self.send_json({"ok": True, "time": now_iso(), "core": core_status()})
                    return
                if method == "GET" and path == "/api/state":
                    self.send_json(public_state())
                    return
                if method == "POST" and path == "/api/subscriptions":
                    self.create_subscription()
                    return
                match = re.fullmatch(r"/api/subscriptions/([^/]+)/nodes", path)
                if method == "GET" and match:
                    self.list_nodes(match.group(1))
                    return
                match = re.fullmatch(r"/api/subscriptions/([^/]+)/nodes/delay", path)
                if method == "POST" and match:
                    self.test_nodes_delay(match.group(1))
                    return
                match = re.fullmatch(r"/api/subscriptions/([^/]+)/refresh", path)
                if method == "POST" and match:
                    self.refresh_subscription(match.group(1))
                    return
                match = re.fullmatch(r"/api/subscriptions/([^/]+)", path)
                if method == "DELETE" and match:
                    self.delete_subscription(match.group(1))
                    return
                if method == "POST" and path == "/api/bindings":
                    self.create_binding()
                    return
                match = re.fullmatch(r"/api/bindings/(\d+)", path)
                if method == "DELETE" and match:
                    self.delete_binding(int(match.group(1)))
                    return
                if method == "POST" and path == "/api/rebuild":
                    state = load_state()
                    self.send_json({"ok": True, **rebuild_and_reload(state)})
                    return
                if method == "POST" and path == "/api/probe":
                    self.probe_port()
                    return
                if method == "GET" and path == "/api/system-proxy/settings":
                    self.get_system_proxy_settings()
                    return
                if method == "POST" and path == "/api/system-proxy/settings":
                    self.update_system_proxy_settings()
                    return
                if method == "GET" and path == "/api/system-proxy":
                    self.get_system_proxy()
                    return
                if method == "POST" and path == "/api/system-proxy":
                    self.update_system_proxy()
                    return
                if method == "POST" and path == "/api/system-proxy/node":
                    self.select_system_proxy_node()
                    return
                if method == "POST" and path == "/api/system-proxy/probe":
                    self.probe_system_proxy()
                    return
                raise ApiError(404, "接口不存在。")
        except ApiError as exc:
            self.send_json({"ok": False, "error": exc.message}, exc.status)
        except Exception as exc:
            traceback.print_exc()
            self.send_json({"ok": False, "error": str(exc)}, 500)

    def create_subscription(self) -> None:
        body = self.read_body_json()
        url = str(body.get("url") or "").strip()
        if not url:
            raise ApiError(400, "请填写订阅地址。")
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme not in {"http", "https"}:
            raise ApiError(400, "订阅地址必须是 http 或 https。")
        name = str(body.get("name") or parsed.hostname or "订阅").strip() or "订阅"
        proxies, metadata = fetch_subscription(url)
        state = load_state()
        subscription_id = secrets.token_hex(6)
        subscription = {
            "id": subscription_id,
            "name": name,
            "url": url,
            "enabled": True,
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "last_error": None,
            "node_count": len(proxies),
        }
        state["subscriptions"].append(subscription)
        save_subscription_nodes(subscription_id, proxies, metadata)
        save_state(state)
        result = rebuild_and_reload(state)
        self.send_json({"ok": True, "subscription": {**subscription, "url_masked": masked_url(url)}, **result}, 201)

    def find_subscription(self, state: dict[str, Any], subscription_id: str) -> dict[str, Any]:
        for item in state.get("subscriptions", []):
            if item.get("id") == subscription_id:
                return item
        raise ApiError(404, "订阅不存在。")

    def list_nodes(self, subscription_id: str) -> None:
        state = load_state()
        subscription = self.find_subscription(state, subscription_id)
        nodes = subscription_nodes(subscription)
        safe_nodes = [
            {
                "id": node["id"],
                "name": node["name"],
                "type": node["type"],
                "server": node["server"],
                "port": node["port"],
                "subscription_id": node["subscription_id"],
                "subscription_name": node["subscription_name"],
            }
            for node in nodes
        ]
        self.send_json({"ok": True, "nodes": safe_nodes, "count": len(safe_nodes)})

    def test_nodes_delay(self, subscription_id: str) -> None:
        state = load_state()
        subscription = self.find_subscription(state, subscription_id)
        if not subscription.get("enabled", True):
            raise ApiError(400, "订阅已停用。")
        nodes, _ = collect_nodes(state, only_enabled=True)
        subscription_nodes_to_test = [node for node in nodes if node["subscription_id"] == subscription_id]
        if not subscription_nodes_to_test:
            raise ApiError(404, "没有可测速的节点。")
        results = test_node_delays(subscription_nodes_to_test)
        ok_count = sum(1 for item in results if item.get("ok"))
        self.send_json(
            {
                "ok": True,
                "subscription_id": subscription_id,
                "tested_url": NODE_DELAY_TEST_URL,
                "timeout_ms": NODE_DELAY_TIMEOUT_MS,
                "count": len(results),
                "ok_count": ok_count,
                "results": results,
            }
        )

    def refresh_subscription(self, subscription_id: str) -> None:
        state = load_state()
        subscription = self.find_subscription(state, subscription_id)
        try:
            proxies, metadata = fetch_subscription(subscription["url"])
            save_subscription_nodes(subscription_id, proxies, metadata)
            subscription["node_count"] = len(proxies)
            subscription["last_error"] = None
            subscription["updated_at"] = now_iso()
            save_state(state)
            result = rebuild_and_reload(state)
            self.send_json({"ok": True, "subscription": {**subscription, "url_masked": masked_url(subscription["url"])}, **result})
        except Exception as exc:
            subscription["last_error"] = str(exc)
            subscription["updated_at"] = now_iso()
            save_state(state)
            raise

    def delete_subscription(self, subscription_id: str) -> None:
        state = load_state()
        self.find_subscription(state, subscription_id)
        state["subscriptions"] = [item for item in state["subscriptions"] if item.get("id") != subscription_id]
        state["bindings"] = [
            item
            for item in state.get("bindings", [])
            if not (item.get("mode") == "node" and item.get("subscription_id") == subscription_id)
        ]
        path = subscription_path(subscription_id)
        if path.exists():
            path.unlink()
        save_state(state)
        result = rebuild_and_reload(state)
        self.send_json({"ok": True, **result})

    def create_binding(self) -> None:
        body = self.read_body_json()
        try:
            port = int(body.get("port"))
        except Exception:
            raise ApiError(400, "端口必须是数字。")
        if not (PORT_MIN <= port <= PORT_MAX):
            raise ApiError(400, f"端口必须在 {PORT_MIN}-{PORT_MAX} 之间。")

        state = load_state()
        binding: dict[str, Any]
        target = str(body.get("target") or "").strip()
        if target:
            if target not in BUILTIN_TARGETS:
                raise ApiError(400, "内置目标只支持 DIRECT、AUTO、NODE、GLOBAL、REJECT。")
            binding = {
                "port": port,
                "mode": "builtin",
                "target": target,
                "listen": "0.0.0.0",
                "enabled": True,
                "created_at": now_iso(),
                "updated_at": now_iso(),
            }
        else:
            subscription_id = str(body.get("subscription_id") or "").strip()
            node_id = str(body.get("node_id") or "").strip()
            if not subscription_id or not node_id:
                raise ApiError(400, "请选择订阅和节点。")
            subscription = self.find_subscription(state, subscription_id)
            if not subscription.get("enabled", True):
                raise ApiError(400, "订阅已停用。")
            nodes = subscription_nodes(subscription)
            if not any(node["id"] == node_id for node in nodes):
                raise ApiError(400, "节点不存在，可能需要刷新订阅。")
            binding = {
                "port": port,
                "mode": "node",
                "subscription_id": subscription_id,
                "node_id": node_id,
                "listen": "0.0.0.0",
                "enabled": True,
                "created_at": now_iso(),
                "updated_at": now_iso(),
            }

        state["bindings"] = [item for item in state.get("bindings", []) if int(item.get("port") or -1) != port]
        state["bindings"].append(binding)
        state["bindings"] = sorted(state["bindings"], key=lambda item: int(item.get("port") or 0))
        save_state(state)
        result = rebuild_and_reload(state)
        self.send_json({"ok": True, "binding": binding, **result})

    def delete_binding(self, port: int) -> None:
        state = load_state()
        before = len(state.get("bindings", []))
        state["bindings"] = [item for item in state.get("bindings", []) if int(item.get("port") or -1) != port]
        if len(state["bindings"]) == before:
            raise ApiError(404, "端口绑定不存在。")
        save_state(state)
        result = rebuild_and_reload(state)
        self.send_json({"ok": True, **result})

    def probe_port(self) -> None:
        body = self.read_body_json()
        try:
            port = int(body.get("port"))
        except Exception:
            raise ApiError(400, "端口必须是数字。")
        if not (PORT_MIN <= port <= PORT_MAX):
            raise ApiError(400, f"端口必须在 {PORT_MIN}-{PORT_MAX} 之间。")
        target_url = str(body.get("url") or "https://ipinfo.io/json").strip()
        proxies = {"http": f"http://{PORT_PROBE_PROXY_HOST}:{port}", "https": f"http://{PORT_PROBE_PROXY_HOST}:{port}"}
        started = dt.datetime.now()
        try:
            response = requests.get(target_url, proxies=proxies, timeout=25)
            elapsed_ms = int((dt.datetime.now() - started).total_seconds() * 1000)
            self.send_json(
                {
                    "ok": response.ok,
                    "status": response.status_code,
                    "elapsed_ms": elapsed_ms,
                    "body": response.text[:1200],
                },
                200 if response.ok else 502,
            )
        except requests.RequestException as exc:
            elapsed_ms = int((dt.datetime.now() - started).total_seconds() * 1000)
            self.send_json({"ok": False, "elapsed_ms": elapsed_ms, "error": str(exc)}, 502)

    def get_system_proxy(self) -> None:
        state = load_state()
        self.send_json({"ok": True, "system_proxy": public_system_proxy(state)})

    def get_system_proxy_settings(self) -> None:
        state = load_state()
        self.send_json({"ok": True, "system_proxy": public_system_proxy(state)})

    def update_system_proxy_settings(self) -> None:
        body = self.read_body_json()
        try:
            port = int(body.get("server_port"))
        except Exception:
            raise ApiError(400, "System proxy port must be a number.")
        if not (1 <= port <= 65535):
            raise ApiError(400, "System proxy port must be between 1 and 65535.")

        state = load_state()
        proxy_state = normalize_system_proxy_state(state.setdefault("system_proxy", empty_system_proxy_state()))
        proxy_state["server_port"] = port
        proxy_state["bypass"] = normalize_bypass_text(body.get("bypass"))
        proxy_state["updated_at"] = now_iso()

        current_helper = helper_status()
        enabled = bool(current_helper.get("enabled")) if "enabled" in current_helper else bool(proxy_state.get("enabled"))
        helper_result = None
        if current_helper.get("supported") is False:
            proxy_state["enabled"] = False
            helper_result = current_helper
        elif enabled:
            helper_result = update_helper_system_proxy(
                True,
                system_proxy_server(state),
                configured_bypass_text(proxy_state),
            )
            proxy_state["enabled"] = True
        else:
            helper_result = update_helper_system_proxy(
                False,
                system_proxy_server(state),
                configured_bypass_text(proxy_state),
            )
            proxy_state["enabled"] = False

        save_state(state)
        self.send_json(
            {
                "ok": True,
                "helper": helper_result,
                "system_proxy": public_system_proxy(state),
            }
        )

    def select_system_proxy_node(self) -> None:
        body = self.read_body_json()
        subscription_id = str(body.get("subscription_id") or "").strip()
        node_id = str(body.get("node_id") or "").strip()
        if not subscription_id or not node_id:
            raise ApiError(400, "Please select a subscription and node.")

        state = load_state()
        node = find_node_for_system_proxy(state, subscription_id, node_id)
        switch_result = select_mihomo_node(node)
        proxy_state = state.setdefault("system_proxy", empty_system_proxy_state())
        proxy_state["selected_subscription_id"] = node["subscription_id"]
        proxy_state["selected_node_id"] = node["id"]
        proxy_state["updated_at"] = now_iso()
        save_state(state)
        self.send_json(
            {
                "ok": True,
                "node": {
                    "id": node["id"],
                    "name": node["name"],
                    "subscription_id": node["subscription_id"],
                    "subscription_name": node["subscription_name"],
                    "label": node_label(node),
                },
                "switch": switch_result,
                "system_proxy": public_system_proxy(state),
            }
        )

    def update_system_proxy(self) -> None:
        body = self.read_body_json()
        if "enabled" not in body:
            raise ApiError(400, "Missing enabled flag.")
        enabled = bool(body.get("enabled"))

        state = load_state()
        selected_node = None
        switch_result = None
        if enabled:
            selected_node = find_node_for_system_proxy(state, allow_first=True)
            switch_result = select_mihomo_node(selected_node)

        proxy_state = normalize_system_proxy_state(state.setdefault("system_proxy", empty_system_proxy_state()))
        helper_result = update_helper_system_proxy(
            enabled,
            system_proxy_server(state),
            configured_bypass_text(proxy_state),
        )
        proxy_state["enabled"] = enabled
        proxy_state["updated_at"] = now_iso()
        if selected_node:
            proxy_state["selected_subscription_id"] = selected_node["subscription_id"]
            proxy_state["selected_node_id"] = selected_node["id"]
        save_state(state)
        self.send_json(
            {
                "ok": True,
                "helper": helper_result,
                "switch": switch_result,
                "system_proxy": public_system_proxy(state),
            }
        )

    def probe_system_proxy(self) -> None:
        target_url = SYSTEM_PROXY_TEST_URL
        started = dt.datetime.now()
        try:
            response = requests.get(
                target_url,
                proxies={"http": SYSTEM_PROXY_TEST_PROXY, "https": SYSTEM_PROXY_TEST_PROXY},
                timeout=25,
            )
            elapsed_ms = int((dt.datetime.now() - started).total_seconds() * 1000)
            self.send_json(
                {
                    "ok": response.ok,
                    "target_url": target_url,
                    "proxy": SYSTEM_PROXY_TEST_PROXY,
                    "status": response.status_code,
                    "elapsed_ms": elapsed_ms,
                    "body": response.text[:1200],
                },
                200 if response.ok else 502,
            )
        except requests.RequestException as exc:
            elapsed_ms = int((dt.datetime.now() - started).total_seconds() * 1000)
            self.send_json(
                {
                    "ok": False,
                    "target_url": target_url,
                    "proxy": SYSTEM_PROXY_TEST_PROXY,
                    "elapsed_ms": elapsed_ms,
                    "error": str(exc),
                },
                502,
            )

    def do_GET(self) -> None:
        if self.path.startswith("/api/"):
            self.handle_api("GET")
            return
        self.serve_static()

    def do_POST(self) -> None:
        if self.path.startswith("/api/"):
            self.handle_api("POST")
            return
        self.send_error(404)

    def do_DELETE(self) -> None:
        if self.path.startswith("/api/"):
            self.handle_api("DELETE")
            return
        self.send_error(404)

    def serve_static(self) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        request_path = parsed.path
        if request_path in {"", "/"}:
            request_path = "/index.html"
        candidate = (STATIC_DIR / request_path.lstrip("/")).resolve()
        if not str(candidate).startswith(str(STATIC_DIR.resolve())) or not candidate.exists() or not candidate.is_file():
            candidate = STATIC_DIR / "index.html"
        content_type = "text/plain; charset=utf-8"
        if candidate.suffix == ".html":
            content_type = "text/html; charset=utf-8"
        elif candidate.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif candidate.suffix == ".js":
            content_type = "application/javascript; charset=utf-8"
        data = candidate.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SUB_DIR.mkdir(parents=True, exist_ok=True)
    load_state()
    server = ThreadingHTTPServer((MANAGER_HOST, MANAGER_PORT), ManagerHandler)
    print(f"Lite Node Gateway Manager listening on {MANAGER_HOST}:{MANAGER_PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
