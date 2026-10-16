# Acceptance step 3: launch the frozen app for real, prove it lives, and capture
# the actual window so the visual verdict is not based on the source tree alone.
#
# Order matters: confirm QT_QPA_PLATFORM is empty FIRST. A leftover "offscreen"
# in the environment would be inherited by the child process, the window would
# never appear on screen, and the process would still look alive — the classic
# false pass this check exists to prevent.

$ErrorActionPreference = 'Stop'
$root = 'D:\code_workspace\image-compressor'
$exe = Join-Path $root 'dist\PixelPress\PixelPress.exe'
$shot = Join-Path $root 'benchmarks\ui\frozen_live_window.png'

Write-Host "QT_QPA_PLATFORM='$($env:QT_QPA_PLATFORM)'"
if ($env:QT_QPA_PLATFORM) {
    Write-Host 'ABORT: platform override present, this would not be a real window'
    exit 2
}

$env:PIXELPRESS_SETTINGS_DIR = Join-Path $env:TEMP 'pp-frozen-live'
$p = Start-Process -FilePath $exe -PassThru
Start-Sleep -Seconds 12

$alive = Get-Process -Id $p.Id -ErrorAction SilentlyContinue
if (-not $alive) {
    Write-Host "DEAD: process exited within 12s"
    exit 1
}
Write-Host ("ALIVE pid={0} ws={1}MB threads={2}" -f $alive.Id,
    [math]::Round($alive.WorkingSet64 / 1MB), $alive.Threads.Count)

$handle = $alive.MainWindowHandle
Write-Host "MainWindowHandle=$handle"
if ($handle -eq 0) {
    Write-Host 'NO WINDOW HANDLE'
    Stop-Process -Id $alive.Id -Force
    exit 3
}

Add-Type @'
using System;
using System.Runtime.InteropServices;
public class WinRect {
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdcBlt, uint nFlags);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
}
'@
Add-Type -AssemblyName System.Drawing

$rect = New-Object WinRect+RECT
[void][WinRect]::GetWindowRect($handle, [ref]$rect)
$width = $rect.Right - $rect.Left
$height = $rect.Bottom - $rect.Top
Write-Host "window rect: ${width}x${height} at ($($rect.Left),$($rect.Top))"

if ($width -gt 100 -and $height -gt 100) {
    # PrintWindow renders THIS window's own content. CopyFromScreen would capture
    # whatever happens to be on top of those screen coordinates — which is how you
    # end up with a screenshot of the user's desktop (and their video player)
    # instead of the app.
    [void][WinRect]::SetForegroundWindow($handle)
    Start-Sleep -Milliseconds 400

    $bitmap = New-Object System.Drawing.Bitmap($width, $height)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $hdc = $graphics.GetHdc()
    # 0x2 = PW_RENDERFULLCONTENT
    $ok = [WinRect]::PrintWindow($handle, $hdc, 2)
    $graphics.ReleaseHdc($hdc)
    $graphics.Dispose()
    Write-Host "PrintWindow ok=$ok"

    # Reject a blank capture rather than reporting a black rectangle as success.
    $sample = @()
    foreach ($y in 10, [int]($height / 2), ($height - 10)) {
        foreach ($x in 10, [int]($width / 2), ($width - 10)) {
            $sample += $bitmap.GetPixel($x, $y).ToArgb()
        }
    }
    $distinct = ($sample | Sort-Object -Unique).Count
    if ($distinct -le 1) {
        Write-Host 'CAPTURE BLANK: window content did not render'
        $bitmap.Dispose()
    } else {
        $bitmap.Save($shot, [System.Drawing.Imaging.ImageFormat]::Png)
        $bitmap.Dispose()
        Write-Host "captured: $shot (distinct sample colours=$distinct)"
    }
}

Stop-Process -Id $alive.Id -Force
Start-Sleep -Seconds 1
Write-Host 'window closed'
exit 0
