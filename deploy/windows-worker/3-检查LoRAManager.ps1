param(
    [string]$PluginPath = "D:\ComfyUI\custom_nodes\comfyui-lora-manager",
    [string]$LoraPath = "D:\ComfyUI\models\loras",
    [string]$BridgeRoot = "D:\PromptHub-Bridge\prompt-hub"
)

$ErrorActionPreference = "Stop"
$diagnosticsRoot = Join-Path $BridgeRoot "diagnostics"
$outputPath = Join-Path $diagnosticsRoot "lora-manager-inspection.json"
New-Item -ItemType Directory -Path $diagnosticsRoot -Force | Out-Null

function Get-RelativePath {
    param([string]$Root, [string]$Path)

    $normalizedRoot = $Root.TrimEnd("\") + "\"
    if ($Path.StartsWith($normalizedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $Path.Substring($normalizedRoot.Length)
    }
    return $Path
}

function Invoke-LocalJson {
    param([string]$Uri)

    try {
        return Invoke-RestMethod -Uri $Uri -Method Get -TimeoutSec 15
    }
    catch {
        return [ordered]@{ error = $_.Exception.Message }
    }
}

$pluginExists = Test-Path -LiteralPath $PluginPath -PathType Container
$loraExists = Test-Path -LiteralPath $LoraPath -PathType Container

$topLevel = @()
$sourceMatches = @()
$dataFiles = @()
$gitHead = ""
$gitRemote = ""

if ($pluginExists) {
    $topLevel = Get-ChildItem -LiteralPath $PluginPath -Force |
        Sort-Object Name |
        Select-Object Name, Length, Mode, LastWriteTime

    $inspectableFiles = Get-ChildItem -LiteralPath $PluginPath -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Extension -in @(".py", ".js", ".ts", ".tsx", ".json", ".toml", ".yaml", ".yml") }

    $patterns = @(
        "PromptServer.instance.routes",
        "routes.get",
        "routes.post",
        "routes.put",
        "routes.delete",
        "lora-manager",
        "lora_manager",
        "/loras",
        "/lora",
        "sqlite",
        "metadata",
        "preview"
    )
    $sourceMatches = $inspectableFiles |
        Select-String -SimpleMatch -Pattern $patterns -ErrorAction SilentlyContinue |
        Select-Object -First 500 |
        ForEach-Object {
            [ordered]@{
                path = Get-RelativePath -Root $PluginPath -Path $_.Path
                line = $_.LineNumber
                text = $_.Line.Trim()
            }
        }

    $dataFiles = Get-ChildItem -LiteralPath $PluginPath -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Extension -in @(".db", ".sqlite", ".sqlite3", ".json") } |
        Sort-Object FullName |
        Select-Object -First 300 |
        ForEach-Object {
            [ordered]@{
                path = Get-RelativePath -Root $PluginPath -Path $_.FullName
                size_bytes = $_.Length
                modified_at = $_.LastWriteTime.ToString("o")
            }
        }

    if (Test-Path -LiteralPath (Join-Path $PluginPath ".git")) {
        try { $gitHead = (& git -C $PluginPath rev-parse HEAD 2>$null).Trim() } catch { $gitHead = "" }
        try { $gitRemote = (& git -C $PluginPath remote get-url origin 2>$null).Trim() } catch { $gitRemote = "" }
    }
}

$loraFiles = @()
$previewFiles = @()
if ($loraExists) {
    $loraFiles = Get-ChildItem -LiteralPath $LoraPath -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Extension -in @(".safetensors", ".ckpt", ".pt", ".pth") }
    $previewFiles = Get-ChildItem -LiteralPath $LoraPath -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Extension -in @(".png", ".jpg", ".jpeg", ".webp", ".gif") }
}

$report = [ordered]@{
    format = "soda-lora-manager-inspection-v1"
    inspected_at = (Get-Date).ToUniversalTime().ToString("o")
    hostname = $env:COMPUTERNAME
    plugin = [ordered]@{
        path = $PluginPath
        exists = $pluginExists
        git_head = $gitHead
        git_remote = $gitRemote
        top_level = @($topLevel)
        data_files = @($dataFiles)
        source_matches = @($sourceMatches)
    }
    lora_directory = [ordered]@{
        path = $LoraPath
        exists = $loraExists
        model_count = @($loraFiles).Count
        preview_count = @($previewFiles).Count
        model_samples = @($loraFiles | Sort-Object FullName | Select-Object -First 100 | ForEach-Object {
            [ordered]@{
                relative_path = Get-RelativePath -Root $LoraPath -Path $_.FullName
                size_bytes = $_.Length
                modified_at = $_.LastWriteTime.ToString("o")
            }
        })
        preview_samples = @($previewFiles | Sort-Object FullName | Select-Object -First 100 | ForEach-Object {
            Get-RelativePath -Root $LoraPath -Path $_.FullName
        })
    }
    comfyui = [ordered]@{
        system_stats = Invoke-LocalJson -Uri "http://127.0.0.1:8188/system_stats"
        lora_loader = Invoke-LocalJson -Uri "http://127.0.0.1:8188/object_info/LoraLoader"
        extensions = Invoke-LocalJson -Uri "http://127.0.0.1:8188/extensions"
    }
}

$report | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $outputPath -Encoding UTF8
Write-Host "[OK] LoRA Manager inspection written to $outputPath"
