# Project: CoChem-BASE Agent Configuration Fix & Sanitization

## Architecture
- Target Directory: `D:\Gdrive\__CoChem\GitHub-Repo\CoChem-BASE\.agents`
- Source Directory: `C:\Users\ansac\.gemini\config\agents`
- Overwrite Target: 15 `*.agent.md` files in `.agents/`
- Sanitization Mapping:
  - `C:\Users\ansac` / `C:/Users/ansac` -> `<USER_HOME>`
  - `D:\Gdrive\__CoChem` / `D:/Gdrive/__CoChem` -> `<COCHEM_WORKSPACE>`
  - `D:\Gdrive` / `D:/Gdrive` -> `<GDRIVE_ROOT>`
- Preservation Target: `ORIGINAL_REQUEST.md` and framework metadata subdirectories (`orchestrator/`, `sentinel/`, survey folders), with path sanitization applied to ensure 0 search hits.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Agent Config Overwrite | Overwrite 15 agent configuration files in `CoChem-BASE/.agents` with fixed files from source | M1 | Survey |
| 2 | Agent Config Path Sanitization | Sanitize all absolute personal paths (`C:\Users\ansac`, `D:\Gdrive\__CoChem`, `D:\Gdrive`) in `.agent.md` files | M1 | Survey |
| 3 | Metadata & Request Path Sanitization | Sanitize personal paths in `ORIGINAL_REQUEST.md` and metadata `.md` files in `.agents/` so recursive search returns 0 results | M1 | Survey |
| 4 | Verification & Audit | Verify file match, path sanitization, and 0 search hits for `C:\Users\ansac` and `D:\Gdrive\__CoChem` via Reviewers, Challengers, and Forensic Auditor | M2 | Survey |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | M1: Overwrite & Sanitize | Overwrite 15 `.agent.md` files and sanitize personal paths across `CoChem-BASE/.agents` | none | DONE |
| 2 | M2: Review, Challenge & Audit | Run 2 Reviewers, 2 Challengers, and Forensic Auditor to gate-verify criteria | M1 | DONE |

## Code Layout
- `D:\Gdrive\__CoChem\GitHub-Repo\CoChem-BASE\.agents\*.agent.md` (15 files)
- `D:\Gdrive\__CoChem\GitHub-Repo\CoChem-BASE\.agents\ORIGINAL_REQUEST.md`
- `D:\Gdrive\__CoChem\GitHub-Repo\CoChem-BASE\.agents\orchestrator\*`

## Interface Contracts
- Worker owns writing to `D:\Gdrive\__CoChem\GitHub-Repo\CoChem-BASE\.agents\*.agent.md` and updating `ORIGINAL_REQUEST.md`.
- Reviewers, Challengers, and Auditor execute read-only checks and verification commands against `D:\Gdrive\__CoChem\GitHub-Repo\CoChem-BASE\.agents`.
