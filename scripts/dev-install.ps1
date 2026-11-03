param(
  [ValidateSet('Install','Update','Launch','Check')][string]$Action='Install',
  [ValidateSet('client','server','both')][string]$Role='both',
  [string]$Root=(Join-Path $env:LOCALAPPDATA 'UltimateVideoToolDev'),
  [string]$Source=(Split-Path $PSScriptRoot -Parent),
  [string]$ServerUrl='', [switch]$NoUpdate, [switch]$NoLaunch, [switch]$NoShortcuts
)
$ErrorActionPreference='Stop'
$Root=[IO.Path]::GetFullPath($Root);$Source=[IO.Path]::GetFullPath($Source)
$nodeCommand=Get-Command node -ErrorAction SilentlyContinue
$nodePath=if($nodeCommand){$nodeCommand.Source}else{''}
if($nodePath){$version=& $nodePath -p 'process.versions.node';$parts=$version.Split('.');if([int]$parts[0] -lt 22 -or ([int]$parts[0] -eq 22 -and [int]$parts[1] -lt 12)){$nodePath=''}}
if(!$nodePath){
  $version='22.22.1';$asset="node-v$version-win-x64.zip";$toolRoot=Join-Path $Root 'tools\node';$nodePath=Join-Path $toolRoot "node-v$version-win-x64\node.exe"
  if(!(Test-Path -LiteralPath $nodePath)){
    New-Item -ItemType Directory -Force -Path $toolRoot | Out-Null
    $archive=Join-Path $toolRoot $asset;$manifest=Join-Path $toolRoot 'SHASUMS256.txt'
    Invoke-WebRequest -Uri "https://nodejs.org/dist/v$version/$asset" -OutFile $archive
    Invoke-WebRequest -Uri "https://nodejs.org/dist/v$version/SHASUMS256.txt" -OutFile $manifest
    $line=Get-Content -LiteralPath $manifest | Where-Object { $_ -match ('\s'+[regex]::Escape($asset)+'$') } | Select-Object -First 1
    if(!$line -or (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne ($line -split '\s+')[0]){throw 'The private Node download failed checksum verification.'}
    Expand-Archive -LiteralPath $archive -DestinationPath $toolRoot -Force
  }
}
$arguments=@((Join-Path $Source 'scripts\dev-install.mjs'),'--action',$Action.ToLowerInvariant(),'--role',$Role,'--source',$Source,'--root',$Root)
if($ServerUrl){$arguments+=@('--server-url',$ServerUrl)};if($NoUpdate){$arguments+='--no-update'};if($NoLaunch){$arguments+='--no-launch'};if($NoShortcuts){$arguments+='--no-shortcuts'}
& $nodePath @arguments
if($LASTEXITCODE -ne 0){throw "Development setup failed (exit $LASTEXITCODE). Existing projects and edits were preserved."}
if(!$NoShortcuts -and $Action -in @('Install','Update')){
  $shortcutFolder=Join-Path ([Environment]::GetFolderPath('StartMenu')) 'Programs';$shell=New-Object -ComObject WScript.Shell
  $roles=if($Role -eq 'both'){@('client','server')}else{@($Role)}
  foreach($edition in $roles){$shortcut=$shell.CreateShortcut((Join-Path $shortcutFolder "Ultimate Video Tool $edition (Development).lnk"));$shortcut.TargetPath=(Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe');$shortcut.Arguments='-NoProfile -File "'+(Join-Path $Root "launch-$edition.ps1")+'"';$shortcut.WorkingDirectory=$Source;$shortcut.Save()}
}
