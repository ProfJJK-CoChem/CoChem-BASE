# BASE source integrity and CI review

The baseline is **SRS Chunk 17 plus proposal additions**, with the user's clarified scope: BASE supplies core services, setup, routing, interfaces and validated module handoffs. Future TOPOS/TORQ/CFOUR solvers and unavailable hosts are not represented as completed BASE calculations. Historical counts below retain their dates; current 1.0.0 evidence is tracked in the [release record](Release_1_0_0.md).

The canonical BASE source gate passes. **The inventory still flags retained test sources. Deleted legacy items are resolved.** These are distinct scopes, and neither static inspection nor a passing selected test profile proves arbitrary scientific accuracy.

## Reproducible acceptance

Run from the checkout with the prepared BASE interpreter. Evidence must be outside the checkout:

```bash
python -I -S ci_tools/base_ci.py audit --output /tmp/cochem-source-evidence
python ci_tools/base_ci.py controls --output /tmp/cochem-control-evidence
python ci_tools/base_ci.py all --output /tmp/cochem-alpha-evidence
```

`audit` imports no application code and works with only the standard library. It checks all production/CI paths (`src`, `cochem`, `ui`, `frontend`, `scripts`, `.scripts`, `cli.py`, `ci_tools`), selected acceptance-test sources, their `conftest.py` ancestry and statically imported local test helpers, the independent atomic-mass policy, and repository/runtime separation. No path amnesty or special linter/test-file exemption clears executable findings.

`controls` executes the bounded CI-control profile. `all` additionally executes the complete canonical local profile in `pytest.ini`; `pytest-srs.ini` must describe the same profile. Full local acceptance requires the real free-engine silos/checkpoints/native dependencies prepared for that profile, including MACE-OFF24, g-xTB, xTB, CREST, PySCF and QE where those tests request them. Missing free dependencies are failures through unexpected skips, not successful acceptance.

Actual per-node pytest evidence must cover every collected node exactly once with complete execution phases. Empty collection, failures, xfails, deselection, incomplete reporting and unexpected skips fail. Inherited `PYTEST_ADDOPTS` and `PYTEST_PLUGINS` cannot silently alter the run; plugin autoload is disabled and required plugins are explicitly selected. Source snapshots cover production, CI, configuration, all test sources and the exact immutable source inputs before and after execution. Changed source/input bytes fail acceptance. Snapshots are change-detection evidence, not external signatures.

[`ci_tools/deferred_acceptance.json`](../ci_tools/deferred_acceptance.json) names exact licensed/reference and physical Slurm prerequisites. A free-only environment may report an authorized missing prerequisite as an external omission, never a pass. Once actual engines/references are supplied, their physical tests must execute; the policy is not permission to skip available acceptance. Genuine ORCA/CREST union and other licensed local calculations have now run separately, as recorded in [scientific acceptance](ORCA_Scientific_Acceptance.md). Node IDs and skip reasons remain exact, and runtime outcomes determine which omissions actually occurred.

## Verified snapshot

Snapshot: **2026-10-06**, after the canonical CI migration.

| Inspected scope | Result |
|---|---|
| Production and CI anti-spoof findings | 0 |
| Selected-test source blockers | 0 |
| Atomic-mass policy findings | 0 |
| Airgap findings after exact immutable-input validation | 0 |
| Canonical CI-control execution | 157 passed; 0 skipped; no source changes |
| Current retained test-source inventory | 559 source-pattern findings in 121 existing test files; strict whole-tree exit remains nonzero |

Session evidence: `/tmp/cochem-ci-audit-final/source-audit.json` and `/tmp/cochem-ci-controls-final-verified/`. These temporary paths record actual runs, not committed success declarations. Full local-profile outcomes are maintained in the implementation status report; the CI-control count is not a substitute for them. Rerun after further changes.

A fresh reconciliation confirmed that all nine paths in the CI retirement manifest are absent. **Zero findings refer to retired or missing files.** Deleting those items resolved them; the remaining inventory is not a historical backlog for deleted code. All 559 flags occur under `tests/` (330 flags in 83 files) or `test_suite/` (229 flags in 38 files). Of these, 42 conditional-skip references occur in 14 selected-profile files; actual outcomes are governed by the exact runtime deferral policy. The other 517 flags occur in 107 retained files outside that profile. Some concern intentional negative inputs or scanner tests, so the count is not a count of confirmed defects. Reconciliation evidence: `/tmp/cochem-retained-source-reconciliation/source-audit.json`.

The retained test-source inventory contains:

| Category | Findings |
|---|---:|
| `MONKEYPATCH_INTERCEPT` | 347 |
| `PYTEST_SKIP` | 188 |
| `OBFUSCATION` | 10 |
| `SYNTHETIC_DATA` | 10 |
| `EMPTY_PASS_STUB` | 2 |
| `DEFAULT_CONVERGENCE` | 1 |
| `NOT_IMPLEMENTED_ERROR` | 1 |
| **Total** | **559** |

These are source-pattern findings, **not 559 proven runtime fabrications**. Retained tests include environment/interface interception, conditional suppression, obsolete ecosystem contracts and numerical validation inputs requiring contextual review. Deletion or replacement resolves an obsolete item; genuine tests should be classified and migrated rather than deleted merely to reduce an automated count. The canonical report retains their exact locations and does not certify or execute them. Intentionally negative source snippets used to test detectors are inspected as data, while actual executing mock/interception calls remain blockers in the selected profile.

## One canonical pipeline

[`.github/workflows/cochem_base_ci.yml`](../.github/workflows/cochem_base_ci.yml) now owns the source gate, actual cross-OS CI-control tests and the reusable bounded free-engine/dashboard acceptance workflow. The source gate runs in a Python `-I -S` process. The physical workflow retains real eleven-phase Stage 0 setup, isolated xTB/PySCF installation/calculations, CLI publication and rendered dashboard lifecycle checks.

GitHub's free-engine scope is bounded: it does **not** claim that the entire silo-dependent local profile ran on hosted hardware. Separate ORCA access, physical acceptance and student calculation workflows use the reviewed private distribution manifest. Actual licensed local calculations, browser export and installed-wheel checks now supply additional evidence; a hosted run must still establish its own setup/execution result. Native-platform/GPU/Slurm acceptance remains separately identified. See [ORCA Actions evidence](ORCA_Actions_Setup.md) for run-specific outcomes.

[`ci_tools/ci_migration.json`](../ci_tools/ci_migration.json) records the retired duplicate BENCH/SCRIBE workflows, orphaned historical linter patch, misleading uncalled log “sanitizer”, stale self-issued hashrings, and duplicate tests of the old inline workflow logic. Meaningful format/configuration/entropy checks now call the canonical implementation instead of reproducing scanner algorithms inside tests. `verify_core_integrity.py` remains a compatibility entrypoint to the canonical audit; it cannot generate an accepting baseline. Administrative cleanup/classification utilities and the older extension-only scanner are explicitly supplementary, not additional scientific acceptance pipelines.

## Rules and substantive fixes

The structural guard rejects mock imports/use and aliases, executing interface/environment replacement, generated arrays or literal values promoted into successful physical results, unreported convergence defaulted to true, empty implementations, circular self-reexports, unimplemented callable endpoints and application imports in CI. It does not ban legitimate concurrency imports, numerical grids or accumulators. Computed matrix contributions clear allocation-only provenance; literal writes do not launder a generated result into accepted evidence. Positive and adversarial tests cover these distinctions.

The independent mass guard no longer honors built-in/user path amnesty or inline suppression. Read/parse/missing-target failures and disguised static mass tables remain visible. Genuine provider imports are distinguished from aliases that merely borrow authoritative names.

Concrete evidence defects corrected during this work include:

- TORQ no longer labels an HDF5 tensor archive as an ORCA GBW checkpoint. Missing/nonfinite energy or gradients fail parsing; convergence and VRAM remain unknown when absent. Cleanup handles only owned processes. These tests establish boundary behavior, not native ORCA acceptance.
- GEOM results no longer default to successful convergence, unobserved timing/steps, zero energy, a small invented gradient norm, or unreported software/constants provenance.
- Embedded Scribe, formatter, bootstrap, environment/path and selected CI tests use actual child environments and real processes instead of substituting executing interfaces. Native watchdog dispatch was verified with a real OS observer.
- Circular legacy interface shells were replaced by a BASE capability registry and explicit validated artifact handoffs. A pending future integration does not expose a fabricated result or count as a completed module solver.
- Three legacy NPY/NPZ “reference” artifacts were removed from source acceptance after history showed EMT Hessians with incorrect unit assumptions and manufactured calibration uncertainty/noise. Remaining geometry inputs have explicit limited provenance; H2CO species labels were corrected to the generator's atom order.

[`ci_tools/source_fixtures.json`](../ci_tools/source_fixtures.json) permits only exact SHA-256-pinned test/example input bytes with purpose and provenance. There is no folder exemption. The recorded xTB trajectory is identified as genuine historical engine output; replaying it is parser/transport validation, not another live calculation. Other coordinates are mathematical/structural inputs with known EMT or unverified origins, never ab initio accuracy references.

The optional SDK installed here is `google-genai==2.28.0`, persisted through the `scribe` dependency extra with `zstandard`; watchdog is included in UI requirements. SDK construction does not establish authenticated remote inference. Scientific reference accuracy and unavailable external execution still require their own evidence.
