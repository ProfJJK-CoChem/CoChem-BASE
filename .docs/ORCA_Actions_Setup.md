# ORCA 6.1.1 Actions provisioning and acceptance

For the complete instructor and student walkthrough, start with
[Classroom50 and ORCA on GitHub Actions: instructor and student setup](GitHub_Classroom_ORCA_Setup.md).
It covers Classroom50 in an instructor-managed GitHub organization, Windows PowerShell
checksums, private Release uploads, the current token permission controls,
secret access for each course repository, and the actual acceptance run.
This page records technical behavior and execution evidence.

The reviewed distribution is pinned in `scripts/orca-distribution.json`:

- Repository: `ProfJJK-CoChem/CoChem-ORCA`
- Release: `orca-6.1.1`
- Asset: `orca_6_1_1_linux_x86-64_shared_openmpi418.tar.xz`
- SHA-256: `a0bc1d6d2c3c00620367bbc5dbf2b3a7018abc92d1ff65f06cec46f75350b9be`
- Runtime: Linux x86-64, ORCA 6.1.1, Open MPI 4.1.8.

The archive must be attached to a published GitHub Release. A Git tag by itself
does not establish that a release asset exists. Keep the licensed archive private
and limit access according to the applicable license.

## GitHub configuration

The instructor-managed [GitHub App deployment](Personal_Project_App_Deployment.md)
is the primary route for private projects owned by students. The instructor
configures access once; the student authorizes the App for their selected private
project. The controller supplies encrypted repository credentials and their
private configuration bindings. Students do not create, copy or enter tokens.
Organization secrets do not automatically enter personal repositories.

Public source contains generic binding keys rather than the instructor's stored
credential labels:

| Private repository variable | Value in private settings |
| --- | --- |
| `COCHEM_ORCA_ACCESS_SECRET` | Name of the approved repository or organization archive secret |
| `COCHEM_SOURCE_ACCESS_SECRET` | Name of the separately scoped private source secret |

The ORCA workflow resolves `secrets[vars.COCHEM_ORCA_ACCESS_SECRET]`. For an
organization-owned course repository, an instructor may use a selected-repository
organization secret and grant the matching variable to the same repositories.
No duplicate repository secret is needed when that organization policy already
covers the project. Keep both policies restricted to approved private projects;
template files do not copy settings, credentials or access grants.

A fine-grained archive reader needs **Contents: Read-only** for the approved
private asset repository, an appropriate expiry and any required organization
approval. In GitHub's editor use **Permissions → Add permissions → Contents**.
The default project `GITHUB_TOKEN` cannot automatically read separate private
repositories. Team Read access and credential access are separate controls.

The downloader reads the reviewed `scripts/orca-distribution.json`. The private
binding variable selects a credential, not a different binary or checksum.
Missing credential configuration leaves ORCA unavailable in general BASE; a
calculation explicitly requiring ORCA fails with retained diagnostics. Leave
**Send secrets and variables to workflows from fork pull requests** disabled.

A `release not found` response can mean denied access. Check the App enrollment
or selected-repository policy, reader expiry and approval before changing a
reviewed repository, release or checksum. Run **Actions → ORCA 6.1.1 calculation
acceptance → Run workflow** in the approved project after configuring access.
The licensed acceptance has no pull-request trigger.

## What actually executes

1. Audit the selected BASE source with the canonical source gate.
2. Download the private release asset; verify its independently supplied SHA-256.
   The asset token is scoped to this download step.
3. Download checksum-pinned Open MPI 4.1.8 from the upstream release site; build a
   fresh shared C/C++ runtime, check versions and run a two-rank C++ collective.
   The source digest is also recorded by Spack's Open MPI 4.1.8 package recipe.
4. Verify the ORCA checksum again before safe extraction. Check expanded archive
   size against available installation storage, retaining a 4 GiB reserve.
   This 471,531,860-byte archive expands to 17,442,002,115 bytes; compressed size
   is not a suitable disk requirement. The disposable GitHub-hosted Linux job
   removes unrelated preinstalled SDKs to make room. Local and HPC installations
   do not perform that cleanup. Require a native
   executable and exact ORCA/MPI versions; record all distribution file hashes.
   ORCA's version probe invokes the genuine executable with an intentionally
   absent input filename inside a temporary directory and reads its own
   `Program Version` banner, as ASE's ORCA adapter does. Its expected input-file
   error is metadata interrogation, not a successful calculation. Bare ORCA
   does not print this banner, and `--version` is not a supported version flag.
5. Install the bounded BASE/UI profile and run all eleven real Stage 0 phases.
   The explicit 1 GB minimum free-storage profile is for these small CPU tests;
   the production setup default remains 50 GB.
6. Run the physical ORCA acceptance test and two failure-boundary tests. The
   physical test calls BASE's canonical CLI for HF/STO-3G water with one and two
   processes. It requires actual SCF convergence, normal termination, the MPI
   banner, energy agreement within `1e-8 Eh`, unchanged executable identity and
   agreement between engine output, published JSON/QCSchema and HDF5 telemetry.
7. Upload selected scientific/provisioning evidence, including failed-run logs;
   remove the downloaded archive and installed licensed distribution. Neither is
   an Actions artifact or cache entry.

Download/hash success is not ORCA execution success. These small calculations
validate installation and integration, not high-level scientific accuracy, R2
reference acceptance, or TOPOS/TORQ domain algorithms. Missing ORCA, a missing
registry, failed MPI or failed calculations fail the licensed acceptance.

## Running a student calculation

Students open their private BASE project in Codespaces and wait for automatic
setup. They upload and classify their own scientific inputs using BASE's full
Input library, select **GitHub Actions**, and use **Run with GitHub Actions**.
BASE prepares the hash-bound request, monitors its actual run and retrieves the
verified scientific result. Students do not edit JSON, run terminal commands or
install TOPOS/TORQ directly. See the [student research guide](Student_Research_No_Code.md).

The approved canonical worker provisions only the requested engines and modules,
creates fresh Stage 0 authority for its actual host and records exact source,
engine, input and result identities. Missing engine access disables its dependent
choices; failures remain failed scientific runs. Downloaded licensed archives and
installations are excluded from calculation artifacts and caches.

The separate `ORCA calculation` workflow is an instructor acceptance interface
for bounded flat `CalculationMatrixConfig` examples. Its defaults, process/memory
limits and scientific admission checks apply to that workflow; it is not the
student's complete ingestion or provider interface. HF/STO-3G water validates
installation and execution, not a vdW research protocol or experimental accuracy.

## Reuse and other execution environments

`.github/actions/setup-orca` is a composite provisioning action. Other ecosystem
repositories can use it at an approved full BASE commit SHA, provide its
`asset-token` input, then run their own Stage 0/module acceptance. It expects a
Linux x86-64 runner, Python 3.11 or newer, GitHub CLI, GCC/G++, make and suitable
system runtime libraries. The action installs outside the checkout and exports
`COCHEM_ORCA_BIN`, `ORCA_CMD`, `ORCA_PATH`, MPI paths and provenance for this job.

Direct acceptance runs use the current course repository and selected commit,
so a Classroom50 copy does not try to check out its own commit from the upstream
BASE repository. The full workflow also supports `workflow_call`; callers must
pass a full 40-character BASE commit as `base_ref` and explicitly pass the
generic `engine_asset_credential` input using their private binding. `base_repository` defaults to
`ProfJJK-CoChem/CoChem-BASE` and can select a reviewed BASE mirror. When the
caller's default token cannot read that private source repository, the caller
can pass the separate optional `base_source_credential` with Contents read
access to the source. Private action/workflow reuse also depends on GitHub's
repository sharing rules. The ORCA-only token is not source access to another
private repository, and Classroom50's service token is not an ORCA credential.

This downloader does not replace platform-neutral engine discovery. Local Linux
and WSL use their configured compatible installation; macOS needs its matching
official build; HPC uses a compatible site installation/MPI module and actual
allocation resources. Produce a registry for the execution host/allocation.
Never reuse Actions absolute paths or audited CPU/RAM limits on another host.
The existing HPC/TORQ integration limits documented in `BASE_Alpha_Scope.md`
remain separate acceptance work.

For a prepared host with real ORCA and a current Stage 0 registry, the same
physical checks can be invoked without the Actions-only downloader:

```bash
python scripts/verify_orca.py --registry "$COCHEM_CONFIG" --output /external/new-evidence/acceptance.json
```

The output must be a fresh path outside the checkout. The script preserves a
failed report on a failed attempt and refuses to overwrite earlier evidence.

## Current local release validation — 2026-10-07

The complete canonical local 1.0.0 profile passed **1,532 tests**, with **2
physical Slurm checks deferred**, **0 failures** and **1,534 collected** in
950.50 seconds. Source and test gates passed with no unexpected skips, omitted
node outcomes or source mutation. The 10,672 warnings remain in the logs.
Unlike the preceding 1,241-pass/4-deferral snapshot, actual R2 and CREST/GOAT
acceptance executed; only the two exact physical Slurm nodes remain skipped.
Evidence: `/workspace/cochem-runtime/evidence/base-1.0.0-final-v4/`, tested
at `e2aaca60fefc4d1fd716aea176d54df9c1794d39`. The preceding v2 run on
2026-10-07 passed 1,469 tests; v3 passed 1,477 tests at `190e5c5`, with the same
two physical Slurm deferrals. Both are historical, not the current count.

The separate 479-test bounded selection and a fresh isolated 1.0.0 wheel install
passed at `01cca5be1f917af29ce36900c5da4dad30564bed`. The bounded selection is
not the full canonical profile; the packaging test generates a real input deck
without claiming an engine calculation. See the [release record](Release_1_0_0.md)
for evidence paths, revision boundaries and remaining publication checks.

The earlier **1,241 passed, 4 deferred, 0 failures** result (1,245 collected;
486.08 seconds) is historical evidence at
`/workspace/cochem-runtime/evidence/orca-actions-prepublication/`. Its deferrals
were R2/reference acceptance, CREST/GOAT union and two physical Slurm nodes.
It is not the current suite count or a hosted result.

## Hosted execution status — 2026-10-07

[ORCA acceptance run 37613653904](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37613653904)
**succeeded** at commit `1cfa49a84d45da7c60ffd1fa0d6eae3889dbe049`. Every
provisioning, Stage 0, physical-test, artifact-upload and cleanup step passed.
The hosted log records **3 passed, 1 deprecation warning in 13.20 seconds**,
including actual serial and two-rank BASE publication with energy agreement
within `1e-8 Eh`. The registry records one physical CPU, two logical CPUs and
two allocatable vCPUs under the explicit `github_hosted_vcpus` policy.

The evidence artifact is `orca-6.1.1-acceptance-37613653904-1`
(artifact ID `11478918809`, 1,218,780 bytes). It contains the actual scientific
and provisioning records. Exact energies and their difference were not printed
in the pytest log and are not invented here. Sanitized logs and run metadata
are retained at `/workspace/cochem-runtime/evidence/hosted-orca-37613653904/`.

[Student optimization/frequency run 37616684042](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37616684042)
**passed** at `0a9effed573816bf3e802684e26097d7b697ea81`. It completed source
validation, private provisioning, all eleven Stage 0 phases, actual two-process
ORCA optimization plus harmonic frequencies, result validation and artifact
upload. It validates the student submission workflow independently of the
serial/parallel installation acceptance above.

The actual hosted HF/STO-3G water result used **2 processes at 512 MB per
process** and reported **−74.965901192195 Eh**. Principal-isotope harmonic
frequencies were **2170.013986, 4139.994538 and 4391.055250 cm⁻¹**. The retained
9×9 Hessian uses hartree/bohr²; independent spectrum reconstruction differed
from the native spectrum by at most `0.0002495644403 cm⁻¹`. This verifies the
optimization/derivative/publication pathway, not experimental frequency accuracy.

Artifact `orca-calculation-37616684042-1` (ID `11480713186`, 861,592 bytes) has
GitHub's recorded SHA-256 digest
`0094d54db33765f91b91a88aa79940f90f8f2deb2e0f047e24ffbbe425936cb0`.
The report extracted from actual hosted logs and run/artifact API metadata is
`/workspace/cochem-runtime/evidence/student-hosted-37616684042/hosted-acceptance-summary.json`.

The preceding [student run 37613654179](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37613654179)
failed because ORCA reported optimizer completion while its final measured RMS
gradient exceeded BASE's unchanged acceptance threshold. Canonical generated
inputs now request a tenfold margin on all five geometry thresholds; the result
parser's scientific acceptance gates remain unchanged. The successful hosted
rerun validates the corrected path instead of treating the old partial output
as a pass.

[Bounded hosted CI run 37624167721](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37624167721)
**passed** for head `e2aaca60fefc4d1fd716aea176d54df9c1794d39`. The actual
checkout was GitHub's pull-request merge commit
`a438644d168d72508ee7c40511f868d547ced74d`; its tree
`2626a26dcd3b33039f17cdc20308cd4d76320b3c` exactly matches that head.
Source integrity, Ubuntu/macOS/Windows control tests and isolated wheel/CLI
checks all succeeded, including actual native launcher diagnostics. The Linux
physical job completed all eleven Stage 0 phases, real xTB/PySCF calculations,
bounded regressions with source-hash verification and rendered dashboard
lifecycle. The bounded setup truthfully reports `DEGRADED_OPERATIONAL`.

Actual logs record **164 control tests passed on each operating system**:
Windows 5.03 seconds, macOS 3.41 seconds, Ubuntu 4.73 seconds. **537 bounded
regression tests passed** in 95.85 seconds, with 116 retained deprecation
warnings and no failures, unexpected skips, coverage errors or source changes.
These separate profiles overlap and are not summed into a test total. The
actual log-derived summary, checkout identity and per-platform wheel results
are retained in
`/workspace/cochem-runtime/evidence/hosted-ci-37624167721/validation-summary.json`.

The earlier run `37617769942` at `190e5c5` passed 480 bounded tests and is
historical evidence. Hosted bounded CI does not claim that the entire
silo-dependent scientific profile ran on every operating system. Full local
acceptance independently passed on `e2aaca60`: 1,532 passed and two physical
Slurm deferrals. Publication must record source equivalence between any final
documentation-only commit and the tested implementation; see the
[release record](Release_1_0_0.md).

For historical context, the [initial push run](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37571459336)
and [initial dispatched run](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37571482477)
at `cf709d040fff7a5c4db433cb921f3451f7888328` failed at private release download
with `release not found` and did not reach MPI or chemistry. The subsequently
replaced Actions token now has demonstrated effective access in the successful
hosted run above. Those historical failures no longer describe current asset
authorization.
