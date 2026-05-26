param()

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$ProjectRootPath = $ProjectRoot.Path
Push-Location $ProjectRoot

try {
    $Python = Join-Path $ProjectRootPath ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $Python)) {
        Write-Error "Virtualenv Python not found: $Python. Run .\scripts\setup_demo.ps1 first."
    }

    $LabEnvNames = @(
        "LAB_PDF_ROOT",
        "LAB_CATALOG_PATH",
        "LAB_CHUNKS_PATH",
        "LAB_INDEX_PATH",
        "LAB_STRUCTURED_CHUNKS_PATH",
        "LAB_STRUCTURED_INDEX_PATH",
        "LAB_VECTOR_PATH",
        "LAB_SNAPSHOT_MANIFEST_PATH",
        "LAB_SNAPSHOT_HISTORY_PATH",
        "LAB_SNAPSHOT_RECORD_DIR"
    )

    Remove-Item -LiteralPath "Env:KB_MODE" -ErrorAction SilentlyContinue
    foreach ($Name in $LabEnvNames) {
        Remove-Item -LiteralPath "Env:$Name" -ErrorAction SilentlyContinue
    }
    $env:KB_MODE = "demo"

    function Resolve-ProjectPath {
        param([string]$RelativePath)
        return [System.IO.Path]::GetFullPath((Join-Path $ProjectRootPath $RelativePath))
    }

    function Load-LlmProfile {
        $LlmProfilePath = Join-Path $ProjectRootPath ".runtime\llm\current_profile.json"
        if (-not (Test-Path -LiteralPath $LlmProfilePath)) {
            Write-Host "No LLM profile found. Run .\scripts\configure_llm.ps1 to enable AI answers."
            return
        }

        $LlmProfile = Get-Content -LiteralPath $LlmProfilePath -Raw | ConvertFrom-Json
        $env:LLM_PROFILE_NAME = [string]$LlmProfile.profile_name
        $env:LLM_DEFAULT_PROVIDER = [string]$LlmProfile.provider
        if ($LlmProfile.provider -eq "ollama") {
            $env:OLLAMA_BASE_URL = [string]$LlmProfile.ollama_base_url
            $env:OLLAMA_MODEL = [string]$LlmProfile.ollama_model
            $env:OLLAMA_TEMPERATURE = [string]$LlmProfile.temperature
            $env:OLLAMA_NUM_CTX = [string]$LlmProfile.num_ctx
            $env:OLLAMA_NUM_PREDICT = [string]$LlmProfile.num_predict
            Remove-Item -LiteralPath "Env:API_LLM_BASE_URL" -ErrorAction SilentlyContinue
            Remove-Item -LiteralPath "Env:API_LLM_MODEL" -ErrorAction SilentlyContinue
            Remove-Item -LiteralPath "Env:API_LLM_API_KEY" -ErrorAction SilentlyContinue
            Remove-Item -LiteralPath "Env:API_LLM_TEMPERATURE" -ErrorAction SilentlyContinue
            Remove-Item -LiteralPath "Env:API_LLM_MAX_TOKENS" -ErrorAction SilentlyContinue
        } elseif ($LlmProfile.provider -eq "api") {
            $env:API_LLM_BASE_URL = [string]$LlmProfile.api_base_url
            $env:API_LLM_MODEL = [string]$LlmProfile.api_model
            $env:API_LLM_API_KEY = [string]$LlmProfile.api_key
            $env:API_LLM_TEMPERATURE = [string]$LlmProfile.temperature
            $env:API_LLM_MAX_TOKENS = [string]$LlmProfile.max_tokens
            Remove-Item -LiteralPath "Env:OLLAMA_BASE_URL" -ErrorAction SilentlyContinue
            Remove-Item -LiteralPath "Env:OLLAMA_MODEL" -ErrorAction SilentlyContinue
            Remove-Item -LiteralPath "Env:OLLAMA_TEMPERATURE" -ErrorAction SilentlyContinue
            Remove-Item -LiteralPath "Env:OLLAMA_NUM_CTX" -ErrorAction SilentlyContinue
            Remove-Item -LiteralPath "Env:OLLAMA_NUM_PREDICT" -ErrorAction SilentlyContinue
        } else {
            Write-Warning "Unknown LLM provider in .runtime\llm\current_profile.json. Run .\scripts\configure_llm.ps1 again."
            return
        }
        Write-Host "Loaded LLM profile: $($LlmProfile.profile_name) ($($LlmProfile.provider))"
    }

    $RequiredDemoAssets = @(
        "data\processed\chunks.jsonl",
        "data\index\tfidf_index.pkl",
        "data\processed\structured_chunks.jsonl",
        "data\index\structured_tfidf_index.pkl",
        "data\vector\chroma"
    )

    $MissingAssets = @()
    foreach ($Relative in $RequiredDemoAssets) {
        if (-not (Test-Path -LiteralPath (Resolve-ProjectPath $Relative))) {
            $MissingAssets += $Relative
        }
    }

    if ($MissingAssets.Count -gt 0) {
        Write-Host "Missing demo assets:"
        foreach ($Relative in $MissingAssets) {
            Write-Host "  - $Relative"
        }
        Write-Host "Running setup_demo.ps1 to install dependencies, preflight native libraries, and prepare missing assets..."
        & (Join-Path $PSScriptRoot "setup_demo.ps1")
        if ($LASTEXITCODE -ne 0) {
            Write-Error "setup_demo.ps1 failed."
        }
    }

    $SnapshotManifest = Resolve-ProjectPath "data\metadata\kb_snapshot_manifest.json"
    if (-not (Test-Path -LiteralPath $SnapshotManifest)) {
        Write-Host "Demo snapshot metadata is missing. Writing snapshot metadata..."
        & (Join-Path $PSScriptRoot "write_demo_snapshot.ps1")
        if ($LASTEXITCODE -ne 0) {
            Write-Error "write_demo_snapshot.ps1 failed."
        }
    }

    Load-LlmProfile

    Write-Host "Starting ThesisAgent demo UI..."
    & $Python -m streamlit run app.py
} finally {
    Pop-Location
}
