# BASE SRS conformance — implementation and release evidence

Baseline: [Chunk 17](SRS_Chunk_17_CoChem_BASE_Architecture.md) **plus** [BASE proposal additions](SRS_Chunk_Proposal_CoChem_BASE_Architectural_Review.md), as selected by the user. Requirement numbers below belong to Chunk 17; the proposal uses the same numbers for different obligations. Its sixteen vectors and additional workflow obligations are tracked separately.

The user's scope clarification governs this pass: **BASE owns ingestion, setup, GUI and validated ecosystem integration**, within the 20-module system. Domain solvers belonging to future modules are not standalone BASE implementation obligations. BASE must faithfully validate their inputs, describe missing capabilities, preserve handoff evidence and avoid reporting unexecuted science as success. See [alpha scope and fixture corrections](BASE_Alpha_Scope.md).

Local runnable acceptance, downstream scientific acceptance and platform acceptance are separate. TOPOS/TORQ development is future repository work. ORCA 6.1.1 is installed and actual local calculations have run; hosted acceptance is recorded separately in [ORCA Actions setup](ORCA_Actions_Setup.md). CFOUR, GPU, Slurm, Codespaces and native-platform physical acceptance remain deferred pending the appropriate hosts/providers. The [1.0.0 release record](Release_1_0_0.md) separates current validation from publication. Neither authorization nor deferral turns an unexecuted check into a pass.

The previous snapshot (994 passed, 4 skipped, 1 failed) and its strict-scan counts are historical evidence under `/workspace/cochem-runtime/evidence/srs-pass2/`. This pass corrects the failed PES analysis, withdraws misleading fixture evidence, replaces legacy interface shells with versioned capability/handoff contracts, and replaces duplicated CI pipelines. Current-run counts and evidence follow below.

## Historical BASE alpha acceptance — 2026-10-06

The canonical `ci_tools/base_ci.py all` run on **2026-10-06** passed both gates:

- **1,189 tests passed, 4 external checks deferred, 0 failed**, from 1,193 collected tests in **391.21 seconds**. The 10,669 warnings are retained in the log, not suppressed. Deferrals are the actual ORCA R2/reference calculation, ORCA/CREST union and two physical Slurm-node checks.
- **Zero blocking findings** across production/CI source, selected-test source, mass policy and source/data airgap. The runner verified complete per-node outcomes and **no audited source change during testing**.
- The current retained test-source inventory has **559 automated flags in 121 existing test files**. **No flags refer to deleted legacy files; those items are resolved.** This includes 42 conditional-skip references in selected tests and 517 flags outside the profile. It is not a count of 559 confirmed code defects or an unfinished backlog for deleted code. See [current CI review](SRS_AST_Review.md) and the machine-readable audit.
- Actual Chromium acceptance passed **30 checks**, including xTB, PySCF, CREST, QE, isotope exports and verified future-module handoff download, with no page errors or failed requests. The separate focused GUI selection passed 52 tests; overlapping selections are not added to the canonical count.
- The **complete reusable installation script was rerun successfully**. All eleven setup phases republished genuine authority, retaining native xTB/CREST/g-xTB/MOPAC/QE and isolated PySCF/MACE. Explicit four-silo selection fixes the former lightweight-default capability loss. Setup remains truthfully degraded for unavailable licensed/host capabilities and the explicitly reduced disk workload profile.

Evidence is retained under `/workspace/cochem-runtime/evidence/base-alpha-2026-10-06/`: `summary.json`, `source-audit.json`, `pytest-outcomes.json`, `pytest.xml`, `test-acceptance.json`, source snapshots, actual setup/install logs and independent scientific-boundary review. CI-control-only acceptance separately passed 157 tests with no skips. The workflows at that revision passed `actionlint`; hosted execution had not been accepted at that snapshot. These counts are historical, not the final 1.0.0 suite count.

A subsequent reporting clarification reproduced the affine error scaling, removed the demo’s misleading “spectroscopic grade” display and verified **20 focused PES tests**, the actual numerical demo and the canonical source audit. It did not tune the fitter or change either energy-error result. The prior full-suite snapshot remains retained unchanged. Follow-up evidence: `/workspace/cochem-runtime/evidence/pes-and-retirement-clarification/`.

## Chunk 17 requirement traceability

| Requirement | Current implementation and evidence | Remaining scope |
|---|---|---|
| 001 — OS/hardware ingress | Measured Linux/cgroup CPU, RAM, instruction capabilities and bounded GPU discovery. Registry records unavailable capabilities instead of inventing them. | User-deferred host acceptance: Windows/WSL, macOS/OrbStack, Codespaces and actual GPU measurements. |
| 002 — micro-silos | All eleven Stage 0 phases execute. Core/UI/PySCF/ML package locks, interpreter isolation, import origins and `pip check` are verified before final registry publication. Partial phases cannot publish a completed master. | Accelerator variants and native platform combinations. This workspace explicitly uses a 1 GB free-disk workload profile; it does not meet the default 50 GB policy on its 32 GB filesystem. |
| 003 — canonical SWMR telemetry | Canonical `complexes.h5` writer/reader locks, commit counts, crash-tail recovery, and real coordinate/energy/gradient publication. Native calculation, T9, TOPOS, MLFF and Chain results now call the shared publisher. An incremental XYZ follower streams actual trajectory frames during execution. | Complete live gradient/trajectory coverage of every legacy adapter and all search-engine intermediate artifacts; distributed-filesystem guarantees need their actual filesystems. Chain also retains a separate campaign metadata/Hessian archive. |
| 004 — dynamic masses | Dynamic Mendeleev resolution, strict isotope assignments, principal isotopes for spectra, conformer screening, Chain and Stage 0. No fallback from unknown isotopes to atomic averages. | Exhaustive third-party/legacy interface coverage is not implied by the bounded numerical checks. |
| 005 — COM/Eckart ingress | Native calculations, TOPOS and Chain normalize ingress using exact isotope masses; proper rotation and residual gates are tested. Quantum decks retain sufficient coordinate precision after normalization. | Verification of every imported tensor/state frame and each external engine's independently rotated output remains required. |
| 006 — graph/geometric conformer sieve | WL graph/isomorphism, atom mapping, mass-weighted alignment, stricter Chunk 17 RMSD/rotation gates and proposal energy agreement `<0.05 kcal/mol`. Actual CREST plus ORCA GOAT water union passed, including HDF5 publication and durable promotion. | This bounded two-engine ingestion check does not implement the future TOPOS domain solver. |
| 007 — R1 frozen monomers | Wilson bond/angle/dihedral and linear-bending handling; all-frame monomer drift checks. Actual ORCA water-dimer R1 optimization passed with maximum monomer drift `6.1213138e-7 Å`. | `r2SCAN-3c` retains its published composite basis; no appended unrelated basis is accepted. One successful case does not certify every system’s coordinate or rotational accuracy. |
| 008 — R2 production | Actual ORCA canonical CCSD(T)/TZ-QZ reference generation, independent PySCF energy comparison and real five-leg R2 execution have been exercised. Source hashes, atom mapping, gradients, trajectory drift, achieved convergence and signed counterpoise evidence remain explicit. | Final accepted run status belongs in [scientific acceptance](ORCA_Scientific_Acceptance.md), separately from attempted execution. A finite-basis CBS estimate is not exact-CBS geometry certification. Higher-order R2 frequency/VPT2 providers remain downstream work. |
| 009 — grid lifecycle | Native models and Chain, including compound decks, enforce DEFGRID1 → DEFGRID2 → DEFGRID3 minima. T5/T7/T8 and frequencies cannot silently use a coarse grid. | Actual rotational/grid convergence requires independently executed solver outputs. Stage progression is not a proof of empirical integration error. |
| 010 — quintuple convergence | Required thresholds are emitted; achieved-value parsing rejects absent, incomplete, nonfinite or failed convergence. Chain cannot override geometry/resource policy through arbitrary raw blocks. | Actual coordinate and rotational-error targets need independent physical reference data. Configured tolerances cannot guarantee those errors for every molecule. |
| 011 — Hessian discipline | XTB2/Lindh/READ policy, forbidden exact initial Hessians, nonempty checkpoints, safe identifiers, unique basenames and geometry-bearing Hessian validation. Compound generation shares the same policy. | Real ORCA state-transfer and compound execution acceptance. A nonempty file alone is not proof that every external wavefunction format is valid. |
| 012 — dispersion | B3LYP/PBE0 require D3BJ/D4, including isolated molecules. VV10 plus empirical dispersion is rejected. Real B3LYP-D4 and wB97M-V calculations passed through DEFGRID1/2/3 with retained convergence/refinement evidence. | The measured combinations do not certify all functionals, molecules or empirical accuracy targets. |
| 013 — spin and T9 fallback | Inclusive 10% relative spin rejection and real isolated PySCF CASSCF/NEVPT2 recovery. Actual stretched H3 ORCA `<S²>=1.591697` was rejected and explicit CAS(3,3)/NEVPT2 recovered the doublet (`<S²>≈0.75`). CLI, GUI and Chain preserve the recovery contract. | Active spaces remain explicit. Single-point recovery does not complete an interrupted optimization/frequency request. Open-shell CFOUR diagnostics require its provider. |
| 014 — isotope transformations | Actual ORCA water Hessian ingestion and simultaneous 18O/D2 substitutions passed library/GUI parity, rigid-mode removal, unchanged-source and changed-geometry rejection checks, without new electronic calculations. | Harmonic mass scaling does not supply VPT2 `B0`; missing anharmonic corrections stay unknown. The minimal-basis example is integration evidence, not experimental frequency accuracy. |
| 015 — subprocess lifecycle | Actual Linux children/grandchildren, cancellation, affinity, owned-process cleanup and crash handling. TORQ no longer kills unrelated descendant processes at shutdown. | Actual Windows/macOS lifecycle and Slurm/GPU execution, including each scheduler/filesystem topology. |
| 016 — strict CI boundary | CI tools remain independent of application imports; structural checks and the canonical scanner verify source and actual test outcomes. | Deleted legacy findings are resolved. Retained test-source pattern flags remain a separate classification inventory, not proved production defects; counts belong to the exact [audit snapshot](SRS_AST_Review.md). |

## Additional proposal vectors

| Vector | Implementation/evidence | Outstanding acceptance |
|---|---|---|
| 1 — code/data separation | External artifact roots, source/symlink write guards and locked atomic configuration updates. | Native platform/filesystem coverage. |
| 2 — Golden Registry authority | Engine execution binds the actual executable path and SHA-256, package/interpreter evidence, CPU allocation, NUMA/affinity and memory bounds. Named scientific jobs cannot substitute a different command. | Every legacy external adapter must use that boundary. Checksums detect drift; they are not independent auditor signatures. |
| 3 — eleven-phase setup | All eleven phases completed against this workspace; measured IOPS, isotope precision, Eckart checks and silo evidence retained. Fake timings, fake default capacity and premature final publication removed. | Operational status is truthfully degraded for absent capabilities, with the explicit reduced disk workload profile. |
| 4 — atomic I/O/SWMR | Ten-second canonical locks, atomic registry replacement and committed HDF5 rows; actual readers/writers and recovery tests. | Full legacy archive migration and real distributed filesystems. |
| 5 — process groups/NUMA | Audited CPU/NUMA selection and owned process handles in native, TOPOS, Chain and MLFF routes. | Native Windows/macOS and actual cluster NUMA validation. |
| 6 — crash forensics | Exact return codes and last 256 stderr bytes, binary hash, real Git object identity/SHA-256 and observed resource metadata. Source manifests now have a real implementation instead of a self-importing wrapper. | Snapshot manifests require stable source and trusted reference records. No signed audit identity is invented. |
| 7 — resource guard/LTTB | Production Scribe now uses the canonical cgroup/available-memory/registry guard; `RESOURCE_GUARD=0` cannot bypass it. Prompt compression retains actual moments and at most 500 samples. | Authenticated remote API and GPU model acceptance. |
| 8 — constants | Shared CODATA conversion exports and required rotational conversion; discrepant formatter/propagation/Chain copies corrected. | Third-party numerical libraries retain their own documented versions. |
| 9 — quadrature | Chunk 17's three-stage sequence governs overlapping proposal language. | Real output-based grid/rotation acceptance. |
| 10 — stationary convergence | Emission and achieved-value gates are connected to execution. | Universal sub-mÅ/rotational accuracy is not established by thresholds alone. |
| 11 — Wilson freezing | Real derivative/nullspace mathematics, complete fragments and live trajectory integrity. | Licensed R1/R2 physical acceptance. |
| 12 — chained Hessians | Structured policy, checkpoint presence/content checks and output geometry agreement. | Actual cross-stage ORCA/CFOUR state transfer. |
| 13 — dispersion | Common sanitizer covers standalone and Chain inputs; actual B3LYP-D4/wB97M-V grid series passed. | Additional solver combinations and systems. |
| 14 — CREST/GOAT union | Actual CREST plus ORCA GOAT water union, graph/RMSD/rotation/energy gates, HDF5 publication and promotion passed. | Additional systems and future TOPOS domain acceptance. |
| 15 — multireference escalation | Real configured CASSCF/NEVPT2 execution after typed spin rejection. | Workflow-specific active spaces and completion of requested higher-order tasks. |
| 16 — principal isotope masses | Dynamic exact nuclides throughout the corrected scientific paths. | Complete external-interface review. |

The proposal workflow's **MACE-OFF24m ↔ g-xTB fallback is now executed**, not merely recommended: both directions ran on actual CPU backends, retained measured energies/gradients, recorded both attempts and wrote canonical telemetry. Corrupt checkpoint evidence aborts instead of being hidden by a fallback. Heavy libraries stay inside the ML silo. The exact official OFF24 medium v0.2 checkpoint is distinct from OFF23.

## Scientific and integration acceptance boundaries

1. **The PES failure had real implementation and analysis defects.** The corrected paired high-minus-low fit uses training-only centering for absolute energies and preserves dissociation-zero constraints for interaction energies. The unchanged 500-frame, 350/150 split gives **6.271842 cm⁻¹** for paired correction, against the unchanged **10 cm⁻¹** threshold. The predicted-low-plus-delta surface remains **319.863926 cm⁻¹**, and must not be certified or used as a validated standalone surface. The Cu/Ag/Au EMT data and affine target are now labeled correctly, with no ORCA/DFT/CCSD(T) or measured-timing claims. The artificial target is exactly `1.02 * E_EMT - 0.005 eV`, so the 6.27 correction error is 2% of the baseline error by construction. This verifies limited numerical behavior, not independent quantum spectroscopic accuracy. All 150 held-out geometries extend beyond the training Cu–Ag separation range; the 319.86 value is an energy-fitting RMSE (0.915 kcal/mol), not a predicted vibrational frequency.
2. **CFOUR/VPT2 belongs at an explicit scientific-provider boundary.** BASE owns complete validated input configuration, geometry/artifact hashes, required output evidence, capability discovery and pending handoff. Missing scientific adapters must not fabricate energies, anharmonic corrections, isotope `B0`, convergence or completed operations. Domain implementation and physical acceptance proceed with the corresponding ecosystem modules and licensed host.
3. **TOPOS/TORQ future work is recorded, not counted as a BASE-only solver deficit.** BASE retains its working native calculation, CREST, isotope inspector and scientific export flows, and provides validated future-module handoffs in the GUI. Full multidimensional PES exploration and domain workflows will be completed in their repositories. Accessibility and real platform acceptance remain bounded by actual tests.
4. **Product B now has direct BASE ingestion examples.** Ordered CIF and periodic JSON with fractional or Cartesian coordinates and explicit Angstrom/Bohr units preserve the periodic frame, original source hash and canonical converted structure hash. Singular/left-handed cells, duplicate lattice-equivalent sites, disorder/partial occupancy and invalid PAW inputs are rejected. The real registered QE PAW GaAs single point remains connected. Advanced bands, SOC, cell optimization and empirical accuracy claims need their scientific providers and benchmark evidence; ingesting a cell or executing one SCF does not certify them.
5. **CI must preserve failures as evidence.** Obsolete duplicated workflows and misleading physical fixtures are retired with recorded replacements. Selected test interface interception is migrated to actual child-process configuration. The canonical pipeline rejects missing/zero-test evidence, source changes during validation and unexpected skips. The wider legacy collection is inventoried explicitly, not claimed as executed or compliant.
6. **External acceptance requires actual execution evidence:** the user has authorized the ORCA 6.1.1 Actions pathway. Codespaces, CFOUR, GPU/Slurm, deployment filesystems and native platforms remain deferred. Existing local browser/lifecycle checks remain valid only for their local scope.

## Reproduction and retained evidence

```bash
source /workspace/cochem-runtime/activate.sh
python -m pip check
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python ci_tools/base_ci.py all --output /tmp/cochem-base-alpha-evidence
# Wider historical inventory, not an alpha acceptance substitute:
python ci_tools/anti_spoof_linter.py . --strict --json > /tmp/cochem-strict-repository-inventory.json
```

Final logs, JUnit, strict scans and a source manifest are retained together in `/workspace/cochem-runtime/evidence/srs-pass2/`. Session evidence also includes `/workspace/cochem-runtime/stage0-complete-audit.json`, `/workspace/cochem-runtime/topos-second-pass/`, `/workspace/cochem-runtime/mlff-second-pass/`, `/workspace/cochem-runtime/gui-srs-pass/` and `/workspace/cochem-runtime/chain-pass2-jt1upcd8/`. Runtime artifacts remain outside the repository. The self-contained cloud install script completed successfully, including all free-engine/ML checks and all eleven Stage 0 phases. The environment setup draft is saved for review; a fresh published/restored environment is a separate acceptance step. The repaired hosted lifecycle also completed setup twice in a separate external environment, passed 27 native CLI/lifecycle checks, all five workflow syntax checks, and actual Chromium interactions. That earlier local lifecycle report did not establish hosted acceptance; subsequent run-specific outcomes are recorded in ORCA_Actions_Setup.md.

A separate full-repository collection attempt discovered **4,416 tests and 237 collection errors** (`/tmp/cochem-all-collection-pass2.log`). These include missing sibling interfaces, legacy import paths and tests that import heavy libraries directly into BASE even though those libraries are installed in their required silos. This is not evidence that every low-compute test ran. An isolated built-wheel check imports the shipped CLI, GUI, frontend adapter, native setup service and provenance implementation without checkout paths or `.pth` processing.

This audit records implementation and measured evidence. It does not manufacture council approvals, scientific signatures, experimental reference data or a blanket conformance certificate.


## ORCA Actions integration follow-up

The user supplied the ORCA 6.1.1 private release and independently calculated
SHA-256 and authorized commit/push and hosted calculation acceptance. The pinned
installer, MPI runtime build, reusable action and real serial/parallel BASE CLI
acceptance are documented in [ORCA Actions setup](ORCA_Actions_Setup.md). ORCA
MPI rank/thread oversubscription was fixed in native, TOPOS, R2 and Slurm paths.

The fresh prepublication canonical local run passed **1,241 tests**, with the
same **4 external deferrals** and no failures, collected-node omissions,
unexpected skips or source changes. This supersedes the earlier local count;
it does not relabel earlier evidence or certify hosted ORCA execution. Evidence:
`/workspace/cochem-runtime/evidence/orca-actions-prepublication/`.

## Real ORCA and Classroom50 evidence — 2026-10-07

The strict local report
`/workspace/cochem-runtime/evidence/orca-scientific-acceptance-strict.json`
passed frozen R1 water-dimer optimization, the B3LYP-D4 and wB97M-V three-grid
series, and actual contaminated ORCA H3 rejection followed by explicit isolated
PySCF CAS(3,3)/NEVPT2 recovery. It preserves actual inputs/output hashes and
records `scientific_accuracy_established=false`.

The CREST plus ORCA GOAT water union passed in 155.19 seconds, including HDF5
publication and promotion. Canonical CCSD(T)/TZ-QZ reference energies were
independently reproduced with PySCF; the bounded H2 finite-basis CBS-estimate
geometry is not an exact-CBS or experimental accuracy certificate. Detailed
R2 convergence/counterpoise evidence is retained in
[scientific acceptance](ORCA_Scientific_Acceptance.md).

The real ORCA water Hessian passed library/GUI parent and 18O/D2 isotope parity
without a new SCF, with unchanged input-hash, rigid-mode, geometry-rejection and
missing-anharmonic-data checks. Evidence:
`/workspace/cochem-runtime/evidence/orca-hessian-gui-parity/acceptance.json`.
Actual Chromium also verified the Classroom50 Actions job download with no page
or request errors; its report explicitly states that no hosted calculation was
performed by the export test:
`/workspace/cochem-runtime/evidence/classroom-actions-ui/browser/browser-summary.json`.

The complete instructor/student procedure is the
[Classroom50 guide](GitHub_Classroom_ORCA_Setup.md). Final 1.0.0 canonical counts
and hosted results must refer to the final source revision; neither the earlier
1,189/1,241 counts nor overlapping targeted selections replace that validation.
