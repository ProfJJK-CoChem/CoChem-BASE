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
`PRIVATE_ORCA_ASSET_CREDENTIAL`. Its fine-grained token needs Contents read access to the
private `ProfJJK-CoChem/CoChem-ORCA` repository. The default `GITHUB_TOKEN` cannot
automatically read another private repository. Organization approval, when
required by the repository owner, must be complete before download.

In GitHub's fine-grained token editor, select resource owner
`ProfJJK-CoChem`, then **Only select repositories → CoChem-ORCA**. Under
**Permissions → Add permissions**, select **Contents** directly
and set its access to **Read-only**. This is the asset repository, not BASE.
Generate the token with an expiration date and save its value in
**CoChem-BASE → Settings → Secrets and variables → Actions →
PRIVATE_ORCA_ASSET_CREDENTIAL**. Do not put the token in source, logs or chat.
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
`PRIVATE_ORCA_ASSET_CREDENTIAL`. `base_repository` defaults to
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

## Prepublication validation

The complete canonical local run passed: **1,241 passed, 4 external checks
deferred, 0 failures**, from 1,245 collected tests in 486.08 seconds. The source
audit passed and source bytes were unchanged during testing. The 10,669 warnings
are retained in the log. The four deferred checks are physical R2/reference
acceptance, CREST/GOAT union and two physical Slurm-node checks. Actual licensed
ORCA installation and the separate hosted serial/parallel test are not included
in this local pass count. All workflow files passed `actionlint`; the prepared
Python environment passed `pip check`.

Evidence is retained at
`/workspace/cochem-runtime/evidence/orca-actions-prepublication/`.

## Hosted execution status

Commit `cf709d040fff7a5c4db433cb921f3451f7888328` was pushed to
`codex/orca-6.1.1-actions`. Both the [push run](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37571459336)
and [dispatched run](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37571482477)
executed on GitHub-hosted runners and failed at the private release download:
`release not found`. The Actions secret was present, but its credential did not
provide effective access. Neither run reached MPI installation or calculations.

An independently authorized cloud credential successfully retrieved the
published release and archive, and the archive matches the user-supplied SHA-256.
GitHub API and upstream MPI download access now work in the cloud environment.
The user has since saved a replacement Actions token. Its effective access and
the complete installation must be established by a new hosted calculation run;
the historical failures above do not describe the replacement token's result.
Download/hash success in this cloud environment does not establish hosted
calculation success.
