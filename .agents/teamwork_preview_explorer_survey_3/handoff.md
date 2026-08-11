# Handoff Report: Agent Files Comparison & Sanitization Strategy Survey

**Working Directory**: `<COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents\teamwork_preview_explorer_survey_3`  
**Date**: 2026-08-11  
**Author**: Explorer Agent (`teamwork_preview_explorer_survey_3`)  
**Parent Conversation ID**: `39f39eb0-6bb9-4f9a-b544-6a701d124d30`

---

## 1. Observation

Direct observations obtained during filesystem inspection and analysis:

1. **Source File Inventory**:
   - Location: `<USER_HOME>\.gemini\config\agents`
   - Command: `Get-ChildItem -Path "<USER_HOME>\.gemini\config\agents" -File`
   - Result: Exactly 15 `.agent.md` files:
     `0rchestrator.agent.md`, `artist.agent.md`, `cochem-audit.agent.md`, `cochem-coder.agent.md`, `cochem-debug.agent.md`, `cochem-helper.agent.md`, `cochem-improve.agent.md`, `cochem-scribe.agent.md`, `cochem-sdp_manager.agent.md`, `cochem-tester.agent.md`, `educator.agent.md`, `researcher.agent.md`, `teacher.agent.md`, `ui.agent.md`, `web_mcp.agent.md`.

2. **Target File Inventory**:
   - Location: `<COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents`
   - Command: `Get-ChildItem -Path "<COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents"`
   - Result: 16 root files (15 `.agent.md` files matching source names + 1 metadata file `ORIGINAL_REQUEST.md`) and 5 subdirectories (`orchestrator/`, `sentinel/`, `teamwork_preview_explorer_survey_1/`, `teamwork_preview_explorer_survey_2/`, `teamwork_preview_explorer_survey_3/`).

3. **File Hashes & Content Differences**:
   - Command: `Get-FileHash` SHA256 comparison between source and target files.
   - Result: `Equal=False` for all 15 files. Target files use outdated `tools: [...]` lists in YAML frontmatter, whereas source files use updated `enable_write_tools: true` and `enable_mcp_tools: true`.

4. **Literal Personal Paths in Source Files**:
   - Command: Regex search `(?i)[a-z]:[\\/][^\s\`"''>]+` across all source files.
   - Result: All 15 source files contain hardcoded Windows absolute paths:
     - `<COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\Method_Matrix.md` (Line 14 or 15)
     - `<COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\CoChem_User_Manual.md` (Line 15 or 16)
     - `<COCHEM_WORKSPACE>\GitHub-Repo\Resources` (Line 16 or 17)
     - `<GDRIVE_ROOT>\__Books` (Line 17 or 18)
     - `<COCHEM_WORKSPACE>\GitHub-Repo\Resources\PMBOK-2021` (`0rchestrator.agent.md` L19, `cochem-sdp_manager.agent.md` L18)
     - `<COCHEM_WORKSPACE>\GitHub-Repo\Resources\SWEBOKv3-published` (`0rchestrator.agent.md` L20, `cochem-sdp_manager.agent.md` L19)
   - Zero instances of `<USER_HOME>` were found in the source `.agent.md` files, but requirement R2 explicitly specifies setting sanitization rules for `<USER_HOME>` -> `<USER_HOME>` to prevent personal path leakage across operating systems and future variants.

---

## 2. Logic Chain

1. **Premise 1 (File Alignment)**: From Observation #1 and #2, all 15 source `.agent.md` files have direct target counterparts in `<COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents`. No agent files are missing from the target directory, and no extra `.agent.md` files exist in the source.
2. **Premise 2 (Overwrite Requirement)**: From Observation #3, target files are outdated (`Equal=False`). Overwriting them with source files updates the agent configuration schema to the fixed version required by R1.
3. **Premise 3 (Sanitization Requirement)**: From Observation #4, source files introduce absolute drive paths starting with `<COCHEM_WORKSPACE>` and `<GDRIVE_ROOT>`. Overwriting target files directly without sanitization would violate R2 and fail acceptance search criteria.
4. **Premise 4 (Workspace Metadata Protection)**: From Observation #2, `ORIGINAL_REQUEST.md` and runtime subdirectories exist in `<COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents`. Overwriting operations must strictly target the 15 `.agent.md` files to prevent data loss.
5. **Conclusion**: Overwriting the 15 target `.agent.md` files while applying regex-based string replacements (`<USER_HOME>` -> `<USER_HOME>`, `<COCHEM_WORKSPACE>` -> `<COCHEM_WORKSPACE>`, `<GDRIVE_ROOT>` -> `<GDRIVE_ROOT>`) satisfies R1 and R2 while preserving workspace integrity.

---

## 3. Caveats

- **Scope of Investigation**: This survey performed read-only static analysis on the configuration files. It did not execute any file copy or modification operations.
- **Handling of `<GDRIVE_ROOT>\__Books`**: While R2 explicitly lists `<USER_HOME>` and `<COCHEM_WORKSPACE>`, source files also contain `<GDRIVE_ROOT>\__Books`. Replacing `<GDRIVE_ROOT>` with `<GDRIVE_ROOT>` ensures all drive-letter personal references are eliminated.
- **Assumptions**: Assumed UTF-8 encoding for all `.agent.md` files.

---

## 4. Conclusion

1. Exactly 15 `.agent.md` files must be copied from `<USER_HOME>\.gemini\config\agents` to `<COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents`.
2. The file `ORIGINAL_REQUEST.md` and all subdirectories in `.agents` must remain untouched.
3. The exact path replacement rules are:
   - `(?i)C:[\\/]Users[\\/]ansac` -> `<USER_HOME>`
   - `(?i)D:[\\/]Gdrive[\\/]__CoChem` -> `<COCHEM_WORKSPACE>`
   - `(?i)D:[\\/]Gdrive` -> `<GDRIVE_ROOT>`
4. Upon applying these replacements during copy, 0 instances of `<USER_HOME>` or `<COCHEM_WORKSPACE>` will remain in `<COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents\*.agent.md`, satisfying all acceptance criteria.

---

## 5. Verification Method

To independently verify these findings:

1. **Run Inventory Check**:
   ```powershell
   pwsh -Command 'Get-ChildItem -Path "<USER_HOME>\.gemini\config\agents" -File | Measure-Object'
   pwsh -Command 'Get-ChildItem -Path "<COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents" -Filter "*.agent.md" -File | Measure-Object'
   ```
   *Expected*: Both return Count = 15.

2. **Verify Source Personal Paths**:
   ```powershell
   pwsh -Command 'Get-ChildItem -Path "<USER_HOME>\.gemini\config\agents" -File | Select-String -Pattern "<GDRIVE_ROOT>" '
   ```
   *Expected*: Returns matches in lines 14-20 across all 15 source files.

3. **Verify Post-Sanitization Absence**:
   After the implementer agent completes the copy and sanitization:
   ```powershell
   pwsh -Command 'Get-ChildItem -Path "<COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents" -Filter "*.agent.md" | Select-String -Pattern "<USER_HOME>","<COCHEM_WORKSPACE>"'
   ```
   *Expected*: Returns 0 matching lines.
