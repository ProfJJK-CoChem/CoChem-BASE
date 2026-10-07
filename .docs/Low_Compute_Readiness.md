# BASE installation and low-compute readiness

The current acceptance boundary is BASE ingestion, setup, GUI and validated integration. The governing specification remains Chunk 17 plus proposal additions, with the user's clarified module ownership and deferred host acceptance. See [scope](BASE_Alpha_Scope.md) and [requirement traceability](SRS_Implementation_Status.md).

## Installed and executed in this cloud environment

| Capability | Evidence and scope |
|---|---|
| xTB, CREST, g-xTB, MOPAC | Verified native installations and actual small-molecule calculations; artifacts under `/workspace/cochem-runtime/free-engines/`. |
| PySCF and OpenMM | Isolated interpreters and actual CPU calculations. Configured PySCF CASSCF/NEVPT2 H3 CAS(3,3) executed with explicit state/active-space evidence. |
| MACE-OFF24 medium | Exact official v0.2 checkpoint from the user's release URL. SHA-256 `e5ccf5837f685899811a68754e7c994393bfd1a81720393b03c643b46c70bc69`. Both MACE-OFF24 → g-xTB and reverse fallback executed and published actual results. OFF23 evidence is separate. |
| Other ML CPU backends | Separate silo and retained model/download/CPU numerical evidence under `/workspace/cochem-runtime/ml-*`. This does not certify GPU variants. |
| Quantum ESPRESSO PAW | Pinned binary/dependencies and official Ga/As PAWs. Actual GaAs SCF energy −226.8926158164 Hartree; shared-service execution and periodic-input validation tested. |
| Stage 0 | All eleven phases completed with actual package, interpreter, I/O and hardware evidence. Golden Registry is checksummed, not independently signed. Status truthfully records `DEGRADED_OPERATIONAL` and an explicit 1 GB free-disk workload profile on this small workspace. The default production policy remains 50 GB. |
| Voilà | Actual browser interactions exercised native calculations, CREST, cancellation, telemetry, Hessian isotope inspection and scientific exports. Newly added module-handoff and periodic ingestion flows have separate current-pass checks. |
| ORCA 6.1.1 / Open MPI 4.1.8 | Approved archive hash/version and real MPI execution; actual serial/parallel, R1, DFT grid-series, harmonic and contaminated-spin recovery calculations. See [scientific evidence](ORCA_Scientific_Acceptance.md) and reports below. |
| Classroom50 Actions interface | Guide based on official Classroom50 documentation; real browser JSON export uses shared workflow validation. Actual student backend single-point and optimization/frequency jobs executed locally; hosted two-process optimization/frequency run 37616684042 also passed. |

These are measured configurations on the current CPU/Linux machine. ORCA is now available and has run real calculations. CFOUR, accelerator variants, additional platforms and independent physical accuracy targets retain their own requirements.

## Reproduce local acceptance

```bash
source /workspace/cochem-runtime/activate.sh
python -m pip check
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python ci_tools/base_ci.py all --output /tmp/cochem-base-alpha-evidence
```

The canonical reporting tests exercise real Parquet I/O and require the declared
`catalog` extra; this is a test prerequisite, not an optional skip. The prepared
main environment and bounded hosted workflow install those dependencies and
pass `pip check`. For a fresh development environment, use the
[README installation command](../README.md#python-installation-and-cli), including
`dev,ui,catalog,symmetry,scribe`. The `scribe` extra declares its tokenizer
`tiktoken`; configuring it does not establish authenticated remote inference.

The default `python -m pytest` and compatibility `pytest-srs.ini` select the same BASE profile. Canonical CI records actual node outcomes and before/after source hashes. Zero tests, collection failures, unexpected skips and source changes fail. The exact licensed/reference/Slurm deferrals are recorded separately in `ci_tools/deferred_acceptance.json` and never counted as passes.

The previous repository-wide collection attempt found 4,416 tests and 237 collection errors. It included absent sibling APIs, obsolete module paths and heavy-library imports in the BASE interpreter. Those historical tests have not all been executed or certified. The current pipeline retains a wider legacy AST inventory separately from the explicit BASE alpha gate; cleanup of future-module tests must proceed with their repositories.

## Scientific evidence corrections

The failed 1631.753 cm⁻¹ PES report mixed incorrect fitting/energy-reference semantics with out-of-domain extrapolation and mislabeled EMT data as quantum reference data. The artificial affine target makes the paired correction error 2% of the fitted baseline error: 6.271842 cm⁻¹. That historical synthetic example’s standalone predicted surface remains 319.863926 cm⁻¹ (0.915 kcal/mol) and is not certified. These are energy-fitting errors, not vibrational frequencies or independent quantum accuracy measurements. See the scope report for the independent decomposition.

A separate real quantum H2 interpolation protocol now meets the 10 cm⁻¹
energy-error target: 128 RHF/STO-3G baseline points, 32 CCSD(T)/cc-pVTZ correction
pairs and 31 fresh held-out geometries give 3.176715694 cm⁻¹ standalone RMSE and
8.242899532 cm⁻¹ maximum absolute error with unchanged model defaults. The
0.55–1.80 Å two-electron one-dimensional interpolation does not certify spectra,
extrapolation or arbitrary molecules. Evidence:
`/workspace/cochem-runtime/evidence/quantum-pes-2026-10-07/dual-resolution-acceptance.json`.

The historical saved water Hessian had wrong unit interpretation. It is replaced by a fresh ASE/EMT Hessian with explicit conversion. Fabricated formaldehyde calibration/uncertainty data and the dependent TORQ “physical acceptance” test were removed. These corrections do not create quantum accuracy evidence.

## Hosted and future-module acceptance

Codespaces and Actions share the tested installer/dashboard lifecycle. Historical local setup/lifecycle evidence remains separate from hosted execution. The ORCA workflows now provide private archive access, full physical acceptance and submitted student calculations using one reviewed manifest. They check out the approved course revision, provision a fresh host-specific registry and retain scientific evidence. Follow the [Classroom50 guide](GitHub_Classroom_ORCA_Setup.md); workflow implementation alone is not a hosted pass.

ORCA 6.1.1 local physical acceptance has expanded beyond archive access; hosted outcomes are in [ORCA Actions setup](ORCA_Actions_Setup.md). Codespaces, CFOUR, GPU, Slurm, native platforms and deployment-filesystem acceptance remain deferred pending suitable hosts/providers. TOPOS/TORQ domain workflows and multidimensional PES exploration belong to those repositories. BASE prepares validated handoffs and shows capability state.

The reusable cloud installation and startup draft is retained in environment settings. Saving that draft does not publish or validate a fresh restored environment. Current-pass final counts and evidence paths are recorded in the main implementation report.

## Historical measured result — 2026-10-06

Canonical BASE acceptance: **1,189 passed, 4 user-deferred external checks, 0 failures**; source gate passed with no blocking findings and unchanged audited source. Actual Chromium: **30 checks passed**, no page/request errors. The complete saved installation script completed successfully after explicit four-silo deployment selection was added. Evidence: `/workspace/cochem-runtime/evidence/base-alpha-2026-10-06/`. These results do not certify all historical tests or deferred host/scientific domains.

## Additional measured evidence — 2026-10-07

The strict local scientific report
`/workspace/cochem-runtime/evidence/orca-scientific-acceptance-strict.json`
passed actual R1 frozen optimization, B3LYP-D4/wB97M-V DEFGRID1/2/3 calculations
and explicit ORCA spin-rejection to PySCF CAS(3,3)/NEVPT2 recovery. It records
`scientific_accuracy_established=false`; these bounded checks validate their
execution and ingestion contracts.

Real CREST plus ORCA GOAT water union passed with durable HDF5 publication.
The actual ORCA Cartesian Hessian passed parent/18O-D2 isotope GUI parity
without an electronic rerun in
`/workspace/cochem-runtime/evidence/orca-hessian-gui-parity/acceptance.json`.
Classroom50 browser export passed independently of hosted execution. Installed
1.0.0 wheel checks and the final release evidence are described in
[the release record](Release_1_0_0.md). Historical and overlapping selections
are not summed into a fabricated final suite count.

## Current canonical result — 2026-10-07

The complete 1.0.0 profile passed **1,477 tests**, with **2 physical Slurm skips**,
**0 failures**, **1,479 collected** and no source mutation in 931.49 seconds.
All 10,672 warnings are retained. Actual R2 and CREST/GOAT acceptance executed;
the two remaining deferrals require physical Slurm allocation. Evidence:
`/workspace/cochem-runtime/evidence/base-1.0.0-final-v3/`.

[Hosted ORCA serial/parallel acceptance](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37613653904)
passed separately. [Student optimization/frequency run 37616684042](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37616684042)
also passed, with actual two-process ORCA calculation and accepted publication.
[Bounded hosted CI run 37617769942](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37617769942)
passed all Ubuntu/macOS/Windows controls and clean wheel checks, native launcher
diagnostics, real Linux xTB/PySCF calculations, Stage 0 and dashboard lifecycle.
The complete local profile also passed on that final code revision `190e5c5`;
the preceding 1,469-pass v2 run remains historical. Consult
the [release record](Release_1_0_0.md) for evidence and publication boundaries. Neither the complete canonical
profile nor the bounded hosted selection claims execution of every retained
historical test or unavailable platform.
