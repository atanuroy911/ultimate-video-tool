<#
  Starts the Studio (http://127.0.0.1:8765) and opens it in your browser.
    .\scripts\start.ps1                 normal start
    .\scripts\start.ps1 -Port 9000      another port
    .\scripts\start.ps1 -NoBrowser      do not open a browser window
#>
param([int]$Port = 8765, [switch]$NoBrowser)
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:PYTHONIOENCODING = "utf-8"
$env:HYPERFRAMES_NO_TELEMETRY = "1"
$env:DO_NOT_TRACK = "1"
$env:HF_HUB_DISABLE_XET = "1"
$args2 = @("-m", "vt.cli", "studio", "--port", $Port)
if ($NoBrowser) { $args2 += "--no-open" }
& .venv\Scripts\python.exe @args2
