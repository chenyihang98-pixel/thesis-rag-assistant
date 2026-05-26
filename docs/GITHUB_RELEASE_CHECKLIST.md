# GitHub Release Checklist

Use this checklist before publishing ThesisAgent to a public repository.

## Files To Commit

- `app.py`
- `pyproject.toml`
- `README.md`
- `.gitignore`
- `.env.example`
- `.streamlit/config.toml`
- `src/`
- `scripts/setup_demo.ps1`
- `scripts/run_demo.ps1`
- `scripts/configure_llm.ps1`
- `scripts/configure_internal.ps1`
- `scripts/run_internal.ps1`
- `scripts/prepare_demo_assets.ps1`
- `scripts/write_demo_snapshot.ps1`
- `scripts/set_internal_env.example.ps1`
- `docs/RUNBOOK.md`
- `docs/ARCHITECTURE.md`
- `docs/GITHUB_RELEASE_CHECKLIST.md`
- `data/samples/`

## Files Not To Commit

- `.venv/`
- `.runtime/`
- `.env`
- `.env.*`
- `.tmp/`
- `.pytest_cache/`
- `__pycache__/`
- `outputs/`
- `tests/`
- `data/evaluation/`
- `scripts/set_internal_env.local.ps1`
- `scripts/set_llm_env.local.ps1`
- `data/processed/`
- `data/index/`
- `data/vector/`
- `data/chroma/`
- `data/metadata/kb_snapshot_manifest.json`
- `data/metadata/kb_snapshot_history.json`
- `data/metadata/kb_snapshots/`
- `chroma_db/`
- `*.pyc`
- `*.pyo`
- `*.pkl`
- `*.joblib`

## Safety Checks

- Confirm `.runtime/` is ignored before configuring internal or LLM profiles.
- Confirm no real PDF files are under the repository.
- Confirm no private catalog, chunks, TF-IDF index, vector store, or snapshot files are committed.
- Confirm `scripts/set_internal_env.local.ps1` and `scripts/set_llm_env.local.ps1` are ignored.
- Confirm `.env.example` contains placeholders only.
- Confirm API keys are not committed.
- Confirm personal model names are examples only, not runtime defaults.

## Demo Smoke Test

```powershell
.\scripts\setup_demo.ps1
.\scripts\run_demo.ps1
```

For AI answers in demo mode:

```powershell
.\scripts\configure_llm.ps1
.\scripts\run_demo.ps1
```

## Internal Smoke Test

Use a local PDF folder outside the repository.

```powershell
.\scripts\configure_internal.ps1
.\scripts\run_internal.ps1
```

To switch corpora:

```powershell
.\scripts\configure_internal.ps1
.\scripts\run_internal.ps1 -Profile <profile_name>
```

## Validation

```powershell
python -m pytest -q --basetemp=.tmp\pytest-tmp
python -X pycache_prefix=.tmp\compile_pycache -m compileall src app.py
```

## Git Checklist

Run these only after the safety checks pass.

```powershell
git init
git status
git add app.py pyproject.toml README.md .gitignore .env.example .streamlit src scripts docs data/samples
git status
git commit -m "release: prepare local-first ThesisAgent demo and profile runtime"
git tag v0.1.0
```
