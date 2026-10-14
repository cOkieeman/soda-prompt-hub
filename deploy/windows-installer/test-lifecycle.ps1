param(
    [Parameter(Mandatory = $true)]
    [string]$InstallerRoot,
    [string]$StatusPath = "",
    [string]$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\.."))
)

$ErrorActionPreference = "Stop"
$installers = (Resolve-Path -LiteralPath $InstallerRoot).Path
$release = Get-Content -LiteralPath (Join-Path $RepositoryRoot "RELEASE.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$version = [string]$release.product_version
if ([string]::IsNullOrWhiteSpace($version)) {
    throw "RELEASE.json is missing product_version."
}
$desktopSetup = Join-Path $installers "Soda-Prompt-Hub-Desktop-$version-Setup.exe"
$workerSetup = Join-Path $installers "Soda-Compute-Worker-$version-Setup.exe"
$desktopRoot = Join-Path $env:LOCALAPPDATA "Programs\Soda Prompt Hub"
$workerRoot = Join-Path $env:LOCALAPPDATA "Programs\Soda Compute Worker"
$desktopData = Join-Path ([Environment]::GetFolderPath("MyDocuments")) "Soda Prompt Hub"
$workerData = Join-Path $env:LOCALAPPDATA "Soda Prompt Hub\Compute Worker"
$testId = [Guid]::NewGuid().ToString("N")
$desktopMarker = Join-Path $desktopData ".commercial-lifecycle-test"
$workerMarker = Join-Path $workerData ".commercial-lifecycle-test"
$desktopProcess = $null
$workerProcess = $null

if ([string]::IsNullOrWhiteSpace($StatusPath)) {
    $StatusPath = Join-Path $installers "windows-lifecycle-status.json"
}

function Invoke-Setup {
    param([string]$Path)
    $process = Start-Process -FilePath $Path -ArgumentList @(
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        "/CLOSEAPPLICATIONS=NO",
        "/SP-"
    ) -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "$([IO.Path]::GetFileName($Path)) failed with exit code $($process.ExitCode)"
    }
}

function Stop-InstalledProductTree {
    param([string]$ExecutablePath)
    $matches = @(Get-CimInstance Win32_Process | Where-Object {
        $_.ExecutablePath -and
        [string]::Equals($_.ExecutablePath, $ExecutablePath, [StringComparison]::OrdinalIgnoreCase)
    })
    foreach ($match in $matches) {
        & taskkill.exe /PID $match.ProcessId /T /F | Out-Null
        if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 128) {
            throw "Unable to stop installed process tree $($match.ProcessId)"
        }
    }
}

function Invoke-Uninstall {
    param([string]$ProductRoot)
    $uninstaller = Join-Path $ProductRoot "unins000.exe"
    if (-not (Test-Path -LiteralPath $uninstaller -PathType Leaf)) {
        throw "Missing uninstaller: $uninstaller"
    }
    Start-Process -FilePath $uninstaller -ArgumentList @(
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART"
    ) | Out-Null
    $deadline = [DateTime]::UtcNow.AddSeconds(90)
    while ([DateTime]::UtcNow -lt $deadline) {
        if (-not (Test-Path -LiteralPath $ProductRoot)) {
            return
        }
        Start-Sleep -Milliseconds 500
    }
    throw "Uninstaller did not remove the program directory within 90 seconds: $ProductRoot"
}

function Write-ProgressState {
    param([string]$Step)
    [ordered]@{
        status = "running"
        step = $Step
        updated_at = [DateTimeOffset]::Now.ToString("O")
    } | ConvertTo-Json | Set-Content -LiteralPath $StatusPath -Encoding UTF8
}

function Read-Health {
    for ($attempt = 0; $attempt -lt 90; $attempt++) {
        $previousErrorAction = $ErrorActionPreference
        try {
            $ErrorActionPreference = "Continue"
            $json = & curl.exe --silent --show-error --connect-timeout 1 --max-time 2 `
                "http://127.0.0.1:8765/api/health" 2>$null
            $curlExitCode = $LASTEXITCODE
        }
        finally {
            $ErrorActionPreference = $previousErrorAction
        }
        if ($curlExitCode -eq 0 -and $json) {
            try {
                $health = $json | ConvertFrom-Json
                if ($health.service -eq "soda-prompt-hub") {
                    return $health
                }
            }
            catch {
                # The service may still be starting and return a partial response.
            }
        }
        Start-Sleep -Milliseconds 500
    }
    throw "Installed Desktop did not expose Prompt Hub health within 45 seconds"
}

function Assert-Marker {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "User-data marker was removed: $Path"
    }
    if ((Get-Content -LiteralPath $Path -Raw -Encoding UTF8).Trim() -ne $testId) {
        throw "User-data marker was modified: $Path"
    }
}

function Remove-OwnedMarker {
    param([string]$Path)
    if ((Test-Path -LiteralPath $Path -PathType Leaf) -and
        (Get-Content -LiteralPath $Path -Raw -Encoding UTF8).Trim() -eq $testId) {
        Remove-Item -LiteralPath $Path -Force
    }
}

try {
    Write-ProgressState "preflight"
    foreach ($required in @($desktopSetup, $workerSetup)) {
        if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
            throw "Missing commercial installer: $required"
        }
    }
    New-Item -ItemType Directory -Path $desktopData, $workerData -Force | Out-Null
    [IO.File]::WriteAllText($desktopMarker, $testId, [Text.UTF8Encoding]::new($false))
    [IO.File]::WriteAllText($workerMarker, $testId, [Text.UTF8Encoding]::new($false))
    $workerConfig = Join-Path $workerData "worker-config.json"
    $workerConfigHashBefore = if (Test-Path -LiteralPath $workerConfig -PathType Leaf) {
        (Get-FileHash -LiteralPath $workerConfig -Algorithm SHA256).Hash.ToLowerInvariant()
    } else {
        $null
    }

    Stop-InstalledProductTree (Join-Path $desktopRoot "Soda Prompt Hub.exe")
    Stop-InstalledProductTree (Join-Path $workerRoot "Soda Compute Worker.exe")
    Write-ProgressState "install"
    Invoke-Setup $desktopSetup
    Invoke-Setup $workerSetup

    Write-ProgressState "runtime-probe"
    $desktopPython = Join-Path $desktopRoot "runtime\python\python.exe"
    $workerPython = Join-Path $workerRoot "runtime\python\python.exe"
    & $desktopPython -B -c "import fastapi,mcp,numpy,onnxruntime,PIL,uvicorn,win32api,prompt_hub"
    if ($LASTEXITCODE -ne 0) { throw "Desktop bundled Python import failed" }
    & $workerPython -c "import json,pathlib,urllib.request"
    if ($LASTEXITCODE -ne 0) { throw "Worker bundled Python import failed" }

    Write-ProgressState "launch"
    $desktopProcess = Start-Process -FilePath (Join-Path $desktopRoot "Soda Prompt Hub.exe") -PassThru
    $workerProcess = Start-Process -FilePath (Join-Path $workerRoot "Soda Compute Worker.exe") -PassThru
    $health = Read-Health
    if ([string]$health.version -ne $version) {
        throw "Installed Desktop reported unexpected version: $($health.version)"
    }
    if ([string]$health.release_channel -ne "stable") {
        throw "Installed Desktop reported unexpected release channel: $($health.release_channel)"
    }
    Start-Sleep -Seconds 2
    $bundledCore = @(Get-CimInstance Win32_Process | Where-Object {
        $_.Name -eq "python.exe" -and
        $_.ExecutablePath -and
        $_.ExecutablePath.StartsWith(
            (Join-Path $desktopRoot "runtime\python\"),
            [StringComparison]::OrdinalIgnoreCase)
    })
    if ($bundledCore.Count -eq 0) {
        throw "Prompt Hub Core is not using the bundled Python runtime"
    }
    if (Test-Path -LiteralPath (Join-Path $desktopRoot ".venv")) {
        throw "Installed Desktop generated an unexpected .venv"
    }

    Write-ProgressState "stop-products"
    Stop-InstalledProductTree (Join-Path $desktopRoot "Soda Prompt Hub.exe")
    Stop-InstalledProductTree (Join-Path $workerRoot "Soda Compute Worker.exe")
    $desktopProcess = $null
    $workerProcess = $null
    Write-ProgressState "uninstall-desktop"
    Invoke-Uninstall $desktopRoot
    Write-ProgressState "uninstall-worker"
    Invoke-Uninstall $workerRoot
    Start-Sleep -Seconds 2

    $uninstall = [ordered]@{
        desktop_program_removed = -not (Test-Path -LiteralPath $desktopRoot)
        worker_program_removed = -not (Test-Path -LiteralPath $workerRoot)
        desktop_data_preserved = Test-Path -LiteralPath $desktopMarker
        worker_data_preserved = Test-Path -LiteralPath $workerMarker
        worker_config_preserved = if ($null -eq $workerConfigHashBefore) {
            $true
        } else {
            (Test-Path -LiteralPath $workerConfig -PathType Leaf) -and
            ((Get-FileHash -LiteralPath $workerConfig -Algorithm SHA256).Hash.ToLowerInvariant() -eq
                $workerConfigHashBefore)
        }
    }
    if ($uninstall.Values -contains $false) {
        throw "Uninstall did not remove program files while preserving user data"
    }
    Assert-Marker $desktopMarker
    Assert-Marker $workerMarker

    Write-ProgressState "reinstall"
    Invoke-Setup $desktopSetup
    Invoke-Setup $workerSetup
    $reinstall = [ordered]@{
        desktop_exe = Test-Path -LiteralPath (Join-Path $desktopRoot "Soda Prompt Hub.exe")
        worker_exe = Test-Path -LiteralPath (Join-Path $workerRoot "Soda Compute Worker.exe")
        desktop_uninstaller = Test-Path -LiteralPath (Join-Path $desktopRoot "unins000.exe")
        worker_uninstaller = Test-Path -LiteralPath (Join-Path $workerRoot "unins000.exe")
        desktop_data_reused = Test-Path -LiteralPath $desktopMarker
        worker_data_reused = Test-Path -LiteralPath $workerMarker
    }
    if ($reinstall.Values -contains $false) {
        throw "Reinstall did not restore both products with preserved user data"
    }

    [ordered]@{
        status = "ok"
        version = [string]$health.version
        release_channel = [string]$health.release_channel
        bundled_core_python = $true
        generated_venv = $false
        uninstall = $uninstall
        reinstall = $reinstall
    } | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $StatusPath -Encoding UTF8
}
catch {
    [ordered]@{
        status = "error"
        message = $_.Exception.Message
        detail = ($_ | Out-String)
    } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $StatusPath -Encoding UTF8
    exit 1
}
finally {
    Remove-OwnedMarker $desktopMarker
    Remove-OwnedMarker $workerMarker
}
