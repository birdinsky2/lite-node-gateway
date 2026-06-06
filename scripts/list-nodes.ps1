param(
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
$proxies = Invoke-RestMethod -Uri "$Controller/proxies" -Headers $headers
$groupInfo = $proxies.proxies.$Group
if (-not $groupInfo) {
  throw "Group '$Group' was not found."
}

Write-Host "Group:   $Group"
Write-Host "Current: $($groupInfo.now)"
Write-Host ""
Write-Host "Available:"
$i = 1
$groupInfo.all | ForEach-Object {
  Write-Host ("  {0}. {1}" -f $i, $_)
  $i++
}
