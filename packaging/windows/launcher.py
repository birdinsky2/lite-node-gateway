from __future__ import annotations

import argparse
import atexit
import json
import os
import pathlib
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from typing import Iterable


APP_NAME = "Lite Node Gateway"
DEFAULT_MANAGER_PORT = 8089
DEFAULT_HELPER_PORT = 18089
DEFAULT_PROXY_PORT = 7896
DEFAULT_CONTROLLER_PORT = 9090


def app_root() -> pathlib.Path:
    if getattr(sys, "frozen", False):
        return pathlib.Path(sys.executable).resolve().parent
    return pathlib.Path(__file__).resolve().parents[2]


def http_json(url: str, timeout: float = 2.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")
    try:
        value = json.loads(body or "{}")
    except json.JSONDecodeError:
        return {"ok": False, "raw": body}
    return value if isinstance(value, dict) else {"ok": False, "raw": value}


def wait_for(name: str, url: str, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    last_error = ""
    while time.monotonic() < deadline:
        try:
            payload = http_json(url)
            if payload.get("ok", True) is not False:
                return payload
            last_error = str(payload)
        except Exception as exc:  # noqa: BLE001 - display startup diagnostics.
            last_error = str(exc)
        time.sleep(0.35)
    raise RuntimeError(f"{name} did not become ready at {url}. Last error: {last_error}")


def ensure_initial_config(data_dir: pathlib.Path, proxy_port: int, controller_port: int) -> pathlib.Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "subscriptions").mkdir(parents=True, exist_ok=True)
    config_file = data_dir / "config.yaml"
    if config_file.exists():
        return config_file

    config_file.write_text(
        "\n".join(
            [
                f"mixed-port: {proxy_port}",
                "allow-lan: true",
                'bind-address: "*"',
                "mode: rule",
                "log-level: info",
                f"external-controller: 127.0.0.1:{controller_port}",
                'secret: ""',
                "unified-delay: true",
                "tcp-concurrent: true",
                "profile:",
                "  store-selected: true",
                "  store-fake-ip: true",
                "dns:",
                "  enable: true",
                "  ipv6: false",
                "  enhanced-mode: fake-ip",
                "  fake-ip-range: 198.18.0.1/16",
                "  default-nameserver:",
                "    - 223.5.5.5",
                "    - 119.29.29.29",
                "  nameserver:",
                "    - https://dns.alidns.com/dns-query",
                "    - https://doh.pub/dns-query",
                "proxies: []",
                "proxy-groups:",
                "  - name: AUTO",
                "    type: select",
                "    proxies:",
                "      - DIRECT",
                "  - name: NODE",
                "    type: select",
                "    proxies:",
                "      - DIRECT",
                "listeners: []",
                "rules:",
                "  - MATCH,NODE",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return config_file


def open_log(path: pathlib.Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.open("ab")


def start_process(
    name: str,
    args: list[str],
    cwd: pathlib.Path,
    env: dict[str, str],
    log_dir: pathlib.Path,
) -> subprocess.Popen:
    stdout = open_log(log_dir / f"{name}.out.log")
    stderr = open_log(log_dir / f"{name}.err.log")
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    return subprocess.Popen(
        args,
        cwd=str(cwd),
        env=env,
        stdout=stdout,
        stderr=stderr,
        stdin=subprocess.DEVNULL,
        creationflags=creationflags,
    )


def terminate_processes(processes: Iterable[subprocess.Popen]) -> None:
    for process in reversed(list(processes)):
        if process.poll() is not None:
            continue
        try:
            if os.name == "nt":
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                process.terminate()
        except Exception:
            process.terminate()

    deadline = time.monotonic() + 6
    for process in reversed(list(processes)):
        while process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.1)
        if process.poll() is None:
            process.kill()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"Start {APP_NAME} without Docker.")
    parser.add_argument("--data-dir", help="Runtime data directory. Defaults to ./data beside the launcher.")
    parser.add_argument("--manager-port", type=int, default=DEFAULT_MANAGER_PORT)
    parser.add_argument("--helper-port", type=int, default=DEFAULT_HELPER_PORT)
    parser.add_argument("--proxy-port", type=int, default=DEFAULT_PROXY_PORT)
    parser.add_argument("--controller-port", type=int, default=DEFAULT_CONTROLLER_PORT)
    parser.add_argument("--no-browser", action="store_true", help="Do not open the Manager page automatically.")
    parser.add_argument("--run-seconds", type=int, default=0, help="Stop automatically after N seconds. Useful for smoke tests.")
    parser.add_argument("--wait-seconds", type=int, default=35)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = app_root()
    data_dir = pathlib.Path(args.data_dir).resolve() if args.data_dir else root / "data"
    log_dir = data_dir / "logs"

    manager_exe = root / "manager.exe"
    helper_exe = root / "system-proxy-helper.exe"
    mihomo_exe = root / "bin" / "mihomo.exe"
    missing = [str(path) for path in (manager_exe, helper_exe, mihomo_exe) if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing bundled executable(s): " + ", ".join(missing))

    config_file = ensure_initial_config(data_dir, args.proxy_port, args.controller_port)
    env = os.environ.copy()
    env.update(
        {
            "GATEWAY_DATA_DIR": str(data_dir),
            "MIHOMO_API_URL": f"http://127.0.0.1:{args.controller_port}",
            "MIHOMO_CONFIG_IN_CORE": str(config_file),
            "MIHOMO_MIXED_PORT": str(args.proxy_port),
            "MIHOMO_EXTERNAL_CONTROLLER": f"127.0.0.1:{args.controller_port}",
            "SYSTEM_PROXY_HELPER_URL": f"http://127.0.0.1:{args.helper_port}",
            "SYSTEM_PROXY_SERVER": f"127.0.0.1:{args.proxy_port}",
            "SYSTEM_PROXY_TEST_PROXY": f"http://127.0.0.1:{args.proxy_port}",
            "MANAGER_HOST": "127.0.0.1",
            "MANAGER_PORT": str(args.manager_port),
            "SYSTEM_PROXY_HELPER_HOST": "127.0.0.1",
            "SYSTEM_PROXY_HELPER_PORT": str(args.helper_port),
        }
    )

    processes: list[subprocess.Popen] = []
    atexit.register(lambda: terminate_processes(processes))

    print(f"Starting {APP_NAME} ...")
    print(f"Data: {data_dir}")
    print(f"Logs: {log_dir}")

    processes.append(
        start_process(
            "mihomo",
            [str(mihomo_exe), "-d", str(data_dir), "-f", str(config_file)],
            root,
            env,
            log_dir,
        )
    )
    wait_for("mihomo", f"http://127.0.0.1:{args.controller_port}/version", args.wait_seconds)

    processes.append(start_process("system-proxy-helper", [str(helper_exe)], root, env, log_dir))
    wait_for("system-proxy-helper", f"http://127.0.0.1:{args.helper_port}/api/system-proxy", args.wait_seconds)

    processes.append(start_process("manager", [str(manager_exe)], root, env, log_dir))
    wait_for("manager", f"http://127.0.0.1:{args.manager_port}/api/health", args.wait_seconds)

    manager_url = f"http://127.0.0.1:{args.manager_port}"
    print("")
    print("Ready.")
    print(f"Manager:    {manager_url}")
    print(f"Main proxy: http://127.0.0.1:{args.proxy_port}")
    print(f"Core API:   http://127.0.0.1:{args.controller_port}")
    print(f"Helper:     http://127.0.0.1:{args.helper_port}/api/system-proxy")
    print("")
    print("Keep this window open while using the gateway. Press Ctrl+C to stop.")
    if not args.no_browser:
        webbrowser.open(manager_url)

    try:
        if args.run_seconds > 0:
            time.sleep(args.run_seconds)
            print("Timed run finished.")
            return 0
        while True:
            for process in processes:
                code = process.poll()
                if code is not None:
                    raise RuntimeError(f"A child process exited unexpectedly with code {code}: PID {process.pid}")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping ...")
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, FileNotFoundError, urllib.error.URLError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
