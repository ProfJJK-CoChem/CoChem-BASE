# Private student projects: Codespaces and Actions calculations

A student's **personal private, standalone repository** uses that owner's
Actions allowance. Codespaces hosts the interface and stages approved licensed
assets. There is no separate asset service and no laboratory credential copied
into the student repository. Authorized license and repository access remain
prerequisites. Engine archives and installations stay outside Git.

## Create the project

From a clean checkout of the instructor-approved public BASE source, use the
student's authorized GitHub CLI identity to create a standalone private copy:

```sh
gh auth status
gh repo create STUDENT/PROJECT --private --source . --remote student --push
```

These are placeholders for the actual student owner and project. Creating the
repository is an explicit student operation. A public repository's ordinary
fork cannot simply become private. Confirm real private/User ownership through
GitHub before any licensed staging; local variables do not establish privacy.
The canonical workflows must be present on the project's default branch.
Review upstream updates deliberately; a standalone copy does not auto-update.

Use the reviewed public BASE/TOPOS/TORQ source and immutable module catalog.
Public source retrieval does not require access to licensed archives. The
mandatory TOPOS ecosystem has its own all-three-package kit and integrity
checks; see [ecosystem setup](Ecosystem_Modules_Setup.md). Keep independent
producer environments and scientific capability gates intact.

## Authorize Codespaces and stage one task

The instructor grants the student authorized read access to the approved lab
release within the license. Open the private project in Codespaces and follow
[browser authentication](../docs/private_student_engine_staging.md#browser-authentication-in-codespaces).
The student's stored native GitHub CLI login is selected for private interface
operations; a scoped Codespaces injection must not shadow that identity.
Do not reveal or export credentials. Personal Codespaces declarations do not
automatically grant cross-owner organization access. Missing real access fails.

Prepare and commit a validated ORCA or CFOUR job. The receipt binds the exact
job bytes, source commit, branch, workflow and CPU/memory limits. Stage its
approved descriptor with `python -m scripts.private_engine_assets` from the BASE
checkout root, or use the private Actions controller. Keep the immutable intent,
journal and ready receipt in persistent private storage outside every checkout.
The stager verifies actual identities and archive bytes, uploads one uniquely
marked private draft-release asset and authenticates a complete readback.

Actions receives `asset_receipt`, `asset_receipt_sha256` and `asset_task_id`.
Its own repository authority reads only the exact staged task asset. Do not
configure a separate cross-owner archive credential in the student's Actions
settings. Each calculation uses its own source/request/resource intent.

## Run, retrieve and clean up

Use `.github/workflows/orca_calculation.yml` for scientific ORCA jobs or
`.github/workflows/cfour_calculation.yml` for scientific CFOUR jobs. Both require
the actual job-file path/hash, cores and memory intent. The separate
`cfour_provisioning.yml` utility omits calculation intent and qualifies
provisioning only. Installer success does not establish scientific acceptance.

Inspect the real run and attempt, convergence, native output, scientific report
and immutable artifacts. Retain genuine failures. Licensed runtimes and archives
are removed from job-local storage and never included in public result artifacts.
After the genuine matching run is terminal, close admission and clean up only
the exact task-owned staged asset using its original private receipt. The
task-owned private draft is retained when present; unrelated concurrent assets
are preserved. Expiry denies consumption but does not delete GitHub storage.
Interrupted staging retains intent/history for explicit repair.

See the [ORCA guide](ORCA_Actions_Setup.md), [CFOUR guide](CFOUR_Actions_Setup.md)
and [student pilot](Student_Deployment_Pilot.md) for supported scientific scope.
The current resource defaults and bounds are documented against those workflows;
they are not a guarantee that an arbitrary calculation will fit.

## Pilot and billing limits

No real student-owned private target was available for this implementation
cycle. Live source access, upload/readback, owning-token consumption, dispatch,
result retrieval and cleanup remain **UNRUN**. The first pilot must explicitly
establish owning Actions `contents:read` access to the private draft release and
its exact asset. A denial requires review of the private permission/release route,
not a fabricated provider response or silent permission expansion.

The personal repository owner's billing settings must permit Actions. An
organization-owned assignment uses organization Actions minutes even when a
student starts it; Codespaces core-hours do not pay for Actions. A private
project can incur compute and storage costs. Stop the Codespace when finished.
Classroom50 collection and grading remain separate from calculation ownership.

## GitHub references

- [Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
- [Codespaces repository access](https://docs.github.com/en/codespaces/managing-your-codespaces/managing-repository-access-for-your-codespaces)
- [Codespaces ownership and billing](https://docs.github.com/en/codespaces/managing-codespaces-for-your-organization/choosing-who-owns-and-pays-for-codespaces-in-your-organization)
