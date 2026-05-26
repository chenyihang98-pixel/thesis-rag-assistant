param(
    [switch]$ForceRebuild,
    [switch]$SkipVector
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$ProjectRootPath = $ProjectRoot.Path
Push-Location $ProjectRoot

try {
    $Python = Join-Path $ProjectRootPath ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $Python)) {
        Write-Error "Missing .\.venv\Scripts\python.exe. Run .\scripts\setup_demo.ps1 first."
    }

    $DemoSampleDir = Join-Path $ProjectRootPath "data\samples"
    if (-not (Test-Path -LiteralPath $DemoSampleDir)) {
        Write-Error "Missing synthetic demo samples: data\samples"
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

    function Assert-DemoRuntimePath {
        param([string]$RelativePath)

        $Resolved = Resolve-ProjectPath $RelativePath
        if (-not $Resolved.StartsWith($ProjectRootPath, [System.StringComparison]::OrdinalIgnoreCase)) {
            Write-Error "Refusing to touch path outside the project: $Resolved"
        }

        $Protected = @(
            ".git",
            ".venv",
            "src",
            "tests",
            "docs",
            "scripts",
            "app.py",
            "pyproject.toml",
            "README.md",
            "AGENTS.md",
            "data\samples",
            "data\evaluation"
        )
        foreach ($Item in $Protected) {
            $ProtectedPath = Resolve-ProjectPath $Item
            if ($Resolved -eq $ProtectedPath -or $Resolved.StartsWith($ProtectedPath + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
                Write-Error "Refusing to touch protected project path: $Resolved"
            }
        }
        return $Resolved
    }

    function Invoke-PythonCommand {
        param([string[]]$Arguments)

        $CommandText = "python $($Arguments -join ' ')"
        Write-Host $CommandText
        & $Python @Arguments
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Python command failed: $CommandText"
        }
    }

    if ($ForceRebuild) {
        foreach ($Relative in @(
            "data\processed",
            "data\index",
            "data\vector",
            "data\metadata\kb_snapshot_manifest.json",
            "data\metadata\kb_snapshot_history.json",
            "data\metadata\kb_snapshots"
        )) {
            $Full = Assert-DemoRuntimePath $Relative
            if (Test-Path -LiteralPath $Full) {
                Write-Host "Removing demo runtime asset: $Relative"
                Remove-Item -LiteralPath $Full -Recurse -Force
            }
        }
    }

    New-Item -ItemType Directory -Force -Path (Resolve-ProjectPath "data\processed") | Out-Null
    New-Item -ItemType Directory -Force -Path (Resolve-ProjectPath "data\index") | Out-Null
    New-Item -ItemType Directory -Force -Path (Resolve-ProjectPath "data\metadata") | Out-Null

    $FixedChunks = "data\processed\chunks.jsonl"
    $FixedIndex = "data\index\tfidf_index.pkl"
    $StructuredChunks = "data\processed\structured_chunks.jsonl"
    $StructuredIndex = "data\index\structured_tfidf_index.pkl"
    $VectorDir = "data\vector\chroma"

    if (-not (Test-Path -LiteralPath (Resolve-ProjectPath $FixedChunks))) {
        Invoke-PythonCommand @(
            "-m", "thesis_agent.cli.ingest",
            "--input", "data/samples",
            "--input-type", "markdown",
            "--language", "ja",
            "--chunk-mode", "fixed",
            "--output", "data/processed/chunks.jsonl",
            "--metadata-output", "data/metadata/documents.jsonl"
        )
    } else {
        Write-Host "Fixed chunks already exist. Skipping fixed ingest."
    }

    if (-not (Test-Path -LiteralPath (Resolve-ProjectPath $FixedIndex))) {
        Invoke-PythonCommand @(
            "-m", "thesis_agent.cli.build_index",
            "--chunks", "data/processed/chunks.jsonl",
            "--output", "data/index/tfidf_index.pkl",
            "--language", "ja"
        )
    } else {
        Write-Host "Fixed TF-IDF index already exists. Skipping fixed build_index."
    }

    if (-not (Test-Path -LiteralPath (Resolve-ProjectPath $StructuredChunks))) {
        Invoke-PythonCommand @(
            "-m", "thesis_agent.cli.ingest",
            "--input", "data/samples",
            "--input-type", "markdown",
            "--language", "ja",
            "--chunk-mode", "structured",
            "--output", "data/processed/structured_chunks.jsonl",
            "--metadata-output", "data/metadata/structured_documents.jsonl"
        )
    } else {
        Write-Host "Structured chunks already exist. Skipping structured ingest."
    }

    if (-not (Test-Path -LiteralPath (Resolve-ProjectPath $StructuredIndex))) {
        Invoke-PythonCommand @(
            "-m", "thesis_agent.cli.build_index",
            "--chunks", "data/processed/structured_chunks.jsonl",
            "--output", "data/index/structured_tfidf_index.pkl",
            "--language", "ja"
        )
    } else {
        Write-Host "Structured TF-IDF index already exists. Skipping structured build_index."
    }

    if ($SkipVector) {
        Write-Host "SkipVector requested. Skipping demo vector index."
    } elseif (-not (Test-Path -LiteralPath (Resolve-ProjectPath $VectorDir))) {
        Invoke-PythonCommand @(
            "-m", "thesis_agent.cli.build_vector_index",
            "--chunks", "data/processed/structured_chunks.jsonl",
            "--persist-dir", "data/vector/chroma",
            "--collection", "thesis_agent_demo",
            "--embedding-provider", "hash",
            "--reset"
        )
    } else {
        Write-Host "Demo vector index already exists. Skipping vector build."
    }

    Write-Host "Demo runtime assets are ready."
} finally {
    Pop-Location
}
