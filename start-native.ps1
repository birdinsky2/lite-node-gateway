param(
  [switch]$BuildFrontend,
  [switch]$SkipFrontendBuild,
  [switch]$SkipHelper,
  [switch]$NoBrowser,
  [switch]$SkipMihomoDownload,
  [int]$RunSeconds = 0,
  [int]$ManagerPort = 8089,
  [int]$ProxyPort = 7896,
  [int]$ControllerPort = 9090,
  [int]$HelperPort = 18089,
  [int]$WaitSeconds = 35,
  [string]$DataDir = "",
  [string]$MihomoVersion = "v1.19.26"
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$ManagerDir = Join-Path $Root "manager"
$FrontendDir = Join-Path $ManagerDir "frontend"
$StaticDir = Join-Path $ManagerDir "static"
$RequirementsFile = Join-Path $ManagerDir "requirements.txt"
$HelperScript = Join-Path $Root "scripts\system_proxy_helper.py"
$VenvDir = Join-Path $Root ".venv-windows"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VendorMihomoDir = Join-Path $Root "vendor\mihomo\windows-amd64"
$MihomoExe = Join-Path $VendorMihomoDir "mihomo.exe"
$BuildDir = Join-Path $Root "build\native"

if ([string]::IsNullOrWhiteSpace($DataDir)) {
  $DataDir = Join-Path $Root "data"
}
$DataDir = [System.IO.Path]::GetFullPath($DataDir)
$LogDir = Join-Path $DataDir "logs"
$ConfigFile = Join-Path $DataDir "config.yaml"
$ManagerUrl = "http://127.0.0.1:$ManagerPort"
$ControllerUrl = "http://127.0.0.1:$ControllerPort"
$HelperUrl = "http://127.0.0.1:$HelperPort/api/system-proxy"

function Require-Command {
  param([string]$Name)
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "$Name was not found in PATH."
  }
}

function Get-PythonLaunch {
  $python = Get-Command python -ErrorAction SilentlyContinue
  if ($python) {
    return @{ FilePath = $python.Source; Args = @(); Display = "python" }
  }
  $py = Get-Command py -ErrorAction SilentlyContinue
  if ($py) {
    return @{ FilePath = $py.Source; Args = @("-3"); Display = "py -3" }
  }
  throw "Python 3 was not found. Install Python 3.11+ and rerun this script."
}

function Invoke-Checked {
  param(
    [string]$FilePath,
    [string[]]$Arguments,
    [string]$WorkingDirectory = $Root
  )
  & $FilePath @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($Arguments -join ' ')"
  }
}

function Test-FrontendStatic {
  $index = Join-Path $StaticDir "index.html"
  $assets = Join-Path $StaticDir "assets"
  if (-not (Test-Path -LiteralPath $index) -or -not (Test-Path -LiteralPath $assets)) {
    return $false
  }
  return @(Get-ChildItem -LiteralPath $assets -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Extension -in @(".js", ".css") }).Count -gt 0
}

function Build-FrontendIfNeeded {
  if ($SkipFrontendBuild -and -not (Test-FrontendStatic)) {
    throw "manager/static is missing. Rerun without -SkipFrontendBuild or build the frontend first."
  }
  if (-not $BuildFrontend -and (Test-FrontendStatic)) {
    Write-Host "Using existing frontend build: $StaticDir"
    return
  }

  Require-Command npm
  Write-Host "Building frontend ..."
  Push-Location $FrontendDir
  try {
    if (-not (Test-Path -LiteralPath (Join-Path $FrontendDir "node_modules"))) {
      npm ci
      if ($LASTEXITCODE -ne 0) { throw "npm ci failed with exit code $LASTEXITCODE." }
    }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "npm run build failed with exit code $LASTEXITCODE." }
  } finally {
    Pop-Location
  }
}

function Ensure-PythonEnv {
  $launch = Get-PythonLaunch
  if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Host "Creating Python virtual environment with $($launch.Display) ..."
    Invoke-Checked -FilePath $launch.FilePath -Arguments ($launch.Args + @("-m", "venv", $VenvDir))
  }

  $previousErrorActionPreference = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  try {
    & $VenvPython -c "import yaml, requests" *> $null
    $dependencyCheckExitCode = $LASTEXITCODE
  } finally {
    $ErrorActionPreference = $previousErrorActionPreference
  }
  if ($dependencyCheckExitCode -eq 0) {
    Write-Host "Using existing Python dependencies: $VenvDir"
    return
  }

  Write-Host "Installing Python dependencies ..."
  Invoke-Checked -FilePath $VenvPython -Arguments @("-m", "pip", "install", "--upgrade", "pip")
  Invoke-Checked -FilePath $VenvPython -Arguments @("-m", "pip", "install", "-r", $RequirementsFile)
}

function Download-File {
  param(
    [string[]]$Urls,
    [string]$OutFile
  )
  Require-Command curl.exe
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $OutFile) | Out-Null
  foreach ($url in $Urls) {
    Write-Host "Downloading $url"
    & curl.exe -L --retry 3 --retry-delay 2 --connect-timeout 20 --max-time 240 -o $OutFile $url
    if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $OutFile) -and (Get-Item -LiteralPath $OutFile).Length -gt 1000000) {
      return
    }
    if (Test-Path -LiteralPath $OutFile) {
      Remove-Item -LiteralPath $OutFile -Force
    }
  }
  throw "Could not download mihomo $MihomoVersion."
}

function Ensure-Mihomo {
  if (Test-Path -LiteralPath $MihomoExe) {
    Write-Host "Using existing mihomo: $MihomoExe"
    return
  }
  if ($SkipMihomoDownload) {
    throw "mihomo.exe was not found. Place it at $MihomoExe or rerun without -SkipMihomoDownload."
  }

  $zipPath = Join-Path $BuildDir "mihomo-windows.zip"
  $urls = @(
    "https://downloads.sourceforge.net/project/mihomo.mirror/$MihomoVersion/mihomo-windows-amd64-v1-$MihomoVersion.zip",
    "https://downloads.sourceforge.net/project/mihomo.mirror/$MihomoVersion/mihomo-windows-amd64-compatible-$MihomoVersion.zip",
    "https://downloads.sourceforge.net/project/mihomo.mirror/$MihomoVersion/mihomo-windows-amd64-$MihomoVersion.zip",
    "https://github.com/MetaCubeX/mihomo/releases/download/$MihomoVersion/mihomo-windows-amd64-v1-$MihomoVersion.zip",
    "https://github.com/MetaCubeX/mihomo/releases/download/$MihomoVersion/mihomo-windows-amd64-compatible-$MihomoVersion.zip",
    "https://github.com/MetaCubeX/mihomo/releases/download/$MihomoVersion/mihomo-windows-amd64-$MihomoVersion.zip"
  )
  Download-File -Urls $urls -OutFile $zipPath

  $extractDir = Join-Path $BuildDir "mihomo-extract"
  if (Test-Path -LiteralPath $extractDir) {
    Remove-Item -LiteralPath $extractDir -Recurse -Force
  }
  Expand-Archive -LiteralPath $zipPath -DestinationPath $extractDir -Force
  $candidate = Get-ChildItem -LiteralPath $extractDir -Recurse -File |
    Where-Object { $_.Name -eq "mihomo.exe" -or $_.Name -like "mihomo*.exe" } |
    Select-Object -First 1
  if (-not $candidate) {
    throw "Downloaded archive did not contain mihomo.exe."
  }
  New-Item -ItemType Directory -Force -Path $VendorMihomoDir | Out-Null
  Copy-Item -LiteralPath $candidate.FullName -Destination $MihomoExe -Force
}

function Ensure-InitialConfig {
  New-Item -ItemType Directory -Force -Path $DataDir, (Join-Path $DataDir "subscriptions"), $LogDir | Out-Null
  if (Test-Path -LiteralPath $ConfigFile) {
    return
  }

  $config = @(
    "mixed-port: $ProxyPort",
    "allow-lan: true",
    "bind-address: ""*""",
    "mode: rule",
    "log-level: info",
    "external-controller: 127.0.0.1:$ControllerPort",
    "secret: """"",
    "unified-delay: true",
    "tcp-concurrent: true",
    "profile:",
    "  store-selected: true",
    "  store-fake-ip: true",
    "dns:",
    "  enable: true",
    "  ipv6: false",
    "  enhanced-mode: fake-ip",
    "  fake-ip-range: 198.18.0.1/16",
    "  default-nameserver:",
    "    - 223.5.5.5",
    "    - 119.29.29.29",
    "  nameserver:",
    "    - https://dns.alidns.com/dns-query",
    "    - https://doh.pub/dns-query",
    "proxies: []",
    "proxy-groups:",
    "  - name: AUTO",
    "    type: select",
    "    proxies:",
    "      - DIRECT",
    "  - name: NODE",
    "    type: select",
    "    proxies:",
    "      - DIRECT",
    "listeners: []",
    "rules:",
    "  - MATCH,NODE",
    ""
  ) -join [Environment]::NewLine
  Set-Content -LiteralPath $ConfigFile -Value $config -Encoding UTF8
}

function Wait-Http {
  param(
    [string]$Name,
    [string]$Url
  )
  $deadline = (Get-Date).AddSeconds($WaitSeconds)
  $lastError = ""
  while ((Get-Date) -lt $deadline) {
    try {
      Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2 | Out-Null
      return
    } catch {
      $lastError = $_.Exception.Message
      Start-Sleep -Milliseconds 350
    }
  }
  throw "$Name did not become ready at $Url. Last error: $lastError"
}

function Test-HttpReady {
  param([string]$Url)
  try {
    Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2 | Out-Null
    return $true
  } catch {
    return $false
  }
}

function Start-LoggedProcess {
  param(
    [string]$Name,
    [string]$FilePath,
    [string[]]$ArgumentList
  )
  $outLog = Join-Path $LogDir "$Name.out.log"
  $errLog = Join-Path $LogDir "$Name.err.log"
  Write-Host "Starting $Name ..."
  Start-Process `
    -FilePath $FilePath `
    -ArgumentList $ArgumentList `
    -WorkingDirectory $Root `
    -WindowStyle Hidden `
    -RedirectStandardOutput $outLog `
    -RedirectStandardError $errLog `
    -PassThru
}

function Stop-StartedProcesses {
  param([System.Collections.ArrayList]$Processes)
  for ($i = $Processes.Count - 1; $i -ge 0; $i--) {
    $process = $Processes[$i]
    if ($process -and -not $process.HasExited) {
      try {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
      } catch {
        # Ignore shutdown races.
      }
    }
  }
}

Build-FrontendIfNeeded
Ensure-PythonEnv
Ensure-Mihomo
Ensure-InitialConfig

$env:GATEWAY_DATA_DIR = $DataDir
$env:MIHOMO_API_URL = $ControllerUrl
$env:MIHOMO_CONFIG_IN_CORE = $ConfigFile
$env:MIHOMO_MIXED_PORT = "$ProxyPort"
$env:MIHOMO_EXTERNAL_CONTROLLER = "127.0.0.1:$ControllerPort"
$env:SYSTEM_PROXY_HELPER_URL = "http://127.0.0.1:$HelperPort"
$env:SYSTEM_PROXY_SERVER = "127.0.0.1:$ProxyPort"
$env:SYSTEM_PROXY_TEST_PROXY = "http://127.0.0.1:$ProxyPort"
$env:PORT_PROBE_PROXY_HOST = "127.0.0.1"
$env:MANAGER_HOST = "127.0.0.1"
$env:MANAGER_PORT = "$ManagerPort"
$env:SYSTEM_PROXY_HELPER_HOST = "127.0.0.1"
$env:SYSTEM_PROXY_HELPER_PORT = "$HelperPort"

$processes = [System.Collections.ArrayList]::new()
try {
  [void]$processes.Add((Start-LoggedProcess -Name "mihomo" -FilePath $MihomoExe -ArgumentList @("-d", $DataDir, "-f", $ConfigFile)))
  Wait-Http -Name "mihomo" -Url "$ControllerUrl/version"

  if (-not $SkipHelper) {
    if (Test-HttpReady -Url $HelperUrl) {
      Write-Host "System proxy helper is already running: $HelperUrl"
    } else {
      [void]$processes.Add((Start-LoggedProcess -Name "system-proxy-helper" -FilePath $VenvPython -ArgumentList @($HelperScript)))
      Wait-Http -Name "system-proxy-helper" -Url $HelperUrl
    }
  }

  [void]$processes.Add((Start-LoggedProcess -Name "manager" -FilePath $VenvPython -ArgumentList @(Join-Path $ManagerDir "app.py")))
  Wait-Http -Name "manager" -Url "$ManagerUrl/api/health"

  Write-Host ""
  Write-Host "Ready."
  Write-Host "Manager:      $ManagerUrl"
  Write-Host "Main proxy:   http://127.0.0.1:$ProxyPort"
  Write-Host "Core API:     $ControllerUrl"
  if (-not $SkipHelper) {
    Write-Host "Helper:       $HelperUrl"
  }
  Write-Host ""
  Write-Host "Keep this window open while using the gateway. Press Ctrl+C to stop."

  if (-not $NoBrowser) {
    Start-Process $ManagerUrl | Out-Null
  }

  if ($RunSeconds -gt 0) {
    Start-Sleep -Seconds $RunSeconds
    Write-Host "Timed run finished."
  } else {
    while ($true) {
      foreach ($process in $processes) {
        if ($process.HasExited) {
          throw "A child process exited unexpectedly. PID: $($process.Id), exit code: $($process.ExitCode)"
        }
      }
      Start-Sleep -Seconds 1
    }
  }
} finally {
  Stop-StartedProcesses -Processes $processes
}
