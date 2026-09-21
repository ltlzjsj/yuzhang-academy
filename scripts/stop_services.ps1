<#
停止由「启动系统.bat」拉起的服务。

优先按 .run\*.pid 里记录的进程号停（启动脚本每次都会写），
找不到时再按命令行特征兜底匹配。加 -DryRun 只列不杀，便于确认。

用法：
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\stop_services.ps1
    powershell ... -File scripts\stop_services.ps1 -DryRun
#>
[CmdletBinding()]
param(
    [string]$Root,
    [string]$RunDir,
    [switch]$DryRun
)

$ErrorActionPreference = 'SilentlyContinue'

if (-not $Root) { $Root = Split-Path -Parent $PSScriptRoot }
$Root = (Resolve-Path -LiteralPath $Root).Path.TrimEnd('\')
if (-not $RunDir) { $RunDir = Join-Path $Root '.run' }

function Get-ProcessTree {
    param([int]$Id)
    foreach ($child in (Get-CimInstance Win32_Process -Filter "ParentProcessId=$Id")) {
        Get-ProcessTree -Id $child.ProcessId
    }
    $Id
}

# ---------------------------------------------------------------- by pid file
$targets = [System.Collections.Generic.List[int]]::new()
foreach ($file in (Get-ChildItem -LiteralPath $RunDir -Filter '*.pid' -ErrorAction SilentlyContinue)) {
    $value = 0
    if ([int]::TryParse((Get-Content -LiteralPath $file.FullName -Raw).Trim(), [ref]$value)) {
        $targets.Add($value)
    }
}
$source = if ($targets.Count) { 'pid files in .run' } else { 'command-line fallback' }

# ------------------------------------------------------------ fallback match
if (-not $targets.Count) {
    $pattern = 'uvicorn\s+app\.main:app|celery\s+-A\s+app\.workers\.celery_app|npm(-cli\.js)?\s+run\s+dev|node_modules[\\/]vite|app\.py\s+--transport'
    Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -and
        ($_.Name -eq 'python.exe' -or $_.Name -eq 'node.exe' -or $_.Name -eq 'cmd.exe') -and
        ($_.CommandLine -like "*$Root*" -or $_.CommandLine -match $pattern)
    } | ForEach-Object { $targets.Add([int]$_.ProcessId) }
}

if (-not $targets.Count) {
    Write-Host '[i] no running service of this repository was found.'
    return
}

Write-Host ("[i] matched by {0}" -f $source)
$stopped = 0
foreach ($processId in ($targets | Sort-Object -Unique)) {
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if (-not $process) {
        Write-Host ("    - {0} already exited" -f $processId)
        continue
    }
    Write-Host ("    - {0} (PID {1})" -f $process.ProcessName, $processId)
    if (-not $DryRun) {
        foreach ($child in (Get-ProcessTree -Id $processId)) {
            Stop-Process -Id $child -Force -ErrorAction SilentlyContinue
        }
        $stopped++
    }
}

if ($DryRun) {
    Write-Host '[i] dry run - nothing was stopped.'
} else {
    Get-ChildItem -LiteralPath $RunDir -Filter '*.pid' -ErrorAction SilentlyContinue |
        Remove-Item -Force -ErrorAction SilentlyContinue
    Write-Host ("[ok] stopped {0} process group(s)." -f $stopped)
}
