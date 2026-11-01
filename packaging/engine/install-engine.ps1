# Video Tool Engine: installs this computer as the server for Video Tool (Windows).
#
#   .\install-engine.ps1                       # install, download Ollama + ComfyUI + the picture models, start nothing
#   .\install-engine.ps1 -Service              # ...and start the engine at every login
#   .\install-engine.ps1 -Check                # install the program only and prove it starts (no models); used by the build
#
# Options: -Dir DIR  -Engines ollama,comfy  -Bundles pictures,clips  -Models DIR  -Port 8790  -NoSetup  -Service  -Check  -Python PATH
# No administrator rights are needed. Everything goes under -Dir (default %LOCALAPPDATA%\VideoToolEngine).
[CmdletBinding()]
param(
  [string]$Dir = $(if ($env:VT_ENGINE_DIR) { $env:VT_ENGINE_DIR } else { Join-Path $env:LOCALAPPDATA "VideoToolEngine" }),
  [string]$Engines = "ollama,comfy",
  [string]$Bundles = "pictures",
  [string]$Models = "",
  [int]$Port = 8790,
  [string]$Python = "",
  [switch]$NoSetup,
  [switch]$Service,
  [switch]$Check
)
$ErrorActionPreference = "Stop"
if ($Check) { $NoSetup = $true }
function Say($m) { Write-Host ""; Write-Host "== $m" -ForegroundColor Cyan }

$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$App = Join-Path $Dir "app"; $Data = Join-Path $Dir "data"; $Venv = Join-Path $Dir "venv"
New-Item -ItemType Directory -Force -Path $Dir, $Data | Out-Null

Say "1/4 Copying the program to $App"
if ((Resolve-Path $Here).Path -ne $App) {
  if (Test-Path $App) { Remove-Item -Recurse -Force $App }
  New-Item -ItemType Directory -Force -Path $App | Out-Null
  Copy-Item -Path (Join-Path $Here "*") -Destination $App -Recurse -Force
}

if (-not $Python) {
  Say "2/4 Python 3.11 and the locked packages (uv)"
  $uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
  if (-not $uv) {
    Write-Host "uv is not installed; getting it (astral.sh) into $Dir\bin"
    $env:UV_INSTALL_DIR = Join-Path $Dir "bin"; $env:UV_NO_MODIFY_PATH = "1"
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    $uv = Join-Path $Dir "bin\uv.exe"
  }
  Push-Location $App
  try {
    $env:UV_PROJECT_ENVIRONMENT = $Venv
    & $uv sync --frozen --no-dev --python 3.11
    if ($LASTEXITCODE -ne 0) { throw "uv sync failed" }
  } finally { Pop-Location }
  $Python = Join-Path $Venv "Scripts\python.exe"
} else {
  Say "2/4 Using the Python you gave: $Python"
}

$env:VT_DATA = $Data; $env:PYTHONIOENCODING = "utf-8"; $env:PYTHONPATH = $App
function Vt { Push-Location $App; try { & $Python -m vt.cli @args; if ($LASTEXITCODE -ne 0) { throw "vt $($args -join ' ') failed ($LASTEXITCODE)" } } finally { Pop-Location } }

Say "3/4 What this computer can do"
$extra = @(); if ($Models) { $extra = @("--models", $Models) }
Vt engine plan --engines $Engines --bundles $Bundles @extra

if (-not $NoSetup) {
  Say "Downloading and installing (can be stopped and started again: it resumes)"
  Vt engine setup --yes --engines $Engines --bundles $Bundles @extra
}

$run = @"
@echo off
set "VT_DATA=$Data"
set "PYTHONIOENCODING=utf-8"
set "PYTHONPATH=$App"
cd /d "$App"
"$Python" -m vt.cli engine run --port $Port --engines $Engines %*
"@
Set-Content -Path (Join-Path $Dir "run-engine.cmd") -Value $run -Encoding ASCII

if ($Check) {
  Say "4/4 Proving it starts"
  $log = Join-Path $Dir "check.log"
  $p = Start-Process -FilePath $Python -ArgumentList @("-m", "vt.cli", "engine", "run", "--port", "$Port", "--engines", '""', "--no-start") -WorkingDirectory $App -PassThru -WindowStyle Hidden -RedirectStandardOutput $log -RedirectStandardError (Join-Path $Dir "check.err")
  $ok = $false; $body = ""
  for ($i = 0; $i -lt 60; $i++) {
    try { $body = (Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$Port/.well-known/vt-engine").Content; $ok = $true; break } catch { Start-Sleep -Seconds 1 }
  }
  Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
  if (-not $ok) { Get-Content $log, (Join-Path $Dir "check.err") -ErrorAction SilentlyContinue | Write-Host; throw "the engine did not answer" }
  Write-Host $body
  if ($body -notmatch '"engine_server"') { throw "the answer is not an engine document" }
  Write-Host "OK: the engine starts and answers." -ForegroundColor Green
  exit 0
}

if ($Service) { Say "4/4 Starting it automatically"; Vt engine service --install --port $Port } else { Say "4/4 Done" }

Write-Host @"

The engine is installed in $Dir.
Start it:        $Dir\run-engine.cmd
It prints an address and a pairing code. On the computer with the Video Tool window:
Settings, Engines, "Another Video Tool computer", then the address and the code.
"@
