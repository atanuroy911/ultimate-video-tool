# Video Tool Engine: installs this computer as the server for Video Tool (Windows).
#
#   .\install-engine.ps1                       # install, download Ollama + ComfyUI + the picture models, start nothing
#   .\install-engine.ps1 -Service              # ...and start the engine at every login
#   .\install-engine.ps1 -Check                # install the program only and prove it starts (no models); used by the build
#
# Options: -Dir DIR  -Engines ollama,comfy  -Bundles pictures,clips  -Models DIR  -Port 8790  -NoSetup  -Service  -Check  -Python PATH
#          -Gpus 1,2|all|none  (the graphics cards Video Tool may use; with two or more cards and no flag it asks, or keeps one card only when nobody is there)
# No administrator rights are needed. Everything goes under -Dir (default %LOCALAPPDATA%\VideoToolEngine).
[CmdletBinding()]
param(
  [string]$Dir = $(if ($env:VT_ENGINE_DIR) { $env:VT_ENGINE_DIR } else { Join-Path $env:LOCALAPPDATA "VideoToolEngine" }),
  [string]$Engines = "ollama,comfy",
  [string]$Bundles = "pictures",
  [string]$Models = "",
  [int]$Port = 8790,
  [string]$Python = "",
  [string]$Gpus = "",
  [switch]$NoSetup,
  [switch]$Service,
  [switch]$Check
)
$ErrorActionPreference = "Stop"
if ($Check) { $NoSetup = $true }
function Say($m) { Write-Host ""; Write-Host "== $m" -ForegroundColor Cyan }

$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Dir = [IO.Path]::GetFullPath($Dir)
$App = Join-Path $Dir "app"; $Data = Join-Path $Dir "data"; $Venv = Join-Path $Dir "venv"
New-Item -ItemType Directory -Force -Path $Dir, $Data | Out-Null

Say "1/4 Copying the program to $App"
if ((Resolve-Path $Here).Path -ne $App) {
  if (Test-Path -LiteralPath $App) {
    $resolvedApp = (Resolve-Path -LiteralPath $App).Path
    $expectedApp = [IO.Path]::GetFullPath((Join-Path $Dir "app"))
    if ($resolvedApp -ne $expectedApp -or (Get-Item -LiteralPath $App).Attributes -band [IO.FileAttributes]::ReparsePoint) {
      throw "Refusing to replace an app directory outside the installation folder: $resolvedApp"
    }
    Remove-Item -LiteralPath $resolvedApp -Recurse -Force
  }
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

Say "Graphics cards"
$gpuArgs = @(); if ($Gpus) { $gpuArgs = @("--gpus", $Gpus) }
Vt gpu setup @gpuArgs                       # asks which cards Video Tool may use when there are two or more and a person is here; change later: vt gpu allow, or the Server page

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
  & $Python (Join-Path $App 'check-engine.py') --app $App --data $Data --port $Port
  if ($LASTEXITCODE -ne 0) { throw 'The installed engine did not pass its startup check. See check.log.' }
  exit 0
}

if ($Service) { Say "4/4 Starting it automatically"; Vt engine service --install --port $Port } else { Say "4/4 Done" }

Write-Host @"

The engine is installed in $Dir.
Start it:        $Dir\run-engine.cmd
It prints an address and a pairing code. On the computer with the Video Tool window:
Settings, Engines, "Another Video Tool computer", then the address and the code.
"@
