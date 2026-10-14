param(
    [string]$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\.."))
)

$ErrorActionPreference = "Stop"
$buildScript = Join-Path $RepositoryRoot "deploy\windows-installer\build.ps1"
$tokens = $null
$parseErrors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($buildScript, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count -ne 0) {
    throw "Installer build script has $($parseErrors.Count) parser errors."
}
$definition = $ast.Find({
    param($node)
    $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq "Assert-CleanPayload"
}, $true)
if ($null -eq $definition) { throw "Missing payload verifier." }
# Load only the verifier function; never run the installer build or any installation.
. ([ScriptBlock]::Create($definition.Extent.Text))
$runtimeScript = Join-Path $RepositoryRoot "deploy\windows-installer\prepare-runtime.ps1"
$runtimeAst = [Management.Automation.Language.Parser]::ParseFile($runtimeScript, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count -ne 0) { throw "Runtime script has parser errors." }
$sanitizer = $runtimeAst.Find({
    param($node)
    $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq "Remove-RuntimeBuildArtifacts"
}, $true)
if ($null -eq $sanitizer) { throw "Missing runtime sanitizer." }
. ([ScriptBlock]::Create($sanitizer.Extent.Text))

function Assert-Rejected {
    param([ScriptBlock]$Action, [string]$Case)
    $rejected = $false
    try { & $Action } catch { $rejected = $true }
    if (-not $rejected) { throw "Payload verifier accepted $Case." }
}

$temporary = Join-Path ([IO.Path]::GetTempPath()) ("soda-payload-regression-" + [Guid]::NewGuid().ToString("N"))
$payload = Join-Path $temporary "payload"
New-Item -ItemType Directory -Path $payload -Force | Out-Null
$file = Join-Path $payload "fixture.txt"
$manifest = Join-Path $payload "PACKAGE_MANIFEST.sha256"
try {
    [IO.File]::WriteAllText($file, "original fixture")
    $hash = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()
    $valid = "$hash  fixture.txt"
    [IO.File]::WriteAllText($manifest, $valid + "`n")
    Assert-CleanPayload -Root $payload

    [IO.File]::WriteAllText($file, "tampered fixture")
    Assert-Rejected { Assert-CleanPayload -Root $payload } "tampered hash"
    [IO.File]::WriteAllText($file, "original fixture")

    $extra = Join-Path $payload "unlisted.txt"
    [IO.File]::WriteAllText($extra, "unlisted fixture")
    Assert-Rejected { Assert-CleanPayload -Root $payload } "unlisted file"
    Remove-Item -LiteralPath $extra

    [IO.File]::WriteAllText($manifest, $valid + "`n" + $valid + "`n")
    Assert-Rejected { Assert-CleanPayload -Root $payload } "duplicate path"

    [IO.File]::WriteAllText($manifest, "$hash  ../outside.txt`n")
    Assert-Rejected { Assert-CleanPayload -Root $payload } "outside path"

    [IO.File]::WriteAllText($manifest, "$hash  $file`n")
    Assert-Rejected { Assert-CleanPayload -Root $payload } "absolute path"

    [IO.File]::WriteAllText($manifest, "invalid manifest`n")
    Assert-Rejected { Assert-CleanPayload -Root $payload } "invalid entry"

    $runtimePayload = Join-Path $temporary "runtime-payload"
    $sitePackages = Join-Path $runtimePayload "runtime\python\Lib\site-packages"
    $localInfo = Join-Path $sitePackages "anonymous-local.dist-info"
    $remoteInfo = Join-Path $sitePackages "anonymous-remote.dist-info"
    $cache = Join-Path $sitePackages "anonymous\__pycache__"
    New-Item -ItemType Directory -Path $localInfo, $remoteInfo, $cache -Force | Out-Null
    $localMetadata = Join-Path $localInfo "direct_url.json"
    $remoteMetadata = Join-Path $remoteInfo "direct_url.json"
    $looseCache = Join-Path $sitePackages "loose.pyc"
    $source = Join-Path $sitePackages "source.py"
    [IO.File]::WriteAllText($localMetadata, '{"url":"file:///C:/private/build/fixture.whl"}')
    [IO.File]::WriteAllText($remoteMetadata, '{"url":"https://example.invalid/public-fixture.whl"}')
    [IO.File]::WriteAllText((Join-Path $cache "fixture.pyc"), "cache")
    [IO.File]::WriteAllText($looseCache, "cache")
    [IO.File]::WriteAllText($source, "VALUE = 1")
    $sourceHash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
    Remove-RuntimeBuildArtifacts -Payload $runtimePayload -SitePackages $sitePackages
    if (Test-Path -LiteralPath $localMetadata) { throw "Local provenance was retained." }
    if (-not (Test-Path -LiteralPath $remoteMetadata)) { throw "Remote provenance was removed." }
    if (Test-Path -LiteralPath $cache) { throw "Bytecode cache directory was retained." }
    if (Test-Path -LiteralPath $looseCache) { throw "Loose bytecode was retained." }
    if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne $sourceHash) { throw "Runtime source was changed." }

    [ordered]@{ status = "passed"; cases = 12; installation_performed = $false } | ConvertTo-Json
}
finally {
    Remove-Item -LiteralPath $temporary -Recurse -Force -ErrorAction SilentlyContinue
}
