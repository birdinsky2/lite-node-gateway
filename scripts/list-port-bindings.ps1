$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Config = Join-Path $Root "data\config.yaml"
@'
import pathlib
import yaml

config = yaml.safe_load(pathlib.Path(r"CONFIG_PATH").read_text(encoding="utf-8")) or {}
listeners = config.get("listeners") or []
rows = []
for item in listeners:
    if isinstance(item, dict) and str(item.get("name", "")).startswith("port-"):
        rows.append((int(item.get("port") or 0), item.get("proxy", ""), item.get("listen", "")))
for port, proxy, listen in sorted(rows):
    print(f"{port}\t{listen}\t{proxy}")
if not rows:
    print("No fixed port bindings.")
'@.Replace("CONFIG_PATH", $Config.Replace("\", "\\")) | python -
