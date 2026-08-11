## 2026-08-11T18:03:20Z
You are a Worker agent.
Your working directory: <COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents\teamwork_preview_worker_m1
Original Request path: <COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents\ORIGINAL_REQUEST.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Instructions:
1. Read <COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents\ORIGINAL_REQUEST.md.
2. Read the survey handoff reports in:
   - <COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents\teamwork_preview_explorer_survey_2\handoff.md
   - <COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents\teamwork_preview_explorer_survey_3\handoff.md
3. Overwrite the 15 `.agent.md` files in `<COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents` with the fixed code files from `<USER_HOME>\.gemini\config\agents`.
4. Apply path sanitization on all 15 `.agent.md` files in `<COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents`:
   - Replace any variant of `<USER_HOME>` (including forward/backward slashes and case variations) with `<USER_HOME>`
   - Replace any variant of `<COCHEM_WORKSPACE>` with `<COCHEM_WORKSPACE>`
   - Replace any remaining variant of `<GDRIVE_ROOT>` with `<GDRIVE_ROOT>`
5. Also check `<COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents\ORIGINAL_REQUEST.md` and any orchestrator/metadata markdown files inside `<COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents` for occurrences of `<USER_HOME>` and `<COCHEM_WORKSPACE>`, replacing them with `<USER_HOME>` and `<COCHEM_WORKSPACE>` respectively, to ensure that a recursive search inside `<COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents` for `<USER_HOME>` or `<COCHEM_WORKSPACE>` yields exactly 0 results.
6. Verify your implementation by running powershell / ripgrep search commands:
   - Search for `<USER_HOME>` inside `<COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents` (must return 0 results).
   - Search for `<COCHEM_WORKSPACE>` inside `<COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents` (must return 0 results).
   - Verify that all 15 `.agent.md` files exist in `<COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents` and match the source contents (modulo sanitization).
7. Document all changes in `<COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents\teamwork_preview_worker_m1\changes.md` and `<COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents\teamwork_preview_worker_m1\handoff.md`.
8. Send a completion message back to the orchestrator referencing your handoff report and verification output.
