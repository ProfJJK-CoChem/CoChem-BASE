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

In the repository running the workflow, create the Actions secret
`ORCA_ASSET_READ_TOKEN`. Its fine-grained token needs Contents read access to the
private `ProfJJK-CoChem/CoChem-ORCA` repository. The default `GITHUB_TOKEN` cannot
automatically read another private repository. Organization approval, when
required by the repository owner, must be complete before download.

In GitHub's fine-grained token editor, select resource owner
`ProfJJK-CoChem`, then **Only select repositories → CoChem-ORCA**. Under
**Permissions → Add permissions**, select **Contents** directly
and set its access to **Read-only**. This is the asset repository, not BASE.
Generate the token with an expiration date and save its value in
**CoChem-BASE → Settings → Secrets and variables → Actions →
ORCA_ASSET_READ_TOKEN**. Do not put the token in source, logs or chat.
For a course, an instructor can provide the same narrowly scoped organization
secret to selected authorized calculation repositories; it is not copied with
assignment template files. The [course guide](GitHub_Classroom_ORCA_Setup.md#5-make-the-secret-available-to-the-calculation-repository)
explains organization-plan limits, student-owned repositories and why students
who can edit credential-bearing workflows must be authorized to use that access.
GitHub also supports a [prefilled token form](https://github.com/settings/personal-access-tokens/new?name=CoChem%20ORCA%20asset%20reader&target_name=ProfJJK-CoChem&contents=read&expires_in=90)
that selects the owner and Contents read permission; select `CoChem-ORCA`
manually before generating it.

A `release not found` response can mean that the token cannot access a private
release. Check the token's repository selection, expiration and any required
organization approval before changing the reviewed repository or tag. Updating
a token in GitHub does not automatically replace an older token value saved in
the Actions secret.

The access check, full acceptance and student calculation workflows all read
the same reviewed `scripts/orca-distribution.json`; no Actions variables are
required. The earlier `ORCA_ASSET_*` and `ORCA_RELEASE_TAG` variable overrides
are no longer used. Instructors can review and change the private repository,
tag and independently verified checksum in the manifest. The supported build
identity remains ORCA 6.1.1 for Linux x86-64 with Open MPI 4.1.8; another platform
or MPI build requires its own supported provisioner.

Run **Actions → ORCA 6.1.1 calculation acceptance → Run workflow** after the
workflow is on the default branch. The implementation branch
`codex/orca-6.1.1-actions` also triggers it on pushes changing the integration,
so the first authorized publication can test the proposed code before merging.
The licensed job has no pull-request trigger.

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

The separate `ORCA calculation` workflow accepts a reviewed repository-relative
`job_file` containing a flat `CalculationMatrixConfig` JSON document. The
default example is `examples/jobs/water-single-point.json`; additional examples
are `examples/jobs/water-optimization.json` and `examples/jobs/water-harmonic.json`.
The Voilà interface's **Prepare GitHub
Actions job** button exports a validated portable JSON request for submission
under `jobs/`; it does not execute the calculation locally or silently dispatch
a GitHub job. Follow the [student walkthrough](GitHub_Classroom_ORCA_Setup.md#run-your-assignment-calculation)
to commit the input and start the workflow.

The workflow checks out the selected revision of its own calculation repository,
then uses the same ORCA provisioner and fresh Stage 0 setup as acceptance. It
allows one or two ORCA processes, defaults to 512 MB per process, and caps that
setting at 1024 MB per process. The job is limited to 50 atoms, a 256 KiB JSON
document and at most 1800 seconds of calculation execution. Referenced files,
R2 reference manifests, T9 recovery, periodic operations and VPT2 require other
workflows and are rejected here. Full scientific capability validation follows
the early path/JSON/resource checks.

The artifact `orca-calculation-<run-id>-<attempt>` retains the submitted and
validated inputs, SHA-256 records, engine output, accepted result, HDF5 scientific
record, provisioning and Stage 0 evidence, and available failure diagnostics.
The token is supplied only to the archive-download step. Neither the licensed
archive nor its installation is uploaded. This calculation workflow does not
automatically post a Classroom50 assignment score. Its actual hosted execution
must be reported separately from implementation or unit-test results.

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
pass a full 40-character BASE commit as `base_ref` and explicitly pass
`ORCA_ASSET_READ_TOKEN`. `base_repository` defaults to
`ProfJJK-CoChem/CoChem-BASE` and can select a reviewed BASE mirror. When the
caller's default token cannot read that private source repository, the caller
can pass the separate optional `BASE_SOURCE_READ_TOKEN` with Contents read
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

The complete canonical local 1.0.0 profile passed **1,477 tests**, with **2
physical Slurm checks deferred**, **0 failures** and **1,479 collected** in
931.49 seconds. Source and test gates passed with no unexpected skips, omitted
node outcomes or source mutation. The 10,672 warnings remain in the logs.
Unlike the preceding 1,241-pass/4-deferral snapshot, actual R2 and CREST/GOAT
acceptance executed; only the two exact physical Slurm nodes remain skipped.
Evidence: `/workspace/cochem-runtime/evidence/base-1.0.0-final-v3/`, tested
at `190e5c548b800872626b87a463f0e6d854ba2030`. The preceding v2 run on
2026-10-07 passed 1,469 tests with the same two physical Slurm deferrals;
it is retained as historical evidence, not the current count.

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

[Bounded hosted CI run 37617769942](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37617769942)
**passed** at `190e5c548b800872626b87a463f0e6d854ba2030`: source integrity,
Ubuntu/macOS/Windows control tests and isolated wheel/CLI checks, including
actual native launcher diagnostics, all succeeded. The Linux physical job also
completed all eleven Stage 0 phases, real xTB/PySCF calculations, bounded
regressions with source-hash verification and rendered dashboard lifecycle.
Actual logs record **164 control tests passed on each operating system** and
**480 bounded regression tests passed** in 67.24 seconds, with 116 retained
deprecation warnings and no unexpected skips, failures or source changes.
These are separate, overlapping profiles and are not summed into a test total.
The extracted summary is
`/workspace/cochem-runtime/evidence/hosted-ci-37617769942/validation-summary.json`.
Run metadata and exact job/step outcomes are retained at
`/workspace/cochem-runtime/evidence/hosted-ci-37617769942/latest-run.json`.
The prior Windows control failures are resolved by this run. This is bounded
hosted CI, not execution of the entire silo-dependent canonical scientific
profile on each operating system. Full local acceptance also passed on
`190e5c5`: 1,477 passed and two physical Slurm deferrals. Publication status and
the mapping between tested and release revisions remain in the
[release record](Release_1_0_0.md).

For historical context, the [initial push run](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37571459336)
and [initial dispatched run](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37571482477)
at `cf709d040fff7a5c4db433cb921f3451f7888328` failed at private release download
with `release not found` and did not reach MPI or chemistry. The subsequently
replaced Actions token now has demonstrated effective access in the successful
hosted run above. Those historical failures no longer describe current asset
authorization.
