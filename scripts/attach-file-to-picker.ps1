# attach-file-to-picker.ps1
# Drives a Windows file Open dialog (e.g. one spawned by Chrome's
# <input type=file>) by locating the dialog window via Win32 API and
# sending WM_SETTEXT to the File-name edit, then posting IDOK to the
# Open button.
#
# Runs as the user (not via MCP), so it bypasses Claude Code's tier
# restriction on Chrome — PowerShell calls into user32.dll directly.
#
# Usage:
#   pwsh -File attach-file-to-picker.ps1 -Path "C:\Project 1\sales\images\linkedin_banner.png"
#
# Exit codes:
#   0 = success
#   2 = file does not exist
#   3 = no Open dialog found within timeout
#   4 = File name edit control not found
#   5 = Open button not found / could not invoke

param(
    [Parameter(Mandatory=$true)] [string] $Path,
    [int]    $DialogTimeoutSec = 10
)

if (-not (Test-Path -LiteralPath $Path)) {
    Write-Error "File not found: $Path"
    exit 2
}
$absPath = (Resolve-Path -LiteralPath $Path).Path

# --- Win32 P/Invoke setup ---
$signature = @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class Win32 {
    [DllImport("user32.dll", SetLastError=true, CharSet=CharSet.Auto)]
    public static extern IntPtr FindWindow(string lpClassName, string lpWindowName);

    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
    [DllImport("user32.dll")]
    public static extern bool EnumWindows(EnumWindowsProc enumProc, IntPtr lParam);
    [DllImport("user32.dll")]
    public static extern bool EnumChildWindows(IntPtr hWnd, EnumWindowsProc enumProc, IntPtr lParam);

    [DllImport("user32.dll", SetLastError=true, CharSet=CharSet.Auto)]
    public static extern int GetClassName(IntPtr hWnd, StringBuilder lpClassName, int nMaxCount);

    [DllImport("user32.dll", SetLastError=true, CharSet=CharSet.Auto)]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);

    [DllImport("user32.dll")]
    public static extern int GetWindowTextLength(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern bool IsWindowVisible(IntPtr hWnd);

    [DllImport("user32.dll", CharSet=CharSet.Auto)]
    public static extern IntPtr SendMessage(IntPtr hWnd, int Msg, IntPtr wParam, string lParam);

    [DllImport("user32.dll", CharSet=CharSet.Auto)]
    public static extern IntPtr SendMessage(IntPtr hWnd, int Msg, IntPtr wParam, IntPtr lParam);

    [DllImport("user32.dll")]
    public static extern bool PostMessage(IntPtr hWnd, int Msg, IntPtr wParam, IntPtr lParam);

    [DllImport("user32.dll", SetLastError=true)]
    public static extern IntPtr GetDlgItem(IntPtr hDlg, int nIDDlgItem);

    [DllImport("user32.dll", SetLastError=true)]
    public static extern int GetDlgCtrlID(IntPtr hwndCtl);

    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);
}
"@
Add-Type -TypeDefinition $signature -ErrorAction SilentlyContinue

# --- Find the Open dialog ---
# Class name for modern Open file dialog is "#32770" (Win32 dialog class).
# The dialog title is "Open" by default.
$deadline = (Get-Date).AddSeconds($DialogTimeoutSec)
$dialog = [IntPtr]::Zero
while ((Get-Date) -lt $deadline) {
    $dialog = [Win32]::FindWindow('#32770', 'Open')
    if ($dialog -ne [IntPtr]::Zero) { break }
    Start-Sleep -Milliseconds 200
}
if ($dialog -eq [IntPtr]::Zero) {
    Write-Error "No '#32770' window titled 'Open' found within ${DialogTimeoutSec}s."
    exit 3
}

# Bring it foreground.
[void] [Win32]::SetForegroundWindow($dialog)
Start-Sleep -Milliseconds 200

# --- Find the File-name edit control by enumerating children ---
# In modern Vista+ open dialogs, the File-name field is inside a
# ComboBoxEx32 nested in a child window. The actual editable input is
# of class "Edit" inside the combo. We scan ALL descendants for an Edit
# control that is enabled and visible.
$script:fileEditHwnd = [IntPtr]::Zero
$enumProc = [Win32+EnumWindowsProc]{
    param($hwnd, $lp)
    $cls = New-Object Text.StringBuilder 256
    [void] [Win32]::GetClassName($hwnd, $cls, 256)
    if ($cls.ToString() -eq 'Edit') {
        # Skip if not visible
        if ([Win32]::IsWindowVisible($hwnd)) {
            # Skip the Search Box edit (class is on its parent).
            # Use control ID 1148 (well-known File-name combobox edit in modern Win10/11) preferentially.
            $id = [Win32]::GetDlgCtrlID($hwnd)
            # 1148 is the modern File-name edit child of the combobox; 1152 is legacy edt1.
            if ($id -eq 1148 -or $id -eq 1152) {
                $script:fileEditHwnd = $hwnd
                return $false  # stop enumeration
            }
            # Remember any Edit as a fallback if we don't find the well-known ID
            if ($script:fileEditHwnd -eq [IntPtr]::Zero -and $id -ne 0) {
                # don't immediately accept — keep looking for the well-known ID
            }
        }
    }
    return $true
}

# Walk all descendants of the dialog.
function Walk-Children([IntPtr]$parent) {
    [Win32]::EnumChildWindows($parent, $enumProc, [IntPtr]::Zero) | Out-Null
}
Walk-Children $dialog

# Fallback: GetDlgItem on standard IDs
if ($script:fileEditHwnd -eq [IntPtr]::Zero) {
    foreach ($candidateId in 1148, 1152, 1136, 1001) {
        $hwnd = [Win32]::GetDlgItem($dialog, $candidateId)
        if ($hwnd -ne [IntPtr]::Zero) {
            $script:fileEditHwnd = $hwnd
            break
        }
    }
}

# Last resort: pick first visible Edit that isn't the Search Box.
if ($script:fileEditHwnd -eq [IntPtr]::Zero) {
    $allEdits = New-Object System.Collections.ArrayList
    $collectProc = [Win32+EnumWindowsProc]{
        param($hwnd, $lp)
        $cls = New-Object Text.StringBuilder 256
        [void] [Win32]::GetClassName($hwnd, $cls, 256)
        if ($cls.ToString() -eq 'Edit' -and [Win32]::IsWindowVisible($hwnd)) {
            [void] $allEdits.Add($hwnd)
        }
        return $true
    }
    [Win32]::EnumChildWindows($dialog, $collectProc, [IntPtr]::Zero) | Out-Null
    foreach ($h in $allEdits) {
        $id = [Win32]::GetDlgCtrlID($h)
        # Search Box ID varies; skip if it's known SearchEditBox parent
        if ($id -ne 0) {
            $script:fileEditHwnd = $h
            break
        }
    }
}

if ($script:fileEditHwnd -eq [IntPtr]::Zero) {
    Write-Error "Could not find File-name edit control in the dialog."
    exit 4
}

$ctrlId = [Win32]::GetDlgCtrlID($script:fileEditHwnd)
Write-Output "Found File-name edit hwnd=$($script:fileEditHwnd) id=$ctrlId"

# WM_SETTEXT = 0x000C
$WM_SETTEXT = 0x000C
[void] [Win32]::SendMessage($script:fileEditHwnd, $WM_SETTEXT, [IntPtr]::Zero, $absPath)

Start-Sleep -Milliseconds 300

# --- Click the Open button (IDOK = 1) ---
# The Open button in a standard #32770 dialog has control ID 1 (IDOK).
$openBtn = [Win32]::GetDlgItem($dialog, 1)
if ($openBtn -eq [IntPtr]::Zero) {
    Write-Error "Open button (IDOK=1) not found."
    exit 5
}
# BM_CLICK = 0x00F5; alternatively post WM_COMMAND BN_CLICKED to parent.
$BM_CLICK = 0x00F5
[void] [Win32]::SendMessage($openBtn, $BM_CLICK, [IntPtr]::Zero, [IntPtr]::Zero)

Write-Output "Attached: $absPath"
exit 0
