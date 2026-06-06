param(
  [Parameter(Mandatory = $true)]
  [string]$Source,

  [string]$Secret = "",
  [switch]$NoStart
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$DataDir = Join-Path $Root "data"
$Downloaded = Join-Path $DataDir "subscription.yaml"
$Config = Join-Path $DataDir "config.yaml"
New-Item -ItemType Directory -Force -Path $DataDir | Out-Null

if ($Source -match '^https?://') {
  Invoke-WebRequest -UseBasicParsing -Uri $Source -OutFile $Downloaded
  $SourcePath = $Downloaded
} else {
  $SourcePath = (Resolve-Path -LiteralPath $Source).Path
}

$normalizeArgs = @(
  (Join-Path $Root "scripts\normalize_config.py"),
  "--source", $SourcePath,
  "--dest", $Config
)
if (-not [string]::IsNullOrWhiteSpace($Secret)) {
  $normalizeArgs += @("--secret", $Secret)
}

python @normalizeArgs

if (-not $NoStart) {
  docker compose -f (Join-Path $Root "docker-compose.yml") up -d
}

Write-Host ""
Write-Host "Proxy:      http://127.0.0.1:7896"
if ([string]::IsNullOrWhiteSpace($Secret)) {
  Write-Host "Controller: http://127.0.0.1:9090  Secret: <empty>"
} else {
  Write-Host "Controller: http://127.0.0.1:9090  Secret: $Secret"
}
Write-Host "Dashboard:  http://127.0.0.1:8088"
