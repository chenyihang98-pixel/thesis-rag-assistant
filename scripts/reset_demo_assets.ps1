param()

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..")).Path
Set-Location $RepoRoot

function Resolve-ProjectPath {
    param([string]$RelativePath)
    return [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $RelativePath))
}

function Assert-DemoResetCandidate {
    param([string]$Path)
    $Resolved = [System.IO.Path]::GetFullPath($Path)
    if (-not $Resolved.StartsWith($RepoRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        Write-Error "Refusing outside path: $Resolved"
    }
    foreach ($Protected in @(".git", ".venv", "src", "tests", "docs", "scripts", "app.py", "pyproject.toml", "README.md", "AGENTS.md", "data\samples", "data\evaluation")) {
        $ProtectedPath = Resolve-ProjectPath $Protected
        if ($Resolved -eq $ProtectedPath -or $Resolved.StartsWith($ProtectedPath + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
            Write-Error "Refusing protected path: $Resolved"
        }
    }
    foreach ($EnvName in @("LAB_PDF_ROOT", "LAB_CATALOG_PATH", "LAB_CHUNKS_PATH", "LAB_INDEX_PATH", "LAB_STRUCTURED_CHUNKS_PATH", "LAB_STRUCTURED_INDEX_PATH", "LAB_VECTOR_PATH", "LAB_SNAPSHOT_MANIFEST_PATH", "LAB_SNAPSHOT_HISTORY_PATH", "LAB_SNAPSHOT_RECORD_DIR")) {
        $EnvValue = [Environment]::GetEnvironmentVariable($EnvName)
        if (-not [string]::IsNullOrWhiteSpace($EnvValue)) {
            $EnvPath = [System.IO.Path]::GetFullPath($EnvValue)
            if ($Resolved -eq $EnvPath -or $Resolved.StartsWith($EnvPath + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
                Write-Error "Refusing LAB_* path: $Resolved"
            }
        }
    }
    return $Resolved
}

$Candidates = @()
foreach ($Relative in @(
    "data\processed",
    "data\index",
    "data\vector",
    "data\chroma",
    "chroma_db",
    "data\metadata\kb_snapshot_manifest.json",
    "data\metadata\kb_snapshot_history.json",
    "data\metadata\kb_snapshots"
)) {
    $Full = Assert-DemoResetCandidate (Resolve-ProjectPath $Relative)
    if (Test-Path -LiteralPath $Full) {
        $Candidates += $Full
    }
}

if (-not $Candidates) {
    Write-Host "No demo assets found."
    return
}
Write-Host "Demo reset candidates:"
foreach ($Candidate in ($Candidates | Sort-Object -Unique)) {
    Write-Host "  $Candidate"
}
$Answer = Read-Host "Type RESET_DEMO to delete only the listed demo assets"
if ($Answer -ne "RESET_DEMO") {
    Write-Host "Demo reset cancelled."
    return
}
foreach ($Candidate in ($Candidates | Sort-Object -Unique)) {
    Remove-Item -LiteralPath $Candidate -Recurse -Force
}
Write-Host "Demo assets reset complete."
