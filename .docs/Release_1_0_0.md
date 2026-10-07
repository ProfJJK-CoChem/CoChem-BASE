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

The preceding complete local profile recorded **1,241 passed, 4 declared
external checks deferred and 0 failures** at its historical prepublication
revision. That count must not be reused for subsequent source changes. The
canonical release profile is `python ci_tools/base_ci.py all` in the prepared
environment; its report records exact deferred checks and source integrity.

Current provisioning and hosted evidence belongs in
[ORCA Actions setup](ORCA_Actions_Setup.md). Additional scientific calculations
are recorded in [ORCA scientific acceptance](ORCA_Scientific_Acceptance.md).
The final release record must identify the tested commit, canonical suite
report, hosted calculation runs, browser evidence and distribution hashes.

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
