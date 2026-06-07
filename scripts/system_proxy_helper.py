from __future__ import annotations

import ctypes
import ipaddress
import json
import os
import shutil
import subprocess
import sys
from abc import ABC, abstractmethod
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


HOST = os.environ.get("SYSTEM_PROXY_HELPER_HOST", "0.0.0.0")
PORT = int(os.environ.get("SYSTEM_PROXY_HELPER_PORT", "18089"))
REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
INTERNET_OPTION_SETTINGS_CHANGED = 39
INTERNET_OPTION_REFRESH = 37
ALLOWED_CLIENT_NETWORKS = (
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.65.0/24"),
)
GSETTINGS_TIMEOUT = 5


class ProxyBackendError(RuntimeError):
    pass


class ProxyBackend(ABC):
    name: str
    platform: str

    @abstractmethod
    def read(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def write(self, enabled: bool, server: str, override: str | None = None) -> dict[str, Any]:
        raise NotImplementedError


class UnsupportedProxyBackend(ProxyBackend):
    name = "unsupported"

    def __init__(self, reason: str) -> None:
        self.reason = reason
        self.platform = sys.platform

    def read(self) -> dict[str, Any]:
        return {
            "enabled": False,
            "server": "",
            "override": "",
            "supported": False,
            "backend": self.name,
            "platform": self.platform,
            "error": self.reason,
        }

    def write(self, enabled: bool, server: str, override: str | None = None) -> dict[str, Any]:
        raise ProxyBackendError(self.reason)


class WindowsWininetProxyBackend(ProxyBackend):
    name = "wininet"
    platform = "windows"

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise ProxyBackendError("WinINET proxy backend is only available on Windows.")
        import winreg

        self.winreg = winreg

    def read(self) -> dict[str, Any]:
        winreg = self.winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ) as key:
            try:
                enabled = bool(winreg.QueryValueEx(key, "ProxyEnable")[0])
            except FileNotFoundError:
                enabled = False
            try:
                server = str(winreg.QueryValueEx(key, "ProxyServer")[0])
            except FileNotFoundError:
                server = ""
            try:
                override = str(winreg.QueryValueEx(key, "ProxyOverride")[0])
            except FileNotFoundError:
                override = ""
        return self.state(enabled, server, override)

    def write(self, enabled: bool, server: str, override: str | None = None) -> dict[str, Any]:
        winreg = self.winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1 if enabled else 0)
            if server:
                winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, server)
            if override is not None:
                winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, override)
        self.refresh_wininet()
        return self.read()

    def refresh_wininet(self) -> None:
        wininet = ctypes.windll.Wininet
        wininet.InternetSetOptionW(0, INTERNET_OPTION_SETTINGS_CHANGED, 0, 0)
        wininet.InternetSetOptionW(0, INTERNET_OPTION_REFRESH, 0, 0)

    def state(self, enabled: bool, server: str, override: str) -> dict[str, Any]:
        return {
            "enabled": enabled,
            "server": server,
            "override": override,
            "supported": True,
            "backend": self.name,
            "platform": self.platform,
        }


class GSettingsProxyBackend(ProxyBackend):
    name = "gsettings"
    platform = "linux"

    def __init__(self) -> None:
        self.gsettings = shutil.which("gsettings")
        if not self.gsettings:
            raise ProxyBackendError("gsettings was not found. Linux system proxy control requires a desktop session such as GNOME or MATE.")
        self._run("get", "org.gnome.system.proxy", "mode")

    def read(self) -> dict[str, Any]:
        mode = self._get("org.gnome.system.proxy", "mode").strip("'\"")
        host = self._get("org.gnome.system.proxy.http", "host").strip("'\"")
        port = self._int_value(self._get("org.gnome.system.proxy.http", "port"))
        ignore_hosts = self._parse_gsettings_list(self._get("org.gnome.system.proxy", "ignore-hosts"))
        server = f"{host}:{port}" if host and port else ""
        return {
            "enabled": mode == "manual",
            "server": server,
            "override": ";".join(ignore_hosts),
            "supported": True,
            "backend": self.name,
            "platform": self.platform,
        }

    def write(self, enabled: bool, server: str, override: str | None = None) -> dict[str, Any]:
        if enabled:
            host, port = parse_host_port(server)
            for schema in ("http", "https", "ftp"):
                self._set(f"org.gnome.system.proxy.{schema}", "host", host)
                self._set(f"org.gnome.system.proxy.{schema}", "port", str(port), raw=True)
            self._set("org.gnome.system.proxy", "mode", "manual")
        else:
            self._set("org.gnome.system.proxy", "mode", "none")

        if override is not None:
            self._set("org.gnome.system.proxy", "ignore-hosts", format_gsettings_ignore_hosts(split_override(override)), raw=True)
        return self.read()

    def _get(self, schema: str, key: str) -> str:
        return self._run("get", schema, key).stdout.strip()

    def _set(self, schema: str, key: str, value: str, raw: bool = False) -> None:
        self._run("set", schema, key, value if raw else quote_gsettings_string(value))

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        assert self.gsettings
        try:
            return subprocess.run(
                [self.gsettings, *args],
                check=True,
                capture_output=True,
                text=True,
                timeout=GSETTINGS_TIMEOUT,
            )
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or str(exc)).strip()
            raise ProxyBackendError(f"gsettings failed: {detail}") from exc
        except subprocess.TimeoutExpired as exc:
            raise ProxyBackendError("gsettings timed out. Is a desktop DBus session available?") from exc

    @staticmethod
    def _int_value(value: str) -> int:
        try:
            return int(value.strip())
        except ValueError:
            return 0

    @staticmethod
    def _parse_gsettings_list(value: str) -> list[str]:
        text = value.strip()
        if not (text.startswith("[") and text.endswith("]")):
            return []
        try:
            parsed = json.loads(text.replace("'", '"'))
        except json.JSONDecodeError:
            return []
        if not isinstance(parsed, list):
            return []
        return [str(item) for item in parsed if str(item).strip()]


def select_backend() -> ProxyBackend:
    if sys.platform == "win32":
        return WindowsWininetProxyBackend()
    if sys.platform.startswith("linux"):
        try:
            return GSettingsProxyBackend()
        except ProxyBackendError as exc:
            return UnsupportedProxyBackend(str(exc))
    return UnsupportedProxyBackend(f"System proxy helper does not support platform {sys.platform}.")


BACKEND = select_backend()


def client_allowed(host: str) -> bool:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(address in network for network in ALLOWED_CLIENT_NETWORKS)


def parse_host_port(server: str) -> tuple[str, int]:
    host, sep, port_text = server.rpartition(":")
    if not sep or not host:
        raise ValueError("Proxy server must use host:port format.")
    try:
        port = int(port_text)
    except ValueError as exc:
        raise ValueError("Proxy server port must be a number.") from exc
    if not (1 <= port <= 65535):
        raise ValueError("Proxy server port must be between 1 and 65535.")
    return host, port


def split_override(value: str) -> list[str]:
    rules: list[str] = []
    seen: set[str] = set()
    for item in value.replace("\r", "\n").replace(";", "\n").splitlines():
        rule = item.strip()
        if not rule or rule in seen:
            continue
        seen.add(rule)
        rules.append(rule)
    return rules


def quote_gsettings_string(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def quote_gsettings_list_item(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _linux_ignore_host(rule: str) -> str:
    if rule == "<local>":
        return "local"
    wildcard_network = windows_wildcard_network(rule)
    if wildcard_network:
        return wildcard_network
    if rule.endswith(".*"):
        return rule[:-2]
    if rule.startswith("*."):
        return rule[2:]
    return rule


def _windows_override_rule(rule: str) -> str:
    if rule == "local":
        return "<local>"
    return rule


def windows_wildcard_network(rule: str) -> str | None:
    if not rule.endswith(".*"):
        return None
    parts = rule[:-2].split(".")
    if not 1 <= len(parts) <= 3:
        return None
    try:
        octets = [int(part) for part in parts]
    except ValueError:
        return None
    if any(octet < 0 or octet > 255 for octet in octets):
        return None
    return ".".join(str(octet) for octet in [*octets, *([0] * (4 - len(octets)))]) + f"/{len(octets) * 8}"


def normalize_override_for_response(override: str) -> str:
    if sys.platform.startswith("linux"):
        return ";".join(_windows_override_rule(rule) for rule in split_override(override))
    return override


def format_gsettings_ignore_hosts(rules: list[str]) -> str:
    return "[" + ", ".join(quote_gsettings_list_item(_linux_ignore_host(rule)) for rule in rules) + "]"


def read_proxy_state() -> dict[str, Any]:
    state = BACKEND.read()
    if state.get("override"):
        state["override"] = normalize_override_for_response(str(state["override"]))
    return state


def write_proxy_state(enabled: bool, server: str, override: str | None = None) -> dict[str, Any]:
    if enabled:
        parse_host_port(server)
    state = BACKEND.write(enabled, server, override)
    if state.get("override"):
        state["override"] = normalize_override_for_response(str(state["override"]))
    return state


class ProxyHelperHandler(BaseHTTPRequestHandler):
    server_version = "LiteNodeGatewaySystemProxyHelper/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[system-proxy-helper] {self.client_address[0]} - {fmt % args}")

    def send_json(self, value: dict[str, Any], status: int = HTTPStatus.OK) -> None:
        payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(payload)

    def read_body_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            value = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError("Request body must be a JSON object.")
        return value

    def do_OPTIONS(self) -> None:
        if not client_allowed(self.client_address[0]):
            self.send_json({"ok": False, "error": "Forbidden."}, HTTPStatus.FORBIDDEN)
            return
        self.send_json({"ok": True, "backend": BACKEND.name, "platform": BACKEND.platform})

    def do_GET(self) -> None:
        if not client_allowed(self.client_address[0]):
            self.send_json({"ok": False, "error": "Forbidden."}, HTTPStatus.FORBIDDEN)
            return
        if self.path.split("?", 1)[0] != "/api/system-proxy":
            self.send_json({"ok": False, "error": "Not found."}, HTTPStatus.NOT_FOUND)
            return
        try:
            state = read_proxy_state()
            if state.get("supported") is False:
                self.send_json({"ok": False, **state})
                return
            self.send_json({"ok": True, **state})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc), "backend": BACKEND.name, "platform": BACKEND.platform}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:
        if not client_allowed(self.client_address[0]):
            self.send_json({"ok": False, "error": "Forbidden."}, HTTPStatus.FORBIDDEN)
            return
        if self.path.split("?", 1)[0] != "/api/system-proxy":
            self.send_json({"ok": False, "error": "Not found."}, HTTPStatus.NOT_FOUND)
            return
        try:
            body = self.read_body_json()
            enabled = bool(body.get("enabled"))
            server = str(body.get("server") or "").strip()
            if enabled and not server:
                self.send_json({"ok": False, "error": "Proxy server is required when enabling proxy."}, HTTPStatus.BAD_REQUEST)
                return
            override = body.get("override")
            override_value = str(override).strip() if override is not None else None
            state = write_proxy_state(enabled, server, override_value)
            self.send_json({"ok": True, **state})
        except ProxyBackendError as exc:
            self.send_json({"ok": False, "error": str(exc), "backend": BACKEND.name, "platform": BACKEND.platform}, HTTPStatus.NOT_IMPLEMENTED)
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc), "backend": BACKEND.name, "platform": BACKEND.platform}, HTTPStatus.INTERNAL_SERVER_ERROR)


def main() -> int:
    server = ThreadingHTTPServer((HOST, PORT), ProxyHelperHandler)
    print(f"System proxy helper listening on http://127.0.0.1:{PORT} ({BACKEND.platform}/{BACKEND.name})")
    if isinstance(BACKEND, UnsupportedProxyBackend):
        print(f"System proxy backend unavailable: {BACKEND.reason}", file=sys.stderr)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
