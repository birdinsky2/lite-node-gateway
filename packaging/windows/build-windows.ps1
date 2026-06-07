param(
  [string]$MihomoVersion = "v1.19.26",
  [switch]$SkipFrontendBuild,
  [switch]$SkipMihomoDownload,
  [switch]$NoClean
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$BuildDir = Join-Path $Root "build\windows"
$DistDir = Join-Path $Root "dist\lite-node-gateway-windows"
$VendorMihomoDir = Join-Path $Root "vendor\mihomo\windows-amd64"
$VendorMihomoExe = Join-Path $VendorMihomoDir "mihomo.exe"
$FrontendDir = Join-Path $Root "manager\frontend"
$ManagerDir = Join-Path $Root "manager"
$StaticDir = Join-Path $ManagerDir "static"

function Require-Command {
  param([string]$Name)
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "$Name was not found in PATH."
  }
}

function Download-File {
  param(
    [string[]]$Urls,
    [string]$OutFile
  )
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $OutFile) | Out-Null
  foreach ($url in $Urls) {
    Write-Host "Downloading $url"
    try {
      & curl.exe -L --retry 3 --retry-delay 2 --connect-timeout 20 --max-time 240 -o $OutFile $url
      if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $OutFile) -and (Get-Item -LiteralPath $OutFile).Length -gt 1000000) {
        return
      }
    } catch {
      Write-Host "Download failed: $($_.Exception.Message)"
    }
    if (Test-Path -LiteralPath $OutFile) {
      Remove-Item -LiteralPath $OutFile -Force
    }
  }
  throw "Could not download any of: $($Urls -join ', ')"
}

function Ensure-Mihomo {
  if (Test-Path -LiteralPath $VendorMihomoExe) {
    Write-Host "Using existing mihomo: $VendorMihomoExe"
    return
  }
  if ($SkipMihomoDownload) {
    throw "mihomo.exe was not found. Place it at $VendorMihomoExe or rerun without -SkipMihomoDownload."
  }

  Require-Command curl.exe
  $zipPath = Join-Path $BuildDir "mihomo-windows.zip"
  $urls = @(
    "https://downloads.sourceforge.net/project/mihomo.mirror/$MihomoVersion/mihomo-windows-amd64-compatible-$MihomoVersion.zip",
    "https://downloads.sourceforge.net/project/mihomo.mirror/$MihomoVersion/mihomo-windows-amd64-$MihomoVersion.zip",
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
  Copy-Item -LiteralPath $candidate.FullName -Destination $VendorMihomoExe -Force
}

function Build-Frontend {
  if ($SkipFrontendBuild) {
    return
  }
  Require-Command npm
  Push-Location $FrontendDir
  try {
    if (-not (Test-Path -LiteralPath (Join-Path $FrontendDir "node_modules"))) {
      npm ci
    }
    npm run build
  } finally {
    Pop-Location
  }
}

function Build-Exe {
  param(
    [string]$Name,
    [string]$Script,
    [string[]]$ExtraArgs = @()
  )
  python -m PyInstaller --noconfirm --clean --onefile --name $Name --distpath $BuildDir --workpath (Join-Path $BuildDir "pyinstaller") --specpath (Join-Path $BuildDir "spec") @ExtraArgs $Script
}

Require-Command python

if (-not $NoClean) {
  if (Test-Path -LiteralPath $BuildDir) {
    Remove-Item -LiteralPath $BuildDir -Recurse -Force
  }
  if (Test-Path -LiteralPath $DistDir) {
    Remove-Item -LiteralPath $DistDir -Recurse -Force
  }
}
New-Item -ItemType Directory -Force -Path $BuildDir, $DistDir | Out-Null

Build-Frontend
python -m pip install -r (Join-Path $ManagerDir "requirements.txt")
python -m pip install pyinstaller

Build-Exe -Name "manager" -Script (Join-Path $ManagerDir "app.py") -ExtraArgs @("--add-data", "$StaticDir;static")
Build-Exe -Name "system-proxy-helper" -Script (Join-Path $Root "scripts\system_proxy_helper.py")
Build-Exe -Name "lite-node-gateway" -Script (Join-Path $Root "packaging\windows\launcher.py")
Ensure-Mihomo

Copy-Item -LiteralPath (Join-Path $BuildDir "manager.exe") -Destination (Join-Path $DistDir "manager.exe") -Force
Copy-Item -LiteralPath (Join-Path $BuildDir "system-proxy-helper.exe") -Destination (Join-Path $DistDir "system-proxy-helper.exe") -Force
Copy-Item -LiteralPath (Join-Path $BuildDir "lite-node-gateway.exe") -Destination (Join-Path $DistDir "lite-node-gateway.exe") -Force
New-Item -ItemType Directory -Force -Path (Join-Path $DistDir "bin") | Out-Null
Copy-Item -LiteralPath $VendorMihomoExe -Destination (Join-Path $DistDir "bin\mihomo.exe") -Force

Copy-Item -LiteralPath (Join-Path $Root "LICENSE") -Destination (Join-Path $DistDir "LICENSE.txt") -Force
@"
Lite Node Gateway for Windows

Run:
  lite-node-gateway.exe

Smoke test:
  lite-node-gateway.exe --no-browser --run-seconds 5

Default endpoints:
  Manager:    http://127.0.0.1:8089
  Main proxy: http://127.0.0.1:7896
  Core API:   http://127.0.0.1:9090

Runtime data and logs are stored in the data directory beside this file.
"@ | Set-Content -LiteralPath (Join-Path $DistDir "README-windows.txt") -Encoding UTF8

Write-Host ""
Write-Host "Windows portable package created:"
Write-Host "  $DistDir"
