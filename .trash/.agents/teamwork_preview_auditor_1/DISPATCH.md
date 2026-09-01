## 2026-08-11T18:04:23Z
<USER_REQUEST>
You are a Forensic Auditor agent.
Your working directory: <COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents\teamwork_preview_auditor_1
Original Request path: <COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents\ORIGINAL_REQUEST.md

Instructions:
1. Read <COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents\ORIGINAL_REQUEST.md.
2. Conduct a forensic integrity audit on the work product in `<COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents`.
3. Check for integrity violations:
   - Verify that all 15 `.agent.md` files were genuinely overwritten and sanitized, not mocked or hardcoded with dummy text.
   - Verify that file replacement and regex transformations were actually executed on the files on disk.
   - Audit for any hidden, un-sanitized absolute path leaks in all subdirectories or metadata files.
   - Confirm that no cheating, facade implementations, or fake verification outputs were used.
4. Document all evidence and forensic findings in `<COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents\teamwork_preview_auditor_1\audit.md` and handoff report `<COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents\teamwork_preview_auditor_1\handoff.md`.
5. Issue an explicit verdict: `CLEAN` or `INTEGRITY VIOLATION`.
6. Send a message back to the orchestrator with your verdict and handoff report reference.
</USER_REQUEST>
