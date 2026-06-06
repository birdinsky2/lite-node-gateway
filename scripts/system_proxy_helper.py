from __future__ import annotations

import ctypes
import ipaddress
import json
import sys
import winreg
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


HOST = "0.0.0.0"
PORT = 18089
REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
INTERNET_OPTION_SETTINGS_CHANGED = 39
INTERNET_OPTION_REFRESH = 37
ALLOWED_CLIENT_NETWORKS = (
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("172.16.0.0/12"),
)


def client_allowed(host: str) -> bool:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(address in network for network in ALLOWED_CLIENT_NETWORKS)


def read_proxy_state() -> dict[str, Any]:
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
    return {"enabled": enabled, "server": server, "override": override}


def refresh_wininet() -> None:
    wininet = ctypes.windll.Wininet
    wininet.InternetSetOptionW(0, INTERNET_OPTION_SETTINGS_CHANGED, 0, 0)
    wininet.InternetSetOptionW(0, INTERNET_OPTION_REFRESH, 0, 0)


def write_proxy_state(enabled: bool, server: str, override: str | None = None) -> dict[str, Any]:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1 if enabled else 0)
        if server:
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, server)
        if override is not None:
            winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, override)
    refresh_wininet()
    return read_proxy_state()


class ProxyHelperHandler(BaseHTTPRequestHandler):
    server_version = "LiteNodeGatewaySystemProxyHelper/1.0"

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
        self.send_json({"ok": True})

    def do_GET(self) -> None:
        if not client_allowed(self.client_address[0]):
            self.send_json({"ok": False, "error": "Forbidden."}, HTTPStatus.FORBIDDEN)
            return
        if self.path.split("?", 1)[0] != "/api/system-proxy":
            self.send_json({"ok": False, "error": "Not found."}, HTTPStatus.NOT_FOUND)
            return
        try:
            self.send_json({"ok": True, **read_proxy_state()})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

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
            self.send_json({"ok": True, **write_proxy_state(enabled, server, override_value)})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)


def main() -> int:
    if sys.platform != "win32":
        print("This helper only supports Windows.", file=sys.stderr)
        return 1
    server = ThreadingHTTPServer((HOST, PORT), ProxyHelperHandler)
    print(f"System proxy helper listening on http://127.0.0.1:{PORT}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
