param()

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$ProjectRootPath = $ProjectRoot.Path
Push-Location $ProjectRoot

try {
    $Python = Join-Path $ProjectRootPath ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $Python)) {
        Write-Host "Virtualenv Python was not found."
        Write-Host "Run first:"
        Write-Host "  .\scripts\setup_demo.ps1"
        exit 1
    }

    function Read-HostWithDefault {
        param([string]$Prompt, [string]$Default)

        $Value = Read-Host "$Prompt [$Default]"
        if ([string]::IsNullOrWhiteSpace($Value)) {
            return $Default
        }
        return $Value.Trim()
    }

    function Read-DecimalWithDefault {
        param([string]$Prompt, [double]$Default)

        $Value = Read-Host "$Prompt [$Default]"
        if ([string]::IsNullOrWhiteSpace($Value)) {
            return $Default
        }
        return [double]$Value
    }

    function Read-IntWithDefault {
        param([string]$Prompt, [int]$Default)

        $Value = Read-Host "$Prompt [$Default]"
        if ([string]::IsNullOrWhiteSpace($Value)) {
            return $Default
        }
        return [int]$Value
    }

    function ConvertTo-PlainText {
        param([System.Security.SecureString]$SecureValue)

        if ($null -eq $SecureValue) {
            return ""
        }
        $Bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureValue)
        try {
            return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Bstr)
        } finally {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Bstr)
        }
    }

    function ConvertTo-PowerShellSingleQuoted {
        param([string]$Value)

        return "'" + ($Value -as [string]).Replace("'", "''") + "'"
    }

    function Test-OllamaTags {
        param([string]$BaseUrl)

        $Endpoint = $BaseUrl.TrimEnd("/") + "/api/tags"
        try {
            $Response = Invoke-RestMethod -Uri $Endpoint -Method Get -TimeoutSec 5
            $Models = @()
            foreach ($Model in @($Response.models)) {
                if ($Model.name) {
                    $Models += [string]$Model.name
                }
            }
            if ($Models.Count -gt 0) {
                Write-Host "Installed Ollama models:"
                foreach ($Name in $Models) {
                    Write-Host "  - $Name"
                }
            } else {
                Write-Host "Ollama /api/tags is reachable, but no installed models were reported."
            }
        } catch {
            Write-Warning "Could not reach Ollama /api/tags. You can still save the profile and start Ollama later."
        }
    }

    Write-Host ""
    Write-Host "Configure a local LLM profile for ThesisAgent."
    Write-Host "This wizard stores settings only in ignored local files."
    Write-Host ""

    $ProfileName = Read-HostWithDefault "Profile name" "local_llm"
    if ($ProfileName -notmatch "^[A-Za-z0-9_.-]+$" -or $ProfileName -in @(".", "..")) {
        Write-Error "Profile name may contain only letters, numbers, dot, underscore, and dash."
    }

    $Provider = (Read-HostWithDefault "Provider (ollama/api)" "ollama").ToLowerInvariant()
    if ($Provider -notin @("ollama", "api")) {
        Write-Error "Provider must be ollama or api."
    }

    $ProfileData = [ordered]@{
        profile_name = $ProfileName
        provider = $Provider
    }

    if ($Provider -eq "ollama") {
        $OllamaBaseUrl = Read-HostWithDefault "Ollama Base URL" "http://localhost:11434"
        $CheckTags = Read-HostWithDefault "Check Ollama /api/tags now? (Y/n)" "Y"
        if ($CheckTags -notin @("n", "N", "no", "NO", "No")) {
            Test-OllamaTags -BaseUrl $OllamaBaseUrl
        }
        $OllamaModel = Read-Host "Ollama Model"
        if ([string]::IsNullOrWhiteSpace($OllamaModel)) {
            Write-Error "Ollama Model is required for an Ollama profile."
        }
        $Temperature = Read-DecimalWithDefault "Temperature" 0.2
        $NumCtx = Read-IntWithDefault "num_ctx" 4096
        $NumPredict = Read-IntWithDefault "num_predict" 1200
        $ProfileData["ollama_base_url"] = $OllamaBaseUrl
        $ProfileData["ollama_model"] = $OllamaModel.Trim()
        $ProfileData["temperature"] = $Temperature
        $ProfileData["num_ctx"] = $NumCtx
        $ProfileData["num_predict"] = $NumPredict
    } else {
        $ApiBaseUrl = Read-Host "API Base URL"
        $ApiModel = Read-Host "API Model"
        $ApiKeySecure = Read-Host "API Key" -AsSecureString
        $ApiKey = ConvertTo-PlainText $ApiKeySecure
        if ([string]::IsNullOrWhiteSpace($ApiBaseUrl) -or [string]::IsNullOrWhiteSpace($ApiModel) -or [string]::IsNullOrWhiteSpace($ApiKey)) {
            Write-Error "API Base URL, API Model, and API Key are required for an API profile."
        }
        $Temperature = Read-DecimalWithDefault "Temperature" 0.2
        $MaxTokens = Read-IntWithDefault "max_tokens" 2000
        $ProfileData["api_base_url"] = $ApiBaseUrl.Trim()
        $ProfileData["api_model"] = $ApiModel.Trim()
        $ProfileData["api_key"] = $ApiKey
        $ProfileData["temperature"] = $Temperature
        $ProfileData["max_tokens"] = $MaxTokens
    }

    $RuntimeDir = Join-Path $ProjectRootPath ".runtime\llm"
    $ProfilesDir = Join-Path $RuntimeDir "profiles"
    $ProfilePath = Join-Path $ProfilesDir "$ProfileName.json"

    $CreatedAt = [DateTime]::UtcNow.ToString("o")
    if (Test-Path -LiteralPath $ProfilePath) {
        try {
            $ExistingProfile = Get-Content -LiteralPath $ProfilePath -Raw | ConvertFrom-Json
            if (-not [string]::IsNullOrWhiteSpace($ExistingProfile.created_at)) {
                $CreatedAt = [string]$ExistingProfile.created_at
            }
        } catch {
            Write-Warning "Existing profile could not be read; created_at will be reset."
        }
    }
    $ProfileData["created_at"] = $CreatedAt
    $ProfileData["updated_at"] = [DateTime]::UtcNow.ToString("o")

    Write-Host ""
    Write-Host "LLM profile summary:"
    Write-Host "  profile_name: $ProfileName"
    Write-Host "  provider: $Provider"
    if ($Provider -eq "ollama") {
        Write-Host "  ollama_base_url: $($ProfileData["ollama_base_url"])"
        Write-Host "  ollama_model: $($ProfileData["ollama_model"])"
        Write-Host "  temperature: $($ProfileData["temperature"])"
        Write-Host "  num_ctx: $($ProfileData["num_ctx"])"
        Write-Host "  num_predict: $($ProfileData["num_predict"])"
    } else {
        Write-Host "  api_base_url: $($ProfileData["api_base_url"])"
        Write-Host "  api_model: $($ProfileData["api_model"])"
        Write-Host "  api_key: ****"
        Write-Host "  temperature: $($ProfileData["temperature"])"
        Write-Host "  max_tokens: $($ProfileData["max_tokens"])"
    }

    $Confirm = Read-Host "Type YES to save this LLM profile"
    if ($Confirm -ne "YES") {
        Write-Host "Cancelled. No LLM profile was written."
        exit 1
    }

    New-Item -ItemType Directory -Force -Path $ProfilesDir | Out-Null
    $ProfileJson = $ProfileData | ConvertTo-Json -Depth 4
    Set-Content -LiteralPath $ProfilePath -Value $ProfileJson -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $RuntimeDir "current_profile.json") -Value $ProfileJson -Encoding UTF8

    $LocalEnvPath = Join-Path $PSScriptRoot "set_llm_env.local.ps1"
    $EnvLines = @(
        "# Generated by scripts/configure_llm.ps1.",
        "# This local file is ignored by Git.",
        "`$env:LLM_PROFILE_NAME=" + (ConvertTo-PowerShellSingleQuoted $ProfileName),
        "`$env:LLM_DEFAULT_PROVIDER=" + (ConvertTo-PowerShellSingleQuoted $Provider)
    )
    if ($Provider -eq "ollama") {
        $EnvLines += @(
            "`$env:OLLAMA_BASE_URL=" + (ConvertTo-PowerShellSingleQuoted $ProfileData["ollama_base_url"]),
            "`$env:OLLAMA_MODEL=" + (ConvertTo-PowerShellSingleQuoted $ProfileData["ollama_model"]),
            "`$env:OLLAMA_TEMPERATURE=" + (ConvertTo-PowerShellSingleQuoted ([string]$ProfileData["temperature"])),
            "`$env:OLLAMA_NUM_CTX=" + (ConvertTo-PowerShellSingleQuoted ([string]$ProfileData["num_ctx"])),
            "`$env:OLLAMA_NUM_PREDICT=" + (ConvertTo-PowerShellSingleQuoted ([string]$ProfileData["num_predict"]))
        )
    } else {
        $EnvLines += @(
            "`$env:API_LLM_BASE_URL=" + (ConvertTo-PowerShellSingleQuoted $ProfileData["api_base_url"]),
            "`$env:API_LLM_MODEL=" + (ConvertTo-PowerShellSingleQuoted $ProfileData["api_model"]),
            "`$env:API_LLM_API_KEY=" + (ConvertTo-PowerShellSingleQuoted $ProfileData["api_key"]),
            "`$env:API_LLM_TEMPERATURE=" + (ConvertTo-PowerShellSingleQuoted ([string]$ProfileData["temperature"])),
            "`$env:API_LLM_MAX_TOKENS=" + (ConvertTo-PowerShellSingleQuoted ([string]$ProfileData["max_tokens"]))
        )
    }
    Set-Content -LiteralPath $LocalEnvPath -Value $EnvLines -Encoding UTF8

    Write-Host ""
    Write-Host "LLM profile is ready: $ProfileName"
    Write-Host "Next steps:"
    Write-Host "  .\scripts\run_demo.ps1"
    Write-Host "  .\scripts\run_internal.ps1"
} finally {
    Pop-Location
}
