---
schema: cochem-srs/5.0
repo: ProfJJK-CoChem/CoChem-BASE
status: ACTIVE_CORE
pipeline_baseline: 5.0.0
source_commit: f97fdd69b0d28943f0efd4cfdbb36699d2af9ba4
decision_ref: swarm-1126-8efd
---

# CoChem-BASE Software Requirements Specification (SRS) — Pipeline 5.0.0 Canonical Edition

## 1. Purpose, Scope & System Classification

`CoChem-BASE` (`ProfJJK-CoChem/CoChem-BASE`, classification `ACTIVE_CORE`) is the foundational Python package, artifact ingestion boundary, host-setup bootstrapper, ecosystem module registry, shared canonical schema host, and local/student interface layer for the CoChem computational chemistry and rotational spectroscopy platform.

This document (`SRS-COCHEM-BASE-5.0.0`) is the **sole normative SRS** for `CoChem-BASE`, governed by signed Portal decisions `sys-1126-a3d4`, `swarm-1126-8efd`, `own-1126-84f4`, `own-1126-3019`, and `swarm-1126-9fc4`.

### Package Ownership & Distribution Requirements (`REQ-BASE-PKG`)

- **`REQ-BASE-PKG-01` (Single Distribution Owner):** `CoChem-BASE` MUST ship a real top-level `src/cochem_base/__init__.py` replacing PEP-420 implicit namespace packaging so downstream distributions (including `CoChem-SPYFY`) cannot shadow `cochem_base`.
- **`REQ-BASE-PKG-02` (Re-Export Parity):** `src/cochem_base/__init__.py` MUST expose `__version__`, `__author__`, `__license__`, `get_version()`, `check_runtime_environment()`, and lazy submodule re-exports without eagerly importing optional desktop GUI stacks (`PySide6`, `vtk`, `pyvista`).
- **`REQ-BASE-PKG-03` (Clean Wheel & Sdist Gate):** Clean wheel + sdist builds installed into an isolated virtual environment **without `PYTHONPATH`** MUST resolve `import cochem_base` inside `site-packages` and ship all JSON schema artifacts under `src/cochem_base/schemas/`.

## 2. Pipeline 5.0.0 Architecture Alignment & Resolved Conflicts

Every historical contradiction between legacy v4.x specifications and Pipeline 5.0.0 (`rev 2026-11-20`, `15x10 v5.0.2` routing matrix) is normatively resolved below:

| Conflict ID | Retired v4.x Claim | Normative Pipeline 5.0.0 Requirement |
|---|---|---|
| **CONTRA-01** | Hosted Codespaces browser containers & GitHub Actions compute workflows | **Guardrail HC-1 (Zero GitHub Actions Compute Minutes):** Scientific compute runs strictly via local WSL2 (`host-guard`, `<= 4` MPI ranks per `OWN-257`), Google Colab GPU (`w51`–`w58` via `colab-offload`), GCP Spot CPU (`c2d`/`c3d`/`c4d`), and Cloud Run `/mcp` (`https://cochem-control-plane-5bww6cxnyq-uc.a.run.app/mcp`) + Drive `cochem-mcp-mailbox-request/2`. |
| **CONTRA-02** | `CoChem-ORACLE` offline `llama.cpp` GGUF + ChromaDB RAG chat + GPU VRAM preemption | `CoChem-ORACLE` is pivoted (`swarm-1126-9fc4`) to a **100% deterministic, zero-LLM, zero-RAG, local-only FERPA-safe Student Publication-Readiness Audit Portal**. |
| **CONTRA-03** | `DLPNO-CCSD(T)` / `DLPNO-CCSD(T1)/CBS` default coupled-cluster track | **`DLPNOExclusionFirewall`:** All new `DLPNO` submissions are blocked in favor of canonical `CCSD(T)` (CFOUR 2.1 / ORCA 6.1.1), `CCSD(T)-F12b`, `ORCA 6.1.1 revDSD-PBEP86-D4`, `GPU4PySCF wB97X-V`, and verified MLFF screening (`MACE-OFF24`, `AIMNet2`, `SO3LR`). |
| **CONTRA-04** | Spectroscopy module registered as `'spycfit'` (`CoChem-SPYCFIT`) without `SURF` bridge | Canonical module identifier is **`'spyfy'`** (`CoChem-SPYFY`, incorporating the `GruLabRotSpec/SURF` 2–18 GHz CP-FTMW instrument bridge). Legacy `'spycfit'` is retained strictly as a deprecated alias emitting `DeprecationWarning`. |
| **CONTRA-05** | Phantom/retired modules (`UNITY`, `MInt`, `CORE`, `SYNAP`, `CROWN`, `DOCK`, `ORB`) listed as active | `core`, `mint`, `unity`, and `synap` consolidate into `'base'`. Phantom **`'dock'`** (`CoChem-DOCK`) is removed (`ValueError`). Empty **`'orb'`** (`CoChem-ORB`, LICENSE-only) has status **`UNIMPLEMENTED`** and dispatching `'orb'` MUST raise `NotImplementedError`. |
| **CONTRA-06** | Legacy queues (`__agentic/Gemini_Web_Tasks/01..06_lane_*`, `SRS_Inbox`, `mcp_mailbox/`, `g01..g22` `jobs/queue/`, `11x10` matrix) | All legacy 4.2.8 / v0 queues are **RETIRED**. Active orchestration uses the 3-Tier Scheduled Waterfall (`cochem-scheduled-prompt/1`), Drive Web-Harness (`cochem-mcp-mailbox-request/2`, `allowance_id: "A-2026-11"`), and the `15x10 v5.0.2` routing matrix. |
| **CONTRA-07** | Diverged local-only workstation runner SRS and uncoordinated `CoChem-Project-Access` fork | Compute submission follows `cochem-cloud-job-runner-500` (`OWN-117`). Student Colab seats remain gated pending `src/cochem_base/interfaces/student_colab.py` / `src/cochem_base/interfaces/course_access.py` parity verification and owner admission sign-off. |

## 3. Authoritative Scientific Engines, Methods & Method Matrix Constraints

`CoChem-BASE` provides authentic execution wrappers and chemical-regime guards across the Pipeline 5.0.0 engine stack with zero mocks and zero simulated outputs:

- **Authentic Engine Wrappers:** `src/cochem_base/calc/cfour_execution.py` (CFOUR 2.1 analytic CCSD(T)/VPT2), `src/cochem_base/calc/gpu4pyscf_execution.py` (GPU4PySCF v1.5.2 `wB97X-V`/`wB97M-V`), `src/cochem_base/calc/pyscf_execution.py` (CPU PySCF), `src/cochem_base/calc/xtb_execution.py` (GFN2-xTB), `src/cochem_base/calc/multiwfn_execution.py` (Multiwfn QTAIM/ELF), `src/cochem_base/calc/nbo7_execution.py` (authentic NBO7), and `src/cochem_base/spectroscopy/spcat_runner.py` (Pickett SPCAT).
- **Chemical Regime & Method Matrix Guards:** `src/cochem_base/calc/regime_guards.py` blocks anion basis zeta/family downgrades and unphysical overrides; `src/cochem_base/cochem_catalog_compiler.py` traps prohibited `Calc_Hess true`; Method Matrix §4.4 requires explicit 5-threshold `%geom` tolerance blocks rather than shorthand `! TightOpt`.
- **Verified Citation Provenance:** `src/cochem_base/provenance/citations.py` maintains the DOI-verified BibTeX catalog consumed by downstream reporting (`CoChem-SCRIBE`).

## 4. Cross-Repo Interfaces, Contracts & Canonical Schemas

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

- **Zero-Mock & Mockup-Leak Firewall (`tests/test_zero_mock_and_no_sim_gate.py`):** `.anti_spoof_amnesty.json` MUST parse strictly to `[]`; 0 banned mock imports/aliases/monkeypatch/fake helpers, 0 fabricated `.ipynb` SCF outputs, and 0 tracked PNG/PDF `cochem:mockup=true` or `NOT SCIENTIFIC DATA` leaks.
- **Registry & Package Gate (`tests/base/test_module_registry_v500.py`, `tests/base/test_module_handoff_contract.py`):** Verifies non-namespace `src/cochem_base/__init__.py` re-export parity, `'spyfy'`/`'spycfit'`/`'orb'`/`'dock'` semantics, and clean wheel + sdist import in an isolated venv without `PYTHONPATH`.
- **Canonical Schema Conformance Gate (`tests/test_v500_canonical_schemas.py`):** Verifies `DRAFT` status, `>= 20` inventoried legacy HANDOFF IDs, lossless roundtrip preservation of units / missing-vs-`null` / provenance, and fail-closed rejection of all negative fixtures.
- **Source Integrity Gate (`ci_tools/base_ci.py`):** Enforces clean Git checkout binding, reviewed `.core_infrastructure_hashring.json` verification, airgap sweep, and mass policy.

## 6. Verified Implementation Gaps, Known Holds & Non-Goals

- **Golden-Master Hashring & Linter False Positives (PR #38):** `ci_tools/anti_spoof_linter.py` currently flags legitimate matplotlib `fig.patch` (`src/cochem_geom/interfaces/vibrations.py`) and SemVer `self.patch`/`other.patch` (`scripts/auto_version_bump.py`); resolving this requires a signed Portal decision updating `ci_tools/anti_spoof_linter.py` and its single entry in `.core_infrastructure_hashring.json`.
- **Set 3 P10 Colab GPU Gate (`blind-s3-p10`):** Merge to `main` remains machine-blocked until Colab GPU parity job `blind.s3.hof.gpu4pyscf.wb97xv.p1` clears its active `OWNER_HOLD_COLAB_PRECLAIM_DIAGNOSIS` hold and passes without CPU fallback.
- **Deferred Scope & Non-Goals:** `CoChem-BASE` does not execute student PII grading in cloud context (FERPA processing remains strictly local via Ollama `gemma4`), does not ship desktop Qt/VTK binaries as required headless runtimes, and does not perform direct unverified `orb` execution.

## 7. Legacy Specification Disposition (Non-Normative Archive)

All historical v1–v3, monolithic, and chunk-proposal BASE SRS documents (`CoChem-BASE_SRS.md`, `CoChem-BASE_SRS_v2_Expanded.md`, `CoChem-BASE_SRS_v3_Expanded.md`, `CoChem_BASE_Master_Recovery_SRS.md`, `CoChem_BASE_Monolithic_SRS.md`, `.docs/SRS_Chunk_17_CoChem_BASE_Architecture.md`, `.docs/SRS_Chunk_Proposal_CoChem_BASE_Architectural_Review.md`) are formally classified as **NON-NORMATIVE ARCHIVE** in [`docs/archive/README.md`](archive/README.md). They are retained read-only for provenance and archaeology only and MUST NOT override this specification.
