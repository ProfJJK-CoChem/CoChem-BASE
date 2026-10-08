# BASE SRS conformance — implementation and release evidence

Baseline: [Chunk 17](SRS_Chunk_17_CoChem_BASE_Architecture.md) **plus** [BASE proposal additions](SRS_Chunk_Proposal_CoChem_BASE_Architectural_Review.md), as selected by the user. Requirement numbers below belong to Chunk 17; the proposal uses the same numbers for different obligations. Its sixteen vectors and additional workflow obligations are tracked separately.

The user's scope clarification governs this pass: **BASE owns ingestion, setup, GUI and validated ecosystem integration**, within the 20-module system. Domain solvers belonging to future modules are not standalone BASE implementation obligations. BASE must faithfully validate their inputs, describe missing capabilities, preserve handoff evidence and avoid reporting unexecuted science as success. See [alpha scope and fixture corrections](BASE_Alpha_Scope.md).

The current published stable version is 1.0.1. The student no-code entry point and the broader ingestion corrections are **1.1 release-candidate work**, tracked in [PR 10](https://github.com/ProfJJK-CoChem/CoChem-BASE/pull/10), the [complete obligation trace](SRS_Student_1_1_Conformance_Trace.md), and the [student workflow](Student_Research_No_Code.md). Current working-tree changes are not a published student release. Historical 1.0.1 results below cannot qualify changed 1.1 source.

The current review covers molecular formats and all contained records, isotope/state identity, conformer pools, periodic cells/PAW inputs, measured Hessians, spectroscopy, trajectory/property archives and native result ingestion. Student monomer/complex geometry is one supported research path, not the complete ingestion specification. BASE manages the approved module installations, source updates, execution routes and result interface; students use its GUI rather than install module repositories or execute setup code.

Local runnable acceptance, downstream scientific acceptance and platform acceptance remain distinct. ORCA 6.1.1 and the approved CFOUR 2.1 runtime have genuine historical Linux CPU and hosted calculations; see [ORCA setup](ORCA_Actions_Setup.md) and [CFOUR setup](CFOUR_Actions_Setup.md). Both engines remain optional and strongly recommended: missing installations disable dependent local operations while BASE and installed free engines remain usable. Current 1.1 native acceptance and the final immutable complete profile must be bound to the final revised source. Unavailable NBO/NAO, VPT2/anharmonic and additional Product B providers remain unavailable; placeholders do not fulfill their physical acceptance. GPU, Slurm, other native platforms and a real student-identity Classroom50/fresh Codespace pilot retain their separate acceptance. See the [deployment checklist](Student_Deployment_Pilot.md).

Current hosted 1.1 jobs are blocked before execution by GitHub organization billing/spending-limit enforcement. This environment's Codespaces creation API also returns HTTP 403. Neither is a passing platform check. The [1.0.1 closure record](Release_1_0_1.md) and [1.0.0 record](Release_1_0_0.md) remain historical. Neither authorization nor deferral turns an unexecuted check into a pass.

The previous snapshot (994 passed, 4 skipped, 1 failed) and its strict-scan counts are historical evidence under `/workspace/cochem-runtime/evidence/srs-pass2/`. This pass corrects the failed PES analysis, withdraws misleading fixture evidence, replaces legacy interface shells with versioned capability/handoff contracts, and replaces duplicated CI pipelines. Current-run counts and evidence follow below.

Instructors should follow the [Classroom50 assignment deployment guide](Classroom50_Assignment_Deployment.md)
for the release template, approved access, assignment creation, one-student
pilot and course rollout. It links the engine/module setup guides and preserves
the distinction between public release evidence and institution-specific
student acceptance.

## Historical 1.0.1 validation and gap closure

The 2026-10-07 final SRS audit identified four connected BASE gaps: automatic
measured-gradient grid progression, authentic live derivative records, general
isotope-label ingress/handoff and persisted native-runner crash provenance.
Their implementation and revision-specific acceptance are tracked in the
[1.0.1 closure record](Release_1_0_1.md). The current complete-profile result
below is separate from the historical results later in this document.

The complete-profile source is `583a6d22db0fab0fdd54d2659ceac87ba82fa48a`.
Its application/workflow/devcontainer source matches accepted `7144f82` and
`80dfec3`; the correction changes only a GUI acceptance test and hosted selection.
[Hosted CFOUR acceptance 37704401496](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37704401496)
passed ten genuine native cases plus an `18O`/D2O input-isotopologue harmonic
and Hessian-ingestion case. The [student-style CFOUR job](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37704003113)
passed on application-equivalent `80dfec3`. The approved build is OpenMP-enabled
and MPI-disabled; VPT2, open-shell and correlated derivatives remain separately
scoped providers.

[Hosted ORCA acceptance 37703993551](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37703993551)
passed physical serial/parallel checks and three genuine SRS completion cases:
three-grid progression, labelled harmonic/Hessian ingestion and native xTB
optimization. They retained seventeen, seven and eleven Cartesian-gradient
evaluations. The [student ORCA calculation](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37704000193)
also passed on `80dfec3`. Source comparison verifies 2,101 identical
production/workflow/test blobs to `7144f82`; the only helper differences do not
change the ORCA scientific path. A redundant cancelled run is not acceptance.

[Hosted public CI at `583a6d2`](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37706334481)
passed source integrity, Ubuntu/macOS/Windows controls and isolated-wheel
checks, **883 bounded regressions** with no failures, skips, deferrals, coverage
errors or source changes; all 1,368 source-snapshot entries matched the frozen
Git blob. Real
free-engine/derivative checks, all eleven Stage 0 phases and rendered dashboard
lifecycle also passed. The [earlier 869-test hosted run](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37704370113)
at `7144f82` remains separately retained. The complete canonical profile at
exact `583a6d2` passed **1,827 tests** out of **1,829 collected**, with **two
exact physical Slurm deferrals**, **zero failures or unexpected skips**, and
10,672 retained warnings in 879.89 seconds. Audit/test gates passed with no
coverage errors; all 1,368 source/input snapshots matched the frozen Git blob
and remained unchanged. Evidence is retained under
`/workspace/cochem-runtime/evidence/srs-1.0.1-complete-final-v3/` in
`summary.json`, `test-acceptance.json` and the actual pytest XML report.
Independent comparison confirms all 511
production/UI/native-workflow/source-integrity paths identical to accepted
`7144f82`/`80dfec3`. The corrected focused GUI selection passed 14 tests;
it resolves the final manifest-bound result while validating genuine derivative
records. Earlier incomplete/failed profiles are retained, not reported as
passes. Verify final merged-source builds, uploaded assets and non-draft
`v1.0.1` publication through the actual release entry and attached validation
report/checksums described in the [release record](Release_1_0_1.md); the
passing profile does not itself establish publication.

A genuinely fresh local configured Bookworm container passed the version-1.0.1
interface, all eleven Stage 0 phases, strict isotope CLI JSON and real free-xTB
energy/Hessian checks with ORCA/CFOUR absent. Its 2,104 tracked files remained
unchanged. The captured `80dfec3` application/GUI/devcontainer bytes match
`7144f82` and `583a6d2`; subsequent changes affect only CI transport/selection
and a GUI test. This local evidence does not
replace the real student-identity [deployment pilot](Student_Deployment_Pilot.md).
Native D/T Chain execution also retained six genuine Cartesian gradient
vectors and isotope identity. Stale checked-in package metadata is removed;
source and installed version checks now use the canonical release metadata.

## Historical 1.0.0 acceptance — 2026-10-07

The complete canonical profile passed **1,532 tests**, with **2 exact physical
Slurm skips**, **0 failures**, **1,534 collected** and **10,672 retained warnings**
in **950.50 seconds**. The source audit passed, all collected-node outcomes were
accounted for, and no audited source/input bytes changed during execution.
The remaining skipped checks require an actual Slurm allocation; they are not
successful platform acceptance. Real R2 and CREST/GOAT checks now execute.
Evidence: `/workspace/cochem-runtime/evidence/base-1.0.0-final-v4/`, against
`e2aaca60fefc4d1fd716aea176d54df9c1794d39`. The earlier 1,469-pass v2 and
1,477-pass v3 (`190e5c5`) runs on 2026-10-07 remain historical; this result
includes the final review corrections.

The retained-source inventory at that historical revision contained **565
source-pattern flags**, separate from its passing canonical source gate. Two additional detections
relative to the 563-flag snapshot refer to the same POSIX-only Git timeout/FIFO
guard; that test executed successfully on Linux. These are static patterns,
not fabricated-result defects. Deleted legacy findings are resolved, and the
dated 559-flag inventory below remains historical.

[Actual hosted ORCA acceptance](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37613653904)
passed at `1cfa49a84d45da7c60ffd1fa0d6eae3889dbe049`, including fresh private
archive installation, all eleven Stage 0 phases and genuine serial/two-rank
calculation publication. The separate [student optimization/frequency run](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37616684042)
passed at `0a9effe`, including actual two-process ORCA derivatives and result
publication. [Bounded hosted CI](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37624167721)
passed for the `e2aaca60` source tree, using the identical-tree GitHub merge
checkout `a438644d`: source integrity, 164 controls per operating system, all
three wheel/CLI jobs, 537 bounded regressions, native launcher diagnostics,
real Linux xTB/PySCF calculations, Stage 0 and dashboard lifecycle. A 479-test bounded local selection and isolated
wheel installation also passed at `01cca5b`; overlapping selections are not
added to the canonical count. The full local profile tested the final
`e2aaca60` implementation. Changes made solely to publish that historical
1.0.0 snapshot were documentation only; later CFOUR/module/1.0.1 changes include
production code and require their own revision-specific acceptance.
The [release record](Release_1_0_0.md) preserves exact revision boundaries,
evidence paths and outstanding publication checks.

## Historical BASE alpha acceptance — 2026-10-06

The canonical `ci_tools/base_ci.py all` run on **2026-10-06** passed both gates:

- **1,189 tests passed, 4 external checks deferred, 0 failed**, from 1,193 collected tests in **391.21 seconds**. The 10,669 warnings are retained in the log, not suppressed. Deferrals are the actual ORCA R2/reference calculation, ORCA/CREST union and two physical Slurm-node checks.
- **Zero blocking findings** across production/CI source, selected-test source, mass policy and source/data airgap. The runner verified complete per-node outcomes and **no audited source change during testing**.
- The retained test-source inventory at that historical snapshot had **559 automated flags in 121 existing test files**. **No flags refer to deleted legacy files; those items are resolved.** This includes 42 conditional-skip references in selected tests and 517 flags outside the profile. It is not a count of 559 confirmed code defects or an unfinished backlog for deleted code. See [current CI review](SRS_AST_Review.md) and the machine-readable audit.
- Actual Chromium acceptance passed **30 checks**, including xTB, PySCF, CREST, QE, isotope exports and verified future-module handoff download, with no page errors or failed requests. The separate focused GUI selection passed 52 tests; overlapping selections are not added to the canonical count.
- The **complete reusable installation script was rerun successfully**. All eleven setup phases republished genuine authority, retaining native xTB/CREST/g-xTB/MOPAC/QE and isolated PySCF/MACE. Explicit four-silo selection fixes the former lightweight-default capability loss. Setup remains truthfully degraded for unavailable licensed/host capabilities and the explicitly reduced disk workload profile.

Evidence is retained under `/workspace/cochem-runtime/evidence/base-alpha-2026-10-06/`: `summary.json`, `source-audit.json`, `pytest-outcomes.json`, `pytest.xml`, `test-acceptance.json`, source snapshots, actual setup/install logs and independent scientific-boundary review. CI-control-only acceptance separately passed 157 tests with no skips. The workflows at that revision passed `actionlint`; hosted execution had not been accepted at that snapshot. These counts are historical, not the final 1.0.0 suite count.

A subsequent reporting clarification reproduced the affine error scaling, removed the demo’s misleading “spectroscopic grade” display and verified **20 focused PES tests**, the actual numerical demo and the canonical source audit. It did not tune the fitter or change either energy-error result. The prior full-suite snapshot remains retained unchanged. Follow-up evidence: `/workspace/cochem-runtime/evidence/pes-and-retirement-clarification/`.

## Chunk 17 requirement traceability

| Requirement | Current implementation and evidence | Remaining scope |
|---|---|---|
| 001 — OS/hardware ingress | Measured Linux/cgroup CPU, RAM, instruction capabilities and bounded GPU discovery. Registry records unavailable capabilities instead of inventing them. | User-deferred host acceptance: Windows/WSL, macOS/OrbStack, Codespaces and actual GPU measurements. |
| 002 — micro-silos | All eleven Stage 0 phases execute. Core/UI/PySCF/ML package locks, interpreter isolation, import origins and `pip check` are verified before final registry publication. Partial phases cannot publish a completed master. | Accelerator variants and native platform combinations. This workspace explicitly uses a 1 GB free-disk workload profile; it does not meet the default 50 GB policy on its 32 GB filesystem. |
| 003 — canonical SWMR telemetry | Canonical committed-row `complexes.h5` telemetry publishes geometry/energy/gradient with nuclear identity. ORCA intermediate gradients bind the immediately preceding native Bohr geometry/energy to retained selected-output transcript hashes and offsets; declared print precision is retained. xTB optimization now uses genuine native `--grad` evaluations through BASE BFGS, recording each evaluation and raw evidence instead of inventing Cartesian derivatives from a gradient norm. CFOUR native BFGS likewise records actual analytic-gradient evaluations. | An evaluated trial geometry is labeled as an evaluation, not a completed optimizer iteration. Coordinates without an available derivative remain explicitly coordinate-only. Full search-engine artifact and distributed-filesystem coverage requires its own provider/host acceptance. |
| 004 — dynamic masses | Dynamic Mendeleev validates `13C`/`C-13`/`C13`, D/T and exact physical nuclides. Canonical prefix identity survives XYZ/multiframe and SMILES ingress, COM/Eckart alignment, geometry/Hessian/result handoffs, SWMR nuclide/mass attributes, GUI selectors and conformer seeds. Electronic decks serialize true element labels. | Unknown/nonphysical nuclides are rejected; ghost centers use their specialized counterpoise adapter rather than general XYZ ingress. Complete third-party/legacy provider coverage still requires its own acceptance. |
| 005 — COM/Eckart ingress | Native calculations, TOPOS and Chain normalize ingress using exact isotope masses; proper rotation and residual gates are tested. Quantum decks retain sufficient coordinate precision after normalization. | Verification of every imported tensor/state frame and each external engine's independently rotated output remains required. |
| 006 — graph/geometric conformer sieve | WL graph/isomorphism, atom mapping, mass-weighted alignment, stricter Chunk 17 RMSD/rotation gates and proposal energy agreement `<0.05 kcal/mol`. Actual CREST plus ORCA GOAT water union passed, including HDF5 publication and durable promotion. | This bounded two-engine ingestion check does not implement the future TOPOS domain solver. |
| 007 — R1 frozen monomers | Wilson bond/angle/dihedral and linear-bending handling; all-frame monomer drift checks. Actual ORCA water-dimer R1 optimization passed with maximum monomer drift `6.1213138e-7 Å`. | `r2SCAN-3c` retains its published composite basis; no appended unrelated basis is accepted. One successful case does not certify every system’s coordinate or rotational accuracy. |
| 008 — R2 production | Actual ORCA canonical CCSD(T)/TZ-QZ reference generation, independent PySCF energy comparison and accepted five-leg R2 execution. Source hashes, atom mapping, gradients, trajectory drift and achieved convergence are retained. Signed counterpoise ordering and residual-gradient warnings remain explicit. | The bounded accepted run is recorded in [scientific acceptance](ORCA_Scientific_Acceptance.md); it does not claim a rigorous counterpoise energy bound. A finite-basis CBS estimate is not exact-CBS geometry certification. Higher-order R2 frequency/VPT2 providers remain downstream work. |
| 009 — grid lifecycle | Supported native ORCA DFT optimizations connect measured-gradient/energy/last-step convergence to DEFGRID1 → DEFGRID2 → DEFGRID3 execution. Actual geometry and immutable GBW state carry forward under one operation budget and fresh authority. Explicit grid, high-tier, transition-metal, R2 and frequency minima are preserved; fixed HF/correlated jobs do not acquire an invented DFT grid. | Stage progression does not establish universal empirical integration/rotational accuracy. A private native `.opt` is not converted into a portable Hessian; an explicitly supplied genuine geometry-bound Hessian retains its READ validation. |
| 010 — quintuple convergence | Required thresholds are emitted; achieved-value parsing rejects absent, incomplete, nonfinite or failed convergence. Chain cannot override geometry/resource policy through arbitrary raw blocks. | Actual coordinate and rotational-error targets need independent physical reference data. Configured tolerances cannot guarantee those errors for every molecule. |
| 011 — Hessian discipline | XTB2/Lindh/READ policy, forbidden exact initial Hessians, safe identifiers, unique basenames and geometry-bearing Hessian validation. Actual ORCA checkpoint consumption and compound execution passed, including native MO projection, Hessian initialization, per-stage convergence and unchanged source hashes. | The compound acceptance validates native execution; it does not automatically import compound stages into Chain HDF5. Other external wavefunction formats and CFOUR retain their own acceptance. |
| 012 — dispersion | B3LYP/PBE0 require D3BJ/D4, including isolated molecules. VV10 plus empirical dispersion is rejected. Real B3LYP-D4 and wB97M-V calculations passed through DEFGRID1/2/3 with retained convergence/refinement evidence. | The measured combinations do not certify all functionals, molecules or empirical accuracy targets. |
| 013 — spin and T9 fallback | Inclusive 10% relative spin rejection and real isolated PySCF CASSCF/NEVPT2 recovery. Actual stretched H3 ORCA `<S²>=1.591697` was rejected and explicit CAS(3,3)/NEVPT2 recovered the doublet (`<S²>≈0.75`). CLI, GUI and Chain preserve the recovery contract. | Active spaces remain explicit. Single-point recovery does not complete an interrupted optimization/frequency request. Open-shell CFOUR diagnostics require its provider. |
| 014 — isotope transformations | Actual ORCA water Hessian ingestion and simultaneous 18O/D2 substitutions passed library/GUI parity without new electronic calculations. Isotope-labelled native requests retain the unchanged Cartesian Hessian and selected exact masses/frequencies in geometry-bound NPZ; native/principal spectra are separately validated and identified. | Harmonic mass projection does not supply VPT2 `B0`; missing anharmonic corrections stay unknown. Minimal-basis examples establish integration, not experimental frequency accuracy. |
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
| 6 — crash forensics | Active native runners share an exclusive UUID JSON-LD recorder: exact raw stderr tail before text decoding, prelaunch executable/input hashes, actual cwd/thread/timeout/affinity controls, measured host resources, distinct Git object ID/object SHA-256, package/recorder identity and canonical record hash. Records use read-only file permissions and are retained in licensed calculation artifacts. The CLI arms uncaught-exception JSONL/traceback and emergency HDF5 closure. | File/hash integrity is not an independent audit signature. Missing Git identity is explicit; CPU/RAM values describe the host at recording rather than invented per-job peak usage. Additional native-platform physical acceptance remains separate. |
| 7 — resource guard/LTTB | Production Scribe now uses the canonical cgroup/available-memory/registry guard; `RESOURCE_GUARD=0` cannot bypass it. Prompt compression retains actual moments and at most 500 samples. | Authenticated remote API and GPU model acceptance. |
| 8 — constants | Shared CODATA conversion exports and required rotational conversion; discrepant formatter/propagation/Chain copies corrected. | Third-party numerical libraries retain their own documented versions. |
| 9 — quadrature | Chunk 17's three-stage sequence is connected to supported native ORCA DFT optimization and measured convergence; explicit stronger minima remain authoritative. | Bounded genuine stage/refinement acceptance does not establish every rotational/integration error target for arbitrary molecules. |
| 10 — stationary convergence | Emission and achieved-value gates are connected to execution. | Universal sub-mÅ/rotational accuracy is not established by thresholds alone. |
| 11 — Wilson freezing | Real derivative/nullspace mathematics, complete fragments and live trajectory integrity; actual R1 and R2 frozen-monomer acceptance passed. | Additional molecules and external solver/host combinations retain their own physical acceptance. |
| 12 — chained Hessians | Structured policy, checkpoint presence/content checks, output geometry agreement and actual ORCA checkpoint/compound state-transfer acceptance. | Compound stages are not automatically imported into Chain HDF5 by the deck-generator acceptance. CFOUR state transfer requires its scientific provider. |
| 13 — dispersion | Common sanitizer covers standalone and Chain inputs; actual B3LYP-D4/wB97M-V grid series passed. | Additional solver combinations and systems. |
| 14 — CREST/GOAT union | Actual CREST plus ORCA GOAT water union, graph/RMSD/rotation/energy gates, HDF5 publication and promotion passed. | Additional systems and future TOPOS domain acceptance. |
| 15 — multireference escalation | Real configured CASSCF/NEVPT2 execution after typed spin rejection. | Workflow-specific active spaces and completion of requested higher-order tasks. |
| 16 — principal isotope masses | Dynamic exact nuclides through ingress, alignment, telemetry and immutable handoffs; selected-isotope spectra and principal/native baselines remain explicitly distinct. | Complete external scientific-provider/format coverage. |

The proposal workflow's **MACE-OFF24m ↔ g-xTB fallback is now executed**, not merely recommended: both directions ran on actual CPU backends, retained measured energies/gradients, recorded both attempts and wrote canonical telemetry. Corrupt checkpoint evidence aborts instead of being hidden by a fallback. Heavy libraries stay inside the ML silo. The exact official OFF24 medium v0.2 checkpoint is distinct from OFF23.

## Scientific and integration acceptance boundaries

1. **The PES failure had real implementation and analysis defects; a new quantum protocol now passes its bounded target.** The historical Cu/Ag/Au EMT example used the artificial target `1.02 * E_EMT - 0.005 eV` and placed all 150 holdout geometries beyond its training Cu–Ag separation range. Correct fitting/provenance reduced its paired correction RMSE to 6.271842 cm⁻¹, but its standalone extrapolation RMSE remained 319.863926 cm⁻¹ (0.915 kcal/mol). These are energy errors, not vibrational frequencies; that example remains uncertified and cannot provide independent quantum accuracy evidence. The new actual ORCA H2 protocol instead uses 128 RHF/STO-3G baseline points, 32 canonical CCSD(T)/cc-pVTZ correction pairs and 31 fresh holdout geometries excluded from both training sets over 0.55–1.80 Å. Unchanged model defaults give paired RMSE **1.189292656 cm⁻¹** (maximum **3.726415424 cm⁻¹**) and standalone RMSE **3.176715694 cm⁻¹** (maximum **8.242899532 cm⁻¹**), meeting the unchanged 10 cm⁻¹ threshold for both metrics. Denser independent baseline sampling addressed interpolation error; the model was not tuned on holdouts. This two-electron one-dimensional interpolation does not certify nonzero triples contributions, vibrational frequencies, extrapolation, experimental agreement or arbitrary molecules. Full provenance is in `/workspace/cochem-runtime/evidence/quantum-pes-2026-10-07/dual-resolution-acceptance.json`.
2. **CFOUR native execution is accepted within a defined provider boundary.** BASE provisions and seals the approved runtime, authorizes isolated native jobs and accepts closed-shell HF single points/optimization/harmonics plus MP2/CCSD/CCSD(T) single points. Geometry-bound harmonic Hessians support downstream ingestion and isotope reanalysis. VPT2, open-shell and correlated derivative operations remain explicit provider handoffs. Missing adapters must not fabricate energies, anharmonic corrections, isotope `B0`, convergence or completed operations. Historical broad CFOUR configuration is preserved as pending input handoff; it is not a second weaker execution path.
3. **TOPOS/TORQ future work is recorded, not counted as a BASE-only solver deficit.** BASE retains its working native calculation, CREST, isotope inspector and scientific export flows, and provides validated future-module handoffs in the GUI. Full multidimensional PES exploration and domain workflows will be completed in their repositories. Accessibility and real platform acceptance remain bounded by actual tests.
4. **Product B now has direct BASE ingestion examples.** Ordered CIF and periodic JSON with fractional or Cartesian coordinates and explicit Angstrom/Bohr units preserve the periodic frame, original source hash and canonical converted structure hash. Singular/left-handed cells, duplicate lattice-equivalent sites, disorder/partial occupancy and invalid PAW inputs are rejected. The real registered QE PAW GaAs single point remains connected. Advanced bands, SOC, cell optimization and empirical accuracy claims need their scientific providers and benchmark evidence; ingesting a cell or executing one SCF does not certify them.
5. **CI must preserve failures as evidence.** Obsolete duplicated workflows and misleading physical fixtures are retired with recorded replacements. Selected test interface interception is migrated to actual child-process configuration. The canonical pipeline rejects missing/zero-test evidence, source changes during validation and unexpected skips. The wider legacy collection is inventoried explicitly, not claimed as executed or compliant.
6. **External acceptance requires actual execution evidence:** ORCA 6.1.1 hosted serial/two-rank acceptance has passed, with its run linked above. The separate student optimization/frequency workflow also passed. Ubuntu/macOS/Windows controls, wheel/CLI checks and native launcher diagnostics passed in bounded hosted CI; this does not certify native ORCA science on Windows/macOS. Actual student Codespaces, GPU/Slurm, deployment filesystems and additional native physical calculations remain deferred; CFOUR Linux/hosted native acceptance is recorded above. Source-level Slurm staging now prepares a real validated, hash-bound request and performs fresh Stage 0 within the compute allocation; those tests do not claim a physical cluster run.

## Reproduction and retained evidence

```bash
source /workspace/cochem-runtime/activate.sh
python -m pip check
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python ci_tools/base_ci.py all --output /tmp/cochem-base-alpha-evidence
# Wider historical inventory, not an alpha acceptance substitute:
python ci_tools/anti_spoof_linter.py . --strict --json > /tmp/cochem-strict-repository-inventory.json
```

Historical second-pass logs, JUnit, strict scans and a source manifest are retained together in `/workspace/cochem-runtime/evidence/srs-pass2/`. Session evidence also includes `/workspace/cochem-runtime/stage0-complete-audit.json`, `/workspace/cochem-runtime/topos-second-pass/`, `/workspace/cochem-runtime/mlff-second-pass/`, `/workspace/cochem-runtime/gui-srs-pass/` and `/workspace/cochem-runtime/chain-pass2-jt1upcd8/`. Runtime artifacts remain outside the repository. The self-contained cloud install script completed successfully, including all free-engine/ML checks and all eleven Stage 0 phases. The environment setup draft is saved for review; a fresh published/restored environment is a separate acceptance step. The repaired hosted lifecycle also completed setup twice in a separate external environment, passed 27 native CLI/lifecycle checks, all five workflow syntax checks, and actual Chromium interactions. That earlier local lifecycle report did not establish hosted acceptance; subsequent run-specific outcomes are recorded in ORCA_Actions_Setup.md.

A historical full-repository collection attempt discovered **4,416 tests and 237 collection errors** (`/tmp/cochem-all-collection-pass2.log`). These include missing sibling interfaces, legacy import paths and tests that import heavy libraries directly into BASE even though those libraries are installed in their required silos. This is not evidence that every low-compute test ran. An isolated built-wheel check imports the shipped CLI, GUI, frontend adapter, native setup service and provenance implementation without checkout paths or `.pth` processing.

This audit records implementation and measured evidence. It does not manufacture council approvals, scientific signatures, experimental reference data or a blanket conformance certificate.


## ORCA Actions integration follow-up

The user supplied the ORCA 6.1.1 private release and independently calculated
SHA-256 and authorized commit/push and hosted calculation acceptance. The pinned
installer, MPI runtime build, reusable action and real serial/parallel BASE CLI
acceptance are documented in [ORCA Actions setup](ORCA_Actions_Setup.md). ORCA
MPI rank/thread oversubscription was fixed in native, TOPOS, R2 and Slurm paths.

The historical prepublication canonical local run passed **1,241 tests**, with the
same **4 external deferrals** and no failures, collected-node omissions,
unexpected skips or source changes. This superseded the earlier alpha count at that revision;
it is now superseded by the 1,532-pass profile above and did not establish hosted ORCA execution. Evidence:
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

Actual ORCA checkpoint and two-step compound execution passed in
`/workspace/cochem-runtime/evidence/orca-state-transfer-resource-final/validated-acceptance.json`.
The checkpoint job consumed genuine XYZ/GBW/Hessian inputs without changing their
hashes and satisfied all five geometry limits. The compound job verified native
MO projection, per-step resources and achieved SCF convergence. This native
deck-generator check does not automatically import compound stages into Chain
HDF5 or certify arbitrary downstream state-transfer providers.

The accepted five-leg R2 publication is retained at
`/workspace/cochem-runtime/evidence/r2-physical-2026-10-07/accepted-r2-publication.json`.
Its maximum internal monomer drift is `8.257453875e-7 Å` against `1e-6 Å`;
its signed counterpoise correction is `-8.39272e-7 Eh`. The report explicitly
states that the measured energy interval is not a rigorous physical bound and
retains the observed residual-gradient warning.

The complete instructor/student procedure is the
[Classroom50 guide](GitHub_Classroom_ORCA_Setup.md). Current canonical counts
and hosted outcomes are recorded above. Final publication must identify the
reviewed revision and source equivalence to these tested revisions; neither the historical
1,189/1,241 counts nor overlapping targeted selections replace that evidence.
