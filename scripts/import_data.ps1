<#
导入仓库自带的业务数据：
  1. 建表（alembic upgrade head）
  2. 导入 data\seed\georag_seed.sql —— 知识库、文档、检索分块、题库、活动
  3. 按 data\kb\manifest.json 把语料 PDF 放回 backend\uploads\ 下数据库记录的位置

用法（仓库根目录）：
    powershell -ExecutionPolicy Bypass -File scripts\import_data.ps1
    powershell ... -File scripts\import_data.ps1 -SkipPdf     # 只导数据库

导入后默认账号：admin / shuyuan@2026（请尽快修改密码）。
#>
[CmdletBinding()]
param(
    [string]$Root,
    [switch]$SkipPdf
)

$ErrorActionPreference = 'Stop'

if (-not $Root) { $Root = Split-Path -Parent $PSScriptRoot }
$Root = (Resolve-Path -LiteralPath $Root).Path.TrimEnd('\')
$Backend = Join-Path $Root 'backend'
$Seed = Join-Path $Root 'data\seed\georag_seed.sql'
$Manifest = Join-Path $Root 'data\kb\manifest.json'

Write-Host '=== 导入业务数据 ===' -ForegroundColor Cyan

# ------------------------------------------------------------ 读取后端配置 ---
$envFile = Join-Path $Backend '.env'
$cfg = @{
    DB_HOST = '127.0.0.1'; DB_PORT = '3306'; DB_USER = 'georag'
    DB_PASSWORD = 'georag_pass'; DB_NAME = 'georag'
}
if (Test-Path $envFile) {
    foreach ($line in Get-Content $envFile) {
        if ($line -match '^\s*([A-Z_]+)\s*=\s*(.*)$' -and $cfg.ContainsKey($matches[1])) {
            $cfg[$matches[1]] = $matches[2].Trim()
        }
    }
} else {
    Write-Host '[!] backend\.env 不存在，先运行 安装依赖.bat 生成' -ForegroundColor Yellow
}

# ------------------------------------------------------------------ python ---
$py = $null
foreach ($candidate in @(
        (Join-Path $Backend '.venv\Scripts\python.exe'),
        'D:\Anaconda\envs\geogemma\python.exe',
        "$env:USERPROFILE\anaconda3\envs\geogemma\python.exe",
        "$env:USERPROFILE\miniconda3\envs\geogemma\python.exe")) {
    if ($candidate -and (Test-Path $candidate)) { $py = $candidate; break }
}
if (-not $py) {
    $found = Get-Command python -ErrorAction SilentlyContinue
    if ($found) { $py = $found.Source }
}
if (-not $py) { throw '找不到 Python，请先运行 安装依赖.bat' }
Write-Host ("[i] python : {0}" -f $py)

# ------------------------------------------------------------- 1. 建表 ------
Write-Host '[1/3] alembic upgrade head ...'
Push-Location $Backend
try {
    & $py -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'alembic 迁移失败，请检查 backend\.env 里的数据库配置' }
} finally {
    Pop-Location
}

# --------------------------------------------------------- 2. 导入 SQL ------
$mysql = (Get-Command mysql -ErrorAction SilentlyContinue).Source
if (-not $mysql) {
    $mysql = Get-ChildItem 'C:\Program Files\MySQL\*\bin\mysql.exe' -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty FullName
}
if (-not $mysql) { throw '找不到 mysql 客户端，请确认已安装 MySQL 8 并加入 PATH' }

Write-Host ("[2/3] 导入 {0} ..." -f (Split-Path -Leaf $Seed))
$mysqlArgs = @(
    "--host=$($cfg.DB_HOST)", "--port=$($cfg.DB_PORT)", "--user=$($cfg.DB_USER)",
    "--password=$($cfg.DB_PASSWORD)", "--default-character-set=utf8mb4", $cfg.DB_NAME
)
Get-Content -LiteralPath $Seed -Raw -Encoding UTF8 | & $mysql @mysqlArgs
if ($LASTEXITCODE -ne 0) { throw '导入 SQL 失败' }
Write-Host '      - 数据库导入完成'

# ----------------------------------------------------------- 3. 语料 PDF ----
if ($SkipPdf) {
    Write-Host '[3/3] 已跳过 PDF（-SkipPdf）'
} elseif (-not (Test-Path $Manifest)) {
    Write-Host '[3/3] 没有 data\kb\manifest.json，跳过 PDF' -ForegroundColor Yellow
} else {
    Write-Host '[3/3] 还原语料 PDF ...'
    $manifestData = Get-Content -LiteralPath $Manifest -Raw -Encoding UTF8 | ConvertFrom-Json
    $copied = 0
    foreach ($doc in $manifestData.documents) {
        $source = Join-Path $Root ("data\kb\pdf\" + $doc.pdf)
        $target = Join-Path $Backend ($doc.target -replace '/', '\')
        if (-not (Test-Path $source)) {
            Write-Host ("      - 缺少 {0}" -f $doc.pdf) -ForegroundColor Yellow
            continue
        }
        $dir = Split-Path -Parent $target
        if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
        Copy-Item -LiteralPath $source -Destination $target -Force
        $copied++
    }
    Write-Host ("      - 已还原 {0} 篇语料" -f $copied)
}

Write-Host ''
Write-Host '完成。默认管理员账号：admin / shuyuan@2026（登录后请立即修改密码）。' -ForegroundColor Green
