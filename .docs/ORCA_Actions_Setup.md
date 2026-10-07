# ORCA 6.1.1 Actions provisioning and acceptance

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
GitHub also supports a [prefilled token form](https://github.com/settings/personal-access-tokens/new?name=CoChem%20ORCA%20asset%20reader&target_name=ProfJJK-CoChem&contents=read&expires_in=90)
that selects the owner and Contents read permission; select `CoChem-ORCA`
manually before generating it.

A `release not found` response can mean that the token cannot access a private
release. Check the token's repository selection, expiration and any required
organization approval before changing the reviewed repository or tag. Updating
a token in GitHub does not automatically replace an older token value saved in
the Actions secret.

The full installation workflow reads the reviewed manifest directly; no Actions
variables are required. The separate `ORCA private archive access` workflow
supports the earlier four optional `ORCA_ASSET_*`/`ORCA_RELEASE_TAG` settings and
defaults to the supplied distribution. Changing those variables does not change
the full installation's reviewed checksum or version.

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

## Reuse and other execution environments

`.github/actions/setup-orca` is a composite provisioning action. Other ecosystem
repositories can use it at an approved full BASE commit SHA, provide its
`asset-token` input, then run their own Stage 0/module acceptance. It expects a
Linux x86-64 runner, Python 3.11 or newer, GitHub CLI, GCC/G++, make and suitable
system runtime libraries. The action installs outside the checkout and exports
`COCHEM_ORCA_BIN`, `ORCA_CMD`, `ORCA_PATH`, MPI paths and provenance for this job.

The full workflow also supports `workflow_call`; callers must pass the exact
BASE commit as `base_ref` and explicitly pass `PRIVATE_ORCA_ASSET_CREDENTIAL`. Private
BASE repository reuse additionally depends on GitHub's repository access rules;
the ORCA-only token does not grant source access to a different private repo.

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
The remaining hosted prerequisite is correcting the Actions secret's effective
repository access, then rerunning the calculation workflow. Download/hash
success in this cloud environment does not establish hosted calculation success.
