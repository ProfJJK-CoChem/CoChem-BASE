# Agent Council Engineering Dispatch Order: Task 5.3.2

**Task ID:** `TASK-5-3-2-ORCA-RECIPE-R2-DECK-GENERATION` `[GOV]` `[M]`  
**Council Session:** `COUNCIL-SESSION-056` `[GOV]`  
**Supervising Authority:** `0rchestrator` *(Council Presidium)*  
**Governance & SDPM Authority:** [`cochem-sdp-manager`](file:///C:/Users/ansac/.gemini/config/skills/agent-cochem-sdp-manager/SKILL.md)  
**Single Accountable Execution Agent:** [`cochem-coder`](file:///C:/Users/ansac/.gemini/config/skills/agent-cochem-coder/SKILL.md)  
**Asymmetric Auditing Authority:** [`adversary`](file:///C:/Users/ansac/.gemini/config/skills/agent-adversary/SKILL.md)  
**WBS Work Package:** 5.3.2 — *Publication-Grade ORCA Recipe R2 Deck Generation*  
**Predecessor Tasks:** 5.3.1 (Reference Monomer Ingestion & Wilson Constraints — RATIFIED `[M]`), 5.2.5 (RATIFIED `[GOV]`)  
**Target Source Filepath:** [`D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/calc/cochem_calc_input_generator.py`](file:///D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/calc/cochem_calc_input_generator.py)  
**Target Test Suite:** [`D:/__CoChem/GitHub-Repo/CoChem-BASE/tests/calc/test_recipe_r2_deck_generation.py`](file:///D:/__CoChem/GitHub-Repo/CoChem-BASE/tests/calc/test_recipe_r2_deck_generation.py)  
**Governing Charters:** Method Matrix v4.1, Anti-Spoofing Protocol v4, SWEBOK v3/v4, PMBOK 7th Edition, Mendeleev Library Mandate, Council Directives PCA-01, PCA-05, PCA-07, PCA-13, PCA-14, PCA-18  

---

## 1. Governance Rationale & RACI Role Segregation (PCA-05)

In strict adherence to Council Directive **PCA-05 (Strict Role Segregation & Dispatch Gate)** and the authoritative Work Breakdown Structure master [`task5_level2_wbs_breakdown.md`](file:///D:/__CoChem/.docs/task5_level2_wbs_breakdown.md) (Lines 93, 284–299):
1. **Governance & Specification Authority (`cochem-sdp-manager`):** Formulates the project management boundary, MECE work breakdown, acceptance criteria, and hardened prompt specification under PMBOK 7th Edition and SWEBOK standards.
2. **Code Implementation Authority (`cochem-coder`):** Exclusive accountability for physical codebase mutations, Python functions, data classes, and ORCA input deck generation. `cochem-sdp-manager` is strictly barred from code implementation.
3. **Verification Authority (`cochem-tester` / `cochem-audit` / `adversary`):** Independent testing and asymmetric verification. Implementing agents cannot verify their own code.

---

## 2. Technical Scope & Implementation Mandates

The Single Accountable Agent [`cochem-coder`](file:///C:/Users/ansac/.gemini/config/skills/agent-cochem-coder/SKILL.md) is tasked with implementing publication-grade ORCA Recipe R2 input generation in [`cochem_calc_input_generator.py`](file:///D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/calc/cochem_calc_input_generator.py):

### 1. Electronic Structure Keywords & Theory Discipline:
- **Theory Level:** `! wB97M-V def2-QZVPP def2/J RIJCOSX TightOpt TightSCF DEFGRID3` `[M]`
- **No External D3/D4:** External dispersion correction (`D3`, `D4`) is strictly forbidden for $\omega\text{B97M-V}$ because VV10 non-local correlation is built-in.
- **Integration Grid:** Enforce coupled `DEFGRID3` (special integration grid for high-precision density functional evaluations).

### 2. SCF Convergence Block:
- `TolE 1.0e-08`
- `Thresh 1.0e-11`
- `MaxIter 150`

### 3. Geometry Optimization & Hessian Preconditioning:
- `InHess XTB2` (Hessian preconditioning via xTB2 model Hessian; `Calc_Hess true` is strictly prohibited for initial optimization)
- **Quintuple Convergence Block:**
  - `TolE 1.0e-07`
  - `TolRMSG 3.0e-06`
  - `TolMaxG 1.0e-05`
  - `TolRMSD 5.0e-05`
  - `TolMaxD 1.0e-04`
  - `MaxIter 200`

### 4. Integration with Task 5.3.1 (Wilson Internal Coordinate Locking):
- Directly ingest reference $\text{CO}_2\cdots\text{H}_2\text{O}$ geometries and Wilson internal coordinate constraints from [`src/cochem_base/geometry/constraints.py`](file:///D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/geometry/constraints.py) (`formulate_recipe_r2_wilson_constraints`, `format_orca_frozen_monomer_constraints_block`).
- Format `%geom Constraints ... end end` locking exactly 6 intramolecular degrees of freedom (4 bonds, 2 angles, 0 dihedrals) while leaving all 6 intermolecular degrees of freedom fully unconstrained.

### 5. Counterpoise (CP) Distance Bracketing Flags:
- Support generation of Counterpoise correction flags and atom partition blocks for 3-leg distance bracketing non-covalent energy decomposition.

### 6. Dynamic Mendeleev Invariant:
- Dynamic mass and covalent radii queries via `from mendeleev import element`. Zero static mass/radii dictionaries.

---

## 3. Physical Acceptance Thresholds

1. **Syntax & Formatting:** Generated input deck strictly adheres to ORCA 6.x specification in [`SRS_Chunk_17.md`](file:///D:/__CoChem/__agentic/dropzones/inbox_srs/SRS_Chunk_17.md) §6.1 with zero syntax errors.
2. **Constraint Boundary:** Exactly 6 intramolecular constraints; 0 cross-monomer constraints.
3. **Monomer Integrity:** Initial geometric distortion strictly $< 10^{-12}\text{ \AA}$.
4. **Automated Test Suite:** `pytest tests/calc/test_recipe_r2_deck_generation.py` exits code 0 with 100% pass.
