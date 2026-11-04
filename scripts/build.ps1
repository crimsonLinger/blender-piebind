# Build/validate the PieBind extension package (ASCII-only for PS 5.1).
# Usage: pwsh -File scripts/build.ps1 [-Blender <path to blender>]
# Blender is resolved from -Blender, then the BLENDER env var, then PATH.

param(
    [string]$Blender = $env:BLENDER
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($Blender)) { $Blender = 'blender' }
if (-not (Test-Path $Blender) -and -not (Get-Command $Blender -ErrorAction SilentlyContinue)) {
    throw "Blender not found: pass -Blender <path> or set the BLENDER env var"
}

$root = Split-Path -Parent $PSScriptRoot
$source = Join-Path $root 'src\piebind'
$dist = Join-Path $root 'dist'

New-Item -ItemType Directory -Force -Path $dist | Out-Null

Write-Host '[build] validate manifest...'
& $Blender --command extension build --source-dir $source --output-dir $dist
if ($LASTEXITCODE -ne 0) { throw "build failed with exit $LASTEXITCODE" }

$zip = Get-ChildItem $dist -Filter 'piebind-*.zip' | Sort-Object LastWriteTime | Select-Object -Last 1
Write-Host "[build] validating $($zip.Name)..."
& $Blender --command extension validate $zip.FullName

Write-Host ''
Write-Host ("[build] OK -> {0} ({1:N0} bytes)" -f $zip.FullName, $zip.Length)