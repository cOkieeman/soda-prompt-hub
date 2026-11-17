param(
    [Parameter(Mandatory = $true)]
    [string]$PublishedRoot,
    [Parameter(Mandatory = $true)]
    [string]$WorkerRoot
)

$ErrorActionPreference = "Stop"
$source = (Resolve-Path -LiteralPath $PublishedRoot).Path
$target = (Resolve-Path -LiteralPath $WorkerRoot).Path
$exePath = Join-Path $source "Soda Compute Worker.exe"
if (-not (Test-Path -LiteralPath $exePath -PathType Leaf)) {
    throw "PublishedRoot 中找不到 Soda Compute Worker.exe。"
}
if (-not (Test-Path -LiteralPath (Join-Path $target "prompt_hub_worker.py") -PathType Leaf)) {
    throw "WorkerRoot 不是现有 Worker 目录。"
}

$configPath = Join-Path $target "worker-config.json"
$configHash = if (Test-Path -LiteralPath $configPath -PathType Leaf) {
    (Get-FileHash -LiteralPath $configPath -Algorithm SHA256).Hash
} else {
    $null
}

Get-ChildItem -LiteralPath $source -Force |
    Where-Object {
        $_.Name -notin @(
            "worker",
            "worker-config.json",
            "PACKAGE_MANIFEST.sha256",
            "校验桌面包.ps1"
        )
    } |
    ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $target -Recurse -Force
    }

$publishedWorker = Join-Path $source "worker"
if (Test-Path -LiteralPath $publishedWorker -PathType Container) {
    Get-ChildItem -LiteralPath $publishedWorker -Force |
        Where-Object { $_.Name -ne "worker-config.json" } |
        ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination $target -Recurse -Force
        }
}

if ($null -ne $configHash) {
    $currentHash = (Get-FileHash -LiteralPath $configPath -Algorithm SHA256).Hash
    if ($currentHash -ne $configHash) {
        throw "安全检查失败：worker-config.json 被修改。"
    }
}

Write-Host "[OK] 图形启动器已安装到 $target"
Write-Host "原有 worker-config.json 保持不变。"
