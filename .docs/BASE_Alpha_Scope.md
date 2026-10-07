# BASE alpha scope and deferred ecosystem acceptance

The governing baseline is SRS Chunk 17 plus proposal additions. The user's scope clarification is authoritative: CoChem-BASE is the ingestion, setup and GUI module of the 20-module CoChem ecosystem. BASE must validate, preserve and route scientific data, expose actual capabilities, execute its connected adapters faithfully, and provide reproducible module handoffs. It must not manufacture downstream results to make the interface appear complete.

A downstream scientific operation is distinct from BASE's responsibility to represent and hand off that operation. CFOUR/VPT2 and full anharmonic isotope workflows require their scientific providers. TOPOS and TORQ domain implementation and full multidimensional PES exploration are future repository work. Existing connected CREST/native calculation paths remain tested. Missing providers produce an explicit pending-integration artifact, not an energy, completed optimization, or passing scientific acceptance.

The user has now authorized ORCA 6.1.1 provisioning and actual GitHub Actions acceptance; its implementation and evidence are tracked in [ORCA Actions setup](ORCA_Actions_Setup.md). Codespaces rebuilds, CFOUR, GPU, Slurm and native-platform acceptance remain deferred until a stable alpha and a supplied host. Local lifecycle/browser checks are retained as local evidence. `ci_tools/deferred_acceptance.json` names the exact currently selected external tests, prerequisite and skip reason; an unexpected skipped local check remains an error.

## Test entrypoints

`python -m pytest` runs the canonical BASE profile. `pytest-srs.ini` is the equivalent compatibility entrypoint. It deliberately has no sibling-repository path injection and does not suppress whole warning classes. This profile is an explicit test selection, not a claim that all historical tests in this repository have passed. The wider repository collection and AST inventory remain separately visible.

The profile includes mathematical invariant checks, invalid-input checks and real low-cost calculations. An analytical or empirical fixture proves only the corresponding mathematical or empirical contract. It does not establish DFT, coupled-cluster, experimental or spectroscopic accuracy.

## Withdrawn misleading fixture evidence

Review of commit `ec5c2f8`'s `tests/data/generate_test_files.py` established:

- `water_hessian.npy` was generated with ASE EMT in eV/angstrom², but consumed as Hartree/bohr² and described as ab-initio evidence. The file is removed. The isotope acceptance now computes a fresh real ASE EMT Hessian, converts units explicitly and checks mass reweighting and rigid-rotor invariants. It makes no quantum accuracy claim.
- `h2co_cal_data.npz` and `h2co_trajectory.npz` combined unseeded noise, constant uncertainties and a CHHO/COHH identity mismatch. They are removed along with `tests/torq/test_conformal_quench_intervention.py`, whose claimed physical quench acceptance depended on them. Authentic TORQ calibration/quenching remains future TORQ work; BASE's replacement coverage validates durable module handoff and data integrity without certifying a quench.
- The ML schema test no longer describes numerical serialization inputs as an authentic ab-initio run. It remains an ecosystem schema test, outside the BASE alpha profile.

Deleted bytes and the historical test are retained for this review under `/workspace/cochem-runtime/evidence/retired-misclassified-fixtures/`. Git history preserves tracked originals. The retained XYZ coordinate examples are structural inputs, not accuracy reference geometries. The formaldehyde XYZ species order is restored to the generator's actual CHHO order; its previous COHH labels were inconsistent with the coordinates. The recorded native xTB trajectory has separate source/version/hash provenance under `tests/fixtures/trajectories/README.md`; replaying it proves parsing, not a fresh calculation.

## PES acceptance meaning

The historical 1631.753 cm⁻¹ result was produced from a chronological Cu/Ag/Au EMT trajectory and an artificial affine-transformed target, mislabeled DFT/CCSD(T). All 150 held frames lie outside the training feature domain. The former fit mixed a predicted low baseline into the training correction target and imposed zero-offset behavior on absolute energies.

Independent evaluation with actual paired high-minus-low targets and training-only centering gives 6.271842 cm⁻¹ on the unchanged 350/150 split and unchanged 10 cm⁻¹ threshold, when the actual low-level energy is supplied at prediction. The fully predicted surface remains approximately 319.863926 cm⁻¹ (low-baseline component 313.592085 cm⁻¹). Both metrics must remain visible; a correction pass is not a full-surface or quantum accuracy pass. Interaction energies with a declared dissociation-zero reference retain their separate zero-anchor constraints.

### What the 319.86 cm⁻¹ result measures

This is RMS potential-energy fitting error across 150 held-out geometries, expressed in spectroscopic energy units. It is not a predicted vibrational frequency, a frequency error or an error measured against experiment. It is equivalent to 0.914537 kcal/mol (0.0396581 eV).

The 500 samples follow one deterministic Cu/Ag/Au trajectory using the ASE EMT empirical potential. The first 350 frames train the model; the final 150 test it. The Cu–Ag separation spans 2.164836–4.003711 Å during training and 4.028296–5.016185 Å in the holdout: every held frame extends beyond the sampled training range in this coordinate. The local RBF baseline extrapolates poorly there.

The second target is constructed as `E_target = 1.02 * E_EMT - 0.005 eV`. It is not an independently calculated higher-level surface. With the same centered linear estimator, the measured errors obey:

| Evaluation | Held-out energy RMSE |
|---|---:|
| Fitted EMT baseline | 313.592085 cm⁻¹ |
| Evaluated EMT plus fitted correction | 6.271842 cm⁻¹ = 2% of baseline error |
| Fitted baseline plus fitted correction | 319.863926 cm⁻¹ = 102% of baseline error |

Consequently, the 6.27 result is limited algebraic regression evidence. It cannot demonstrate the SRS's independent physical accuracy target. Improving a standalone surface requires independently evaluated training geometries spanning its intended domain, training-only model selection and a fresh untouched validation set. Evaluating the actual low-level engine at prediction time removes baseline-surrogate error but does not validate the artificial upper target as quantum chemistry. The failed standalone case remains rejected by the API.
