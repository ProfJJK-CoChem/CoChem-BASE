# Agent Council Engineering Dispatch Order: Task 5.4.1 & Task 5.R.1

**Task ID:** `TASK-5-4-1-SEQUENTIAL-PERSONA-DISPATCH-AND-STAGE-MACHINE-HANDSHAKE` `[GOV]` `[M]`  
**Council Session:** `COUNCIL-SESSION-057` `[GOV]`  
**Supervising Authority:** `0rchestrator` *(Council Presidium)*  
**Presiding Governance & SDPM Authority:** [`cochem-sdp-manager`](file:///C:/Users/ansac/.gemini/config/skills/agent-cochem-sdp-manager/SKILL.md)  
**Single Accountable Execution Agent (Task 5.4.1):** `0rchestrator` *(Sequential Persona Dispatch & Stage Machine Handshake)*  
**Single Accountable Execution Agent (Task 5.R.1):** [`cochem-sdp-manager`](file:///C:/Users/ansac/.gemini/config/skills/agent-cochem-sdp-manager/SKILL.md) *(Level 3 Risk Mitigation WBS Decomposition)*  
**Asymmetric Auditing Authority:** [`cochem-audit`](file:///C:/Users/ansac/.gemini/config/skills/agent-cochem-audit/SKILL.md) *(Subagent `a856c8a2-52da-4465-ad69-bbb91c25693e`)*  
**WBS Work Packages:** 5.4.1 (*Sequential Persona Dispatch & Stage Machine Handshake*) & 5.R.1 (*Level 3 Risk Mitigation WBS Decomposition*)  
**Predecessor Tasks:** 5.3.2 (Publication-Grade ORCA Recipe R2 Deck Generation — RATIFIED `[M]`), 5.3.1 (RATIFIED `[M]`), 5.2.5 (RATIFIED `[GOV]`)  
**Target Source/State Filepaths:** [`swarm_state.json`](file:///D:/__CoChem/swarm_state.json), [`ci_tools/zero_trust_runner.py`](file:///D:/__CoChem/GitHub-Repo/CoChem-BASE/ci_tools/zero_trust_runner.py), [`ci_tools/process_runner.py`](file:///D:/__CoChem/GitHub-Repo/CoChem-BASE/ci_tools/process_runner.py)  
**Governing Charters:** Method Matrix v4.1, Anti-Spoofing Protocol v4, PMBOK Guide 7th Edition, SWEBOK v3/v4, Council Directives PCA-01, PCA-05, PCA-07, PCA-13, PCA-14, PCA-16, PCA-18, Mendeleev Library Mandate  

---

## 1. Governance Rationale & WBS Collision DEF-01 Resolution

### 1.1 Forensic Analysis of Defect DEF-01
Under prior deliberations, candidate dispatch prompts attempted to assign WBS code `5.4.1` to [`cochem-sdp-manager`](file:///C:/Users/ansac/.gemini/config/skills/agent-cochem-sdp-manager/SKILL.md) for decomposing the Risk Register (RSK-CHUNK17-01 to RSK-CHUNK17-06). As formally audited and rejected by [`cochem-audit`](file:///C:/Users/ansac/.gemini/config/skills/agent-cochem-audit/SKILL.md) in [`adversarial_audit_task5_4_1_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/adversarial_audit_task5_4_1_prompt.md) (§2 Finding 1), this caused a critical WBS hierarchy collision:
1. **WBS Code Hijacking:** The authoritative WBS master [`task5_level2_wbs_breakdown.md`](file:///D:/__CoChem/.docs/task5_level2_wbs_breakdown.md) (Lines 96, 338–354) ratifies Task 5.4.1 as **"Sequential Persona Dispatch & Stage Machine Handshake"**, with single accountability assigned exclusively to `0rchestrator` `[GOV]`.
2. **Scope Distortion:** Repurposing 5.4.1 distorted Level 2 Task 5.4 away from the statutory **Sequential Adversarial Swarm Council Audit** and broke automated verification tooling (`ci_tools/path_scoped_hash_gate.py`, `ci_tools/anti_spoof_linter.py`).

### 1.2 Statutory Resolution & Code Disambiguation
Under Council Session 057, Defect DEF-01 is permanently resolved through atomic WBS code disambiguation:
1. **Task 5.4.1 Reaffirmation:** Task 5.4.1 remains cleanly and exclusively assigned to `0rchestrator` for coordinating the sequential stage machine handshake across Council personas (`cochem-coder` $\rightarrow$ `cochem-tester` $\rightarrow$ `cochem-audit` $\rightarrow$ `adversary` $\rightarrow$ `cochem-sdp-manager`).
2. **Task 5.R.1 Codification:** The Level 3 Risk Mitigation WBS Decomposition covering RSK-CHUNK17-01 through RSK-CHUNK17-06 is designated as **Task 5.R.1**, with exclusive accountability assigned to [`cochem-sdp-manager`](file:///C:/Users/ansac/.gemini/config/skills/agent-cochem-sdp-manager/SKILL.md).
3. **Task 5.R.2 Codification:** Downstream architectural defense specification and quantitative acceptance criteria definition are codified under **Task 5.R.2** (referenced in `5.4.2_prompt.json`).
4. **Strict RACI Boundaries (Council Directive PCA-05 & Disciplinary Ruling D1-01):**
   - [`cochem-sdp-manager`](file:///C:/Users/ansac/.gemini/config/skills/agent-cochem-sdp-manager/SKILL.md) is restricted strictly to PMBOK/SWEBOK governance, WBS deconstruction, and acceptance criteria specification. `cochem-sdp-manager` is **strictly barred from modifying Python code in `src/` or executing tests in `tests/`**.
   - Code implementation is reserved strictly for [`cochem-coder`](file:///C:/Users/ansac/.gemini/config/skills/agent-cochem-coder/SKILL.md).
   - Test execution is reserved strictly for [`cochem-tester`](file:///C:/Users/ansac/.gemini/config/skills/agent-cochem-tester/SKILL.md).
   - Asymmetric audit is reserved strictly for [`cochem-audit`](file:///C:/Users/ansac/.gemini/config/skills/agent-cochem-audit/SKILL.md) and [`adversary`](file:///C:/Users/ansac/.gemini/config/skills/agent-adversary/SKILL.md).

---

## 2. Authoritative Execution Specification for Task 5.R.1

The Designated Governance Agent [`cochem-sdp-manager`](file:///C:/Users/ansac/.gemini/config/skills/agent-cochem-sdp-manager/SKILL.md) is ordered to execute Task 5.R.1 under the following mandatory directives:

### Mandatory Operational Directive 1: Context Ingestion via Read Tools
Prior to drafting, execute tool-based physical inspection across authoritative files:
1. `D:/__CoChem/__agentic/dropzones/inbox_srs/SRS_Chunk_17.md` (§1.1, §1.2 8D Ledger, §2.2, §5, §6.1).
2. `D:/__CoChem/GitHub-Repo/CoChem-BASE/tests/test_chunk17_verification_suite.py` (VR-01 through VR-06).
3. `D:/__CoChem/.docs/task5_level2_wbs_breakdown.md` (§3 Task Matrix, §4.4 Task 5.4, §5 Risk Register).
4. `C:/Users/ansac/.gemini/antigravity-cli/scratch/adversarial_audit_task5_4_1_prompt.md` (§2 Findings DEF-01 to DEF-04, §2.4 Quantitative Anchors).
5. `D:/__CoChem/GitHub-Repo/CoChem-BASE/ci_tools/process_runner.py` (UTF-8 encoding enforcement).
6. `D:/__CoChem/GitHub-Repo/CoChem-BASE/ci_tools/path_scoped_hash_gate.py` (LF stream normalization).
7. `D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/calc/cochem_calc_input_generator.py` (Hessian preconditioning).
8. `D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/analysis/electronic_sanitizer.py` (Dispersion validation).

### Mandatory Operational Directive 2: Direct Physical Disk Persistence
Persist all deliverable markdown specifications directly to physical disk across canonical mirrors:
- `C:/Users/ansac/.gemini/antigravity-cli/scratch/task5_l3_risk_implementation_tasks.md`
- `D:/__CoChem/.docs/task5_l3_risk_implementation_tasks.md`
- `D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/task5_l3_risk_implementation_tasks.md`
- `D:/__CoChem/__agentic/dropzones/inbox_srs/task5_l3_risk_implementation_tasks.md`

### Mandatory Technical Invariants (RSK-CHUNK17-01 to RSK-CHUNK17-06):
1. **RSK-CHUNK17-01 (CP1252 Charmap Crash):** Mandate `sys.stdout.reconfigure(encoding="utf-8")` and `sys.stderr.reconfigure(encoding="utf-8")` at all Python entrypoints; enforce `encoding="utf-8", errors="strict"` in `ci_tools/process_runner.py`. Zero tolerance for Unicode replacements.
2. **RSK-CHUNK17-02 (CRLF vs LF Hashring Drift):** Binary stream LF normalization (`.replace(b"\r\n", b"\n")`) in `ci_tools/path_scoped_hash_gate.py` before SHA-256 calculation.
3. **RSK-CHUNK17-03 (Symmetry Automorphism Invariance):** Center-of-mass translation zeroed ($\|\sum m_i \mathbf{r}_i\| < 10^{-12}\text{ a.u.}$); proper rotation verification ($\det(\mathbf{U}) = +1.0$); permutation automorphism orbits ($C_{2v}, C_{3v}$) evaluated prior to Kabsch RMSD alignment; dual acceptance gates: Kabsch $\text{RMSD} < 0.08\text{ \AA}$ and $|\Delta B/B| \le 0.05\%$.
4. **RSK-CHUNK17-04 (Initial Hessian Force Constant Discipline):** Extend `MoleculeInput` schema with `in_hess_type: str = "XTB2"`; parameterize cascaded optimization `%geom InHess READ InHessName "<stage>.opt" end`; strict ban on `Calc_Hess true` during geometry optimization.
5. **RSK-CHUNK17-05 (Counterfeit Compliance in Benchmark Execution):** Frozen Monomer Protocol Wilson constraints on $\text{CO}_2\cdots\text{H}_2\text{O}$; monomer internal drift $\Delta r < 1.0 \times 10^{-6}\text{ \AA}$; maximum residual gradient $\|\mathbf{g}_{\text{residual}}\|_{\infty} \le 1.0 \times 10^{-4}\text{ a.u.}$; verification via `ci_tools/zero_trust_runner.py` in sterile quarantine with real OS PID telemetry.
6. **RSK-CHUNK17-06 (Redundant Dispersion Overcounting):** `ElectronicSanitizer.validate_dispersion_pairing` must raise fail-closed `RedundantDispersionError` when $\omega\text{B97M-V}$ is paired with empirical D3/D4 dispersion.

---

## 3. Sequential Stage Machine Handshake Protocol (Task 5.4.1)

Under `0rchestrator` leadership, the sequential handoff sequence executes without concurrent thread interference:
1. **Stage 1 (Governance):** `cochem-sdp-manager` delivers Task 5.R.1 / Task 5.R.2 specifications to `.docs/`.
2. **Stage 2 (Implementation):** `cochem-coder` implements underlying hooks in `ci_tools/` and `src/cochem_base/`.
3. **Stage 3 (Testing):** `cochem-tester` executes real integration verification suite in `tests/test_chunk17_verification_suite.py`.
4. **Stage 4 (Asymmetric Quarantine Audit):** `cochem-audit` executes `zero_trust_runner.py` in sterile temporary quarantine `/tmp/cochem_exec_<uuid>/` under Task 5.4.2.
5. **Stage 5 (Red-Team Hostile Penetration):** `adversary` evaluates AST tokens, proof-of-work receipts, and temporal causality under Task 5.4.3.
6. **Stage 6 (Final Deliberation & Ratification):** `cochem-sdp-manager` and `0rchestrator` author final closeout ratification under Task 5.4.4.

---

## 4. Auditor Reporting Mandate (Rule 3 Compliance)

The completing agent must conclude execution with an authoritative report structured as:
```text
[SDPM REPORT: TASK 5.R.1 COMPLETE]
Status: COMPLETED_PENDING_COUNCIL_AUDIT
Governing Baseline: Method Matrix v4.1 / Anti-Spoofing Protocol v4
MODIFIED FILE MANIFEST: <table with paths, bytes, lines, sha256>
SUMMARY OF ARCHITECTURAL DEFENSES DEFINED: <RSK-01 to RSK-06>
DOWNSTREAM DELEGATION & COUNCIL HANDOFF: <cochem-coder / cochem-tester / cochem-audit>
```
