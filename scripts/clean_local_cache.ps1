param()

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..")).Path
Set-Location $RepoRoot

function Resolve-ProjectPath {
    param([string]$RelativePath)
    return [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $RelativePath))
}

function Assert-CacheCandidate {
    param([string]$Path)
    $Resolved = [System.IO.Path]::GetFullPath($Path)
    if (-not $Resolved.StartsWith($RepoRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        Write-Error "Refusing outside path: $Resolved"
    }
    foreach ($Forbidden in @(".git", ".venv", "docs", "scripts", "data\samples", "data\evaluation", "data\processed", "data\index", "data\vector")) {
        $ForbiddenPath = Resolve-ProjectPath $Forbidden
        if ($Resolved -eq $ForbiddenPath -or $Resolved.StartsWith($ForbiddenPath + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
            Write-Error "Refusing protected path: $Resolved"
        }
    }
    return $Resolved
}

$Candidates = @()
foreach ($Relative in @("outputs", ".tmp", ".pytest_cache")) {
    $Full = Assert-CacheCandidate (Resolve-ProjectPath $Relative)
    if (Test-Path -LiteralPath $Full) {
        $Candidates += $Full
    }
}
foreach ($Root in @("src", "tests")) {
    $RootPath = Resolve-ProjectPath $Root
    if (Test-Path -LiteralPath $RootPath) {
        Get-ChildItem -LiteralPath $RootPath -Directory -Recurse -Force -Filter "__pycache__" -ErrorAction SilentlyContinue | ForEach-Object {
            $Candidates += (Assert-CacheCandidate $_.FullName)
        }
        Get-ChildItem -LiteralPath $RootPath -File -Recurse -Force -Include *.pyc,*.pyo -ErrorAction SilentlyContinue | ForEach-Object {
            $Candidates += (Assert-CacheCandidate $_.FullName)
        }
    }
}

$Candidates = $Candidates | Sort-Object -Unique
if (-not $Candidates) {
    Write-Host "No local cache files found."
    return
}
Write-Host "Cache cleanup candidates:"
foreach ($Candidate in $Candidates) {
    Write-Host "  $Candidate"
}
foreach ($Candidate in $Candidates) {
    Remove-Item -LiteralPath $Candidate -Recurse -Force -ErrorAction SilentlyContinue
}
Write-Host "Local cache cleanup complete."
