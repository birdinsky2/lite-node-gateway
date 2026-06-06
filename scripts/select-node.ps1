param(
  [Parameter(Mandatory = $true)]
  [string]$Node,

  [string]$Controller = "http://127.0.0.1:9090",
  [string]$Secret = "",
  [string]$Group = "NODE"
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$headers = @{}
if (-not [string]::IsNullOrWhiteSpace($Secret)) {
  $headers.Authorization = "Bearer $Secret"
}
$encodedGroup = [uri]::EscapeDataString($Group)
$body = @{ name = $Node } | ConvertTo-Json -Compress
Invoke-RestMethod -Uri "$Controller/proxies/$encodedGroup" -Method Put -Headers $headers -ContentType "application/json" -Body $body | Out-Null
$proxies = Invoke-RestMethod -Uri "$Controller/proxies" -Headers $headers
Write-Host "Selected: $($proxies.proxies.$Group.now)"
