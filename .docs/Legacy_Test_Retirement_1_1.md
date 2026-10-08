# Legacy test retirement for BASE 1.1

Ten obsolete integration or scientific-success cases were removed by their exact
Python AST definitions. The remaining mathematical, parser, model and filesystem
checks in these files are explicitly engineering test vectors; their input
numbers are not native chemistry evidence. Their historical execution is not
claimed as current release acceptance.

| Retired cases | Defect in the old acceptance claim | Current replacement |
| --- | --- | --- |
| `tests/integration/test_airgap.py`: `test_airgap_boundary_subprocess_job_dispatch`, `test_airgap_boundary_full_end_to_end_pipeline` | A Python child wrote invented ORCA success/energy text, which was subsequently presented as a completed chemistry pipeline. | [Actual transport and source/scratch/store boundary checks](../tests/base/test_subprocess_tokenization_and_airgap.py), [runtime-path integrity](../tests/base/test_runtime_data_paths.py), [real native-record SWMR lifecycle](../tests/base/test_scientific_swmr_lifecycle.py), and [native ORCA derivative admission](../tests/calc/test_orca_derivative_acceptance.py). |
| `test_suite/test_cochem_torq_phases_1_to_5.py`: `TestTorqEngine.test_route_method_matrix_success`, `test_route_method_matrix_provenance_distinction` | A caller-supplied number was promoted to measured `[M]` provenance without a native calculation. | [Missing/converged evidence contracts](../tests/base/test_torq_engine_evidence.py), [measured scientific admission](../tests/base/test_measured_scientific_admission.py), and the actual installed TORQ scan/checkpoint acceptance below. |
| The same TORQ file: `TestTorqMace.test_evaluate_pes_point`, `test_generate_adaptive_grid`, and both `TestTorqQuench` success cases | An unspecified or unavailable selected model could be replaced by an unrequested potential or geometric quench and still pass a scientific-success test. | [Requested model admission](../tests/base/test_requested_worker_model_contract.py), [explicit empirical-potential and refusal contracts](../tests/torq/test_retired_legacy_potential_admission.py), [actual native quench broker](../tests/torq/test_native_quench_broker.py), and [force-converged selected-potential checks](../tests/base/test_topology_scientific_admission.py). |
| `tests/test_cochem_goat_crest_union.py`: `test_goat_crest_union_orchestrator_pipeline`, `test_main_cli_execution` | Hand-written source-labeled seed energies were used to claim a completed GOAT/CREST pipeline and derived thermal results. | [Canonical conformer sieve and full lineage](../tests/base/test_conformer_pool_srs.py), [retained actual-pool compatibility](../tests/torq/test_goat_crest_conformer_union_pipeline.py), [owned asynchronous process lifecycle](../tests/topos/test_async_search_execution.py), and actual physical union acceptance below. |

The current equivalents cover proper rotations, nuclear/isotope identity,
principal masses, unknown-state/energy preservation, typed model refusal,
measured energy/gradient binding, source-boundary protection, process ownership,
and concurrent filtered archives. Mathematical Boltzmann ratios remain tested in
[student report contracts](../tests/base/test_student_reports.py); native thermal
qualification is checked separately and cannot be inferred from those ratios.

All three edited files were outside `selected_test_sources()`, including its
statically imported helper closure. The exact 145-file selected-source hash
inventory remained unchanged during this retirement. No importing test/helper
dependencies on the retired definitions were found. No production code changed.

Actual retained evidence, produced before this retirement:

- `/workspace/cochem-runtime/evidence/base-physical-crest-goat-sieve-immutable-final/acceptance.json`: real CREST/GOAT execution and source-preserving union. Mixed-method members remain incomparable unless a matched protocol is supplied.
- `/workspace/cochem-runtime/evidence/student-topos-c2-policy-baseline/acceptance.json` and `student-topos-c2-policy-extended/acceptance.json`: exact C2 sealed-provider water energy, monomer-pair search, BOM input, matrix optimization and water RRHO records. The two water minima do not demonstrate distinct isomers.
- `/workspace/cochem-runtime/evidence/torq-base-integrated-research-acceptance-final/acceptance.json`: actual three-point PBE-D4/def2-SVP scan and checkpoint-derived HF/STO-3G H2 Löwdin Wiberg analysis. This is not NBO/NAO acceptance.

These evidence paths identify earlier exact source snapshots. The final sealed
science revision requires its own native acceptance before release certification.
Real hosted Actions, student Codespaces and cluster acceptance retain their
separate execution requirements.
