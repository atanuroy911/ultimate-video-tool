<#
  One-time setup for Video Tool on Windows. Safe to re-run: every step is skipped when already done.

  .\scripts\setup.ps1                 full setup (downloads PyTorch with CUDA, builds the app, downloads the Bangla model)
  .\scripts\setup.ps1 -CpuOnly        PyTorch without CUDA (no NVIDIA graphics card): transcription is slower
  .\scripts\setup.ps1 -SkipModel      do not download the speech model now (the app downloads it on first use)
  .\scripts\setup.ps1 -SkipTorch      skip the speech libraries entirely (useful for UI work)

  Needs: Node 20+ and FFmpeg on PATH. Python is not needed: uv (downloaded into .tools\) installs its own Python 3.11 for .venv.
  On Linux and macOS: scripts/setup.sh.
#>
param([switch]$CpuOnly, [switch]$SkipModel, [switch]$SkipTorch)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
function Step($m) { Write-Host "`n== $m" -ForegroundColor Cyan }
function Have($c) { return [bool](Get-Command $c -ErrorAction SilentlyContinue) }
function Run($exe, [string[]]$a) { & $exe @a; if ($LASTEXITCODE -ne 0) { throw "failed: $exe $($a -join ' ')" } }

Step "Checking prerequisites"
if (-not (Have node)) { throw "Node.js 20 or newer is required: https://nodejs.org" }
if ([int]((node -v).TrimStart('v').Split('.')[0]) -lt 20) { throw "Node 20 or newer is required (found $(node -v))" }
if (-not (Have ffmpeg)) { throw "FFmpeg is required on PATH: winget install Gyan.FFmpeg" }
Write-Host "node $(node -v), $((ffmpeg -version | Select-Object -First 1))"

Step "Python 3.11 and the locked packages"
# uv lives in .tools\ (never installed into a system Python); it brings its own Python 3.11 and fills .venv from uv.lock
$uv = ".tools\uv.exe"
if (-not (Test-Path $uv)) {
  $env:UV_INSTALL_DIR = (Join-Path (Get-Location) ".tools"); $env:UV_NO_MODIFY_PATH = "1"
  Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
}
$py = ".venv\Scripts\python.exe"
# the GPU build that fits this computer: cu128 (RTX 50), cu124 (default), cu118 (old drivers) or cpu (vt/gpu_detect.py, standard library only)
$flavour = "cpu"
if (-not $CpuOnly) { $flavour = (& $uv run --no-project --python 3.11 python vt\gpu_detect.py).Trim() }
if ($flavour -notin @("cu128", "cu124", "cu118", "cpu")) { $flavour = "cpu" }
Write-Host "GPU build: $flavour  ($(& $uv run --no-project --python 3.11 python vt\gpu_detect.py --explain))"
Run $uv @("sync", "--frozen", "--extra", "dev", "--extra", $flavour, "--python", "3.11")

Step "Video renderer, fonts and icons"
Push-Location renderer
Run npm.cmd @("install", "--no-audit", "--no-fund")
Run node @("scripts/build-fonts.mjs")
Run node @("scripts/build-icons.mjs")
Pop-Location
if (-not (Test-Path design/textures/paper-grain.png)) { Run $py @("scripts/make_texture.py") }
if (-not (Test-Path assets/music/index.json)) { Step "Bundled music and sound effects"; Run $py @("scripts/make_assets.py") }

Step "Studio (web app)"
Push-Location studio
Run npm.cmd @("install", "--no-audit", "--no-fund")
Run npm.cmd @("run", "build")
Pop-Location

if (-not $SkipTorch -and -not $SkipModel) {
  Step "Bangla speech model (about 3 GB download, converted once; can take 10-20 minutes)"
  $env:HF_HUB_DISABLE_XET = "1"
  Run $py @("-m", "vt.cli", "models", "pull", "bn-medium")
}

Step "System check"
& $py -m vt.cli doctor
Write-Host "`nDone. Start the app with:  .\scripts\start.ps1" -ForegroundColor Green
