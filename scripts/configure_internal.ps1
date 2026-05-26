param()

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..")).Path
Set-Location $RepoRoot

$VenvDir = Join-Path $RepoRoot ".venv"
$Python = Join-Path $VenvDir "Scripts\python.exe"
$RuntimeDir = Join-Path $RepoRoot ".runtime\internal"
$ProfilesDir = Join-Path $RuntimeDir "profiles"
$CorporaDir = Join-Path $RuntimeDir "corpora"

function Invoke-NativeChecked {
    param([string]$Label, [scriptblock]$Command)

    Write-Host $Label
    & $Command
    if ($LASTEXITCODE -ne 0) {
        Write-Error "$Label failed."
    }
}

function New-ProjectVenv {
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
    }
    if (-not (Test-Path -LiteralPath $Python)) {
        Write-Error "Virtualenv Python not found: $Python"
    }
    Invoke-NativeChecked "Upgrading pip..." { & $Python -m pip install --upgrade pip }
    Invoke-NativeChecked "Installing ThesisAgent in editable runtime mode..." { & $Python -m pip install -e . }
}

if (-not (Test-Path -LiteralPath $Python)) {
    Write-Host "Virtualenv Python was not found."
    Write-Host "Recommended first command:"
    Write-Host "  .\scripts\setup_demo.ps1"
    $Choice = Read-Host "Type SETUP to run setup_demo.ps1, CREATE to create only the environment now, or press Enter to stop"
    if ($Choice -eq "SETUP") {
        & (Join-Path $ScriptDir "setup_demo.ps1")
        if ($LASTEXITCODE -ne 0) {
            Write-Error "setup_demo.ps1 failed."
        }
    } elseif ($Choice -eq "CREATE") {
        New-ProjectVenv
    } else {
        Write-Host "Stopped. Run .\scripts\setup_demo.ps1 before configuring internal mode."
        exit 1
    }
}

if (-not (Test-Path -LiteralPath $Python)) {
    Write-Error "Virtualenv Python not found after setup: $Python"
}

function Read-HostWithDefault {
    param([string]$Prompt, [string]$Default)

    $Value = Read-Host "$Prompt [$Default]"
    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $Default
    }
    return $Value.Trim()
}

function Normalize-PathInput {
    param([string]$Value, [switch]$MustExist, [string]$Label)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        Write-Error "$Label is required."
    }
    $Trimmed = $Value.Trim().Trim('"')
    $Expanded = [Environment]::ExpandEnvironmentVariables($Trimmed)
    if ($MustExist) {
        return (Resolve-Path -LiteralPath $Expanded).Path
    }
    return [System.IO.Path]::GetFullPath($Expanded)
}

function Test-PathInside {
    param([string]$ChildPath, [string]$ParentPath)

    $ChildFull = [System.IO.Path]::GetFullPath($ChildPath).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
    $ParentFull = [System.IO.Path]::GetFullPath($ParentPath).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
    return $ChildFull.Equals($ParentFull, [System.StringComparison]::OrdinalIgnoreCase) -or $ChildFull.StartsWith($ParentFull + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)
}

function Invoke-PythonCommand {
    param([string[]]$Arguments, [switch]$AllowFailure)

    Write-Host "python $($Arguments -join ' ')"
    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) {
        if ($AllowFailure) {
            Write-Warning "Python command failed but is optional: $($Arguments -join ' ')"
            return $false
        }
        Write-Error "Python command failed: $($Arguments -join ' ')"
    }
    return $true
}

function ConvertTo-PowerShellSingleQuoted {
    param([string]$Value)

    return "'" + $Value.Replace("'", "''") + "'"
}

function Assert-ProfileName {
    param([string]$ProfileName)

    if ([string]::IsNullOrWhiteSpace($ProfileName)) {
        Write-Error "Profile name cannot be empty."
    }
    if ($ProfileName -notmatch "^[A-Za-z0-9_-]+$") {
        Write-Error "Profile name may contain only letters, numbers, dash, and underscore."
    }
    if ($ProfileName -match "[\\/]" -or $ProfileName -in @(".", "..")) {
        Write-Error "Profile name must not contain path separators."
    }
}

function Get-ProfilePath {
    param([string]$ProfileName)
    return Join-Path $ProfilesDir "$ProfileName.json"
}

function Get-ProjectLocalWorkDir {
    param([string]$ProfileName)
    return Join-Path $CorporaDir $ProfileName
}

function Resolve-ProfileNameChoice {
    while ($true) {
        $Name = Read-HostWithDefault "Profile name" "internal"
        Assert-ProfileName $Name
        $Path = Get-ProfilePath $Name
        if (-not (Test-Path -LiteralPath $Path)) {
            return @{ name = $Name; path = $Path; mode = "new"; existing_profile = $null }
        }

        Write-Host "Profile already exists."
        Write-Host "Options:"
        Write-Host "  - reuse"
        Write-Host "  - overwrite"
        Write-Host "  - choose-another"
        Write-Host "  - cancel"
        $Choice = Read-HostWithDefault "Choose option" "choose-another"
        if ($Choice -eq "reuse") {
            $Existing = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
            return @{ name = $Name; path = $Path; mode = "reuse-profile"; existing_profile = $Existing }
        }
        if ($Choice -eq "overwrite") {
            $ConfirmOverwrite = Read-Host "Type YES to overwrite existing profile metadata"
            if ($ConfirmOverwrite -ne "YES") {
                Write-Host "Cancelled. Existing profile was not overwritten."
                exit 1
            }
            return @{ name = $Name; path = $Path; mode = "overwrite"; existing_profile = $null }
        }
        if ($Choice -eq "choose-another") {
            continue
        }
        if ($Choice -eq "cancel") {
            Write-Host "Cancelled. No profile was written."
            exit 1
        }
        Write-Host "Unknown option. Choose reuse, overwrite, choose-another, or cancel."
    }
}

function Assert-PdfRoot {
    param([string]$PdfRoot)

    if (-not (Test-Path -LiteralPath $PdfRoot)) {
        Write-Error "PDF root does not exist: $PdfRoot"
    }
    $Item = Get-Item -LiteralPath $PdfRoot
    if (-not $Item.PSIsContainer) {
        Write-Error "PDF root must be a directory: $PdfRoot"
    }
    $FirstPdf = Get-ChildItem -LiteralPath $PdfRoot -Filter *.pdf -File -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $FirstPdf) {
        Write-Error "PDF root must contain at least one .pdf file. The wizard checks filenames only and does not read PDF content."
    }
}

function Resolve-WorkDir {
    param([string]$ProfileName, [string]$PdfRoot)

    Write-Host "Work dir mode:"
    Write-Host "  - project-local runtime workspace"
    Write-Host "  - custom work dir"
    $ModeChoice = Read-HostWithDefault "Work dir mode" "project-local runtime workspace"
    if ($ModeChoice -in @("custom", "custom work dir")) {
        $CustomInput = Read-Host "Custom work dir (advanced)"
        $CustomWorkDir = Normalize-PathInput -Value $CustomInput -Label "Work dir"
        return @{ mode = "custom"; path = $CustomWorkDir }
    }
    $ProjectLocalWorkDir = Get-ProjectLocalWorkDir -ProfileName $ProfileName
    return @{ mode = "project_local"; path = $ProjectLocalWorkDir }
}

function Assert-WorkDir {
    param([string]$WorkDir, [string]$PdfRoot, [string]$WorkDirMode)

    if ((Test-Path -LiteralPath $WorkDir) -and -not (Get-Item -LiteralPath $WorkDir).PSIsContainer) {
        Write-Error "Work dir must be a directory if it already exists: $WorkDir"
    }
    $WorkFull = [System.IO.Path]::GetFullPath($WorkDir).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
    $PdfFull = [System.IO.Path]::GetFullPath($PdfRoot).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
    if ($WorkFull.Equals($PdfFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        Write-Error "Work dir must not be the same directory as PDF root."
    }
    if ($WorkDirMode -eq "custom" -and (Test-PathInside -ChildPath $WorkFull -ParentPath $RepoRoot)) {
        Write-Error "Custom work dir should be outside the project root. Use the default project-local runtime workspace or choose an external work directory."
    }
}

function Get-AssetStatus {
    param([hashtable]$Paths)

    return [ordered]@{
        catalog = Test-Path -LiteralPath $Paths.CatalogPath
        chunks = Test-Path -LiteralPath $Paths.ChunksPath
        index = Test-Path -LiteralPath $Paths.IndexPath
        structured_chunks = Test-Path -LiteralPath $Paths.StructuredChunksPath
        structured_index = Test-Path -LiteralPath $Paths.StructuredIndexPath
        vector = Test-Path -LiteralPath $Paths.VectorPath
        snapshot_manifest = Test-Path -LiteralPath $Paths.SnapshotManifestPath
        snapshot_history = Test-Path -LiteralPath $Paths.SnapshotHistoryPath
        snapshot_records = Test-Path -LiteralPath $Paths.SnapshotRecordDir
    }
}

function Get-ExistingAssetNames {
    param([System.Collections.IDictionary]$Status)

    $Names = @()
    foreach ($Key in $Status.Keys) {
        if ($Status[$Key]) {
            $Names += $Key
        }
    }
    return $Names
}

function Select-WorkspaceBuildMode {
    param([System.Collections.IDictionary]$AssetStatus)

    $ExistingCoreAssets = @("catalog", "chunks", "index", "vector") | Where-Object { $AssetStatus[$_] }
    if ($ExistingCoreAssets.Count -eq 0) {
        return "build-missing"
    }

    Write-Host "Existing corpus workspace detected."
    Write-Host "Options:"
    Write-Host "  - reuse existing assets"
    Write-Host "  - build missing assets only"
    Write-Host "  - force rebuild"
    Write-Host "  - cancel"
    $Choice = Read-HostWithDefault "Choose option" "build missing assets only"
    if ($Choice -in @("reuse", "reuse existing assets")) {
        if (-not ($AssetStatus.catalog -and $AssetStatus.chunks -and $AssetStatus.index)) {
            Write-Error "reuse existing assets requires catalog.csv, processed\chunks.jsonl, and processed\tfidf_index.pkl. Choose build missing assets only instead."
        }
        return "reuse"
    }
    if ($Choice -in @("build", "build missing", "build missing assets only")) {
        return "build-missing"
    }
    if ($Choice -in @("force", "force rebuild")) {
        $ConfirmForce = Read-Host "Type YES to force rebuild generated assets in the profile workspace"
        if ($ConfirmForce -ne "YES") {
            Write-Host "Cancelled. No assets were rebuilt."
            exit 1
        }
        return "force-rebuild"
    }
    if ($Choice -eq "cancel") {
        Write-Host "Cancelled. No profile was written."
        exit 1
    }
    Write-Error "Unknown work dir option. Choose reuse existing assets, build missing assets only, force rebuild, or cancel."
}

function Assert-GeneratedAssetTarget {
    param([string]$TargetPath, [string]$WorkDir, [string]$PdfRoot)

    $Resolved = [System.IO.Path]::GetFullPath($TargetPath)
    if (-not (Test-PathInside -ChildPath $Resolved -ParentPath $WorkDir)) {
        Write-Error "Refusing to delete outside profile workspace: $Resolved"
    }
    if (Test-PathInside -ChildPath $Resolved -ParentPath $PdfRoot) {
        Write-Error "Refusing to delete anything under PDF root: $Resolved"
    }
    foreach ($Protected in @(".git", ".venv", "src", "tests", "docs", "scripts", "app.py", "pyproject.toml", "README.md", "data\samples", "data\evaluation")) {
        $ProtectedPath = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $Protected))
        if (Test-PathInside -ChildPath $Resolved -ParentPath $ProtectedPath) {
            Write-Error "Refusing to delete protected project path: $Resolved"
        }
    }
}

function Remove-GeneratedAssetsForForceRebuild {
    param([hashtable]$Paths, [string]$WorkDir, [string]$PdfRoot)

    $Candidates = @(
        $Paths.CatalogPath,
        $Paths.ProcessedDir,
        (Split-Path -Parent $Paths.VectorPath),
        $Paths.SnapshotManifestPath,
        $Paths.SnapshotHistoryPath,
        $Paths.SnapshotRecordDir
    )
    foreach ($Target in $Candidates) {
        Assert-GeneratedAssetTarget -TargetPath $Target -WorkDir $WorkDir -PdfRoot $PdfRoot
        if (Test-Path -LiteralPath $Target) {
            Write-Host "Removing generated internal asset: $Target"
            Remove-Item -LiteralPath $Target -Recurse -Force
        }
    }
}

function Write-InternalLocalEnv {
    param([System.Collections.IDictionary]$ProfileData)

    $LocalEnvPath = Join-Path $ScriptDir "set_internal_env.local.ps1"
    $EnvLines = @(
        "# Generated by scripts/configure_internal.ps1 from the active internal profile.",
        "# This local file is ignored by Git.",
        "`$env:KB_MODE=" + (ConvertTo-PowerShellSingleQuoted "internal"),
        "`$env:LAB_PDF_ROOT=" + (ConvertTo-PowerShellSingleQuoted $ProfileData.pdf_root),
        "`$env:LAB_CATALOG_PATH=" + (ConvertTo-PowerShellSingleQuoted $ProfileData.catalog_path),
        "`$env:LAB_CHUNKS_PATH=" + (ConvertTo-PowerShellSingleQuoted $ProfileData.chunks_path),
        "`$env:LAB_INDEX_PATH=" + (ConvertTo-PowerShellSingleQuoted $ProfileData.index_path),
        "`$env:LAB_STRUCTURED_CHUNKS_PATH=" + (ConvertTo-PowerShellSingleQuoted $ProfileData.structured_chunks_path),
        "`$env:LAB_STRUCTURED_INDEX_PATH=" + (ConvertTo-PowerShellSingleQuoted $ProfileData.structured_index_path),
        "`$env:LAB_VECTOR_PATH=" + (ConvertTo-PowerShellSingleQuoted $ProfileData.vector_path),
        "`$env:LAB_SNAPSHOT_MANIFEST_PATH=" + (ConvertTo-PowerShellSingleQuoted $ProfileData.snapshot_manifest_path),
        "`$env:LAB_SNAPSHOT_HISTORY_PATH=" + (ConvertTo-PowerShellSingleQuoted $ProfileData.snapshot_history_path),
        "`$env:LAB_SNAPSHOT_RECORD_DIR=" + (ConvertTo-PowerShellSingleQuoted $ProfileData.snapshot_record_dir)
    )
    Set-Content -LiteralPath $LocalEnvPath -Value $EnvLines -Encoding UTF8
}

function Convert-ProfileObjectToHashtable {
    param($Profile)

    return [ordered]@{
        profile_name = [string]$Profile.profile_name
        kb_mode = [string]$Profile.kb_mode
        pdf_root = [string]$Profile.pdf_root
        work_dir_mode = [string]$Profile.work_dir_mode
        work_dir = [string]$Profile.work_dir
        catalog_path = [string]$Profile.catalog_path
        chunks_path = [string]$Profile.chunks_path
        index_path = [string]$Profile.index_path
        structured_chunks_path = [string]$Profile.structured_chunks_path
        structured_index_path = [string]$Profile.structured_index_path
        vector_path = [string]$Profile.vector_path
        snapshot_manifest_path = [string]$Profile.snapshot_manifest_path
        snapshot_history_path = [string]$Profile.snapshot_history_path
        snapshot_record_dir = [string]$Profile.snapshot_record_dir
        language = [string]$Profile.language
        embedding_provider = [string]$Profile.embedding_provider
        created_at = [string]$Profile.created_at
        updated_at = [DateTime]::UtcNow.ToString("o")
    }
}

function Write-ProfileFiles {
    param([System.Collections.IDictionary]$ProfileData, [string]$ProfilePath)

    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $ProfilePath) | Out-Null
    New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
    $ProfileJson = $ProfileData | ConvertTo-Json -Depth 4
    Set-Content -LiteralPath $ProfilePath -Value $ProfileJson -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $RuntimeDir "current_profile.json") -Value $ProfileJson -Encoding UTF8
    Write-InternalLocalEnv -ProfileData $ProfileData
}

function Write-CurrentProfileAndLocalEnv {
    param([System.Collections.IDictionary]$ProfileData)

    New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
    $ProfileJson = $ProfileData | ConvertTo-Json -Depth 4
    Set-Content -LiteralPath (Join-Path $RuntimeDir "current_profile.json") -Value $ProfileJson -Encoding UTF8
    Write-InternalLocalEnv -ProfileData $ProfileData
}

function Show-FinalSummary {
    param(
        [string]$ProfileName,
        [string]$PdfRoot,
        [string]$WorkDirMode,
        [string]$WorkDir,
        [string]$Mode,
        [string[]]$CreatedAssets,
        [string[]]$ReusedAssets,
        [string[]]$OverwrittenAssets
    )

    Write-Host ""
    Write-Host "Configuration summary:"
    Write-Host "  profile name: $ProfileName"
    Write-Host "  pdf root: $PdfRoot"
    Write-Host "  work dir mode: $WorkDirMode"
    Write-Host "  work dir: $WorkDir"
    Write-Host "  mode: $Mode"
    Write-Host "  assets that will be created:"
    foreach ($Item in ($CreatedAssets | Sort-Object)) { Write-Host "    - $Item" }
    if ($CreatedAssets.Count -eq 0) { Write-Host "    - none" }
    Write-Host "  assets that will be reused:"
    foreach ($Item in ($ReusedAssets | Sort-Object)) { Write-Host "    - $Item" }
    if ($ReusedAssets.Count -eq 0) { Write-Host "    - none" }
    Write-Host "  assets that will be overwritten:"
    foreach ($Item in ($OverwrittenAssets | Sort-Object)) { Write-Host "    - $Item" }
    if ($OverwrittenAssets.Count -eq 0) { Write-Host "    - none" }
}

Write-Host ""
Write-Host "Configure an internal ThesisAgent profile."
Write-Host "This wizard checks PDF filenames only and never copies original PDFs into the project."
Write-Host ""

$ProfileChoice = Resolve-ProfileNameChoice
$ProfileName = [string]$ProfileChoice.name
$ProfilePath = [string]$ProfileChoice.path

if ($ProfileChoice.mode -eq "reuse-profile") {
    $ProfileData = Convert-ProfileObjectToHashtable $ProfileChoice.existing_profile
    Assert-PdfRoot -PdfRoot $ProfileData.pdf_root
    Show-FinalSummary -ProfileName $ProfileName -PdfRoot $ProfileData.pdf_root -WorkDirMode $ProfileData.work_dir_mode -WorkDir $ProfileData.work_dir -Mode "reuse existing profile" -CreatedAssets @() -ReusedAssets @("profile", "catalog", "chunks", "index", "vector") -OverwrittenAssets @()
    $ConfirmReuseProfile = Read-Host "Type YES to make this existing profile active"
    if ($ConfirmReuseProfile -ne "YES") {
        Write-Host "Cancelled. Active profile was not changed."
        exit 1
    }
    Write-CurrentProfileAndLocalEnv -ProfileData $ProfileData
    Write-Host ""
    Write-Host "Internal profile is active: $ProfileName"
    Write-Host "Next step:"
    Write-Host "  .\scripts\run_internal.ps1"
    exit 0
}

$PdfRootInput = Read-Host "PDF root"
$Language = Read-HostWithDefault "Language" "ja"
if ($Language -notin @("auto", "ja", "zh", "en")) {
    Write-Error "Language must be one of: auto, ja, zh, en."
}

$PdfRoot = Normalize-PathInput -Value $PdfRootInput -MustExist -Label "PDF root"
Assert-PdfRoot -PdfRoot $PdfRoot
$WorkDirSelection = Resolve-WorkDir -ProfileName $ProfileName -PdfRoot $PdfRoot
$WorkDirMode = [string]$WorkDirSelection.mode
$WorkDir = [string]$WorkDirSelection.path
Assert-WorkDir -WorkDir $WorkDir -PdfRoot $PdfRoot -WorkDirMode $WorkDirMode

$ProcessedDir = Join-Path $WorkDir "processed"
$Paths = @{
    CatalogPath = Join-Path $WorkDir "catalog.csv"
    ProcessedDir = $ProcessedDir
    ChunksPath = Join-Path $ProcessedDir "chunks.jsonl"
    IndexPath = Join-Path $ProcessedDir "tfidf_index.pkl"
    StructuredChunksPath = Join-Path $ProcessedDir "structured_chunks.jsonl"
    StructuredIndexPath = Join-Path $ProcessedDir "structured_tfidf_index.pkl"
    VectorPath = Join-Path (Join-Path $WorkDir "vector") "chroma"
    SnapshotManifestPath = Join-Path $WorkDir "kb_snapshot_manifest.json"
    SnapshotHistoryPath = Join-Path $WorkDir "kb_snapshot_history.json"
    SnapshotRecordDir = Join-Path $WorkDir "kb_snapshots"
}

$InitialStatus = Get-AssetStatus -Paths $Paths
$BuildMode = Select-WorkspaceBuildMode -AssetStatus $InitialStatus

$CreatedAssets = @()
$ReusedAssets = Get-ExistingAssetNames -Status $InitialStatus
$OverwrittenAssets = @()
if ($BuildMode -eq "reuse") {
    $CreatedAssets = @()
} elseif ($BuildMode -eq "force-rebuild") {
    $OverwrittenAssets = Get-ExistingAssetNames -Status $InitialStatus
    $ReusedAssets = @()
    $CreatedAssets = @("catalog", "chunks", "index", "structured_chunks", "structured_index", "vector", "snapshot")
} else {
    foreach ($Key in @("catalog", "chunks", "index", "structured_chunks", "structured_index", "vector", "snapshot_manifest", "snapshot_history", "snapshot_records")) {
        if (-not $InitialStatus[$Key]) {
            $CreatedAssets += $Key
        }
    }
    if ($CreatedAssets -contains "structured_chunks" -or $CreatedAssets -contains "structured_index") {
        $CreatedAssets += "structured chunks/index will be attempted; fallback is allowed"
    }
}

Show-FinalSummary -ProfileName $ProfileName -PdfRoot $PdfRoot -WorkDirMode $WorkDirMode -WorkDir $WorkDir -Mode $BuildMode -CreatedAssets $CreatedAssets -ReusedAssets $ReusedAssets -OverwrittenAssets $OverwrittenAssets

$Confirm = Read-Host "Type YES to build/update this internal profile"
if ($Confirm -ne "YES") {
    Write-Host "Cancelled. No profile was written."
    exit 1
}

if ($BuildMode -eq "force-rebuild") {
    Remove-GeneratedAssetsForForceRebuild -Paths $Paths -WorkDir $WorkDir -PdfRoot $PdfRoot
}

foreach ($Dir in @($WorkDir, $ProcessedDir, (Split-Path -Parent $Paths.VectorPath), $Paths.SnapshotRecordDir)) {
    New-Item -ItemType Directory -Force -Path $Dir | Out-Null
}

if ($BuildMode -ne "reuse" -and -not (Test-Path -LiteralPath $Paths.CatalogPath)) {
    Invoke-PythonCommand -Arguments @(
        "-m", "thesis_agent.cli.sync_catalog",
        "--pdf-root", $PdfRoot,
        "--catalog", $Paths.CatalogPath
    )
}

if (-not (Test-Path -LiteralPath $Paths.CatalogPath)) {
    Write-Error "Catalog is missing: $($Paths.CatalogPath). Choose build missing assets only unless you already have a complete workspace."
}

if ($BuildMode -ne "reuse" -and -not (Test-Path -LiteralPath $Paths.ChunksPath)) {
    Invoke-PythonCommand -Arguments @(
        "-m", "thesis_agent.cli.ingest",
        "--input", $PdfRoot,
        "--input-type", "pdf",
        "--language", $Language,
        "--chunk-mode", "fixed",
        "--output", $Paths.ChunksPath,
        "--metadata-output", (Join-Path $ProcessedDir "documents.jsonl"),
        "--catalog", $Paths.CatalogPath
    )
}

if ($BuildMode -ne "reuse" -and -not (Test-Path -LiteralPath $Paths.IndexPath)) {
    Invoke-PythonCommand -Arguments @(
        "-m", "thesis_agent.cli.build_index",
        "--chunks", $Paths.ChunksPath,
        "--output", $Paths.IndexPath,
        "--language", $Language
    )
}

if ($BuildMode -ne "reuse" -and -not (Test-Path -LiteralPath $Paths.StructuredChunksPath)) {
    Invoke-PythonCommand -Arguments @(
        "-m", "thesis_agent.cli.ingest",
        "--input", $PdfRoot,
        "--input-type", "pdf",
        "--language", $Language,
        "--chunk-mode", "structured",
        "--output", $Paths.StructuredChunksPath,
        "--metadata-output", (Join-Path $ProcessedDir "structured_documents.jsonl"),
        "--catalog", $Paths.CatalogPath
    ) -AllowFailure | Out-Null
}

if ($BuildMode -ne "reuse" -and (Test-Path -LiteralPath $Paths.StructuredChunksPath) -and -not (Test-Path -LiteralPath $Paths.StructuredIndexPath)) {
    Invoke-PythonCommand -Arguments @(
        "-m", "thesis_agent.cli.build_index",
        "--chunks", $Paths.StructuredChunksPath,
        "--output", $Paths.StructuredIndexPath,
        "--language", $Language
    ) -AllowFailure | Out-Null
}

if ($BuildMode -ne "reuse" -and -not (Test-Path -LiteralPath $Paths.VectorPath)) {
    $VectorSourceChunks = $Paths.ChunksPath
    if (Test-Path -LiteralPath $Paths.StructuredChunksPath) {
        $VectorSourceChunks = $Paths.StructuredChunksPath
    }
    Invoke-PythonCommand -Arguments @(
        "-m", "thesis_agent.cli.build_vector_index",
        "--chunks", $VectorSourceChunks,
        "--persist-dir", $Paths.VectorPath,
        "--collection", "thesis_agent_$ProfileName",
        "--embedding-provider", "hash",
        "--reset"
    ) -AllowFailure | Out-Null
}

foreach ($Required in @($PdfRoot, $Paths.CatalogPath, $Paths.ChunksPath, $Paths.IndexPath)) {
    if (-not (Test-Path -LiteralPath $Required)) {
        Write-Error "Required internal asset is missing after configuration: $Required"
    }
}

$SnapshotArgs = @(
    "-m", "thesis_agent.cli.write_kb_snapshot_manifest",
    "--mode", "internal",
    "--snapshot-kind", "internal",
    "--catalog-path", $Paths.CatalogPath,
    "--chunks-path", $Paths.ChunksPath,
    "--index-path", $Paths.IndexPath,
    "--output", $Paths.SnapshotManifestPath,
    "--history-output", $Paths.SnapshotHistoryPath,
    "--record-dir", $Paths.SnapshotRecordDir,
    "--embedding-provider", "hash",
    "--notes", "internal runtime snapshot"
)
if (Test-Path -LiteralPath $Paths.StructuredChunksPath) {
    $SnapshotArgs += @("--structured-chunks-path", $Paths.StructuredChunksPath)
}
if (Test-Path -LiteralPath $Paths.StructuredIndexPath) {
    $SnapshotArgs += @("--structured-index-path", $Paths.StructuredIndexPath)
}
if (Test-Path -LiteralPath $Paths.VectorPath) {
    $SnapshotArgs += @("--vector-path", $Paths.VectorPath)
}
Invoke-PythonCommand -Arguments $SnapshotArgs

$CreatedAt = [DateTime]::UtcNow.ToString("o")
if ($ProfileChoice.mode -eq "overwrite" -and (Test-Path -LiteralPath $ProfilePath)) {
    try {
        $ExistingProfile = Get-Content -LiteralPath $ProfilePath -Raw | ConvertFrom-Json
        if (-not [string]::IsNullOrWhiteSpace($ExistingProfile.created_at)) {
            $CreatedAt = [string]$ExistingProfile.created_at
        }
    } catch {
        Write-Warning "Existing profile could not be read; created_at will be reset."
    }
}

$ProfileData = [ordered]@{
    profile_name = $ProfileName
    kb_mode = "internal"
    pdf_root = $PdfRoot
    work_dir_mode = $WorkDirMode
    work_dir = $WorkDir
    catalog_path = $Paths.CatalogPath
    chunks_path = $Paths.ChunksPath
    index_path = $Paths.IndexPath
    structured_chunks_path = $Paths.StructuredChunksPath
    structured_index_path = $Paths.StructuredIndexPath
    vector_path = $Paths.VectorPath
    snapshot_manifest_path = $Paths.SnapshotManifestPath
    snapshot_history_path = $Paths.SnapshotHistoryPath
    snapshot_record_dir = $Paths.SnapshotRecordDir
    language = $Language
    embedding_provider = "hash"
    created_at = $CreatedAt
    updated_at = [DateTime]::UtcNow.ToString("o")
}

Write-ProfileFiles -ProfileData $ProfileData -ProfilePath $ProfilePath

Write-Host ""
Write-Host "Internal profile is ready: $ProfileName"
Write-Host "Workspace:"
Write-Host "  $WorkDir"
Write-Host "Active profile:"
Write-Host "  .runtime\internal\current_profile.json"
Write-Host "Next step:"
Write-Host "  .\scripts\run_internal.ps1"
