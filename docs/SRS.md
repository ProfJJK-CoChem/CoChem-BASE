---
schema: cochem-srs/5.0
repo: ProfJJK-CoChem/CoChem-BASE
status: ACTIVE_CORE
pipeline_baseline: 5.0.0
source_commit: 98aaeba4a864e8487072b31e4ce1edd4a77335a5
decision_ref: swarm-1126-8efd, own-1127-05da, own-1127-dc8d
---

# CoChem-BASE Software Requirements Specification (SRS) — Pipeline 5.0.0 Canonical Edition

## 1. Purpose, Scope & System Classification

`CoChem-BASE` (`ProfJJK-CoChem/CoChem-BASE`, classification `ACTIVE_CORE`) is the foundational Python package, artifact ingestion boundary, host-setup bootstrapper, ecosystem module registry, shared canonical schema host, and local/student interface layer for the CoChem computational chemistry and rotational spectroscopy platform.

This document (`SRS-COCHEM-BASE-5.0.0`) is the **sole normative SRS** for `CoChem-BASE`, governed by signed Portal decisions `sys-1126-a3d4`, `swarm-1126-8efd`, `own-1126-84f4`, `own-1126-3019`, `swarm-1126-9fc4`, **`own-1127-05da`** (`a8479c2`, `dec-own-1127-05da-17e4e950`), and **`own-1127-dc8d`** (`b845b40`, `dec-own-1127-dc8d-ce69a437`).

### Executed Owner-Signed Governance Rulings (`2026-11-27`)

- **`own-1127-05da` (`a8479c2`):** Refined `ci_tools/anti_spoof_linter.py` `.patch` AST detection (`alias_resolved_receiver_or_chained_patch_family_or_call`), eliminating the 9 benign `fig.patch` / SemVer `.patch` false positives while preserving unconditional banned-mock and chained `.patch.*` enforcement; updated its single digest in `.core_infrastructure_hashring.json` with `.anti_spoof_amnesty.json` untouched (`[]`).
- **`own-1127-dc8d` (`b845b40`):** Wired the dynamic `CoChem-CURE` course provider into `scripts/module-distribution.json`, `src/cochem_base/cli.py`, `scripts/kraitchman_rs.py`, and `scripts/fact_ledger.py`, updating those exact 4 digests in `.core_infrastructure_hashring.json` (`250/250` hashring intact on `fix/zero-mock-authentic-engines`, `.anti_spoof_amnesty.json` strictly `[]`).

### Package Ownership & Distribution Requirements (`REQ-BASE-PKG`)

- **`REQ-BASE-PKG-01` (Single Distribution Owner):** `CoChem-BASE` MUST ship a real top-level `src/cochem_base/__init__.py` replacing PEP-420 implicit namespace packaging so downstream distributions (including `CoChem-SPYFY`) cannot shadow `cochem_base`.
- **`REQ-BASE-PKG-02` (Re-Export Parity):** `src/cochem_base/__init__.py` MUST expose `__version__`, `__author__`, `__license__`, `get_version()`, `check_runtime_environment()`, and lazy submodule re-exports without eagerly importing optional desktop GUI stacks (`PySide6`, `vtk`, `pyvista`).
- **`REQ-BASE-PKG-03` (Clean Wheel & Sdist Gate):** Clean wheel + sdist builds installed into an isolated virtual environment **without `PYTHONPATH`** MUST resolve `import cochem_base` inside `site-packages` and ship all JSON schema artifacts under `src/cochem_base/schemas/`.

## 2. Pipeline 5.0.0 Architecture Alignment & Resolved Conflicts

Every historical contradiction between legacy v4.x specifications and Pipeline 5.0.0 (`rev 2026-11-27`, `15x10 v5.0.2` routing matrix) is normatively resolved below:

| Conflict ID | Retired v4.x Claim | Normative Pipeline 5.0.0 Requirement |
|---|---|---|
| **CONTRA-01** | Legacy `classroom50` deployments, hosted GitHub Codespaces browser containers & GitHub Actions compute workflows | **Guardrail HC-1 (Zero GitHub Actions Compute Minutes; `classroom50` / Codespaces / Actions Compute Deprecated):** Scientific and course compute runs primarily via local **WSL2 Ubuntu** (`source ~/CoChem_Workstation_Direct/activate_cochem_wsl.sh`, `host-guard`, `<= 4` MPI ranks per `OWN-257`), Google Colab GPU (`w51`–`w58` via `colab-offload`), GCP Spot CPU (`c2d`/`c3d`/`c4d`), and Cloud Run `/mcp` (`https://cochem-control-plane-5bww6cxnyq-uc.a.run.app/mcp`) + Drive `cochem-mcp-mailbox-request/2`. |
| **CONTRA-02** | `CoChem-ORACLE` offline `llama.cpp` GGUF + ChromaDB RAG chat + GPU VRAM preemption | `CoChem-ORACLE` is redesigned (`swarm-1126-9fc4`) as a **100% deterministic, Zero-LLM Student Data Auditing Model** (zero-RAG, local-only FERPA-safe Student Publication-Readiness Audit Portal). |
| **CONTRA-03** | `DLPNO-CCSD(T)` / `DLPNO-CCSD(T1)/CBS` default coupled-cluster track | **`DLPNOExclusionFirewall`:** All new `DLPNO` submissions are strictly blocked in favor of canonical `CCSD` / `CCSD(T)` (CFOUR 2.1 / ORCA 6.1.1, including CHEM 490 workstation handoffs via `cochem_workstation_job_runner`), `CCSD(T)-F12b`, local WSL2 `ORCA 6.1.1 revDSD-PBEP86-D4/2021` + `VPT2`, `GPU4PySCF wB97X-V`, and verified MLFF screening (`MACE-OFF24`, `AIMNet2`, `SO3LR`). |
| **CONTRA-04** | Spectroscopy module registered as `'spycfit'` (`CoChem-SPYCFIT`) without `SURF` bridge | Canonical module identifier is **`'spyfy'`** (`CoChem-SPYFY`, incorporating the `GruLabRotSpec/SURF` 2–18 GHz CP-FTMW instrument bridge). Legacy `'spycfit'` is retained strictly as a deprecated alias emitting `DeprecationWarning`. |
| **CONTRA-05** | Phantom/retired modules (`UNITY`, `MInt`, `CORE`, `SYNAP`, `CROWN`, `DOCK`, `ORB`) listed as active | `core`, `mint`, `unity`, and `synap` consolidate into `'base'`. Phantom **`'dock'`** (`CoChem-DOCK`) is removed (`ValueError`). Empty **`'orb'`** (`CoChem-ORB`, LICENSE-only) has status **`UNIMPLEMENTED`** and dispatching `'orb'` MUST raise `NotImplementedError`. |
| **CONTRA-06** | Legacy queues (`__agentic/Gemini_Web_Tasks/01..06_lane_*`, `SRS_Inbox`, `mcp_mailbox/`, `g01..g22` `jobs/queue/`, `11x10` matrix) | All legacy 4.2.8 / v0 queues are **RETIRED**. Active orchestration uses the 3-Tier Scheduled Waterfall (`cochem-scheduled-prompt/1`), Drive Web-Harness (`cochem-mcp-mailbox-request/2`, `allowance_id: "A-2026-11"`), and the `15x10 v5.0.2` routing matrix. |
| **CONTRA-07** | Diverged local-only workstation runner SRS and uncoordinated `CoChem-Project-Access` fork | Compute submission follows `cochem-cloud-job-runner-500` (`OWN-117`) and `cochem_workstation_job_runner` for canonical CHEM 490 `CCSD`/`CCSD(T)` handoffs. Student Colab seats remain gated pending `src/cochem_base/interfaces/student_colab.py` / `src/cochem_base/interfaces/course_access.py` parity verification and owner admission sign-off. |
| **CONTRA-08** | Hardcoded monolithic course profiles embedded inside `CoChem-BASE` | **`CoChem-BASE` ↔ `CoChem-CURE` Split (`own-1127-dc8d`):** `CoChem-BASE` runs standalone with zero `CoChem-CURE` dependency by default; **`ProfJJK-CoChem/CoChem-CURE`** (pinned at `7432611286dc`) is the authoritative course provider loaded dynamically on demand via `cochem.course-provider/1`. |

## 3. Authoritative Scientific Engines, Methods & Method Matrix Constraints

`CoChem-BASE` provides authentic execution wrappers and chemical-regime guards across the Pipeline 5.0.0 engine stack with zero mocks and zero simulated outputs:

- **Authentic Engine Wrappers:** `src/cochem_base/calc/cfour_execution.py` (CFOUR 2.1 analytic CCSD(T)/VPT2, including open-shell support and unsupported-basis fail-closed gating), `src/cochem_base/calc/gpu4pyscf_execution.py` (GPU4PySCF v1.5.2 `wB97X-V`/`wB97M-V`), `src/cochem_base/calc/pyscf_execution.py` (CPU PySCF), `src/cochem_base/calc/xtb_execution.py` (GFN2-xTB), `src/cochem_base/calc/multiwfn_execution.py` (Multiwfn QTAIM/ELF), `src/cochem_base/calc/nbo7_execution.py` (authentic NBO7), and `src/cochem_base/spectroscopy/spcat_runner.py` (Pickett SPCAT).
- **CHEM 490 Local WSL2 & Workstation Research Track:** Local WSL2 workstations run ORCA 6.1.1 **`revDSD-PBEP86-D4/2021`** equilibrium geometries and **`VPT2`** anharmonic corrections (composite hybrid-DFT `B3LYP-D4/def2-TZVPP ! VPT2` or external displaced-`NumFreq` VPT2 around `revDSD-PBEP86-D4/2021`), plus CREST 3.0.2 (`--legacy --xnam "$(which xtb)" --nocross`). Higher-end canonical **`CCSD`** and **`CCSD(T)`** calculations are submitted via verified `cochem.student-handoff/2` bundles to **`cochem_workstation_job_runner`**, where **`DLPNOExclusionFirewall`** strictly prohibits `DLPNO-CCSD(T)`.
- **Chemical Regime & Method Matrix Guards:** `src/cochem_base/calc/regime_guards.py` blocks anion basis zeta/family downgrades and unphysical overrides; `src/cochem_base/cochem_catalog_compiler.py` traps prohibited `Calc_Hess true`; Method Matrix §4.4 requires explicit 5-threshold `%geom` tolerance blocks rather than shorthand `! TightOpt`.
- **Verified Citation Provenance:** `src/cochem_base/provenance/citations.py` maintains the DOI-verified BibTeX catalog consumed by downstream reporting (`CoChem-SCRIBE`).

## 4. Cross-Repo Interfaces, Contracts & Canonical Schemas

### Dynamic `CoChem-BASE` ↔ `CoChem-CURE` Course Provider Architecture (`own-1127-dc8d`)

- **Course Loader (`src/cochem_base/course_loader.py`):** Runs in standalone research mode by default with zero `CoChem-CURE` dependency and zero network/install calls on startup. When course mode is requested, dynamically loads `cochem_cure.provider` (`cochem.course-provider/1`) to retrieve authoritative course lists, profiles, milestones, and execution pathways.
- **Voilà `1 · Setup` Prompt (`ui/voila_layout/cochem_gui.py`, `ui/voila_layout/workspace_layout.py`):** Surfaces the **"Is this for a course?"** workflow prompt (`No` = standalone research workbench; `Yes` = dynamic `CoChem-CURE` course provider discovery and pathway binding).
- **CLI Integration (`src/cochem_base/cli.py`):** Provides `cochem-cli course-setup` and `cochem-cli install-addon cure` backed by the pinned distribution manifest.
- **Pinned Distribution Manifest (`scripts/module-distribution.json`):** Pins `cure` (`ProfJJK-CoChem/CoChem-CURE`) at revision `7432611286dc6e5e3e9159e55da5900c1ad36fc1` (`7432611286dc`, distribution `cochem-cure`, entry point `cochem_cure.provider:cure_provider`).
- **Dynamic Course Lookup in Handoff & Analysis Scripts:** `student/handoff.py` (`CHEM311`, `CHEM312`, `CHEM490` validation + atomic seal cleanup on failure), `scripts/kraitchman_rs.py`, and `scripts/fact_ledger.py` dynamically query `CoChem-CURE` course profiles when available and fail closed without fabricating profiles.

### Ecosystem Module Registry (`src/cochem_base/interfaces/module_registry.py`)

- `canonical_module_id("spyfy")` MUST return `"spyfy"` with zero warnings.
- `canonical_module_id("spycfit")` MUST return `"spyfy"` while emitting `DeprecationWarning`.
- `get_module_capability("orb")` MUST return `status == ModuleStatus.UNIMPLEMENTED` (`"UNIMPLEMENTED"`), and dispatching `"orb"` via `assert_module_dispatchable`, `dispatch_module`, `src/cochem_base/interfaces/artifact_handoff.py`, or `src/cochem_base/interfaces/module_execution.py` MUST raise `NotImplementedError`.
- `"dock"` (`CoChem-DOCK`) MUST be absent and raise `ValueError`.

### Shared Pipeline 5.0.0 DRAFT Canonical Schemas (`src/cochem_base/schemas/v500_canonical.py`)

All three schemas carry explicit `SCHEMA_STATUS = "DRAFT"` (`status_until_first_producer = "DRAFT"`) with versioned JSON Schema artifacts under `src/cochem_base/schemas/v500_json_schemas/` and fail-closed validation:

1. **`cochem-job-handoff/1` (`HANDOFF.json`):** Requires `job_id`, 64-hex `registry_sha256`, and non-empty `quantities` entries with explicit canonical physical `unit`, `value` (finite number or explicit `null` strictly paired with `value_status="PENDING"`), `source_file`, and 64-hex `source_sha256`.
2. **`cochem-quantities/1` (`QUANTITIES.json`):** Validates OWN-117 `consumes` (mandatory `source_path` + 64-hex `source_sha256`) and non-empty `produces` (mandatory boolean `required` + finite numeric `gates`).
3. **`cochem-portal-dossier/1.1`:** Validates Unified 6-Stage CoChem-Portal dossiers requiring 64-hex `matrix_sha256`, `stage3_evidence_hash`, `research_evidence_sha256`, non-empty `evidence_refs` with `source_sha256`, concrete `falsification_trigger`, explicit `consequence_class`, and `>= 2` unique lettered options.
4. **Fail-Closed Rules & Legacy Inventory:** Silent unit conversion, silent unit defaults, silent provenance defaults, missing-vs-`null` conflation, and unknown schema IDs MUST fail closed with redacted diagnostics. `src/cochem_base/schemas/legacy_handoff_inventory.json` catalogs `>= 20` legacy ecosystem HANDOFF schema IDs with explicit dispositions (`verified_adapter`, `quarantine`, `retire_with_evidence`).

## 5. Verification, Zero-Mock CI Gates & Acceptance Criteria

- **Zero-Mock & Mockup-Leak Firewall (`tests/test_zero_mock_and_no_sim_gate.py`):** `.anti_spoof_amnesty.json` MUST parse strictly to `[]`; 0 banned mock imports/aliases/monkeypatch/fake helpers, 0 fabricated `.ipynb` SCF outputs, and 0 tracked PNG/PDF `cochem:mockup=true` or `NOT SCIENTIFIC DATA` leaks. Refined `.patch` AST checks landed under signed ruling `own-1127-05da` (`a8479c2`).
- **Course Provider & Student Handoff Gate (`tests/test_course_loader_and_cure_integration.py`, `tests/test_student_handoff_v2_and_workflows.py`):** Verifies zero-network standalone default, Voilà `1 · Setup` "Is this for a course?" prompt, `cochem-cli course-setup` & `install-addon cure`, `scripts/module-distribution.json` pin (`7432611286dc`), dynamic `CoChem-CURE` lookup in `student/handoff.py`, `scripts/kraitchman_rs.py`, and `scripts/fact_ledger.py`, plus atomic `.zip`/`.sha256` seal cleanup (`own-1127-dc8d`, `b845b40`).
- **Registry & Package Gate (`tests/base/test_module_registry_v500.py`, `tests/base/test_module_handoff_contract.py`):** Verifies non-namespace `src/cochem_base/__init__.py` re-export parity, `'spyfy'`/`'spycfit'`/`'orb'`/`'dock'` semantics, and clean wheel + sdist import in an isolated venv without `PYTHONPATH`.
- **Canonical Schema Conformance Gate (`tests/test_v500_canonical_schemas.py`):** Verifies `DRAFT` status, `>= 20` inventoried legacy HANDOFF IDs, lossless roundtrip preservation of units / missing-vs-`null` / provenance, and fail-closed rejection of all negative fixtures.
- **Source Integrity Gate (`ci_tools/base_ci.py`):** Enforces clean Git checkout binding, reviewed 250-file `.core_infrastructure_hashring.json` verification, airgap sweep, and mass policy.

## 6. Verified Implementation Gaps, Known Holds & Non-Goals

- **Resolved — PR #38 Anti-Spoof `.patch` False Positives (`own-1127-05da`, `a8479c2`):** Resolved via owner-signed Portal ruling `own-1127-05da`; `fix/zero-mock-authentic-engines` passes release-mode `ci_tools/base_ci.py audit` with `250/250` hashring integrity and `.anti_spoof_amnesty.json == []`.
- **Pending Owner Governance Ruling — PR #39 Stacked-Branch Hashring Sign-Off (`3f84eb3`):** Commit `3f84eb3` on `feat/ecosystem-v500-consolidation` modified 3 files inside the 250-file `.core_infrastructure_hashring.json` (`pyproject.toml`, `src/cochem_base/interfaces/module_execution.py`, `src/cochem_base/interfaces/module_registry.py`) without mutating the ring. Updating those exact 3 digests requires a dedicated owner-signed `governance_own` Portal dossier before PR #39 promotes to `main` and passes release-mode `ci_tools/base_ci.py audit`.
- **Set 3 P10 Colab GPU Gate (`blind-s3-p10`):** Merge to `main` remains machine-blocked until Colab GPU parity job `blind.s3.hof.gpu4pyscf.wb97xv.p1` clears its active `OWNER_HOLD_COLAB_PRECLAIM_DIAGNOSIS` hold and passes without CPU fallback.
- **Deferred Scope & Non-Goals:** `CoChem-BASE` does not execute student PII grading in cloud context (FERPA processing remains strictly local via Ollama `gemma4`), does not ship desktop Qt/VTK binaries as required headless runtimes, and does not perform direct unverified `orb` execution.

## 7. Legacy Specification Disposition (Non-Normative Archive)

All historical v1–v3, monolithic, and chunk-proposal BASE SRS documents (`CoChem-BASE_SRS.md`, `CoChem-BASE_SRS_v2_Expanded.md`, `CoChem-BASE_SRS_v3_Expanded.md`, `CoChem_BASE_Master_Recovery_SRS.md`, `CoChem_BASE_Monolithic_SRS.md`, `.docs/SRS_Chunk_17_CoChem_BASE_Architecture.md`, `.docs/SRS_Chunk_Proposal_CoChem_BASE_Architectural_Review.md`) are formally classified as **NON-NORMATIVE ARCHIVE** in [`docs/archive/README.md`](archive/README.md). They are retained read-only for provenance and archaeology only and MUST NOT override this specification.
