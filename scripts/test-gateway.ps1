param(
  [string]$Proxy = "http://127.0.0.1:7896"
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
Invoke-WebRequest -UseBasicParsing -Uri "https://ipinfo.io/json" -Proxy $Proxy -TimeoutSec 30 |
  Select-Object -ExpandProperty Content
