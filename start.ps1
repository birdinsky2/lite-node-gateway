param(
  [switch]$Build,
  [switch]$SkipHelper,
  [switch]$SkipDocker,
  [int]$HelperPort = 18089,
  [int]$HelperWaitSeconds = 8
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$ComposeFile = Join-Path $Root "docker-compose.yml"
$HelperScript = Join-Path $Root "scripts\system_proxy_helper.py"
$DataDir = Join-Path $Root "data"
$LogDir = Join-Path $DataDir "logs"
$HelperOutLog = Join-Path $LogDir "system-proxy-helper.out.log"
$HelperErrLog = Join-Path $LogDir "system-proxy-helper.err.log"
$HelperUrl = "http://127.0.0.1:$HelperPort/api/system-proxy"

function Test-SystemProxyHelper {
  try {
    $response = Invoke-RestMethod -Uri $HelperUrl -TimeoutSec 2
    return ($response.ok -eq $true)
  } catch {
    return $false
  }
}

function Get-HelperListenerPids {
  @(Get-NetTCPConnection -LocalPort $HelperPort -State Listen -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique)
}

function Get-PythonLaunch {
  $python = Get-Command python -ErrorAction SilentlyContinue
  if ($python) {
    return @{
      FilePath = $python.Source
      Args = @($HelperScript)
      Display = "python"
    }
  }

  $py = Get-Command py -ErrorAction SilentlyContinue
  if ($py) {
    return @{
      FilePath = $py.Source
      Args = @("-3", $HelperScript)
      Display = "py -3"
    }
  }

  throw "Python was not found. Install Python or add it to PATH before starting the system proxy helper."
}

function Start-SystemProxyHelper {
  if (-not (Test-Path -LiteralPath $HelperScript)) {
    throw "System proxy helper script was not found: $HelperScript"
  }

  if (Test-SystemProxyHelper) {
    Write-Host "System proxy helper is already running: $HelperUrl"
    return
  }

  $listeners = Get-HelperListenerPids
  if ($listeners.Count -gt 0) {
    $owners = foreach ($listenerPid in $listeners) {
      $process = Get-Process -Id $listenerPid -ErrorAction SilentlyContinue
      if ($process) {
        "$($process.Id) $($process.ProcessName)"
      } else {
        "$listenerPid <unknown>"
      }
    }
    throw "Port $HelperPort is already listening, but helper health check failed. Owning process(es): $($owners -join ', ')"
  }

  New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
  $launch = Get-PythonLaunch
  Write-Host "Starting system proxy helper with $($launch.Display) ..."
  $process = Start-Process `
    -FilePath $launch.FilePath `
    -ArgumentList $launch.Args `
    -WorkingDirectory $Root `
    -WindowStyle Hidden `
    -RedirectStandardOutput $HelperOutLog `
    -RedirectStandardError $HelperErrLog `
    -PassThru

  $deadline = (Get-Date).AddSeconds($HelperWaitSeconds)
  while ((Get-Date) -lt $deadline) {
    if (Test-SystemProxyHelper) {
      Write-Host "System proxy helper started. PID: $($process.Id)"
      return
    }
    Start-Sleep -Milliseconds 300
  }

  $errTail = ""
  if (Test-Path -LiteralPath $HelperErrLog) {
    $errTail = (Get-Content -LiteralPath $HelperErrLog -Tail 20 -ErrorAction SilentlyContinue) -join [Environment]::NewLine
  }
  if ([string]::IsNullOrWhiteSpace($errTail)) {
    $errTail = "No stderr output. Logs: $HelperOutLog, $HelperErrLog"
  }
  throw "System proxy helper did not become healthy within $HelperWaitSeconds second(s). $errTail"
}

if (-not $SkipHelper) {
  Start-SystemProxyHelper
}

if (-not $SkipDocker) {
  if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker was not found in PATH."
  }
  if (-not (Test-Path -LiteralPath $ComposeFile)) {
    throw "docker-compose.yml was not found: $ComposeFile"
  }

  $composeArgs = @("compose", "-f", $ComposeFile, "up", "-d")
  if ($Build) {
    $composeArgs += "--build"
  }

  Write-Host "Starting Docker services ..."
  & docker @composeArgs
  if ($LASTEXITCODE -ne 0) {
    throw "docker compose up failed with exit code $LASTEXITCODE."
  }
}

Write-Host ""
Write-Host "Ready."
Write-Host "Manager:      http://127.0.0.1:8089"
Write-Host "Dashboard:    http://127.0.0.1:8088"
Write-Host "Main proxy:   http://127.0.0.1:7896"
Write-Host "Helper:       $HelperUrl"
