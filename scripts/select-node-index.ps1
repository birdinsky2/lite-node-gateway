param(
  [Parameter(Mandatory = $true)]
  [int]$Index,

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

$proxies = Invoke-RestMethod -Uri "$Controller/proxies" -Headers $headers
$groupInfo = $proxies.proxies.$Group
if (-not $groupInfo) {
  throw "Group '$Group' was not found."
}

$nodes = @($groupInfo.all)
if ($Index -lt 1 -or $Index -gt $nodes.Count) {
  throw "Index must be between 1 and $($nodes.Count)."
}

$node = $nodes[$Index - 1]
$encodedGroup = [uri]::EscapeDataString($Group)
$body = @{ name = $node } | ConvertTo-Json -Compress
Invoke-RestMethod -Uri "$Controller/proxies/$encodedGroup" -Method Put -Headers $headers -ContentType "application/json; charset=utf-8" -Body $body | Out-Null

$after = Invoke-RestMethod -Uri "$Controller/proxies" -Headers $headers
Write-Host "Selected [$Index]: $($after.proxies.$Group.now)"
