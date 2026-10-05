param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("desktop", "worker")]
    [string]$Product,
    [Parameter(Mandatory = $true)]
    [string]$PayloadRoot,
    [string]$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")),
    [string]$PythonEmbedArchive = "",
    [string]$UvExecutable = "",
    [string]$GitArchive = ""
)

$ErrorActionPreference = "Stop"
$pythonVersion = "3.12.10"
$pythonArchiveSha256 = "4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3"
$pythonArchiveUrl = "https://www.python.org/ftp/python/$pythonVersion/python-$pythonVersion-embed-amd64.zip"
$payload = (Resolve-Path -LiteralPath $PayloadRoot).Path
$repository = (Resolve-Path -LiteralPath $RepositoryRoot).Path
$runtimeRoot = Join-Path $payload "runtime\python"
$temporaryRoot = Join-Path ([IO.Path]::GetTempPath()) ("soda-runtime-" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $temporaryRoot -Force | Out-Null
$releasePath = if ($Product -eq "desktop") {
    Join-Path $payload "core\RELEASE.json"
}
else {
    Join-Path $payload "worker\RELEASE.json"
}
$release = Get-Content -LiteralPath $releasePath -Raw -Encoding UTF8 | ConvertFrom-Json
$version = if ($Product -eq "desktop") { $release.product_version } else { $release.worker_version }

function Remove-RuntimeBuildArtifacts {
    param([string]$Payload, [string]$SitePackages)
    # pip's local wheel provenance can include the private temporary build path.
    foreach ($metadata in Get-ChildItem -LiteralPath $SitePackages -Filter "direct_url.json" -Recurse -File) {
        if ($metadata.Directory.Name.EndsWith(".dist-info", [StringComparison]::OrdinalIgnoreCase)) {
            $provenance = Get-Content -LiteralPath $metadata.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
            $sourceUrl = [string]$provenance.url
            if ($sourceUrl.StartsWith("file:", [StringComparison]::OrdinalIgnoreCase)) {
                Remove-Item -LiteralPath $metadata.FullName -Force
            }
        }
    }
    # Keep the final payload clean even when an earlier installer supplied caches.
    Get-ChildItem -LiteralPath $Payload -Filter "*.pyc" -Recurse -File |
        ForEach-Object { Remove-Item -LiteralPath $_.FullName -Force }
    Get-ChildItem -LiteralPath $Payload -Filter "__pycache__" -Recurse -Directory |
        Sort-Object { $_.FullName.Length } -Descending |
        ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force }
}

try {
    if ($Product -eq "desktop") {
        & (Join-Path $PSScriptRoot "prepare-git.ps1") -PayloadRoot $payload -GitArchive $GitArchive
    }
    if ([string]::IsNullOrWhiteSpace($PythonEmbedArchive)) {
        $PythonEmbedArchive = Join-Path $temporaryRoot "python-embed-amd64.zip"
        Invoke-WebRequest -Uri $pythonArchiveUrl -OutFile $PythonEmbedArchive -UseBasicParsing
    }
    $archive = (Resolve-Path -LiteralPath $PythonEmbedArchive).Path
    $actualHash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $pythonArchiveSha256) {
        throw "Python runtime SHA-256 不匹配：$actualHash"
    }

    if (Test-Path -LiteralPath $runtimeRoot) {
        Remove-Item -LiteralPath $runtimeRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
    Expand-Archive -LiteralPath $archive -DestinationPath $runtimeRoot -Force
    $sitePackages = Join-Path $runtimeRoot "Lib\site-packages"
    New-Item -ItemType Directory -Path $sitePackages -Force | Out-Null
    $pthPath = Join-Path $runtimeRoot "python312._pth"
    $pthLines = @("python312.zip", ".")
    if ($Product -eq "desktop") {
        $pthLines += "..\..\core\src"
    }
    $pthLines += "Lib\site-packages"
    $pthLines += "import site"
    [IO.File]::WriteAllLines($pthPath, $pthLines, [Text.UTF8Encoding]::new($false))

    if ($Product -eq "desktop") {
        $uvPath = $UvExecutable
        if ([string]::IsNullOrWhiteSpace($uvPath)) {
            $uv = Get-Command uv.exe -ErrorAction SilentlyContinue
            if ($null -eq $uv) {
                $uv = Get-Command uv -ErrorAction SilentlyContinue
            }
            if ($null -ne $uv) {
                $uvPath = $uv.Source
            }
        }
        if ([string]::IsNullOrWhiteSpace($uvPath) -or -not (Test-Path -LiteralPath $uvPath)) {
            throw "构建机缺少 uv，无法从 uv.lock 导出固定依赖。"
        }
        $requirements = Join-Path $temporaryRoot "runtime-requirements.txt"
        & $uvPath export --frozen --no-default-groups --no-emit-project `
            --format requirements-txt --no-hashes --output-file $requirements `
            --project $repository
        if ($LASTEXITCODE -ne 0) {
            throw "uv export 失败，exit code $LASTEXITCODE。"
        }
        $wheels = Join-Path $temporaryRoot "wheels"
        $previousErrorAction = $ErrorActionPreference
        try {
            $ErrorActionPreference = "Continue"
            & $uvPath build --wheel --out-dir $wheels --no-create-gitignore $repository
            $uvBuildExitCode = $LASTEXITCODE
        }
        finally {
            $ErrorActionPreference = $previousErrorAction
        }
        if ($uvBuildExitCode -ne 0) {
            throw "Prompt Hub wheel 构建失败，exit code $uvBuildExitCode。"
        }
        $projectWheels = @(Get-ChildItem -LiteralPath $wheels -Filter "prompt_hub-*.whl" -File)
        if ($projectWheels.Count -ne 1) {
            throw "Prompt Hub wheel 数量异常：$($projectWheels.Count)"
        }

        $previousErrorAction = $ErrorActionPreference
        try {
            # Windows PowerShell 5.1 wraps normal native stderr progress as ErrorRecord.
            # Keep it visible, but use the process exit code as the actual failure signal.
            $ErrorActionPreference = "Continue"
            $builder = Get-Command py.exe -ErrorAction SilentlyContinue
            if ($null -ne $builder) {
                & $builder.Source -3.12 -m pip install --disable-pip-version-check `
                    --no-deps --no-compile --only-binary=:all: --requirement $requirements `
                    $projectWheels[0].FullName --target $sitePackages
            }
            else {
                $builder = Get-Command python.exe -ErrorAction Stop
                & $builder.Source -m pip install --disable-pip-version-check `
                    --no-deps --no-compile --only-binary=:all: --requirement $requirements `
                    $projectWheels[0].FullName --target $sitePackages
            }
            $pipExitCode = $LASTEXITCODE
        }
        finally {
            $ErrorActionPreference = $previousErrorAction
        }
        if ($pipExitCode -ne 0) {
            throw "Windows runtime 依赖安装失败，exit code $pipExitCode。"
        }
    }

    $embeddedPython = Join-Path $runtimeRoot "python.exe"
    # Self-test imports must not add bytecode files after the core manifest was sealed.
    if ($Product -eq "desktop") {
        & $embeddedPython -B -c "import fastapi, mcp, numpy, onnxruntime, PIL, prompt_hub, uvicorn, win32api, pathlib, sys; assert prompt_hub.__version__ == '$version'; assert pathlib.Path(prompt_hub.__file__).resolve() == pathlib.Path(sys.executable).resolve().parents[2] / 'core/src/prompt_hub/__init__.py'"
    }
    else {
        & $embeddedPython -B -c "import json, pathlib, urllib.request"
    }
    if ($LASTEXITCODE -ne 0) {
        throw "随包 Python 自检失败，exit code $LASTEXITCODE。"
    }

    Remove-RuntimeBuildArtifacts -Payload $payload -SitePackages $sitePackages

    $installMode = [ordered]@{
        format = "soda-install-mode-v1"
        product = $Product
        version = [string]$version
        state_location = "local-app-data"
    }
    [IO.File]::WriteAllText(
        (Join-Path $payload "INSTALL_MODE.json"),
        (($installMode | ConvertTo-Json -Depth 4) + "`n"),
        [Text.UTF8Encoding]::new($false))
    $runtimeInfo = [ordered]@{
        format = "soda-python-runtime-v1"
        python_version = $pythonVersion
        python_archive_sha256 = $pythonArchiveSha256
        dependency_source = if ($Product -eq "desktop") { "uv.lock" } else { "stdlib-only" }
    }
    [IO.File]::WriteAllText(
        (Join-Path $payload "PYTHON_RUNTIME.json"),
        (($runtimeInfo | ConvertTo-Json -Depth 4) + "`n"),
        [Text.UTF8Encoding]::new($false))

    $manifestPath = Join-Path $payload "PACKAGE_MANIFEST.sha256"
    $prefix = $payload.TrimEnd("\") + "\"
    $lines = Get-ChildItem -LiteralPath $payload -Recurse -File |
        Where-Object { $_.FullName -ne $manifestPath } |
        Sort-Object FullName |
        ForEach-Object {
            $relative = $_.FullName.Substring($prefix.Length).Replace("\", "/")
            $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
            "$hash  $relative"
        }
    [IO.File]::WriteAllLines($manifestPath, $lines, [Text.UTF8Encoding]::new($false))
    Write-Host "[OK] $Product bundled Python $pythonVersion"
}
finally {
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force -ErrorAction SilentlyContinue
}
