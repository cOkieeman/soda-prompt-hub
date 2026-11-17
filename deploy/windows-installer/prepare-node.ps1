param(
    [Parameter(Mandatory = $true)]
    [string]$PayloadRoot,
    [string]$NodeArchive = ""
)

$ErrorActionPreference = "Stop"
$nodeVersion = "22.14.0"
$archiveName = "node-v$nodeVersion-win-x64.zip"
$expectedHash = "55b639295920b219bb2acbcfa00f90393a2789095b7323f79475c9f34795f217"
$payload = (Resolve-Path -LiteralPath $PayloadRoot).Path
$temporaryRoot = Join-Path ([IO.Path]::GetTempPath()) ("soda-node-" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $temporaryRoot -Force | Out-Null
try {
    if ([string]::IsNullOrWhiteSpace($NodeArchive)) {
        $NodeArchive = Join-Path $temporaryRoot $archiveName
        Invoke-WebRequest -Uri "https://nodejs.org/dist/v$nodeVersion/$archiveName" -OutFile $NodeArchive -UseBasicParsing
    }
    $archive = (Resolve-Path -LiteralPath $NodeArchive).Path
    $actualHash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $expectedHash) {
        throw "Node.js archive SHA-256 mismatch."
    }
    Expand-Archive -LiteralPath $archive -DestinationPath $temporaryRoot -Force
    $source = Join-Path $temporaryRoot "node-v$nodeVersion-win-x64"
    $target = Join-Path $payload "runtime\node"
    New-Item -ItemType Directory -Path $target -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $source "node.exe") -Destination $target -Force
    Copy-Item -LiteralPath (Join-Path $source "LICENSE") -Destination $target -Force
    & (Join-Path $target "node.exe") --version
    if ($LASTEXITCODE -ne 0) { throw "Node.js runtime verification failed." }
}
finally {
    $resolvedTemporary = [IO.Path]::GetFullPath($temporaryRoot)
    $temporaryPrefix = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd("\") + "\soda-node-"
    if (-not $resolvedTemporary.StartsWith($temporaryPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Node.js temporary directory escaped its build directory."
    }
    Remove-Item -LiteralPath $resolvedTemporary -Recurse -Force
}
