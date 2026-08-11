# Original User Request

## Initial Request — 2026-08-10T20:16:49Z

You are the Project Orchestrator for Phase 4: Code Audit Council.

Working directory: <COCHEM_ROOT>\.agents\orchestrator
Project Root: <COCHEM_ROOT>
Original Request: <COCHEM_ROOT>\.agents\ORIGINAL_REQUEST.md

Your mission is to convene a 3-agent Code Audit Council to perform a secondary, literature-backed verification pass over the 15 CoChem repositories.

The Council must consist of 3 specialized auditors:
1. Auditor Alpha (Code Integrity Auditor)
   - Working Directory: <COCHEM_ROOT>\.agents\auditor_alpha
   - Task: Scan all 15 CoChem repositories specifically for mock code, random number generators, hardcoded values, and dummy functions. Validate that all code is fully functional.

2. Auditor Beta (Scientific Validity Auditor)
   - Working Directory: <COCHEM_ROOT>\.agents\auditor_beta
   - Task: Verify physical constants, equations, and chemical parameters (such as v4 Method Matrix values) against published scientific literature.
   - CRITICAL: Must actively use literature-search-arxiv, literature-search-openalex, and pubchem-database skills to cross-check real-world scientific data.

3. Auditor Gamma (Functional Completeness Auditor)
   - Working Directory: <COCHEM_ROOT>\.agents\auditor_gamma
   - Task: Cross-reference implemented codebase against CoChem_User_Manual.md and 20260809_Method_Matrix.md. Ensure all stated functionalities exist and operate correctly.

After the 3 auditors complete their investigations and debate discrepancies, synthesize their findings into a final comprehensive report at:
<COCHEM_ROOT>\Code_Audit_Council_Report.md

Maintain progress.md in your working directory (<COCHEM_ROOT>\.agents\orchestrator\progress.md) throughout the process. When finished, send a completion message to the Sentinel.

## Follow-up — 2026-08-11T18:00:45Z

# Teamwork Project Prompt — Draft

Fix the CoChem-Antigravity sanitized agents by completely overwriting the existing agent files with the fixed code files provided in `<USER_HOME>\.gemini\config\agents`, and ensuring no personal paths remain.

Working directory: <COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE
Integrity mode: development

## Requirements

### R1. Overwrite Existing Agents
Copy the fixed agent configuration files from `<USER_HOME>\.gemini\config\agents` and completely overwrite the existing agent files in `<COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents`.

### R2. Sanitize Absolute Paths
Ensure all newly overwritten agent configurations in `CoChem-BASE/.agents` have personal directory paths (specifically `<USER_HOME>` and `<COCHEM_WORKSPACE>`) scrubbed and replaced with `<USER_HOME>` and `<COCHEM_WORKSPACE>` respectively, or relative paths.

## Acceptance Criteria

### Verification
- [ ] A file comparison (or manual check) confirms the files in `CoChem-BASE/.agents` contain the fixed code from `<USER_HOME>\.gemini\config\agents`.
- [ ] Running a search for `<USER_HOME>` inside `CoChem-BASE/.agents` returns 0 results.
- [ ] Running a search for `<COCHEM_WORKSPACE>` inside `CoChem-BASE/.agents` returns 0 results.

