<#
  The full check on this Windows laptop, run BY HAND (the owner chose no scheduled task, 2026-11-20):

      powershell -ExecutionPolicy Bypass -File scripts\nightly_local.ps1            # everything
      powershell -ExecutionPolicy Bypass -File scripts\nightly_local.ps1 -Quick     # the tests only, no videos

  It runs, in this order, and writes one report to E:\UltimateVideoTool\nightly\<date>\report.md:
    1. the fast tests and the slow tests (the laptop's graphics card is used where the tests want it)
    2. the video matrix with Claude on this PC directing (scripts\lab\local_matrix.py --smoke), then the same six rows with the local AI (gemma), when it is installed
  It needs the installed server running on port 8790 and the installed client open (its helper connects Claude). Nothing is sent to any other computer: it refuses to run
  when the server it would use is not on this one. Close other heavy programs first: the tests hold about 2 GB of graphics memory and Windows slows a busy card silently.
#>
param([switch]$Quick, [string]$Api = "http://127.0.0.1:8790")

$ErrorActionPreference = "Continue"
$repo = Split-Path -Parent $PSScriptRoot
$root = "E:\UltimateVideoTool"
$day = Get-Date -Format "yyyy-MM-dd"
$out = Join-Path $root "nightly\$day"
New-Item -ItemType Directory -Force $out | Out-Null
$uv = Join-Path $root ".tools\uv.exe"
$env:UV_CACHE_DIR = Join-Path $root ".uvcache"
$env:UV_PYTHON_INSTALL_DIR = Join-Path $root ".pythons"
$env:UV_PROJECT_ENVIRONMENT = Join-Path $root "venv-workbench"
Remove-Item Env:ELECTRON_RUN_AS_NODE -ErrorAction SilentlyContinue
$ffmpeg = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Gyan.FFmpeg*\ffmpeg-*\bin" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($ffmpeg) { $env:PATH = "$($ffmpeg.FullName);$env:PATH" }

# 0. only this laptop
$uri = [Uri]$Api
if ($uri.Host -notin @("127.0.0.1", "localhost", "::1")) { throw "This check only runs against the server on this computer, not $($uri.Host)." }
$busy = Get-Process pytest, python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*pytest*" }
if ($busy) { throw "A test run is already going. Wait for it." }

$report = @("# Check $day", "", "Machine: $env:COMPUTERNAME. Server: $Api. Free space on E: $([math]::Round((Get-PSDrive E).Free/1GB)) GB.", "")
function Step($name, $script) {
  $t = Get-Date
  $log = Join-Path $out (($name -replace '[^\w]+', '-') + ".log")
  & $script *> $log
  $code = $LASTEXITCODE
  $secs = [int]((Get-Date) - $t).TotalSeconds
  $tail = (Get-Content $log -Tail 3 -ErrorAction SilentlyContinue) -join " | "
  $script:report += "- **$name**: exit $code in $secs s. ``$tail`` (log: $log)"
  Write-Host "$name -> exit $code ($secs s)"
}

Step "fast tests" { & $uv run --project "$repo\server" pytest -m "not slow" -p no:cacheprovider -rf -o addopts="" }
Step "slow tests" { & $uv run --project "$repo\server" pytest -m slow -p no:cacheprovider -rsfE --durations=10 -o addopts="" }

if (-not $Quick) {
  try { $health = Invoke-RestMethod "$Api/api/health" -TimeoutSec 5 } catch { throw "The server on $Api does not answer. Open Ultimate Video Tool Server first." }
  $claude = (Invoke-RestMethod "$Api/api/directors").directors | Where-Object { $_.id -like "claude@*" -and $_.available }
  if (-not $claude) { $report += "- **Claude matrix**: skipped, Claude on this PC is not ready (open the client and sign in to Claude Code)." }
  else {
    Step "matrix, Claude smoke" { & $uv run --project "$repo\server" python "$repo\scripts\lab\local_matrix.py" run --director claude --smoke --out "$out\matrix-claude" }
  }
  $local = (Invoke-RestMethod "$Api/api/directors").directors | Where-Object { $_.id -eq "local" -and $_.available }
  if (-not $local) { $report += "- **Gemma matrix**: skipped, the local AI is not ready." }
  else {
    Step "matrix, gemma" { & $uv run --project "$repo\server" python "$repo\scripts\lab\local_matrix.py" run --director local --gemma-set --out "$out\matrix-gemma" }
  }
}
$report += "", "Look at the contact sheets in the matrix folders, and watch the videos: numbers cannot tell a cut-off caption from a good one."
$report | Set-Content (Join-Path $out "report.md") -Encoding utf8
Write-Host "Report: $out\report.md"
