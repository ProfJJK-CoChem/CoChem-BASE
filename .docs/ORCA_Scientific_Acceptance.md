# Real ORCA scientific integration acceptance

BASE owns validated input, execution, ingestion, publication and ecosystem
handoffs. These bounded calculations exercise those responsibilities with real
ORCA 6.1.1 outputs. They do not certify experimental accuracy for every molecule
or implement the future TOPOS/TORQ scientific solvers.

## Canonical coupled-cluster reference and Recipe R2

Run the bounded reference-generation and R2 acceptance on a host with a fresh
Stage 0 registry and configured ORCA runtime:

```bash
python scripts/verify_r2.py --registry "$COCHEM_CONFIG" --output /external/new-r2-evidence/acceptance.json
```

The output must be new and outside the source checkout. Failure reports and
actual calculation inputs/outputs remain available for review. One core and
1000 MB of ORCA memory are requested from the audited allocation. The reference
generation budget is ten minutes and the R2 budget is thirty minutes by default.

The reference protocol computes genuine canonical CCSD(T)/cc-pVTZ and cc-pVQZ
energies for H2, minimizing the explicitly defined finite-basis CBS estimate

`E(r) = E_HF,QZ(r) + [64 E_corr,QZ(r) - 27 E_corr,TZ(r)] / 37`.

The search is bounded to 0.70–0.79 angstrom with a 0.000002 angstrom numerical
optimizer tolerance. Separate 0.001 and 0.002 angstrom displacements test the
minimum's energy bracket, small first derivative, positive curvature and
curvature consistency. The report retains every real point, input/output hash,
binary identity and explicit limitations. This is a finite-basis reference
construction protocol, not a mathematical guarantee of the exact CBS geometry.

The generated manifest includes a hashed `geometry_optimization_evidence`
artifact. BASE independently reparses every contributing real TZ/QZ output,
checks its hash and geometry, recomputes each CBS energy and checks both energy
brackets and curvatures. It records `bounded_computational_protocol_verified`;
independent exact-CBS or experimental accuracy remains explicitly unverified.
Ordinary supplied manifests without this evidence cannot acquire that status.

At the resulting H2 bond length, a T-shaped H2 dimer enters BASE's real R2 runner:
frozen-monomer wB97M-V/def2-QZVPP optimization, two isolated monomer energies and
two ghost-basis energies. Checks cover all five actual calculations, complete
trajectory integrity, genuine gradients, SCF/geometry convergence, counterpoise
algebra, reference identity and canonical scientific publication.

ORCA may declare convergence with one displacement criterion unmet. R2 requests
a tenfold displacement margin and independently retains all five original SRS
acceptance limits. A run that exceeds a required achieved value remains rejected.

The SCF block requests `ConvCheckMode 0` and `ConvForced true` so ORCA uses its
all-criteria convergence mode. A tighter requested energy tolerance alone was
insufficient: the default mode could terminate with an energy change above the
required acceptance threshold. Actual achieved SCF changes remain independently
checked against 1e-8 Hartree; the request uses 1e-10 Hartree for margin.

A frozen CCSD(T)/CBS-estimate monomer need not be stationary on the DFT surface.
The measured Wilson-projected residual gradient must therefore agree with its
warning flag and emitted warning. A physically justified strain warning is
retained; it is not hidden to turn an acceptance result green.

Counterpoise ordering is also measured, not presumed. The governing requirement
calls for counterpoise bracketing; it does not require a nonnegative correction.
The prescribed finite RI/COSX quadratures and post-SCF VV10 evaluation need not
preserve strict variational ordering when ghost basis functions are added.
BASE retains both measured interaction energies and their signed difference,
emits `CounterpoiseOrderingWarning` when the expected ordering is reversed, and
explicitly records that the ordered raw/CP interval is **not a verified
conservative physical bound**. The standalone arithmetic helper retains its
strict default for callers requiring variational ordering.

In the real H2 case, the RIJCOSX monomer-A/ghost-A pair gave a correction of
**−3.48309e-7 Hartree**. An additional real calculation with exact integrals
(`NORI`), at identical geometry, functional, basis and DEFGRID3, gave
**+7.6741e-8 Hartree**. This diagnoses approximation-sensitive ordering; it does
not establish a complete exact-integral five-leg result. Original input/output
hashes and the comparison are retained in
`/workspace/cochem-runtime/evidence/r2-physical-2026-10-07/counterpoise-ordering-diagnostic.json`.
No tolerance was loosened and no energy or correction sign was altered.

For independent cross-engine reference verification, use the isolated PySCF
interpreter:

```bash
/path/to/pyscf-silo/bin/python scripts/verify_cbs_reference_pyscf.py \
  --reference /external/new-r2-evidence/acceptance-work/reference/reference-generation.json \
  --output /external/new-r2-evidence/independent-pyscf/reference-check.json
```

The check recomputes converged RHF, CCSD and perturbative triples at both bases,
with one thread and a declared cross-engine energy tolerance of 1e-7 Hartree.
H2 has two electrons, so its triples correction is zero to numerical precision.
This case cannot certify nonzero triples corrections in larger molecules.

## Measured reference and conformer evidence

The 2026-10-07 local run calculated fourteen actual T/Q reference pairs. Its
finite-basis estimated H2 minimum is **0.741802 angstrom**. Independent PySCF
2.14.0 total energies agreed with ORCA within **6.04e-11 Hartree (TZ)** and
**9.36e-11 Hartree (QZ)**. Original evidence is retained under
`/workspace/cochem-runtime/evidence/r2-physical-2026-10-07/`.

Four unchanged final reference input/output files are versioned under
`tests/fixtures/orca_6_1_1/` with immutable fixture digests and source provenance.
They reproduce parser regressions caused by genuine ORCA contributor-banner
text and its actual SCF-energy output format. Replaying them is a parser test,
not a new physical calculation.

The actual CREST plus ORCA GOAT water union passed in **155.19 seconds**. Both
engines exited successfully, two candidates merged to one, and BASE verified
HDF5 publication and durable promotion. The retained ensemble SHA-256 is
`3526850368a9e954d0e358f866c5d32c3736af6d357ae03bc1c2361335c053b4`.
Evidence is under `/workspace/cochem-runtime/evidence/crest-goat-union-2026-10-07/`
and its neighboring JUnit XML and log. This closes that bounded ingestion/union
execution check; it does not claim full TOPOS domain acceptance.

The final R2 test file passed **18 tests with no skips**, including a new actual
five-leg run, in **85.66 seconds**. Evidence is
`/workspace/cochem-runtime/evidence/r2-physical-final-pytest.xml` and its log and
runtime directory. The preceding fully computed five-leg result also has an
independent publication check in
`/workspace/cochem-runtime/evidence/r2-physical-2026-10-07/accepted-r2-publication.json`.
It verifies every final energy against canonical HDF5 telemetry, including the
optimization's genuine intermediate trajectory rows. Its maximum frozen-bond
drift is **8.25746e-7 angstrom**, below the 1e-6 angstrom requirement.

This execution correctly emits two scientific warnings: the frozen-coordinate
residual is approximately **0.0046013 Hartree/bohr**, and the signed counterpoise
correction is approximately **−8.39e-7 Hartree**. Both measurements and their
limits remain in the result. Passing BASE's execution, provenance and warning
contracts does not certify a strain-free DFT monomer or a conservative physical
counterpoise bound.

Independent experimental geometry/rotational accuracy, general quantum PES
accuracy and downstream anharmonic properties require their own reference data
and scientific providers. No such claims are inferred from an installer, a
successful process exit, or these bounded integration calculations.

## Genuine quantum PES interpolation

The earlier EMT-derived 319.86 cm⁻¹ result was an artificial baseline-surrogate
benchmark, not an ORCA vibrational-frequency error. It remains historical
evidence of that benchmark's failed standalone prediction. New genuine ORCA
calculations now independently exercise BASE's existing dual-resolution PES
fitter on H2 over **0.55–1.80 angstrom**, from compressed through substantially
stretched bond lengths. The lower level is RHF/STO-3G and the higher level is
canonical CCSD(T)/cc-pVTZ. This is a bounded electronic-energy interpolation
test; it is not an experimental frequency comparison or general molecular
accuracy certification.

Both experiments declared geometries, methods, unchanged default fitting
parameters and acceptance criteria before their respective calculations.
Neither validation set supplies a fitted label or selects a kernel parameter.
The ordinary SRS criterion is a 10 cm⁻¹ RMS error; these experiments also require
the stricter **maximum absolute error of 10 cm⁻¹** for both prediction modes.

| Experiment | Paired correction RMS / maximum (cm⁻¹) | Standalone prediction RMS / maximum (cm⁻¹) | Result |
| --- | --- | --- | --- |
| 32 low-level and 32 paired correction training points; 31 midpoint holdouts | 1.19157 / 3.68324 | 7.09514 / 24.72782 | RMS target met; stricter maximum criterion failed |
| 128 low-level baseline and the same 32 paired correction training points; 31 fresh holdouts | 1.18929 / 3.72642 | 3.17672 / 8.24290 | Both RMS and maximum criteria passed |

The first result showed that baseline interpolation dominated the standalone
error. The follow-up increased only low-level sampling density, retaining the
same domain, correction training pairs and default fitting configuration.
Its new validation geometries use the predeclared 0.37 fraction of each original
training interval. They are absent from both training grids and from every
previous calculation. The original midpoint experiment remains development
evidence; its failed maximum is not replaced or reclassified as a pass.

The successful experiment ran 128 additional genuine low-level calculations
and 31 new low/high pairs in **77.05 seconds**, using one CPU core. The original
training pairs were hash-checked and reparsed before reuse. A separate replay of
all **316 genuine input/output pairs** checks both experiments and recomputes
the successful metrics. Replay does not count as a new physical calculation.

The retained reports are
`/workspace/cochem-runtime/evidence/quantum-pes-2026-10-07/acceptance-v2.json`
and `dual-resolution-acceptance.json` in the same directory. The latter's
SHA-256 is
`f98643317f44b9897cb75e77338190183dcc7d932f5b78b24ac03d327d88d2a9`;
its unchanged predeclared protocol SHA-256 is
`19ccb849f255ca9d9814642d969de7dc35dfb47d9ec99344d786dbd58cb93e46`.
Every contributing actual input/output has its own recorded hash. The initial
failed SCF attempt is also retained: ORCA's initially stationary TRAH guess
printed an initial energy as its last energy change. Explicit DIIS with
`NoTRAH NoSOSCF` produced two actual iterations and an accepted successive
energy difference. This execution correction preceded any held-out fitting.

Reproduce both experiments with a fresh registry and distinct external paths:

```bash
# This first protocol intentionally reports failure when its maximum exceeds
# 10 cm^-1, even when its RMS error meets the SRS target. Preserve the report.
python scripts/verify_quantum_pes.py \
  --registry "$COCHEM_CONFIG" --output /external/pes/sparse.json
python scripts/verify_quantum_pes_dual.py \
  --registry "$COCHEM_CONFIG" \
  --previous-experiment /external/pes/sparse.json \
  --output /external/pes/dense.json

# Verify existing hashes, achieved convergence, coordinates, energies and fits;
# this mode does not launch any new chemistry calculation.
python scripts/verify_quantum_pes_dual.py \
  --verify-existing /external/pes/dense.json \
  --output /external/pes/dense-replay.json
```

The paired mode receives a genuine evaluated lower-level energy at each
validation geometry; the standalone mode receives geometry alone. Keeping both
metrics separate prevents the correction's good accuracy from concealing a
poor baseline surrogate. Passing this declared two-electron, one-dimensional
domain does not certify nonzero triples corrections, other molecules,
multidimensional surfaces, extrapolation or vibrational spectroscopy.
