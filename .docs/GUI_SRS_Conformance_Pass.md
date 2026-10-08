# Historical BASE GUI and integration record — 2026-10-06/07

This record describes **BASE ingestion, environment setup, execution infrastructure and GUI** at the 2026-10-06/07 snapshot. TOPOS and TORQ were subsequent repository integrations at that point. Their scientific solvers were not substituted with BASE widgets or synthetic results. The baseline remains Chunk 17 plus BASE proposal additions and the [GUI Architecture Charter](improvements/GUI_Architecture_Charter.md).

The export/manual-dispatch route recorded below is historical. For current
personal private projects, App enrollment, automatic setup and direct GUI
submission/retrieval, follow the [student research guide](Student_Research_No_Code.md)
and [instructor App deployment guide](Personal_Project_App_Deployment.md).
The evidence below retains its original scope and does not validate those later routes.

| BASE responsibility | Implementation and evidence | Boundary |
| --- | --- | --- |
| Native controllers | GUI and CLI share `calc.calculation_service.run_calculation`; installation calls `orchestrator.bootstrap_service.run_setup`. Structured progress, cancellation and results do not depend on CLI stdout scraping. | A pending integration is displayed as pending, with its input manifest and no calculated energy or execution-success claim. |
| Setup and engine availability | The installer validates scientific input, records its digest, offers an explicit storage budget and runs all eleven native setup phases. Engine controls query the checksummed registry and actual executable authority. | ORCA/CFOUR licenses and binaries are not invented. A partial discovery audit cannot authorize execution. |
| Molecular ingestion and inspection | Geometry-bound Hessians retain geometry, units, source and SHA-256. Per-atom isotope substitutions use the same Cartesian Hessian; harmonic spectra have SVG/CSV exports. Bounded HDF5 inspection reads actual values under the shared lock. | Missing anharmonic corrections remain absent; harmonic reweighting does not invent B0 corrections. |
| Periodic structure ingestion | Ordered CIF and explicit periodic JSON use the shared Product B parser. The GUI displays the actual cell, fractional coordinates, original-source hash and canonical-structure hash. PBE/PAW settings produce a native calculation request. | Ambiguous units, partial occupancy and disorder are rejected. Source coordinate units are distinct from canonical Å units in handoff metadata. |
| Native CPU science paths | Existing xTB screening, isolated PySCF RHF and Quantum ESPRESSO PBE/PAW single points are connected to actual BASE services and Golden Registry resource limits. | Numerical convergence does not establish empirical product accuracy. Full licensed/GPU/HPC acceptance requires those actual environments and scientific inputs. |
| Future-module capability discovery | `interfaces.module_registry` distinguishes BASE availability, missing modules, installed but unvalidated providers and conflicting providers. Only distribution entry points in `cochem.modules` establish external installation; compatibility files do not. | Discovery never executes providers or attests scientific verification. `execution_verified` is constrained to false in this discovery contract. |
| Validated module handoff | `interfaces.artifact_handoff` copies a real XYZ geometry, Hessian, converged result JSON or periodic structure into a package with schema, recipient, requested operation, units and SHA-256. The receiver rechecks contents, metadata and directory boundaries. The GUI can download the complete ZIP package. | Status remains `pending_integration`; no downstream job is dispatched. Altered artifacts, inconsistent metadata and elevated verification claims are rejected. |
| Accessibility | Text labels, keyboard actions, live status/error roles and button contrast are exercised in real Chromium. | Full WCAG 2.1 AA, screen-reader and responsive-layout certification still requires broader acceptance. |
| Hosted lifecycle | The Codespaces/Actions setup uses complete UI dependencies, isolated pinned core/UI environments, verified xTB and all eleven actual Stage 0 phases. | Local lifecycle/browser acceptance is distinct from an actual hosted Codespace rebuild or Actions run. |
| Classroom50 Actions jobs | Selecting Actions displays the complete instructor/student setup guide, accepts the course repository/branch and exports portable validated ORCA JSON. The GUI shares the workflow's resource and scientific input policy. Real Chromium download/export acceptance passed without page/request errors. | Preparing a file does not run local chemistry or dispatch a hosted calculation. Students submit to the approved repository's `ORCA calculation` workflow; no instructor PAT is requested by the GUI. |
| ORCA harmonic ingestion | Genuine ORCA optimization/Hessian output is accepted and published. Real parent/18O-D2 isotope transformations match the GUI/library outputs while preserving the source Hessian and rejecting changed geometry. | Harmonic reweighting performs no new SCF; anharmonic `B0` remains unknown without its provider. |

## Legacy migration

The obsolete `dock_main.py` and `fast_pass.py` bodies advertised symbols and workflows that their self-importing targets never implemented. Those bodies have been removed. The import-time failure shells have also been replaced:

- `cochem_dock_main`, `cochem_dock_visuals_api`, `cochem_pgopher_bridge`, `cochem_pyckett_bridge`, `cochem_vibspyc_snap` and `oet_gxtb` expose `get_capability`, `prepare_handoff` and a capability/handoff CLI. They do not pretend to provide the former remote server, spectroscopy solver or ExtOpt execution API.
- `cochem_unity_installer_dashboard.SynapInstallerGUI` is the actual BASE GUI. Its headless entrypoint uses the native setup service. CORE, MInt, SYNAP and UNITY selections normalize to consolidated BASE; TOPOS/TORQ are optional future consumers.
- `cochem_unity_fast_pass_widget` and `fast_pass` use canonical calculation configuration and the actual native execution service. Unsupported remote lookup and engine claims were removed.
- The functional MACE-OFF wrapper and bounded React telemetry source were retained. Their existence is not treated as a connected provider.

`frontend.cochem_topos_ui.CochemToposUI` remains a thin adapter to the already connected BASE conformer-screening panel. Actual CREST submission, publication and cancellation were verified; this does not claim implementation of the next TOPOS repository. TORQ's domain workflow, multidimensional torsional/PES views and its solver acceptance belong to that future integration.

## Reproducible checks

The 2026-10-07 Classroom50 export/browser record is
`/workspace/cochem-runtime/evidence/classroom-actions-ui/browser/browser-summary.json`:
`UI_EXPORT_VERIFIED`, no page errors and no failed requests. It explicitly
records `hosted_execution_performed=false`. The real ORCA Hessian/GUI isotope
parity report is
`/workspace/cochem-runtime/evidence/orca-hessian-gui-parity/acceptance.json`:
passed for the parent and simultaneous 18O/D2 substitution, unchanged Hessian,
geometry mismatch rejection and absent unsupported anharmonic corrections.
These are local acceptance facts, not final hosted run results or a universal
chemical accuracy certificate. The [1.0.0 release record](Release_1_0_0.md)
describes that historical release; use the current student guide linked above
for the selected personal-project route.

`tests/base/test_module_handoff_contract.py` verifies copied input, tamper detection, invalid geometry, source-tree write rejection, destination preservation, GUI handoff, raw/exported periodic structures and rejection of false verification claims. Legacy boundary tests prepare and revalidate actual geometry packages. The physical UI tests start real child processes with explicit configuration environments; they do not replace imported functions or use environment monkeypatches.

`tests/ui/voila_browser_acceptance.py` supports `--module-handoff`, `--periodic-input` and `--periodic-settings`, in addition to the established native xTB/PySCF/CREST and Hessian flows. It validates downloaded handoff contents and can run actual periodic PBE/PAW science. Real ASE/EMT finite-difference Hessians test transport and isotope reweighting; they are not ab-initio accuracy references.

The hosted launcher was validated twice through all eleven phases in `/workspace/cochem-runtime/hosted-authority-final`; its CLI/lifecycle selection passed 27 cases, actual render/start/reuse passed, and all workflow files passed `actionlint`. Its explicit 1 GB workload budget applies to bounded small-molecule acceptance; the setup GUI and command retain their 50 GB defaults. Current alpha browser and focused-regression evidence is recorded separately in the main implementation report.

The historical 2026-10-06 focused GUI/contract selection passed **52 tests** in **42.34 seconds** (`/tmp/gui-alpha-frozen-regression.log`). Its Chromium evidence is `/workspace/cochem-runtime/gui-alpha-final/browser-final/browser-evidence.json`: actual xTB optimization, PySCF RHF, CREST publication/cancellation, isotope/Hessian exports, verified future-module ZIP download, periodic CIF ingestion and native Quantum ESPRESSO PBE/PAW execution all passed, with zero page errors and zero failed requests. The GUI reads the canonical service result, preserving engine-private supporting evidence separately. The owned acceptance server was stopped afterward. Those historical counts are not the final 1.0.0 regression count.
