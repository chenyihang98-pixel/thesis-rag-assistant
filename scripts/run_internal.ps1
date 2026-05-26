param([string]$Profile = "")

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..")).Path
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$InternalRuntimeDir = Join-Path $RepoRoot ".runtime\internal"
$ProfilesDir = Join-Path $InternalRuntimeDir "profiles"
$CurrentProfilePath = Join-Path $InternalRuntimeDir "current_profile.json"

if (-not (Test-Path -LiteralPath $Python)) {
    Write-Error "Virtualenv Python not found: $Python. Run .\scripts\setup_demo.ps1 first."
}

function Load-LlmProfile {
    $LlmProfilePath = Join-Path $RepoRoot ".runtime\llm\current_profile.json"
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

function Read-InternalProfileFile {
    param([string]$Path)

    $ProfileData = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    if ([string]::IsNullOrWhiteSpace([string]$ProfileData.profile_name)) {
        $ProfileData | Add-Member -NotePropertyName profile_name -NotePropertyValue ([System.IO.Path]::GetFileNameWithoutExtension($Path)) -Force
    }
    $ProfileData | Add-Member -NotePropertyName profile_path -NotePropertyValue $Path -Force
    return $ProfileData
}

function Get-InternalProfiles {
    if (-not (Test-Path -LiteralPath $ProfilesDir)) {
        return @()
    }
    $Items = @()
    foreach ($File in (Get-ChildItem -LiteralPath $ProfilesDir -Filter *.json -File | Sort-Object Name)) {
        $Items += Read-InternalProfileFile -Path $File.FullName
    }
    return @($Items)
}

function Get-CurrentProfileName {
    if (-not (Test-Path -LiteralPath $CurrentProfilePath)) {
        return ""
    }
    try {
        $Current = Get-Content -LiteralPath $CurrentProfilePath -Raw | ConvertFrom-Json
        return [string]$Current.profile_name
    } catch {
        return ""
    }
}

function Find-InternalProfile {
    param([object[]]$Profiles, [string]$Name)

    foreach ($Item in $Profiles) {
        $ProfileName = [string]$Item.profile_name
        $FileName = [System.IO.Path]::GetFileNameWithoutExtension([string]$Item.profile_path)
        if ($ProfileName.Equals($Name, [System.StringComparison]::OrdinalIgnoreCase) -or $FileName.Equals($Name, [System.StringComparison]::OrdinalIgnoreCase)) {
            return $Item
        }
    }
    return $null
}

function Select-InternalProfile {
    $AvailableProfiles = @(Get-InternalProfiles)
    $CurrentProfileName = Get-CurrentProfileName

    if ($AvailableProfiles.Count -eq 0) {
        if (Test-Path -LiteralPath $CurrentProfilePath) {
            Write-Warning "No profile files found under .runtime\internal\profiles. Using current_profile.json."
            return Read-InternalProfileFile -Path $CurrentProfilePath
        }
        Write-Host "No active internal profile found and no profiles exist."
        Write-Host "Run:"
        Write-Host "  .\scripts\configure_internal.ps1"
        exit 1
    }

    if (-not [string]::IsNullOrWhiteSpace($Profile)) {
        $Requested = Find-InternalProfile -Profiles $AvailableProfiles -Name $Profile
        if ($null -eq $Requested) {
            Write-Error "Internal profile not found: $Profile"
        }
        return $Requested
    }

    if ($AvailableProfiles.Count -eq 1) {
        return $AvailableProfiles[0]
    }

    Write-Host "Available internal profiles:"
    for ($Index = 0; $Index -lt $AvailableProfiles.Count; $Index++) {
        $DisplayIndex = $Index + 1
        Write-Host "[$DisplayIndex] $($AvailableProfiles[$Index].profile_name)"
    }
    if (-not [string]::IsNullOrWhiteSpace($CurrentProfileName)) {
        Write-Host "Current: $CurrentProfileName"
    } else {
        Write-Host "Current: none"
    }

    $Choice = Read-Host "Press Enter to use current profile, or enter number/name to switch"
    if ([string]::IsNullOrWhiteSpace($Choice)) {
        if ([string]::IsNullOrWhiteSpace($CurrentProfileName)) {
            Write-Error "No current profile is set. Enter a number/name or run .\scripts\configure_internal.ps1."
        }
        $CurrentMatch = Find-InternalProfile -Profiles $AvailableProfiles -Name $CurrentProfileName
        if ($null -eq $CurrentMatch) {
            Write-Error "Current profile is not available: $CurrentProfileName"
        }
        return $CurrentMatch
    }

    $SelectedNumber = 0
    if ([int]::TryParse($Choice, [ref]$SelectedNumber)) {
        if ($SelectedNumber -lt 1 -or $SelectedNumber -gt $AvailableProfiles.Count) {
            Write-Error "Profile number is out of range: $Choice"
        }
        return $AvailableProfiles[$SelectedNumber - 1]
    }

    $SelectedByName = Find-InternalProfile -Profiles $AvailableProfiles -Name $Choice.Trim()
    if ($null -eq $SelectedByName) {
        Write-Error "Internal profile not found: $Choice"
    }
    return $SelectedByName
}

function Write-CurrentInternalProfile {
    param($SelectedProfile)

    New-Item -ItemType Directory -Force -Path $InternalRuntimeDir | Out-Null
    $Json = $SelectedProfile | Select-Object * -ExcludeProperty profile_path | ConvertTo-Json -Depth 4
    Set-Content -LiteralPath $CurrentProfilePath -Value $Json -Encoding UTF8
}

function Set-InternalProfileEnvironment {
    param($SelectedProfile)

    Remove-Item -LiteralPath "Env:KB_MODE" -ErrorAction SilentlyContinue
    $env:KB_MODE = "internal"
    $env:LAB_PDF_ROOT = [string]$SelectedProfile.pdf_root
    $env:LAB_CATALOG_PATH = [string]$SelectedProfile.catalog_path
    $env:LAB_CHUNKS_PATH = [string]$SelectedProfile.chunks_path
    $env:LAB_INDEX_PATH = [string]$SelectedProfile.index_path
    $env:LAB_STRUCTURED_CHUNKS_PATH = [string]$SelectedProfile.structured_chunks_path
    $env:LAB_STRUCTURED_INDEX_PATH = [string]$SelectedProfile.structured_index_path
    $env:LAB_VECTOR_PATH = [string]$SelectedProfile.vector_path
    $env:LAB_SNAPSHOT_MANIFEST_PATH = [string]$SelectedProfile.snapshot_manifest_path
    $env:LAB_SNAPSHOT_HISTORY_PATH = [string]$SelectedProfile.snapshot_history_path
    $env:LAB_SNAPSHOT_RECORD_DIR = [string]$SelectedProfile.snapshot_record_dir
}

$SelectedProfile = Select-InternalProfile
if ($SelectedProfile.kb_mode -ne "internal") {
    Write-Error "Selected profile is not an internal profile: $($SelectedProfile.profile_name)"
}

Write-CurrentInternalProfile -SelectedProfile $SelectedProfile
Set-InternalProfileEnvironment -SelectedProfile $SelectedProfile

foreach ($Name in @("LAB_PDF_ROOT", "LAB_CATALOG_PATH", "LAB_CHUNKS_PATH", "LAB_INDEX_PATH")) {
    $Value = [Environment]::GetEnvironmentVariable($Name, "Process")
    if ([string]::IsNullOrWhiteSpace($Value)) {
        Write-Error "$Name is required in the selected internal profile. Run .\scripts\configure_internal.ps1 for profile '$($SelectedProfile.profile_name)'."
    }
    if (-not (Test-Path -LiteralPath $Value)) {
        Write-Error "$Name does not exist: $Value. Run .\scripts\configure_internal.ps1 for profile '$($SelectedProfile.profile_name)'."
    }
}

foreach ($Name in @("LAB_STRUCTURED_CHUNKS_PATH", "LAB_STRUCTURED_INDEX_PATH")) {
    $Value = [Environment]::GetEnvironmentVariable($Name, "Process")
    if (-not [string]::IsNullOrWhiteSpace($Value) -and -not (Test-Path -LiteralPath $Value)) {
        Write-Warning "$Name is missing: $Value. The UI can fall back to the standard chunks/index."
    }
}

$VectorPath = [Environment]::GetEnvironmentVariable("LAB_VECTOR_PATH", "Process")
if (-not [string]::IsNullOrWhiteSpace($VectorPath) -and -not (Test-Path -LiteralPath $VectorPath)) {
    Write-Warning "LAB_VECTOR_PATH is missing: $VectorPath. Hybrid/vector retrieval may fall back depending on UI settings."
}

Load-LlmProfile

Write-Host "Starting ThesisAgent internal UI with active profile: $($SelectedProfile.profile_name)"
& $Python -m streamlit run app.py
