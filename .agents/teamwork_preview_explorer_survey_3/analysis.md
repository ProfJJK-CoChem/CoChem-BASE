# Analysis Report: Agent Configuration Survey and Sanitization Strategy

**Working Directory**: `<COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents\teamwork_preview_explorer_survey_3`  
**Date**: 2026-08-11  
**Author**: Explorer Agent (`teamwork_preview_explorer_survey_3`)  
**Parent Conversation ID**: `39f39eb0-6bb9-4f9a-b544-6a701d124d30`

---

## 1. Executive Summary

This survey compares the fixed agent configuration files located in `<USER_HOME>\.gemini\config\agents` against the existing agent files in the project workspace at `<COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents`.

All 15 agent configuration files present in the source directory are present in the target directory. However, none of the target `.agent.md` files currently match the source file contents (all file hashes differ). The source files contain fixed configuration settings (e.g. updated tool flags `enable_write_tools` and `enable_mcp_tools`) but also introduce literal personal drive paths (`<COCHEM_WORKSPACE>\...` and `<GDRIVE_ROOT>\__Books`).

A precise copy and path sanitization strategy has been formulated to overwrite the target `.agent.md` files, replace personal paths with sanitized placeholders (`<USER_HOME>`, `<COCHEM_WORKSPACE>`, and `<GDRIVE_ROOT>`), and preserve workspace metadata files (such as `ORIGINAL_REQUEST.md`) and runtime subdirectories.

---

## 2. Directory & File Inventory Comparison

### 2.1 Source Directory: `<USER_HOME>\.gemini\config\agents`
- **Total Files**: 15 `.agent.md` files.
- **File List**:
  1. `0rchestrator.agent.md` (4,979 bytes)
  2. `artist.agent.md` (2,208 bytes)
  3. `cochem-audit.agent.md` (3,582 bytes)
  4. `cochem-coder.agent.md` (3,770 bytes)
  5. `cochem-debug.agent.md` (3,135 bytes)
  6. `cochem-helper.agent.md` (3,598 bytes)
  7. `cochem-improve.agent.md` (3,284 bytes)
  8. `cochem-scribe.agent.md` (2,654 bytes)
  9. `cochem-sdp_manager.agent.md` (4,690 bytes)
  10. `cochem-tester.agent.md` (2,701 bytes)
  11. `educator.agent.md` (3,130 bytes)
  12. `researcher.agent.md` (2,763 bytes)
  13. `teacher.agent.md` (2,618 bytes)
  14. `ui.agent.md` (2,917 bytes)
  15. `web_mcp.agent.md` (2,265 bytes)

### 2.2 Target Directory: `<COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents`
- **Root Files**: 16 files (15 `.agent.md` files + 1 metadata file `ORIGINAL_REQUEST.md`).
- **Subdirectories**: 5 runtime/metadata directories:
  - `orchestrator/`
  - `sentinel/`
  - `teamwork_preview_explorer_survey_1/`
  - `teamwork_preview_explorer_survey_2/`
  - `teamwork_preview_explorer_survey_3/`

### 2.3 Discrepancies & File Mapping
- **Missing Files in Target**: None (0). All 15 source files exist in the target root.
- **Extra Files in Target Root**: `ORIGINAL_REQUEST.md` (3,181 bytes). Must **NOT** be overwritten or deleted.
- **Extra Directories in Target**: Agent runtime folders. Must **NOT** be modified or deleted.
- **Content Hashes**: `Equal=False` across all 15 files.

| File Name | Source Size (bytes) | Target Size (bytes) | Hash Equal |
| :--- | :--- | :--- | :--- |
| `0rchestrator.agent.md` | 4,979 | 4,889 | False |
| `artist.agent.md` | 2,208 | 2,136 | False |
| `cochem-audit.agent.md` | 3,582 | 3,521 | False |
| `cochem-coder.agent.md` | 3,770 | 3,727 | False |
| `cochem-debug.agent.md` | 3,135 | 3,667 | False |
| `cochem-helper.agent.md` | 3,598 | 3,554 | False |
| `cochem-improve.agent.md` | 3,284 | 3,447 | False |
| `cochem-scribe.agent.md` | 2,654 | 2,592 | False |
| `cochem-sdp_manager.agent.md` | 4,690 | 4,613 | False |
| `cochem-tester.agent.md` | 2,701 | 2,650 | False |
| `educator.agent.md` | 3,130 | 3,068 | False |
| `researcher.agent.md` | 2,763 | 2,719 | False |
| `teacher.agent.md` | 2,618 | 2,556 | False |
| `ui.agent.md` | 2,917 | 2,855 | False |
| `web_mcp.agent.md` | 2,265 | 2,221 | False |

---

## 3. Path Analysis & Replacement Rules

### 3.1 Observed Path Patterns in Source Files
Inspection of `<USER_HOME>\.gemini\config\agents` reveals the following exact line patterns across all 15 files:

1. **`<COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\Method_Matrix.md`** (All 15 files, line 14 or 15)
2. **`<COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\CoChem_User_Manual.md`** (All 15 files, line 15 or 16)
3. **`<COCHEM_WORKSPACE>\GitHub-Repo\Resources`** (All 15 files, line 16 or 17)
4. **`<GDRIVE_ROOT>\__Books`** (All 15 files, line 17 or 18)
5. **`<COCHEM_WORKSPACE>\GitHub-Repo\Resources\PMBOK-2021`** (`0rchestrator.agent.md` L19, `cochem-sdp_manager.agent.md` L18)
6. **`<COCHEM_WORKSPACE>\GitHub-Repo\Resources\SWEBOKv3-published`** (`0rchestrator.agent.md` L20, `cochem-sdp_manager.agent.md` L19)

### 3.2 Path Replacement Rules

| Search Pattern (Regex / Literal) | Replacement Target | Context / Note |
| :--- | :--- | :--- |
| `(?i)C:[\\/]Users[\\/]ansac` | `<USER_HOME>` | Standard user home path (Windows & POSIX slashes) |
| `(?i)D:[\\/]Gdrive[\\/]__CoChem` | `<COCHEM_WORKSPACE>` | CoChem workspace root (Windows & POSIX slashes) |
| `(?i)D:[\\/]Gdrive` | `<GDRIVE_ROOT>` | Drive root for external references such as `__Books` |

#### Specific Replacement Verification Table

| Source String | Sanitized Output |
| :--- | :--- |
| `<USER_HOME>` | `<USER_HOME>` |
| `<USER_HOME>` | `<USER_HOME>` |
| `<USER_HOME>` | `<USER_HOME>` |
| `<COCHEM_WORKSPACE>` | `<COCHEM_WORKSPACE>` |
| `<COCHEM_WORKSPACE>` | `<COCHEM_WORKSPACE>` |
| `<COCHEM_WORKSPACE>` | `<COCHEM_WORKSPACE>` |
| `<GDRIVE_ROOT>\__Books` | `<GDRIVE_ROOT>\__Books` |

---

## 4. Proposed Copy & Sanitization Strategy

### 4.1 Copy & Sanitization Procedure
An implementation agent should execute the following steps:
1. Iterate over all 15 `.agent.md` filenames in `<USER_HOME>\.gemini\config\agents`.
2. Read the source file content as UTF-8 raw text.
3. Apply case-insensitive replacements in sequence:
   - Replace `<USER_HOME>` (and slash variants) with `<USER_HOME>`.
   - Replace `<COCHEM_WORKSPACE>` (and slash variants) with `<COCHEM_WORKSPACE>`.
   - Replace `<GDRIVE_ROOT>` (and slash variants) with `<GDRIVE_ROOT>`.
4. Overwrite the corresponding target file at `<COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents\<filename>`.
5. Ensure `ORIGINAL_REQUEST.md` and all subdirectories in `.agents` remain untouched.

### 4.2 Post-Operation Acceptance Verification
Run a verification script in PowerShell:
```powershell
$targetDir = "<COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents"
$agentFiles = Get-ChildItem -Path $targetDir -Filter "*.agent.md" -File

# 1. Count of agent files must be 15
Write-Host "Agent File Count: $($agentFiles.Count)" # Expected: 15

# 2. Search for residual <USER_HOME> or <COCHEM_WORKSPACE>
$ansacMatches = $agentFiles | Select-String -Pattern "C:[\\/]Users[\\/]ansac" -CaseSensitive:$false
$cochemMatches = $agentFiles | Select-String -Pattern "D:[\\/]Gdrive[\\/]__CoChem" -CaseSensitive:$false

Write-Host "Residual <USER_HOME> matches: $($ansacMatches.Count)" # Expected: 0
Write-Host "Residual <COCHEM_WORKSPACE> matches: $($cochemMatches.Count)" # Expected: 0

# 3. Verify ORIGINAL_REQUEST.md still exists
Test-Path (Join-Path $targetDir "ORIGINAL_REQUEST.md") # Expected: True
```
