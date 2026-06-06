param(
  [Parameter(Mandatory = $true)]
  [int]$Port,

  [string]$Node,
  [int]$Index,
  [string]$Listen = "0.0.0.0",
  [switch]$Remove,
  [switch]$NoRestart
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Config = Join-Path $Root "data\config.yaml"

if ($Port -lt 7900 -or $Port -gt 7999) {
  throw "This project exposes host ports 7900-7999 for fixed node bindings. Pick a port in that range."
}

if ($Remove) {
  python (Join-Path $Root "scripts\bind_port.py") --config $Config --port $Port --remove
} else {
  if (-not [string]::IsNullOrWhiteSpace($Node) -and $PSBoundParameters.ContainsKey("Index")) {
    throw "Use either -Node or -Index, not both."
  }
  if ($PSBoundParameters.ContainsKey("Index")) {
    $proxies = Invoke-RestMethod -Uri "http://127.0.0.1:9090/proxies"
    $nodes = @($proxies.proxies.NODE.all)
    if ($Index -lt 1 -or $Index -gt $nodes.Count) {
      throw "Index must be between 1 and $($nodes.Count)."
    }
    $Node = $nodes[$Index - 1]
  }
  if ([string]::IsNullOrWhiteSpace($Node)) {
    throw "Provide -Node 'name' or -Index n."
  }
  python (Join-Path $Root "scripts\bind_port.py") --config $Config --port $Port --node $Node --listen $Listen
}

docker compose -f (Join-Path $Root "docker-compose.yml") exec -T mihomo /mihomo -t -f /root/.config/mihomo/config.yaml
if (-not $NoRestart) {
  docker compose -f (Join-Path $Root "docker-compose.yml") up -d --force-recreate mihomo
}
