# CoChem-BASE 1.0.0 release record

**Validation complete for the supported BASE 1.0.0 scope.** Publication status
and final distribution digests belong to the
[GitHub `v1.0.0` release notes](https://github.com/ProfJJK-CoChem/CoChem-BASE/releases/tag/v1.0.0).
Only files actually listed there are published attachments; a source-only
release does not imply that a wheel, built source distribution or checksum file
was uploaded. This validation record does not itself create a tag or publish
files.

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
| GitHub-hosted deployment | Actual hosted archive access, installation, Stage 0, serial/parallel acceptance and student optimization/frequency execution passed at the revisions recorded below. |
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

The complete canonical local 1.0.0 profile passed **1,477 tests**, with **2
explicit physical Slurm deferrals**, **0 failures** and **1,479 collected** in
**931.49 seconds**. All 10,672 warnings remain in the log. Both source and test
gates passed; there were no unexpected skips, missing node outcomes or audited
source changes. The two skipped nodes require an actual Slurm allocation and
are not passed tests. Evidence is retained in
`/workspace/cochem-runtime/evidence/base-1.0.0-final-v3/` (`summary.json`,
`source-audit.json`, `test-acceptance.json`, pytest outcomes and source snapshots).
This run tested commit `190e5c548b800872626b87a463f0e6d854ba2030`, the same
implementation that passed final bounded hosted CI. The earlier 1,189/1,241
counts and the 1,469-pass v2 run on 2026-10-07 are historical; they are not
added to this count. Subsequent release changes are documentation only.
Publication records identify the tested revisions and their source equivalence
to the release revision; earlier hosted logs retain their actual commit IDs.

[Hosted ORCA acceptance run 37613653904](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37613653904)
passed at `1cfa49a84d45da7c60ffd1fa0d6eae3889dbe049`: private asset download,
checksum/version verification, genuine two-rank MPI, all eleven Stage 0 phases,
and **3 physical/boundary tests passed in 13.20 seconds**. The real serial and
two-process BASE calculations satisfied the unchanged `1e-8 Eh` energy
agreement threshold and result/HDF5 publication checks. Evidence artifact:
`orca-6.1.1-acceptance-37613653904-1`. Exact energies are in that artifact;
they are not inferred from the pytest pass count.

The [student optimization/frequency run 37616684042](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37616684042)
**passed** at `0a9effed573816bf3e802684e26097d7b697ea81`, including private
provisioning, all eleven Stage 0 phases, actual two-process ORCA optimization
and harmonic frequencies, scientific validation and evidence upload. This
closes the preceding failed student run `37613654179`: ORCA's reported optimizer
completion had failed BASE's unchanged achieved-gradient gate. Input thresholds
now request additional convergence margin; acceptance limits were not relaxed.
The hosted water result was `−74.965901192195 Eh`, with a 9×9 Hessian and three
physical harmonic modes; its actual log-derived report is
`/workspace/cochem-runtime/evidence/student-hosted-37616684042/hosted-acceptance-summary.json`.
Artifact: `orca-calculation-37616684042-1`. The detailed
[Actions evidence](ORCA_Actions_Setup.md#hosted-execution-status--2026-10-07)
records its frequencies, units, resources and GitHub artifact digest.

The [bounded hosted CI run 37617769942](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37617769942)
**passed** at `190e5c548b800872626b87a463f0e6d854ba2030`. Source integrity,
Ubuntu/macOS/Windows control tests and clean wheel/CLI checks all passed,
including actual platform-native launcher diagnostics. Its Linux job also
passed real xTB/PySCF calculations, all eleven Stage 0 phases, the bounded
regression profile with source-hash checks and rendered dashboard lifecycle.
The logs record 164 control passes per operating system and 480 bounded
regression passes with no unexpected skips or source changes; overlapping
profiles are not added to the canonical count. Evidence:
`/workspace/cochem-runtime/evidence/hosted-ci-37617769942/validation-summary.json`.
This resolves the earlier Windows control failures. Hosted bounded CI is
separate from the full local scientific profile, which also passed against
`190e5c5` as recorded above. See
[ORCA Actions setup](ORCA_Actions_Setup.md) for run-specific evidence.

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

Clean wheel installation on Ubuntu, macOS and Windows passed package-origin,
CLI/module entry-point, isotope database, dependency and actual dry-run deck
checks. These packaging checks do not claim an engine calculation. Wheels and
source distributions are built for validation outside the checkout. Their
exact SHA-256 digests and upload status can be recorded directly in the release
notes; an attached `SHA256SUMS` file is optional. If attachment upload is
unavailable, validated builds remain local and publication is source-only.
Earlier package-validation evidence remains under
`/workspace/cochem-runtime/evidence/release-packaging-1.0.0/` and
`/workspace/cochem-runtime/evidence/release-ci-01cca5b-wheel/`; these historical
artifacts are not the final release distributions.

## Distribution and entry points

`pyproject.toml` is the canonical version source. Source execution reads that
version without importing scientific dependencies; installed wheels read their
distribution metadata. `cochem-cli` and `python -m cochem_base.cli` invoke the
same CLI as `python cli.py` in a checkout.

For a source-only release, use the tagged repository checkout or GitHub's
automatically generated **Source code** ZIP/tar.gz. Those downloads contain the
tagged source tree; they are distinct from a separately built Python source
distribution. Classroom50 students should use their accepted assignment copy.

When a wheel is supplied, it provides Python packages and CLI entry points.
The source checkout and built source distribution include `Start_Here.ipynb`, platform launchers, setup scripts,
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
- Preserve the completed canonical, hosted ORCA/student/browser and packaging
  evidence with its actual tested revisions. For documentation-only release
  commits, verify and record equivalence of production, CI, test and immutable
  input bytes to the tested code; preserve external deferrals explicitly.
- Record final evidence, review the release commit, then create the 1.0.0 tag
  and publish its source release. Attach validated wheel/source-distribution
  files only when upload succeeds, and state which builds remain local.
  Record exact digests in the release notes without promising an attachment.
  Licensed ORCA files are never release assets of CoChem-BASE.

Before rolling the course out to students, the instructor should pilot a real
Classroom50 assignment account, confirm its repository receives approved
archive access, and retrieve a calculation result. That institution-specific
check is a course deployment step, not a requirement to create an account or
enroll students as part of publishing CoChem source.
