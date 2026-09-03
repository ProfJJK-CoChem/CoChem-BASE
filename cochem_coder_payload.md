Cycle 3: Remediate HPC & Scaling (Part 1) per Adversarial Council Veto in D:\__CoChem\GitHub-Repo\CoChem-BASE.
Council Rejection Reasons (Cycle 2 FAILED):
1. 36 Mypy violations: Add cross-platform OS guards for POSIX process controls (os.killpg, os.getpgid, signal.SIGKILL, os.setsid) on Windows in src/cochem/runners/mpi_supervisor.py; fix Path type unions in src/cochem/runners/async_process_runner.py; add type annotations to all test functions.
2. 20 Ruff violations: Remove unused imports (F401), sort import blocks (I001), and fix exception chaining with 'raise ... from None' (B904).
3. Tripartite Storage violation: Ephemeral per-job scratch directories in AsyncProcessRunner.dispatch_task are created but never cleaned up on completion/exit. Enforce scratch cleanup.
4. Hardcoded GPU device_id=0: Make GPU device allocation dynamic.