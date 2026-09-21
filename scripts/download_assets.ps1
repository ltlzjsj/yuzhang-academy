<#
下载并解压仓库附带的大素材包（放在 GitHub Release 里，不占仓库体积）：
    shuyuan-images.zip      书院实拍 / 事件画 / 立绘       约 910 MB
    livetalking-data.zip    数字人说话帧 + 待机帧 + 源视频  约 700 MB

默认都解压到仓库内的 assets\ 目录（LiveTalking 存在时，数字人数据直接进它的 data\）：
    assets\书院文化图片\      → 同时写入 backend\.env 的 ACADEMY_IMAGES_DIR
    ..\LiveTalking\data\     → 数字人帧数据

用法（仓库根目录）：
    powershell -ExecutionPolicy Bypass -File scripts\download_assets.ps1
    powershell ... -File scripts\download_assets.ps1 -Only images
    powershell ... -File scripts\download_assets.ps1 -Only digitalhuman
#>
[CmdletBinding()]
param(
    [string]$Root,
    [ValidateSet('all', 'images', 'digitalhuman')]
    [string]$Only = 'all',
    [string]$LiveTalkingDir
)

$ErrorActionPreference = 'Stop'
if (-not $Root) { $Root = Split-Path -Parent $PSScriptRoot }
$Root = (Resolve-Path -LiteralPath $Root).Path.TrimEnd('\')

if (-not $LiveTalkingDir) { $LiveTalkingDir = Join-Path (Split-Path -Parent $Root) 'LiveTalking' }

$release = 'https://github.com/ltlzjsj/yuzhang-academy/releases/download/assets-v1'
$assets = Join-Path $Root 'assets'
$cache = Join-Path $assets '_download'
New-Item -ItemType Directory -Force -Path $cache | Out-Null

function Get-Asset {
    param([string]$Name)
    $target = Join-Path $cache $Name
    if ((Test-Path $target) -and (Get-Item $target).Length -gt 1MB) {
        Write-Host ("    {0} 已存在，跳过下载" -f $Name)
        return $target
    }
    $url = "$release/$Name"
    Write-Host ("    下载 {0} ..." -f $url)
    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
    if ($curl) {
        & $curl.Source -L --fail --retry 3 -o $target $url
        if ($LASTEXITCODE -ne 0) { throw "下载失败：$url" }
    } else {
        $old = $ProgressPreference
        $ProgressPreference = 'Continue'
        try { Invoke-WebRequest -Uri $url -OutFile $target } finally { $ProgressPreference = $old }
    }
    Write-Host ("    完成 {0:N1} MB" -f ((Get-Item $target).Length / 1MB))
    return $target
}

function Expand-Into {
    param([string]$Zip, [string]$Destination)
    Write-Host ("    解压到 {0}" -f $Destination)
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    if (Test-Path $Zip) {
        Expand-Archive -LiteralPath $Zip -DestinationPath $Destination -Force
    } else {
        # 分卷（Release 附件超过 2GB 时用），按顺序合并后解压
        $parts = Get-ChildItem -Path ($Zip + '.*') -ErrorAction SilentlyContinue | Sort-Object Name
        if (-not $parts) { throw "找不到 $Zip" }
        $merged = "$Zip.merged"
        $out = [IO.File]::Create($merged)
        foreach ($part in $parts) {
            $in = [IO.File]::OpenRead($part.FullName)
            $in.CopyTo($out)
            $in.Close()
        }
        $out.Close()
        Expand-Archive -LiteralPath $merged -DestinationPath $Destination -Force
        Remove-Item -LiteralPath $merged -Force
    }
}

Write-Host '=== 下载素材包 ===' -ForegroundColor Cyan

if ($Only -in @('all', 'images')) {
    Write-Host '[1] 书院文化图片'
    $zip = Get-Asset 'shuyuan-images.zip'
    Expand-Into -Zip $zip -Destination $assets
    $envFile = Join-Path $Root 'backend\.env'
    $example = Join-Path $Root 'backend\.env.example'
    if (-not (Test-Path $envFile) -and (Test-Path $example)) { Copy-Item $example $envFile }
    if (Test-Path $envFile) {
        $lines = Get-Content $envFile
        $out = foreach ($line in $lines) {
            if ($line -match '^\s*ACADEMY_IMAGES_DIR\s*=') { 'ACADEMY_IMAGES_DIR=../assets/书院文化图片' } else { $line }
        }
        Set-Content -LiteralPath $envFile -Value $out -Encoding UTF8
        Write-Host '    backend\.env 里的 ACADEMY_IMAGES_DIR 已指向 ../assets/书院文化图片'
    }
}

if ($Only -in @('all', 'digitalhuman')) {
    Write-Host '[2] 数字人帧数据'
    $zip = Get-Asset 'livetalking-data.zip'
    if (Test-Path (Join-Path $LiveTalkingDir 'app.py')) {
        Write-Host ("    发现 LiveTalking：{0}" -f $LiveTalkingDir)
        Expand-Into -Zip $zip -Destination $LiveTalkingDir
        Write-Host '    说话帧与待机帧已就位（data\avatars、data\custom）'
    } else {
        Write-Host '    未发现 LiveTalking 目录，先解压到 assets\livetalking' -ForegroundColor Yellow
        Expand-Into -Zip $zip -Destination (Join-Path $assets 'livetalking')
        Write-Host '    之后把 assets\livetalking\data 拷进 LiveTalking\data 即可' -ForegroundColor Yellow
        Write-Host '    LiveTalking 的安装与补丁见 docs\数字人实时引擎.md' -ForegroundColor Yellow
    }
}

Write-Host ''
Write-Host '完成。' -ForegroundColor Green
