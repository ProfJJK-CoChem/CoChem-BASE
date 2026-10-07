# BASE alpha installation and low-compute readiness

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

No installation is described as “perfect.” These are measured configurations on the current CPU/Linux machine. ORCA/CFOUR licensing, accelerator variants, additional platforms and independent physical accuracy targets require their own evidence.

## Reproduce local acceptance

```bash
source /workspace/cochem-runtime/activate.sh
python -m pip check
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python ci_tools/base_ci.py all --output /tmp/cochem-base-alpha-evidence
```

The default `python -m pytest` and compatibility `pytest-srs.ini` select the same BASE profile. Canonical CI records actual node outcomes and before/after source hashes. Zero tests, collection failures, unexpected skips and source changes fail. The exact licensed/reference/Slurm deferrals are recorded separately in `ci_tools/deferred_acceptance.json` and never counted as passes.

The previous repository-wide collection attempt found 4,416 tests and 237 collection errors. It included absent sibling APIs, obsolete module paths and heavy-library imports in the BASE interpreter. Those historical tests have not all been executed or certified. The current pipeline retains a wider legacy AST inventory separately from the explicit BASE alpha gate; cleanup of future-module tests must proceed with their repositories.

## Scientific evidence corrections

The failed 1631.753 cm⁻¹ PES report mixed incorrect fitting/energy-reference semantics with out-of-domain extrapolation and mislabeled EMT data as quantum reference data. The artificial affine target makes the paired correction error 2% of the fitted baseline error: 6.271842 cm⁻¹. The standalone predicted surface remains 319.863926 cm⁻¹ (0.915 kcal/mol) and is not certified. These are energy-fitting errors, not vibrational frequencies or independent quantum accuracy measurements. See the scope report for the independent decomposition.

The historical saved water Hessian had wrong unit interpretation. It is replaced by a fresh ASE/EMT Hessian with explicit conversion. Fabricated formaldehyde calibration/uncertainty data and the dependent TORQ “physical acceptance” test were removed. These corrections do not create quantum accuracy evidence.

## Hosted and future-module acceptance

Codespaces and the bounded GitHub Actions calculation workflow share the tested installer/dashboard lifecycle. The local equivalent completed setup twice, 27 native CLI/lifecycle checks and actual Chromium calculations against the audited registry. This is local evidence, not an actual hosted run. The revised canonical workflow uses the common source gate and retains real bounded calculation acceptance.

The user has now authorized the ORCA 6.1.1 GitHub Actions pathway; see [ORCA Actions setup](ORCA_Actions_Setup.md). Codespaces, CFOUR, GPU, Slurm, native platforms and deployment-filesystem acceptance remain deferred until a stable alpha and a supplied host. TOPOS/TORQ domain workflows and multidimensional PES exploration are future repository work. BASE prepares validated handoffs and shows capability state; it does not invent their outputs.

The reusable cloud installation and startup draft is retained in environment settings. Saving that draft does not publish or validate a fresh restored environment. Current-pass final counts and evidence paths are recorded in the main implementation report.

## Current measured result

Canonical BASE acceptance: **1,189 passed, 4 user-deferred external checks, 0 failures**; source gate passed with no blocking findings and unchanged audited source. Actual Chromium: **30 checks passed**, no page/request errors. The complete saved installation script completed successfully after explicit four-silo deployment selection was added. Evidence: `/workspace/cochem-runtime/evidence/base-alpha-2026-10-06/`. These results do not certify all historical tests or deferred host/scientific domains.
