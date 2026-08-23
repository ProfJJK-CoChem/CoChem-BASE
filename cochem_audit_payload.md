Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-TORQ\.in-progress\prompt_task11_spcat_bridge.md.
Original prompt:
# Prompt: The Symmetry & Statistics Router

**Target File:** `D:\__CoChem\GitHub-Repo\CoChem-TORQ\Libraries\cochem_spcat_bridge.py`

## Objective
Implement The Symmetry & Statistics Router for CoChem-TORQ based on Task 11 and Task 2 Phase 8 specifications.

## Instructions for Coder
1. Create or update `cochem_spcat_bridge.py` inside `Libraries/`.
2. Implement `vibrational_partition_coupling()` properly coupling the exact DVR rotational partition function with the vibrational partition function across temperature gradients, explicitly avoiding flawed decoupled RRHO approximations.
3. Implement `apply_symmetry_divisors()` utilizing the external `molsym` library to algorithmically detect the molecular point group and apply the correct rotational symmetry number divisor.
4. Implement `low_frequency_trap()` to intercept and isolate any harmonic frequency < 50 cm^-1, flagging them as suspected LAMs.
5. Enforce immutable CODATA 2022 constants for all statistical mechanics calculations (h, kB, c, C_rot).

## Constraints & Anti-Spoofing
- **One Script Policy**: Only create or modify `cochem_spcat_bridge.py`.
- **Zero Mocking**: Do NOT mock any statistical physics math. Use exact CODATA 2022 constants and implement the true partition function calculations.
- **Context-Safety**: Do not hallucinate imports. Limit dependencies to the `requirements.txt` environment for CoChem-TORQ (e.g. `molsym`).
- **Air-Gap Compliance**: The generated Python script MUST NOT write any data or logs to the repository space at runtime. Read and write strictly according to the paths defined dynamically.

Modified files content:

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.