# Compatibility entry point; independent products.
param([switch]$CpuOnly,[switch]$SkipModel,[switch]$SkipTorch,[switch]$NoLaunch)
$role=if($SkipTorch){'client'}else{'both'}
& (Join-Path $PSScriptRoot 'dev-install.ps1') -Role $role -NoLaunch:$NoLaunch
