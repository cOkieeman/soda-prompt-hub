$ErrorActionPreference = "Stop"
$manifestPath = Join-Path $PSScriptRoot "MANIFEST.sha256"

if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    Write-Host "[ERROR] MANIFEST.sha256 不存在。请重新下载完整的 Windows Worker ZIP。" -ForegroundColor Red
    exit 2
}

$failed = @()
$checked = 0
foreach ($line in Get-Content -LiteralPath $manifestPath -Encoding UTF8) {
    if ([string]::IsNullOrWhiteSpace($line)) { continue }
    if ($line -notmatch '^([0-9a-f]{64})  (.+)$') {
        $failed += "清单格式错误: $line"
        continue
    }
    $expected = $Matches[1]
    $relative = $Matches[2].Replace('/', [IO.Path]::DirectorySeparatorChar)
    $target = Join-Path $PSScriptRoot $relative
    if (-not (Test-Path -LiteralPath $target -PathType Leaf)) {
        $failed += "缺少文件: $relative"
        continue
    }
    $actual = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $expected) {
        $failed += "校验失败: $relative"
        continue
    }
    $checked += 1
}

if ($failed.Count -gt 0) {
    Write-Host "[ERROR] Windows Worker 发行包不完整：" -ForegroundColor Red
    $failed | ForEach-Object { Write-Host "- $_" }
    exit 1
}

Write-Host "[OK] 已校验 $checked 个文件，发行包完整。" -ForegroundColor Green
exit 0
