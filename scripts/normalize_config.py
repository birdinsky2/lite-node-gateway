import argparse
import copy
import pathlib
import re
import sys

import yaml


class QuotedString(str):
    pass


class GatewayYamlDumper(yaml.SafeDumper):
    pass


def quoted_string_representer(dumper, value):
    return dumper.represent_scalar("tag:yaml.org,2002:str", str(value), style='"')


GatewayYamlDumper.add_representer(QuotedString, quoted_string_representer)

DIRECT_RULES = [
    "DOMAIN,localhost,DIRECT",
    "DOMAIN-SUFFIX,local,DIRECT",
    "IP-CIDR,127.0.0.0/8,DIRECT,no-resolve",
    "IP-CIDR,10.0.0.0/8,DIRECT,no-resolve",
    "IP-CIDR,172.16.0.0/12,DIRECT,no-resolve",
    "IP-CIDR,192.168.0.0/16,DIRECT,no-resolve",
    "IP-CIDR,169.254.0.0/16,DIRECT,no-resolve",
    "IP-CIDR6,::1/128,DIRECT,no-resolve",
    "IP-CIDR6,fc00::/7,DIRECT,no-resolve",
    "IP-CIDR6,fe80::/10,DIRECT,no-resolve",
]


def quote_reality_yaml_scalars(text: str) -> str:
    def replace(match):
        prefix, value, suffix = match.groups()
        stripped = value.strip()
        if not stripped or stripped[0] in {"'", '"', "|", ">", "[", "{"}:
            return match.group(0)
        escaped = stripped.replace("\\", "\\\\").replace('"', '\\"')
        return f'{prefix}"{escaped}"{suffix}'

    return re.sub(r"^(\s*(?:public-key|short-id):\s*)([^#\r\n]*?)(\s*(?:#.*)?)$", replace, text, flags=re.MULTILINE)


def normalize_mihomo_proxy(proxy):
    item = copy.deepcopy(proxy)
    reality_opts = item.get("reality-opts")
    if isinstance(reality_opts, dict):
        for key in ("public-key", "short-id"):
            if reality_opts.get(key) is not None:
                reality_opts[key] = QuotedString(str(reality_opts[key]))
    return item


def read_yaml(path: pathlib.Path):
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            text = quote_reality_yaml_scalars(data.decode(encoding))
            return yaml.safe_load(text) or {}
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"Cannot decode subscription file: {path}")


def unique_proxy_names(proxies):
    names = []
    seen = set()
    normalized = []
    for index, proxy in enumerate(proxies, start=1):
        if not isinstance(proxy, dict):
            continue
        item = copy.deepcopy(proxy)
        name = str(item.get("name") or f"node-{index}").strip()
        if not name:
            name = f"node-{index}"
        base = name
        suffix = 2
        while name in seen:
            name = f"{base} #{suffix}"
            suffix += 1
        item["name"] = name
        item = normalize_mihomo_proxy(item)
        seen.add(name)
        names.append(name)
        normalized.append(item)
    return normalized, names


def build_config(source, mixed_port, controller_port, secret, group_name, auto_group):
    raw = read_yaml(source)
    proxies, names = unique_proxy_names(raw.get("proxies") or [])
    if not names:
        raise SystemExit("No proxies found in the subscription file. This MVP expects a Clash/Mihomo YAML with a top-level 'proxies' list.")

    dns = raw.get("dns")
    if not isinstance(dns, dict):
        dns = {
            "enable": True,
            "ipv6": False,
            "enhanced-mode": "fake-ip",
            "fake-ip-range": "198.18.0.1/16",
            "default-nameserver": ["223.5.5.5", "119.29.29.29"],
            "nameserver": ["https://dns.alidns.com/dns-query", "https://doh.pub/dns-query"],
        }

    selectable = [auto_group] + names + ["DIRECT"]
    return {
        "mixed-port": mixed_port,
        "allow-lan": True,
        "bind-address": "*",
        "mode": "rule",
        "log-level": "info",
        "external-controller": f"0.0.0.0:{controller_port}",
        "secret": secret,
        "unified-delay": True,
        "tcp-concurrent": True,
        "dns": dns,
        "proxies": proxies,
        "proxy-groups": [
            {
                "name": auto_group,
                "type": "url-test",
                "proxies": names,
                "url": "http://www.gstatic.com/generate_204",
                "interval": 600,
                "tolerance": 50,
            },
            {
                "name": group_name,
                "type": "select",
                "proxies": selectable,
            },
        ],
        "rules": [*DIRECT_RULES, f"MATCH,{group_name}"],
    }


def main():
    parser = argparse.ArgumentParser(description="Convert a Clash/Mihomo subscription YAML into a single-port selectable gateway config.")
    parser.add_argument("--source", required=True)
    parser.add_argument("--dest", required=True)
    parser.add_argument("--mixed-port", type=int, default=7897)
    parser.add_argument("--controller-port", type=int, default=9090)
    parser.add_argument("--secret", default="")
    parser.add_argument("--group-name", default="NODE")
    parser.add_argument("--auto-group", default="AUTO")
    args = parser.parse_args()

    source = pathlib.Path(args.source)
    dest = pathlib.Path(args.dest)
    config = build_config(source, args.mixed_port, args.controller_port, args.secret, args.group_name, args.auto_group)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(yaml.dump(config, Dumper=GatewayYamlDumper, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"Wrote {dest}")
    print(f"Imported {len(config['proxies'])} nodes into group {args.group_name}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
