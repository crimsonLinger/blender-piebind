# Build/validate the PieBind extension package (ASCII-only for PS 5.1).

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$source = Join-Path $root 'src\piebind'
$dist = Join-Path $root 'dist'
$blender = 'blender'

New-Item -ItemType Directory -Force -Path $dist | Out-Null

Write-Host '[build] validate manifest...'
& $blender --command extension build --source-dir $source --output-dir $dist
if ($LASTEXITCODE -ne 0) { throw "build failed with exit $LASTEXITCODE" }

$zip = Get-ChildItem $dist -Filter 'piebind-*.zip' | Sort-Object LastWriteTime | Select-Object -Last 1
Write-Host "[build] validating $($zip.Name)..."
& $blender --command extension validate $zip.FullName

Write-Host ''
Write-Host ("[build] OK -> {0} ({1:N0} bytes)" -f $zip.FullName, $zip.Length)