param(
    [switch]$ForceRebuild
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$ProjectRootPath = $ProjectRoot.Path
Push-Location $ProjectRoot

try {
    $VenvDir = Join-Path $ProjectRootPath ".venv"
    $Python = Join-Path $VenvDir "Scripts\python.exe"

    function Resolve-ProjectPath {
        param([string]$RelativePath)
        return [System.IO.Path]::GetFullPath((Join-Path $ProjectRootPath $RelativePath))
    }

    function Invoke-NativeCommand {
        param([string]$Label, [scriptblock]$Command)

        Write-Host $Label
        & $Command
        if ($LASTEXITCODE -ne 0) {
            Write-Error "$Label failed."
        }
    }

    function Test-DemoAssetsComplete {
        $RequiredDemoAssets = @(
            "data\processed\chunks.jsonl",
            "data\index\tfidf_index.pkl",
            "data\processed\structured_chunks.jsonl",
            "data\index\structured_tfidf_index.pkl",
            "data\vector\chroma"
        )
        foreach ($Relative in $RequiredDemoAssets) {
            if (-not (Test-Path -LiteralPath (Resolve-ProjectPath $Relative))) {
                return $false
            }
        }
        return $true
    }

    if (-not (Test-Path -LiteralPath $VenvDir)) {
        Write-Host "Creating .venv..."
        $Created = $false
        $PyLauncher = Get-Command py -ErrorAction SilentlyContinue
        if ($PyLauncher) {
            & py -3.11 -m venv .venv
            if ($LASTEXITCODE -eq 0) {
                $Created = $true
            } else {
                Write-Host "py -3.11 was not available. Falling back to python -m venv .venv."
            }
        }
        if (-not $Created) {
            & python -m venv .venv
            if ($LASTEXITCODE -ne 0) {
                Write-Error "Could not create .venv with py -3.11 or python."
            }
        }
    } else {
        Write-Host "Using existing .venv."
    }

    if (-not (Test-Path -LiteralPath $Python)) {
        Write-Error "Virtualenv Python not found after setup: $Python"
    }

    Invoke-NativeCommand "Upgrading pip..." { & $Python -m pip install --upgrade pip }
    Invoke-NativeCommand "Installing ThesisAgent in editable runtime mode..." { & $Python -m pip install -e . }

    Write-Host "Checking native Python dependencies..."
    & $Python -c "import numpy; import numpy.random; import scipy; import sklearn; print('native deps ok')"
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "NumPy/SciPy native extension failed to load."
        Write-Host "Windows application control policy may have blocked a DLL."
        Write-Host "Try recreating the venv in a trusted folder, or adjust security policy."
        Write-Host "Then rerun .\scripts\setup_demo.ps1."
        Write-Error "Native dependency preflight failed. Demo asset build was not started."
    }

    if ($ForceRebuild) {
        Write-Host "ForceRebuild requested. Rebuilding demo runtime assets..."
        & (Join-Path $PSScriptRoot "prepare_demo_assets.ps1") -ForceRebuild
        if ($LASTEXITCODE -ne 0) {
            Write-Error "prepare_demo_assets.ps1 -ForceRebuild failed."
        }
    } elseif (Test-DemoAssetsComplete) {
        Write-Host "Demo runtime assets already exist. Skipping asset generation."
    } else {
        Write-Host "Demo runtime assets are incomplete. Preparing missing assets..."
        & (Join-Path $PSScriptRoot "prepare_demo_assets.ps1")
        if ($LASTEXITCODE -ne 0) {
            Write-Error "prepare_demo_assets.ps1 failed."
        }
    }

    $SnapshotManifest = Resolve-ProjectPath "data\metadata\kb_snapshot_manifest.json"
    if ($ForceRebuild -or -not (Test-Path -LiteralPath $SnapshotManifest)) {
        & (Join-Path $PSScriptRoot "write_demo_snapshot.ps1")
        if ($LASTEXITCODE -ne 0) {
            Write-Error "write_demo_snapshot.ps1 failed."
        }
    } else {
        Write-Host "Demo snapshot metadata already exists. Skipping snapshot write."
    }

    Write-Host ""
    Write-Host "Demo setup complete."
    Write-Host "Next step:"
    Write-Host "  .\scripts\configure_llm.ps1    # optional, for AI answers"
    Write-Host "  .\scripts\run_demo.ps1"
} finally {
    Pop-Location
}
