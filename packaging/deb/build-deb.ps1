param(
  [string]$Version = "0.1.0",
  [string]$Architecture = "amd64",
  [switch]$SkipFrontendBuild,
  [switch]$SkipMihomoCopy,
  [switch]$NoClean
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$BuildDir = Join-Path $Root "build\deb"
$PackageDir = Join-Path $BuildDir "package"
$DistDir = Join-Path $Root "dist"
$VendorMihomoDir = Join-Path $Root "vendor\mihomo\linux-amd64"
$VendorMihomo = Join-Path $VendorMihomoDir "mihomo"
$FrontendDir = Join-Path $Root "manager\frontend"

function Require-Command {
  param([string]$Name)
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "$Name was not found in PATH."
  }
}

function Write-Utf8NoBom {
  param(
    [string]$Path,
    [string]$Text
  )
  $encoding = [System.Text.UTF8Encoding]::new($false)
  [System.IO.File]::WriteAllText($Path, $Text, $encoding)
}

function Normalize-Lf {
  param([string]$Path)
  $text = [System.IO.File]::ReadAllText($Path)
  $text = $text -replace "`r`n", "`n"
  $text = $text -replace "`r", "`n"
  Write-Utf8NoBom -Path $Path -Text $text
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

function Ensure-LinuxMihomo {
  if (Test-Path -LiteralPath $VendorMihomo) {
    Write-Host "Using existing Linux mihomo: $VendorMihomo"
    return
  }
  if ($SkipMihomoCopy) {
    throw "Linux mihomo was not found. Place it at $VendorMihomo or rerun without -SkipMihomoCopy."
  }
  Require-Command docker
  New-Item -ItemType Directory -Force -Path $VendorMihomoDir | Out-Null

  $container = "lite-node-gateway-mihomo"
  $existing = docker ps -a --format "{{.Names}}" | Where-Object { $_ -eq $container } | Select-Object -First 1
  if ($existing) {
    docker cp "${container}:/mihomo" $VendorMihomo
    return
  }

  $tempName = "lite-node-gateway-mihomo-copy-$PID"
  try {
    docker create --name $tempName metacubex/mihomo:latest | Out-Null
    docker cp "${tempName}:/mihomo" $VendorMihomo
  } finally {
    docker rm -f $tempName *> $null
  }
}

function Copy-Directory {
  param(
    [string]$Source,
    [string]$Destination
  )
  New-Item -ItemType Directory -Force -Path $Destination | Out-Null
  Get-ChildItem -LiteralPath $Source -Force | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $Destination -Recurse -Force
  }
}

Require-Command python

if (-not $NoClean) {
  if (Test-Path -LiteralPath $BuildDir) {
    Remove-Item -LiteralPath $BuildDir -Recurse -Force
  }
}
New-Item -ItemType Directory -Force -Path $PackageDir, $DistDir | Out-Null

Build-Frontend
Ensure-LinuxMihomo

$debianDir = Join-Path $PackageDir "DEBIAN"
$optDir = Join-Path $PackageDir "opt\lite-node-gateway"
$binDir = Join-Path $optDir "bin"
$managerDir = Join-Path $optDir "manager"
$scriptsDir = Join-Path $optDir "scripts"
$systemdDir = Join-Path $PackageDir "usr\lib\systemd\system"
$docDir = Join-Path $PackageDir "usr\share\doc\lite-node-gateway"

New-Item -ItemType Directory -Force -Path $debianDir, $binDir, $managerDir, $scriptsDir, $systemdDir, $docDir | Out-Null

$control = Get-Content -LiteralPath (Join-Path $PSScriptRoot "control") -Raw
$control = $control -replace "(?m)^Version: .*$", "Version: $Version"
$control = $control -replace "(?m)^Architecture: .*$", "Architecture: $Architecture"
Write-Utf8NoBom -Path (Join-Path $debianDir "control") -Text $control

Copy-Item -LiteralPath (Join-Path $PSScriptRoot "postinst") -Destination (Join-Path $debianDir "postinst") -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "prerm") -Destination (Join-Path $debianDir "prerm") -Force
Normalize-Lf -Path (Join-Path $debianDir "postinst")
Normalize-Lf -Path (Join-Path $debianDir "prerm")

Copy-Item -LiteralPath (Join-Path $Root "manager\app.py") -Destination (Join-Path $managerDir "app.py") -Force
Copy-Item -LiteralPath (Join-Path $Root "manager\requirements.txt") -Destination (Join-Path $managerDir "requirements.txt") -Force
Copy-Directory -Source (Join-Path $Root "manager\static") -Destination (Join-Path $managerDir "static")
Copy-Item -LiteralPath (Join-Path $Root "scripts\system_proxy_helper.py") -Destination (Join-Path $scriptsDir "system_proxy_helper.py") -Force
Copy-Item -LiteralPath $VendorMihomo -Destination (Join-Path $binDir "mihomo") -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "lite-node-gateway-mihomo.sh") -Destination (Join-Path $binDir "lite-node-gateway-mihomo.sh") -Force
Normalize-Lf -Path (Join-Path $binDir "lite-node-gateway-mihomo.sh")

Copy-Item -LiteralPath (Join-Path $PSScriptRoot "lite-node-gateway-mihomo.service") -Destination (Join-Path $systemdDir "lite-node-gateway-mihomo.service") -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "lite-node-gateway-manager.service") -Destination (Join-Path $systemdDir "lite-node-gateway-manager.service") -Force
Normalize-Lf -Path (Join-Path $systemdDir "lite-node-gateway-mihomo.service")
Normalize-Lf -Path (Join-Path $systemdDir "lite-node-gateway-manager.service")

Copy-Item -LiteralPath (Join-Path $Root "LICENSE") -Destination (Join-Path $docDir "copyright") -Force
Copy-Item -LiteralPath (Join-Path $Root "README.md") -Destination (Join-Path $docDir "README.md") -Force

$output = Join-Path $DistDir "lite-node-gateway_${Version}_${Architecture}.deb"
python (Join-Path $PSScriptRoot "make_deb.py") --package-root $PackageDir --output $output

Write-Host ""
Write-Host "Debian package created:"
Write-Host "  $output"
