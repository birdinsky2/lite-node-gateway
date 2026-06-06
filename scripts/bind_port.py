import argparse
import pathlib
import sys

import yaml


def load_config(path: pathlib.Path):
    if not path.exists():
        raise SystemExit(f"Config file not found: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def dump_config(path: pathlib.Path, config):
    path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")


def all_proxy_names(config):
    names = {"DIRECT", "REJECT", "GLOBAL"}
    for proxy in config.get("proxies") or []:
        if isinstance(proxy, dict) and proxy.get("name"):
            names.add(str(proxy["name"]))
    for group in config.get("proxy-groups") or []:
        if isinstance(group, dict) and group.get("name"):
            names.add(str(group["name"]))
    return names


def normalize_listeners(config):
    listeners = config.get("listeners")
    if not isinstance(listeners, list):
        listeners = []
    config["listeners"] = listeners
    return listeners


def bind_port(config, port, node, listen):
    if port < 1 or port > 65535:
        raise SystemExit("Port must be between 1 and 65535.")
    names = all_proxy_names(config)
    if node not in names:
        raise SystemExit(f"Node or group not found: {node}")

    listeners = normalize_listeners(config)
    name = f"port-{port}"
    replacement = {
        "name": name,
        "type": "mixed",
        "listen": listen,
        "port": port,
        "proxy": node,
        "udp": True,
    }

    kept = []
    for item in listeners:
        if not isinstance(item, dict):
            continue
        if item.get("name") == name or int(item.get("port") or -1) == port:
            continue
        kept.append(item)
    kept.append(replacement)
    config["listeners"] = sorted(kept, key=lambda x: int(x.get("port") or 0))


def remove_port(config, port):
    listeners = normalize_listeners(config)
    config["listeners"] = [
        item for item in listeners
        if isinstance(item, dict) and item.get("name") != f"port-{port}" and int(item.get("port") or -1) != port
    ]


def main():
    parser = argparse.ArgumentParser(description="Bind a mihomo listener port to a node/group.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--node")
    parser.add_argument("--listen", default="0.0.0.0")
    parser.add_argument("--remove", action="store_true")
    args = parser.parse_args()

    config_path = pathlib.Path(args.config)
    config = load_config(config_path)
    if args.remove:
        remove_port(config, args.port)
        action = f"Removed listener port {args.port}"
    else:
        if not args.node:
            raise SystemExit("--node is required unless --remove is used.")
        bind_port(config, args.port, args.node, args.listen)
        action = f"Bound port {args.port} to {args.node}"
    dump_config(config_path, config)
    print(action)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
