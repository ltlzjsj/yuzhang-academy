<#
下载并解压仓库附带的大素材包（放在 GitHub Release 里，不占仓库体积）：
    shuyuan-images.zip      书院实拍 / 事件画 / 立绘         约 911 MB
    livetalking-data.zip    数字人说话帧 + 待机帧 + 源视频    约 742 MB

默认解压到仓库内的 assets\ 目录（若同级存在 LiveTalking，数字人数据直接进它的 data\）：
    assets\书院文化图片\      → 同时写入 backend\.env 的 ACADEMY_IMAGES_DIR
    ..\LiveTalking\data\     → 数字人帧数据

用法（仓库根目录）：
    powershell -ExecutionPolicy Bypass -File scripts\download_assets.ps1
    powershell ... -File scripts\download_assets.ps1 -Only images
    powershell ... -File scripts\download_assets.ps1 -Only digitalhuman

下载走两个通道：先按 API 解析附件直链（直连 CDN，国内网络通常更稳），失败再退回
releases/download 地址；支持断点续传，某个通道长时间没有进展会自动切换。
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

$repoSlug = 'ltlzjsj/yuzhang-academy'
$tag = 'assets-v1'
$releaseBase = "https://github.com/$repoSlug/releases/download/$tag"
$apiBase = "https://api.github.com/repos/$repoSlug/releases/assets"
$apiRelease = "https://api.github.com/repos/$repoSlug/releases/tags/$tag"

# API 查询失败时兜底用的附件 ID
$fallbackIds = @{
    'shuyuan-images.zip'   = 579067342
    'livetalking-data.zip' = 579078876
}

$assets = Join-Path $Root 'assets'
$cache = Join-Path $assets '_download'
New-Item -ItemType Directory -Force -Path $cache | Out-Null

function Resolve-Asset {
    param([string]$Name)
    $info = @{ Id = $fallbackIds[$Name]; Size = 0 }
    try {
        $release = Invoke-RestMethod -Uri $apiRelease -Headers @{ 'User-Agent' = 'codex' } -TimeoutSec 30
        $hit = $release.assets | Where-Object { $_.name -eq $Name } | Select-Object -First 1
        if ($hit) { $info.Id = $hit.id; $info.Size = [int64]$hit.size }
    } catch {
        Write-Host ("    （查询 Release 信息失败，使用内置附件地址：{0}）" -f $_.Exception.Message) -ForegroundColor Yellow
    }
    return $info
}

function Invoke-Download {
    param([string]$Name, [string]$Target, [int64]$Expected, [string[]]$Urls)

    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
    foreach ($url in $Urls) {
        Write-Host ("    通道：{0}" -f $url)
        for ($round = 1; $round -le 60; $round++) {
            $before = if (Test-Path $Target) { (Get-Item $Target).Length } else { 0 }
            if ($Expected -gt 0 -and $before -ge $Expected) { return $true }

            if ($curl) {
                # -C - 断点续传；120s 没有进展（速度低于 20KB/s）就放弃本轮
                $oldEap = $ErrorActionPreference
                $ErrorActionPreference = 'Continue'   # 原生程序写 stderr 时不要中断脚本
                try {
                    & $curl.Source -sS -L --fail --retry 1 -C - --connect-timeout 20 `
                        --speed-limit 20000 --speed-time 30 --max-time 120 `
                        -H 'Accept: application/octet-stream' -o $Target $url 2>$null
                } finally { $ErrorActionPreference = $oldEap }
                $code = $LASTEXITCODE
            } else {
                $old = $ProgressPreference
                $ProgressPreference = 'Continue'
                try {
                    Invoke-WebRequest -Uri $url -Headers @{ Accept = 'application/octet-stream' } `
                        -OutFile $Target -TimeoutSec 120
                    $code = 0
                } catch {
                    $code = 1
                } finally { $ProgressPreference = $old }
            }

            $after = if (Test-Path $Target) { (Get-Item $Target).Length } else { 0 }
            if ($code -eq 0 -and ($Expected -eq 0 -or $after -ge $Expected)) {
                Write-Host ("    完成 {0:N1} MB" -f ($after / 1MB))
                return $true
            }
            if ($after -le $before) {
                Write-Host '    该通道没有进展，换下一个通道' -ForegroundColor Yellow
                break
            }
            Write-Host ("    已下载 {0:N0} MB，继续续传 ..." -f ($after / 1MB))
        }
    }
    return $false
}

function Get-Asset {
    param([string]$Name)
    $target = Join-Path $cache $Name
    $info = Resolve-Asset -Name $Name

    if ((Test-Path $target) -and $info.Size -gt 0 -and (Get-Item $target).Length -ge $info.Size) {
        Write-Host ("    {0} 已下载过，跳过" -f $Name)
        return $target
    }
    Write-Host ("    附件 id={0}，大小约 {1:N0} MB" -f $info.Id, ($info.Size / 1MB))

    $urls = @("$apiBase/$($info.Id)", "$releaseBase/$Name")
    if (Invoke-Download -Name $Name -Target $target -Expected $info.Size -Urls $urls) {
        return $target
    }
    throw "下载失败：$Name（两个通道都不可用，可手动从 Release 页面下载）"
}

function Expand-Into {
    param([string]$Zip, [string]$Destination)
    Write-Host ("    解压到 {0}" -f $Destination)
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    Expand-Archive -LiteralPath $Zip -DestinationPath $Destination -Force
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
        $out = foreach ($line in (Get-Content $envFile)) {
            if ($line -match '^\s*ACADEMY_IMAGES_DIR\s*=') { 'ACADEMY_IMAGES_DIR=../assets/书院文化图片' } else { $line }
        }
        Set-Content -LiteralPath $envFile -Value $out -Encoding UTF8
        Write-Host '    backend\.env 的 ACADEMY_IMAGES_DIR 已指向 ../assets/书院文化图片'
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
