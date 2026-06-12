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

function Test-PythonLaunch {
  param(
    [string]$FilePath,
    [string[]]$Arguments
  )
  $previousErrorActionPreference = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  try {
    & $FilePath @($Arguments + @("-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)")) *> $null
    return ($LASTEXITCODE -eq 0)
  } catch {
    return $false
  } finally {
    $ErrorActionPreference = $previousErrorActionPreference
  }
}

function Get-PythonLaunch {
  $candidates = @(
    @{ Command = "python"; Args = @(); Display = "python" },
    @{ Command = "py"; Args = @("-3"); Display = "py -3" },
    @{ Command = "python3"; Args = @(); Display = "python3" }
  )
  foreach ($candidate in $candidates) {
    $command = Get-Command $candidate.Command -ErrorAction SilentlyContinue
    if (-not $command) {
      continue
    }
    if (Test-PythonLaunch -FilePath $command.Source -Arguments $candidate.Args) {
      return @{ FilePath = $command.Source; Args = $candidate.Args; Display = $candidate.Display }
    }
    Write-Host "Skipping unusable Python launcher: $($candidate.Display)"
  }
  throw "Python 3 was not found. Install Python 3.11+ and rerun this script."
}

function Invoke-Checked {
  param(
    [string]$FilePath,
    [string[]]$Arguments,
    [string]$WorkingDirectory = $Root
  )
  Push-Location $WorkingDirectory
  try {
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
      throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($Arguments -join ' ')"
    }
  } finally {
    Pop-Location
  }
}

function Invoke-Quiet {
  param(
    [string]$FilePath,
    [string[]]$Arguments,
    [string]$WorkingDirectory = $Root
  )
  $previousErrorActionPreference = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  try {
    Push-Location $WorkingDirectory
    try {
      & $FilePath @Arguments *> $null
      return ($LASTEXITCODE -eq 0)
    } finally {
      Pop-Location
    }
  } finally {
    $ErrorActionPreference = $previousErrorActionPreference
  }
}

function Get-PythonVenvInstallHint {
  param([hashtable]$Launch)
  $version = ""
  $previousErrorActionPreference = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  try {
    $output = & $Launch.FilePath @($Launch.Args + @("-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")) 2>$null
    if ($LASTEXITCODE -eq 0 -and $output) {
      $version = ($output | Select-Object -First 1).ToString().Trim()
    }
  } finally {
    $ErrorActionPreference = $previousErrorActionPreference
  }

  if ([string]::IsNullOrWhiteSpace($version)) {
    return "Install or repair Python 3.11+ for Windows, and make sure pip is installed and Python is available in PATH."
  }
  return "Install or repair Python $version for Windows, and make sure pip is installed and Python is available in PATH."
}

function Remove-PythonVenv {
  $expected = [System.IO.Path]::GetFullPath((Join-Path $Root ".venv-windows"))
  $actual = [System.IO.Path]::GetFullPath($VenvDir)
  if ($actual -ne $expected) {
    throw "Refusing to remove unexpected virtual environment path: $VenvDir"
  }
  if (Test-Path -LiteralPath $VenvDir) {
    Remove-Item -LiteralPath $VenvDir -Recurse -Force
  }
}

function Test-VenvPip {
  if (-not (Test-Path -LiteralPath $VenvPython)) {
    return $false
  }
  return (Invoke-Quiet -FilePath $VenvPython -Arguments @("-m", "pip", "--version"))
}

function New-PythonVenv {
  param([hashtable]$Launch)
  Write-Host "Creating Python virtual environment with $($Launch.Display) ..."
  $previousErrorActionPreference = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  try {
    & $Launch.FilePath @($Launch.Args + @("-m", "venv", $VenvDir))
    $venvExitCode = $LASTEXITCODE
  } finally {
    $ErrorActionPreference = $previousErrorActionPreference
  }

  if ($venvExitCode -ne 0) {
    [Console]::Error.WriteLine("Could not create a Python virtual environment.")
    [Console]::Error.WriteLine((Get-PythonVenvInstallHint -Launch $Launch))
    if ((Test-Path -LiteralPath $VenvDir) -and -not (Test-VenvPip)) {
      [Console]::Error.WriteLine("Removing incomplete virtual environment: $VenvDir")
      Remove-PythonVenv
    }
    throw "Python virtual environment creation failed."
  }

  if (Test-VenvPip) {
    return
  }

  [Console]::Error.WriteLine("The virtual environment was created without pip. Trying ensurepip ...")
  if ((Invoke-Quiet -FilePath $VenvPython -Arguments @("-m", "ensurepip", "--upgrade")) -and (Test-VenvPip)) {
    Write-Host "Bootstrapped pip in the virtual environment."
    return
  }

  [Console]::Error.WriteLine("Could not bootstrap pip in the virtual environment.")
  [Console]::Error.WriteLine((Get-PythonVenvInstallHint -Launch $Launch))
  [Console]::Error.WriteLine("Removing incomplete virtual environment: $VenvDir")
  Remove-PythonVenv
  throw "Python virtual environment does not have pip."
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
  if ((Test-Path -LiteralPath $VenvDir) -and -not (Test-Path -LiteralPath $VenvPython)) {
    Write-Host "Detected incomplete Python virtual environment: $VenvDir"
    Write-Host "Recreating Python virtual environment ..."
    Remove-PythonVenv
  }
  if (-not (Test-Path -LiteralPath $VenvPython)) {
    New-PythonVenv -Launch $launch
  } elseif (-not (Test-VenvPip)) {
    Write-Host "Detected broken Python virtual environment: $VenvDir"
    if ((Invoke-Quiet -FilePath $VenvPython -Arguments @("-m", "ensurepip", "--upgrade")) -and (Test-VenvPip)) {
      Write-Host "Repaired pip in the existing Python virtual environment."
    } else {
      Write-Host "Recreating Python virtual environment ..."
      Remove-PythonVenv
      New-PythonVenv -Launch $launch
    }
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
    "  - DOMAIN,localhost,DIRECT",
    "  - DOMAIN-SUFFIX,local,DIRECT",
    "  - IP-CIDR,127.0.0.0/8,DIRECT,no-resolve",
    "  - IP-CIDR,10.0.0.0/8,DIRECT,no-resolve",
    "  - IP-CIDR,172.16.0.0/12,DIRECT,no-resolve",
    "  - IP-CIDR,192.168.0.0/16,DIRECT,no-resolve",
    "  - IP-CIDR,169.254.0.0/16,DIRECT,no-resolve",
    "  - IP-CIDR6,::1/128,DIRECT,no-resolve",
    "  - IP-CIDR6,fc00::/7,DIRECT,no-resolve",
    "  - IP-CIDR6,fe80::/10,DIRECT,no-resolve",
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

function Wait-HttpDown {
  param(
    [string]$Name,
    [string]$Url
  )
  $deadline = (Get-Date).AddSeconds(8)
  while ((Get-Date) -lt $deadline) {
    if (-not (Test-HttpReady -Url $Url)) {
      return
    }
    Start-Sleep -Milliseconds 350
  }
  throw "$Name is still responding at $Url."
}

function Get-PortListenerPids {
  param([int]$Port)
  @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique)
}

function Stop-PortListeners {
  param(
    [string]$Name,
    [int]$Port
  )
  $listenerPids = Get-PortListenerPids -Port $Port
  if ($listenerPids.Count -eq 0) {
    throw "$Name is responding, but no listener PID could be found for port $Port."
  }

  Write-Host "Stopping existing $Name on port $Port ..."
  foreach ($listenerPid in $listenerPids) {
    Stop-Process -Id $listenerPid -ErrorAction SilentlyContinue
  }

  $deadline = (Get-Date).AddSeconds(8)
  while ((Get-Date) -lt $deadline) {
    $stillRunning = $false
    foreach ($listenerPid in $listenerPids) {
      $process = Get-Process -Id $listenerPid -ErrorAction SilentlyContinue
      if ($process) {
        $stillRunning = $true
      }
    }
    if (-not $stillRunning) {
      return
    }
    Start-Sleep -Milliseconds 350
  }

  Write-Host "Existing $Name did not stop gracefully; forcing stop ..."
  foreach ($listenerPid in $listenerPids) {
    Stop-Process -Id $listenerPid -Force -ErrorAction SilentlyContinue
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

function Stop-ManagedProcess {
  param($Process)
  if ($Process -and -not $Process.HasExited) {
    Stop-Process -Id $Process.Id -ErrorAction SilentlyContinue
    $Process.WaitForExit(500) | Out-Null
    if (-not $Process.HasExited) {
      Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
    }
  }
}

function Start-Mihomo {
  $script:mihomoProcess = Start-LoggedProcess -Name "mihomo" -FilePath $MihomoExe -ArgumentList @("-d", $DataDir, "-f", $ConfigFile)
  [void]$script:processes.Add($script:mihomoProcess)
  Wait-Http -Name "mihomo" -Url "$ControllerUrl/version"
}

function Start-SystemProxyHelper {
  $script:helperProcess = Start-LoggedProcess -Name "system-proxy-helper" -FilePath $VenvPython -ArgumentList @($HelperScript)
  [void]$script:processes.Add($script:helperProcess)
  Wait-Http -Name "system-proxy-helper" -Url $HelperUrl
}

function Start-Manager {
  $script:managerProcess = Start-LoggedProcess -Name "manager" -FilePath $VenvPython -ArgumentList @(Join-Path $ManagerDir "app.py")
  [void]$script:processes.Add($script:managerProcess)
  Wait-Http -Name "manager" -Url "$ManagerUrl/api/health"
}

function Ensure-MihomoRunning {
  # If the managed process is still alive, never restart it. Even if the Core
  # API is briefly unreachable (it may just be busy), killing a live process
  # would cut off requests it is currently handling.
  if ($script:mihomoProcess -and -not $script:mihomoProcess.HasExited) {
    return
  }
  # No managed live process: an external listener may exist, or it has exited.
  if (Test-HttpReady -Url "$ControllerUrl/version") {
    return
  }
  Write-Host "mihomo is not running; starting ..."
  Stop-ManagedProcess -Process $script:mihomoProcess
  Start-Mihomo
}

function Ensure-SystemProxyHelperRunning {
  if ($SkipHelper) {
    return
  }
  # If the managed process is still alive, never restart it (even if the
  # Helper API is briefly unreachable).
  if ($script:helperProcess -and -not $script:helperProcess.HasExited) {
    return
  }
  if (Test-HttpReady -Url $HelperUrl) {
    return
  }
  Write-Host "System proxy helper is not running; starting ..."
  Stop-ManagedProcess -Process $script:helperProcess
  Start-SystemProxyHelper
}

function Ensure-ManagerRunning {
  # Critical: only restart when the process has actually exited. A long-running
  # operation such as "test all nodes" can make /api/health briefly unreachable,
  # but the process is still alive and serving requests. Killing it here would
  # abort the in-flight request, which the browser reports as "Failed to fetch".
  if ($script:managerProcess -and -not $script:managerProcess.HasExited) {
    return
  }
  if (Test-HttpReady -Url "$ManagerUrl/api/health") {
    return
  }
  Write-Host "manager is not running; starting ..."
  Stop-ManagedProcess -Process $script:managerProcess
  Start-Manager
}

function Invoke-WatchdogOnce {
  Ensure-MihomoRunning
  Ensure-SystemProxyHelperRunning
  Ensure-ManagerRunning
}

function Sync-ManagerConfig {
  try {
    Invoke-WebRequest `
      -Uri "$ManagerUrl/api/rebuild" `
      -Method Post `
      -Body "{}" `
      -ContentType "application/json" `
      -UseBasicParsing `
      -TimeoutSec 20 | Out-Null
    Write-Host "Synced Mihomo config through manager."
  } catch {
    [Console]::Error.WriteLine("Manager config sync failed. Open the Manager and click rebuild if nodes look stale. $($_.Exception.Message)")
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
$mihomoProcess = $null
$helperProcess = $null
$managerProcess = $null
$managerRestarted = $false
try {
  if (Test-HttpReady -Url "$ControllerUrl/version") {
    Write-Host "mihomo is already running: $ControllerUrl"
  } else {
    Start-Mihomo
  }

  if (-not $SkipHelper) {
    if (Test-HttpReady -Url $HelperUrl) {
      Write-Host "System proxy helper is already running: $HelperUrl"
    } else {
      Start-SystemProxyHelper
    }
  }

  if ($BuildFrontend -and (Test-HttpReady -Url "$ManagerUrl/api/health")) {
    Write-Host "Frontend was rebuilt; restarting existing manager at $ManagerUrl"
    Stop-PortListeners -Name "manager" -Port $ManagerPort
    Wait-HttpDown -Name "manager" -Url "$ManagerUrl/api/health"
    $managerRestarted = $true
  }

  if (Test-HttpReady -Url "$ManagerUrl/api/health") {
    Write-Host "manager is already running: $ManagerUrl"
  } else {
    Start-Manager
  }
  Sync-ManagerConfig

  if ($managerRestarted) {
    Start-Sleep -Milliseconds 1200
    Ensure-MihomoRunning
    Ensure-SystemProxyHelperRunning
  }

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
    $deadline = (Get-Date).AddSeconds($RunSeconds)
    while ((Get-Date) -lt $deadline) {
      Invoke-WatchdogOnce
      Start-Sleep -Seconds 1
    }
    Write-Host "Timed run finished."
  } else {
    while ($true) {
      Invoke-WatchdogOnce
      Start-Sleep -Seconds 1
    }
  }
} finally {
  Stop-StartedProcesses -Processes $processes
}
