param(
    [ValidateSet("win-x64")]
    [string]$Runtime = "win-x64",
    [string]$OutputRoot = (Join-Path $PSScriptRoot "dist"),
    [string]$GitArchive = ""
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$projectPath = Join-Path $PSScriptRoot "SodaPromptHub\SodaPromptHub.csproj"
$release = Get-Content -LiteralPath (Join-Path $repositoryRoot "RELEASE.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$version = [string]$release.product_version
if ([string]::IsNullOrWhiteSpace($version)) {
    throw "RELEASE.json 缺少 product_version。"
}

$packageName = "Soda-Prompt-Hub-Desktop-$version-$Runtime"
$publishRoot = Join-Path ([IO.Path]::GetFullPath($OutputRoot)) $packageName
$archivePath = "$publishRoot.zip"
if (Test-Path -LiteralPath $publishRoot) {
    Remove-Item -LiteralPath $publishRoot -Recurse -Force
}
if (Test-Path -LiteralPath $archivePath) {
    Remove-Item -LiteralPath $archivePath -Force
}

dotnet publish $projectPath `
    --configuration Release `
    --runtime $Runtime `
    --self-contained true `
    --output $publishRoot `
    -p:PublishSingleFile=true `
    -p:IncludeNativeLibrariesForSelfExtract=true `
    -p:PublishTrimmed=false
if ($LASTEXITCODE -ne 0) {
    throw "dotnet publish 失败，exit code $LASTEXITCODE。"
}

Get-ChildItem -LiteralPath $publishRoot -File |
    Where-Object { $_.Extension -in @(".pdb", ".xml") } |
    Remove-Item -Force

& (Join-Path $repositoryRoot "deploy\windows-installer\prepare-git.ps1") -PayloadRoot $publishRoot -GitArchive $GitArchive

function Write-HashManifest {
    param([string]$Root, [string]$ManifestName)

    $manifestPath = Join-Path $Root $ManifestName
    $prefix = $Root.TrimEnd("\") + "\"
    $lines = Get-ChildItem -LiteralPath $Root -Recurse -File |
        Where-Object { $_.FullName -ne $manifestPath } |
        Sort-Object FullName |
        ForEach-Object {
            $relative = $_.FullName.Substring($prefix.Length).Replace("\", "/")
            $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
            "$hash  $relative"
        }
    [IO.File]::WriteAllLines($manifestPath, $lines, [Text.UTF8Encoding]::new($false))
}

Write-HashManifest -Root (Join-Path $publishRoot "core") -ManifestName "MANIFEST.sha256"
Write-HashManifest -Root (Join-Path $publishRoot "worker") -ManifestName "MANIFEST.sha256"
Write-HashManifest -Root $publishRoot -ManifestName "PACKAGE_MANIFEST.sha256"

Compress-Archive -LiteralPath $publishRoot -DestinationPath $archivePath -CompressionLevel Optimal
$hash = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
Write-Host "[OK] $archivePath"
Write-Host "SHA-256: $hash"
