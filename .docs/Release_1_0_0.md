# CoChem-BASE 1.0.0 release record

**Status: prepared for release validation; not yet tagged or published.**
Version metadata alone does not establish release acceptance. Final test
counts, hosted run URLs and distribution digests must refer to the reviewed
release revision before publication.

## Scope

CoChem-BASE owns molecular/scientific input ingestion, environment setup,
audited engine discovery, the Voilà interface, validated native execution,
result storage and versioned handoffs to other CoChem modules. The accepted SRS
baseline is Chunk 17 plus additions from the architectural proposal.

The primary student route is **Classroom50 in an instructor-managed GitHub
organization**, with calculation jobs running on GitHub-hosted Ubuntu x86-64
CPU runners. The instructor provisions an approved private ORCA 6.1.1 archive;
CoChem pins its SHA-256, provisions Open MPI 4.1.8, creates a fresh Stage 0
registry, and validates actual engine results. See the
[complete Classroom50 walkthrough](GitHub_Classroom_ORCA_Setup.md).

## Capability and platform boundaries

| Area | Release scope and evidence requirement |
| --- | --- |
| Linux CPU input/setup/GUI/execution | Local canonical BASE tests, browser checks and actual low-cost calculations provide the applicable evidence. |
| ORCA installation | Approved Linux x86-64 ORCA 6.1.1/Open MPI 4.1.8 archive; complete file/hash/version checks, disk preflight and a genuine two-rank MPI collective. |
| ORCA molecular execution | Serial/parallel energy agreement; optimization and harmonic derivative acceptance with preserved inputs, outputs, provenance and HDF5 records. |
| Student Actions jobs | Molecular ORCA requests with embedded geometry; bounded resources; single point, optimization and supported harmonic frequencies. Input and checked-out revision accompany each result. |
| GitHub-hosted deployment | Actual hosted access, installation, Stage 0 and calculation runs must pass for the release revision. Local equivalents are separate evidence. |
| Other free engines | xTB, CREST, PySCF and QE remain subject to installed/audited capabilities and documented physical acceptance. Discovery is not a passed calculation. |
| WSL and macOS | Platform-aware configuration remains available; each native host needs its own setup and physical tests. Linux evidence does not certify WSL/macOS. |
| GPU, Slurm and other native hosts | Previously deferred until a suitable host is supplied; retained interfaces are not completed physical acceptance. |
| CFOUR/VPT2, TOPOS and TORQ | BASE prepares validated handoffs and capability states. Remaining domain implementation belongs to those ecosystem modules. |
| Classroom50 enrollment and permissions | Instructions verified against official documentation. A real student-account pilot is recommended before course rollout and remains an external institution-specific check. |

No small HF/STO-3G example establishes spectroscopic accuracy or a universal
10 cm⁻¹ PES prediction bound. Harmonic frequencies at supplied coordinates do
not establish a stationary point. Independent references are needed where a
scientific accuracy requirement calls for them.

## Validation record

The complete canonical local 1.0.0 profile passed **1,469 tests**, with **2
explicit physical Slurm deferrals**, **0 failures** and **1,471 collected** in
**908.20 seconds**. All 10,672 warnings remain in the log. Both source and test
gates passed; there were no unexpected skips, missing node outcomes or audited
source changes. The two skipped nodes require an actual Slurm allocation and
are not passed tests. Evidence is retained in
`/workspace/cochem-runtime/evidence/base-1.0.0-final-v2/` (`summary.json`,
`source-audit.json`, `test-acceptance.json`, pytest outcomes and source snapshots).
This run tested the application implementation at `1cfa49a` together with the
input fixture subsequently committed in `01cca5b`; final source metadata and
hosted fixes require their own follow-up verification. The earlier 1,189/1,241
counts belong to historical snapshots and are not added to this count.

[Hosted ORCA acceptance run 37613653904](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37613653904)
passed at `1cfa49a84d45da7c60ffd1fa0d6eae3889dbe049`: private asset download,
checksum/version verification, genuine two-rank MPI, all eleven Stage 0 phases,
and **3 physical/boundary tests passed in 13.20 seconds**. The real serial and
two-process BASE calculations satisfied the unchanged `1e-8 Eh` energy
agreement threshold and result/HDF5 publication checks. Evidence artifact:
`orca-6.1.1-acceptance-37613653904-1`. Exact energies are in that artifact;
they are not inferred from the pytest pass count.

The separate [student optimization/frequency run 37613654179](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37613654179)
failed and is being corrected; it is not covered by the successful acceptance
workflow. The bounded hosted CI rerun is also incomplete: Linux/macOS controls
and wheels have passed, while a Windows control failure is under correction.
These outcomes prevent an all-hosted-pass claim. Current run-specific evidence
belongs in [ORCA Actions setup](ORCA_Actions_Setup.md).

The bounded real H2 PES interpolation used 128 ORCA RHF/STO-3G baseline points,
32 CCSD(T)/cc-pVTZ correction pairs and 31 fresh geometries excluded from both
training sets over 0.55–1.80 Å. With unchanged model defaults, standalone energy
prediction had **3.176715694 cm⁻¹ RMSE** and **8.242899532 cm⁻¹ maximum absolute
error**, both below the 10 cm⁻¹ bound for this protocol. Paired correction RMSE
was 1.189292656 cm⁻¹ and its maximum absolute error was 3.726415424 cm⁻¹.
This is a two-electron one-dimensional interpolation check; it does not measure
nonzero triples contributions, vibrational-frequency accuracy, extrapolation,
experimental agreement or arbitrary molecules. Evidence:
`/workspace/cochem-runtime/evidence/quantum-pes-2026-10-07/dual-resolution-acceptance.json`.

Actual frozen-monomer R1, accepted five-leg R2, grid refinements, spin recovery,
CREST/GOAT union and Hessian/isotope parity are described in
[ORCA scientific acceptance](ORCA_Scientific_Acceptance.md). The accepted R2
report retains its measured signed counterpoise ordering and residual-gradient
warnings; no sign or tolerance was changed to create acceptance.

At committed revision `01cca5be1f917af29ce36900c5da4dad30564bed`, the **479-test
bounded regression selection passed with no skips or source mutation**, and a
fresh isolated wheel install passed package-origin, CLI, isotope database,
`pip check`, hardware and real dry-run deck checks. These local checks do not
claim a hosted run or a chemistry execution by the packaging test. Evidence:
`/workspace/cochem-runtime/evidence/release-ci-01cca5b-regressions/` and
`/workspace/cochem-runtime/evidence/release-ci-01cca5b-wheel/`. The tested wheel
SHA-256 is `9f4b69804de322163d2d9caf0207bab8cad13ad940e75545dc289539379372b4`;
it is a revision-specific validation artifact, not an already published release.

The preliminary 1.0.0 wheel and source archive built successfully outside the
checkout. A second clean virtual environment installed the corrected wheel
using only its declared dependencies and passed seven installed-package checks:
console/module version reporting, CLI run help, a real Mendeleev 13C lookup,
package/configuration imports, `pip check`, and actual HF/STO-3G deck generation
using the existing same-host audited registry read-only. No engine calculation
was claimed for the packaging smoke test. This exercise identified and fixed
the missing core `jinja2` dependency.

A follow-up import regression exposed a legacy `PYTHONPATH` collision between
the root CLI and an installed-module shim. The canonical implementation now
lives in `cochem_base.cli`; the root file is a compatibility launcher and Stage
0 imports the package explicitly. The original failing real setup test and
three CLI memory-boundary tests passed. The rebuilt wheel passed console/module,
mass lookup, help, `pip check`, real partial Stage 0 and deck-generation checks;
the legacy path ordering also passed actual setup without publishing a partial
master registry.

Preliminary build evidence is retained at
`/workspace/cochem-runtime/evidence/release-packaging-1.0.0/`. These artifacts
come from a working-tree snapshot and must be rebuilt from the final reviewed
release revision before publication. `cli-fixed-wheel-smoke.json` and
`cli-fixed-distribution-hashes.json` record the latest packaging checks and
digests; they are not final release artifacts.

## Distribution and entry points

`pyproject.toml` is the canonical version source. Source execution reads that
version without importing scientific dependencies; installed wheels read their
distribution metadata. `cochem-cli` and `python -m cochem_base.cli` invoke the
same CLI as `python cli.py` in a checkout.

The wheel provides Python packages and CLI entry points. The complete source
distribution also includes `Start_Here.ipynb`, platform launchers, setup scripts,
workflow definitions, requirements, examples and guides. Use the source checkout
or unpacked source distribution for the full Voilà launch/setup pathway:

```bash
python3 scripts/bootstrap_environment.py
./Launch_CoChem_Mac_Linux.sh
```

Windows users can use `Launch_CoChem_Windows.bat` for the interface and select
GitHub Actions for chemistry, or use an appropriate Linux installation inside
WSL2. The Linux ORCA archive does not execute natively in PowerShell.

Installing Python packages does not distribute ORCA, create a GitHub secret,
install every scientific engine or replace Stage 0. Runtime data and evidence
must remain outside the source directory.

## Publication checks

- Build wheel and source archive outside the checkout from the reviewed source;
  retain SHA-256 digests and build metadata.
- Install the wheel in a fresh isolated environment; run import/CLI checks and
  `pip check` without importing the active editable checkout by accident.
- Complete the canonical suite and relevant real ORCA/student/browser checks
  against the release source; preserve declared external deferrals explicitly.
- Record final evidence, review the release commit, then create the 1.0.0 tag
  and publish only intended source/wheel assets. Licensed ORCA files are never
  release assets of CoChem-BASE.

Before rolling the course out to students, the instructor should pilot a real
Classroom50 assignment account, confirm its repository receives approved
archive access, and retrieve a calculation result. That institution-specific
check is a course deployment step, not a requirement to create an account or
enroll students as part of publishing CoChem source.
