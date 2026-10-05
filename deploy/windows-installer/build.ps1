param(
    [Parameter(Mandatory = $true)]
    [string]$DesktopPackageRoot,
    [Parameter(Mandatory = $true)]
    [string]$WorkerPackageRoot,
    [string]$OutputRoot = (Join-Path $PSScriptRoot "dist"),
    [string]$PythonEmbedArchive = "",
    [string]$UvExecutable = "",
    [string]$GitArchive = "",
    [string]$InnoCompiler = "",
    [string]$VerificationOutputRoot = ""
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$desktopSource = (Resolve-Path -LiteralPath $DesktopPackageRoot).Path
$workerSource = (Resolve-Path -LiteralPath $WorkerPackageRoot).Path
$verificationOutput = $null
if (-not [string]::IsNullOrWhiteSpace($VerificationOutputRoot)) {
    $verificationOutput = [IO.Path]::GetFullPath($VerificationOutputRoot)
    if (Test-Path -LiteralPath $verificationOutput) {
        throw "验收输出目录必须是不存在的新目录：$verificationOutput"
    }
    foreach ($sourceRoot in @($desktopSource, $workerSource)) {
        $sourcePrefix = $sourceRoot.TrimEnd("\") + "\"
        if ($verificationOutput.StartsWith($sourcePrefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw "验收输出目录不能位于输入 payload 内。"
        }
    }
}
$output = [IO.Path]::GetFullPath($OutputRoot)
$stagingId = [Guid]::NewGuid().ToString("N").Substring(0, 8)
$staging = Join-Path ([IO.Path]::GetTempPath()) ("SB-" + $stagingId)
$installerOutput = Join-Path $output "installers"
New-Item -ItemType Directory -Path $output -Force | Out-Null
if (Test-Path -LiteralPath $installerOutput) {
    Remove-Item -LiteralPath $installerOutput -Recurse -Force
}
New-Item -ItemType Directory -Path $installerOutput -Force | Out-Null
if (Test-Path -LiteralPath $staging) {
    Remove-Item -LiteralPath $staging -Recurse -Force
}
New-Item -ItemType Directory -Path $staging -Force | Out-Null

function Assert-CleanPayload {
    param([string]$Root)
    $manifestPath = Join-Path $Root "PACKAGE_MANIFEST.sha256"
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        throw "缺少 PACKAGE_MANIFEST.sha256：$Root"
    }
    $privateFiles = Get-ChildItem -LiteralPath $Root -Recurse -Force |
        Where-Object {
            $_.Name -in @("worker-config.json", ".venv", "__pycache__") -or
            $_.Extension -eq ".pyc" -or
            ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0
        }
    if ($privateFiles) {
        throw "安装 payload 含有私有配置、缓存或文件链接：$($privateFiles[0].FullName)"
    }
    $prefix = [IO.Path]::GetFullPath($Root).TrimEnd("\") + "\"
    $covered = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($line in Get-Content -LiteralPath $manifestPath -Encoding UTF8) {
        if ($line -notmatch '^([0-9a-fA-F]{64})  (.+)$') {
            throw "安装 payload manifest 条目无效。"
        }
        $expectedHash = $Matches[1].ToLowerInvariant()
        $relative = $Matches[2]
        if ([IO.Path]::IsPathRooted($relative)) {
            throw "安装 payload manifest 不能使用绝对路径。"
        }
        $file = [IO.Path]::GetFullPath((Join-Path $Root $relative))
        if (-not $file.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase) -or
            -not $covered.Add($file) -or
            -not (Test-Path -LiteralPath $file -PathType Leaf)) {
            throw "安装 payload manifest 路径越界、重复或不存在：$relative"
        }
        if (((Get-Item -LiteralPath $file).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "安装 payload 不接受指向其他文件的链接：$relative"
        }
        $actualHash = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualHash -ne $expectedHash) {
            throw "安装 payload SHA-256 不匹配：$relative"
        }
    }
    foreach ($file in Get-ChildItem -LiteralPath $Root -Recurse -File) {
        if ($file.FullName -ne $manifestPath -and -not $covered.Contains($file.FullName)) {
            throw "安装 payload 文件未出现在 manifest：$($file.FullName)"
        }
    }
}

Assert-CleanPayload -Root $desktopSource
Assert-CleanPayload -Root $workerSource
$desktopStage = Join-Path $staging "desktop"
$workerStage = Join-Path $staging "worker"
Copy-Item -LiteralPath $desktopSource -Destination $desktopStage -Recurse
Copy-Item -LiteralPath $workerSource -Destination $workerStage -Recurse

& (Join-Path $PSScriptRoot "prepare-runtime.ps1") -Product desktop `
    -PayloadRoot $desktopStage -RepositoryRoot $repositoryRoot `
    -PythonEmbedArchive $PythonEmbedArchive -UvExecutable $UvExecutable -GitArchive $GitArchive
if ($LASTEXITCODE -ne 0) { throw "Desktop Python runtime 准备失败。" }
& (Join-Path $PSScriptRoot "prepare-runtime.ps1") -Product worker `
    -PayloadRoot $workerStage -RepositoryRoot $repositoryRoot `
    -PythonEmbedArchive $PythonEmbedArchive -UvExecutable $UvExecutable
if ($LASTEXITCODE -ne 0) { throw "Worker Python runtime 准备失败。" }

Assert-CleanPayload -Root $desktopStage
Assert-CleanPayload -Root $workerStage
if ($null -ne $verificationOutput) {
    New-Item -ItemType Directory -Path $verificationOutput -ErrorAction Stop | Out-Null
    Copy-Item -LiteralPath $desktopStage -Destination (Join-Path $verificationOutput "desktop") -Recurse
    Copy-Item -LiteralPath $workerStage -Destination (Join-Path $verificationOutput "worker") -Recurse
}

$desktopRelease = Get-Content -LiteralPath (Join-Path $desktopStage "core\RELEASE.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$workerRelease = Get-Content -LiteralPath (Join-Path $workerStage "worker\RELEASE.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$version = [string]$desktopRelease.product_version
if ($version -ne [string]$workerRelease.worker_version) {
    throw "Desktop 与 Worker 版本不一致。"
}

$webViewBootstrapper = Join-Path $output "MicrosoftEdgeWebview2Setup.exe"
Invoke-WebRequest -UseBasicParsing -Uri "https://go.microsoft.com/fwlink/p/?LinkId=2124703" -OutFile $webViewBootstrapper
$signature = Get-AuthenticodeSignature -FilePath $webViewBootstrapper
if ($signature.Status -ne "Valid" -or $signature.SignerCertificate.Subject -notmatch "Microsoft") {
    throw "WebView2 bootstrapper 的 Microsoft 签名校验失败。"
}

if ([string]::IsNullOrWhiteSpace($InnoCompiler)) {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
    )
    $InnoCompiler = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if ([string]::IsNullOrWhiteSpace($InnoCompiler) -or -not (Test-Path -LiteralPath $InnoCompiler)) {
    throw "未找到 Inno Setup 6 ISCC.exe。请先在构建机安装 Inno Setup 6。"
}

foreach ($definition in @(
    @{ Script = "desktop.iss"; Payload = $desktopStage },
    @{ Script = "worker.iss"; Payload = $workerStage }
)) {
    & $InnoCompiler "/DPayloadRoot=$($definition.Payload)" "/DOutputRoot=$installerOutput" `
        "/DProductVersion=$version" "/DWebView2Bootstrapper=$webViewBootstrapper" `
        (Join-Path $PSScriptRoot $definition.Script)
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup 编译失败：$($definition.Script)"
    }
}

$installers = Get-ChildItem -LiteralPath $installerOutput -Filter "*.exe" -File | Sort-Object Name
$manifest = [ordered]@{
    format = "soda-commercial-windows-release-v1"
    version = $version
    signed = $false
    python_runtime = "3.12.10"
    git_runtime = (Get-Content -LiteralPath (Join-Path $desktopStage "GIT_RUNTIME.json") -Raw -Encoding UTF8 | ConvertFrom-Json)
    installers = @($installers | ForEach-Object {
        [ordered]@{
            file = $_.Name
            bytes = $_.Length
            sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    })
}
[IO.File]::WriteAllText(
    (Join-Path $installerOutput "COMMERCIAL_RELEASE.json"),
    (($manifest | ConvertTo-Json -Depth 6) + "`n"),
    [Text.UTF8Encoding]::new($false))
Remove-Item -LiteralPath $staging -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "[OK] $installerOutput"
