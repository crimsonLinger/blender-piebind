# GUI override probe: launch Blender -> focus window -> SendKeys the hotkey -> collect results
# All text kept ASCII to avoid Windows PowerShell encoding issues.
# Usage: pwsh -NoProfile -File tests\run_gui_probe.ps1

param(
    [string]$Script = ''
)

$ErrorActionPreference = 'Stop'

$root   = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($Script)) {
    $script = Join-Path $root 'tests\gui_probe.py'
} else {
    $script = (Resolve-Path $Script).Path
}
$outDir = Join-Path $env:TEMP 'piebind_gui_probe'
$ready  = Join-Path $outDir 'ready.json'
$stop   = Join-Path $outDir 'stop.txt'
$result = Join-Path $outDir 'result.json'
$log    = Join-Path $outDir 'blender.log'
$errLog = Join-Path $outDir 'blender.err.log'

New-Item -ItemType Directory -Force -Path $outDir | Out-Null
foreach ($f in @($ready, $stop, $result, $log, $errLog)) { if (Test-Path $f) { Remove-Item $f -Force } }

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class WinProbe {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern int GetWindowThreadProcessId(IntPtr h, out int pid);
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint flags, uint dx, uint dy, uint data, UIntPtr extra);
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
}
"@

Write-Host "[probe] launching blender (factory-startup)..."
$proc = Start-Process -FilePath 'blender' `
    -ArgumentList '--factory-startup', '-P', "`"$script`"" `
    -PassThru -RedirectStandardOutput $log -RedirectStandardError $errLog

$deadline = (Get-Date).AddSeconds(90)
while (-not (Test-Path $ready)) {
    if ((Get-Date) -gt $deadline) { Write-Host '[probe] ready timeout'; break }
    if ($proc.HasExited) { Write-Host '[probe] blender exited early'; break }
    Start-Sleep -Milliseconds 400
}

if (Test-Path $ready) {
    $info = Get-Content $ready -Raw | ConvertFrom-Json
    Write-Host ("[probe] ready, will press: {0}" -f $info.label)

    Start-Sleep -Milliseconds 600
    $proc.Refresh()
    $hwnd = $proc.MainWindowHandle
    if ($hwnd -eq 0) {
        Start-Sleep -Milliseconds 1500
        $proc.Refresh()
        $hwnd = $proc.MainWindowHandle
    }
    [void][WinProbe]::ShowWindow($hwnd, 9)

    $rect = New-Object 'WinProbe+RECT'
    [void][WinProbe]::GetWindowRect($hwnd, [ref]$rect)
    $cx = [int](($rect.Left + $rect.Right) / 2)
    $cy = [int]($rect.Top + ($rect.Bottom - $rect.Top) * 0.45)
    if ($cx -gt 0 -and $cy -gt 0) {
        [void][WinProbe]::SetCursorPos($cx, $cy)
    }

    $focused = $false
    for ($i = 0; $i -lt 6; $i++) {
        [void][WinProbe]::SetForegroundWindow($hwnd)
        Start-Sleep -Milliseconds 350
        $fg = [WinProbe]::GetForegroundWindow()
        $fgPid = 0
        [void][WinProbe]::GetWindowThreadProcessId($fg, [ref]$fgPid)
        Write-Host ("[probe] focus try {0}: fg={1} fgPid={2} blenderPid={3}" -f $i, $fg, $fgPid, $proc.Id)
        if ($fg -eq $hwnd -or $fgPid -eq $proc.Id) { $focused = $true; break }
        if ($cx -gt 0 -and $cy -gt 0) {
            [WinProbe]::mouse_event(0x0002, 0, 0, 0, [UIntPtr]::Zero)
            [WinProbe]::mouse_event(0x0004, 0, 0, 0, [UIntPtr]::Zero)
        }
    }
    $title = (Get-Process -Id $proc.Id).MainWindowTitle
    Write-Host ("[probe] focused={0} hwnd={1} title={2}" -f $focused, $hwnd, $title)
    @{ focused = $focused; hwnd = $hwnd.ToString(); fgPid = $fgPid; title = $title } |
        ConvertTo-Json | Set-Content -Path (Join-Path $outDir 'focus.json') -Encoding UTF8

    if ($focused) {
        Start-Sleep -Milliseconds 200
        if ($cx -gt 0 -and $cy -gt 0) {
            [void][WinProbe]::SetCursorPos($cx, $cy)
            Start-Sleep -Milliseconds 150
            [WinProbe]::mouse_event(0x0002, 0, 0, 0, [UIntPtr]::Zero)
            [WinProbe]::mouse_event(0x0004, 0, 0, 0, [UIntPtr]::Zero)
            Start-Sleep -Milliseconds 250
        }
        [System.Windows.Forms.SendKeys]::SendWait('{ESC}')
        Start-Sleep -Milliseconds 600
        $send = $info.sendkeys
        if (-not $send) { $send = '{TAB}' }
        [System.Windows.Forms.SendKeys]::SendWait($send)
        Write-Host ("[probe] key sent: {0}" -f $send)
    } else {
        Write-Host '[probe] focus is not blender, skip sending keys (avoid typing elsewhere)'
    }

    Start-Sleep -Milliseconds 1500
    New-Item -ItemType File -Path $stop -Force | Out-Null
}

Write-Host '[probe] waiting for blender to finish...'
if (-not $proc.WaitForExit(60000)) {
    Write-Host '[probe] timeout, killing'
    try { $proc.Kill() } catch {}
}

Write-Host ''
Write-Host '===== RESULT ====='
if (Test-Path $result) {
    Get-Content $result -Raw -Encoding UTF8 | ConvertFrom-Json |
        ForEach-Object { "{0}  {1}  {2}" -f ($(if ($_.ok) { 'OK  ' } else { 'FAIL' })), $_.name, $_.detail } |
        ForEach-Object { Write-Host $_ }
} else {
    Write-Host '(no result file)'
}

Write-Host ''
Write-Host '===== BLENDER LOG TAIL ====='
if (Test-Path $log) { Get-Content $log -Tail 30 -Encoding UTF8 }
if (Test-Path $errLog) { Get-Content $errLog -Tail 15 -Encoding UTF8 }