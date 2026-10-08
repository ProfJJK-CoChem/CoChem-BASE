# First private student Actions pilot

Codespaces is the interface. Calculations run in a private repository owned by
the student's personal account, using that account's Actions allocation and
billing rules. Codespaces usage has its own billing rules. Running a reusable
laboratory workflow does not move a personal project's computation quota to the
laboratory.

The repository now provides a GUI and controller for private asset staging,
submission, actual run observation, cancellation, evidence download, and
cleanup. No student project currently exists for this implementation's live
pilot. The real Codespaces → private release → Actions → native calculation →
artifact → cleanup journey is **UNRUN**. Mathematical, real filesystem, native
dashboard, and workflow-contract checks are separate from that provider
acceptance.

## Prepare the first project

1. Create a repository in the student's own personal account and keep it private.
   Include the reviewed BASE source and current ORCA/CFOUR calculation workflows.
   Include the ecosystem module revisions required by the chosen calculation.
   An organization-owned repository does not use the intended personal quota.
2. Open that private project in Codespaces. The Codespaces interface must already
   have the student's own authorized GitHub identity with read access to the
   approved private laboratory distribution and write access to the personal
   project and its Actions workflows.
3. Complete the supported browser authentication or credential-manager flow for
   the student's account when that authorization is absent. An instructor must
   grant the student's permitted laboratory access separately. Codespaces
   additional repository permissions do **not** grant cross-owner laboratory
   access. Signing in to the browser alone does not prove that the GitHub CLI
   identity has the necessary access.
4. Retain the reviewed distribution descriptor and its independently recorded
   file SHA-256. The genuine ORCA and CFOUR descriptors in the reviewed BASE
   source identify approved archives; alternative descriptors require actual
   review and corresponding native support. A newly calculated checksum of an
   untrusted file does not establish that review.

The application uses the authorized native GitHub CLI normally. It does not
display or extract tokens, ask for laboratory credential values, commit them,
or pass a laboratory credential to Actions. Missing access blocks staging.
The owning Actions job uses only its ordinary repository-scoped GitHub token.

## Use the interface

1. Enter the private personal OWNER/REPOSITORY project and reviewed branch.
   Choose GitHub Actions as the calculation environment.
2. Select the connected ORCA or CFOUR method and enter the molecular request.
   Prepare the validated request in the matrix. Unavailable scientific operations
   remain unavailable; staging does not qualify a method or enable VPT2.
3. In the private Actions panel, enter the real reviewed descriptor path and
   independently retained file SHA-256. Select one or two cores and the allowed
   memory per core.
4. Choose **Stage privately and submit**. This uploads a uniquely named validated
   job JSON to the personal project, then stages a task-owned temporary private
   release asset containing the original approved engine archive. The interface
   verifies source and destination identities and bytes before dispatch.
5. Retain the actual task UUID and private receipt outside the checkout. Choose
   **Refresh owned run** to observe the real run. Observation binds the personal
   repository and its numeric IDs, branch, source commit, workflow, and task UUID.
   If discovery is ambiguous, enter the real run ID and use **Select observed
   owned run**; unrelated runs are rejected.
6. Use **Cancel owned run** for a real nonterminal owned run. A cancellation
   request is separate from observing the terminal cancellation.
7. After a terminal run, use **Download owned results**. Each run attempt has a
   separate artifact and local directory. The interface retains the actual
   artifact/run/attempt identities and verifies recorded submitted input bytes
   when present. Early failures may have only diagnostics; they do not gain
   scientific acceptance by being downloaded.
8. Use **Clean completed staged assets** after observing the exact owned terminal
   run. Cleanup closes asset admission, audits active matching runs, and deletes
   only the owned asset ID. It retains the empty private ownership draft and
   lifecycle evidence. It does not delete shared releases or source assets.

## Retained intent and recovery

The immutable canonical receipt and its exact SHA-256 bind the approved
distribution, actual source and destination asset/release IDs, personal
repository and owner IDs, source commit, branch, workflow, task UUID, and expiry.
Calculation receipts additionally bind the committed job path and bytes,
requested cores, and memory. Actions verifies those controls and actual
checked-out input bytes before consuming a staged asset. Reusing a receipt for
another calculation or resource request is refused.

The local controller serializes lifecycle mutations with an actual OS file lock.
Provider observations remain distinct from local intentions. A changed branch
between staging and dispatch can cause Actions to reject its receipt; the
interface retains that mismatched run as a rejected observation instead of
claiming a completed calculation. Use **Review staged-asset repair** with the
retained private task record. Interrupted staging may also require the staging
module's private journal repair route; do not create substitute receipts.

Expiration blocks new asset consumption. It does not erase historical run
evidence. A rerun receives a new run attempt and separate downloaded evidence;
earlier attempts remain retained. An ownership or authority change during
download leaves the new directory unclaimed for review.

## Native and scientific acceptance

ORCA provisioning retains its pinned Open MPI and real native version checks.
CFOUR provisioning retains its genuine embedded runtime/source inventories,
ELF/dependency/launcher checks, and controlled native metadata response. Those
installation checks are separate from executing a physical calculation.

The calculation workflows retain the existing actual engine execution and
scientific output validation through BASE. A scientific result requires their
real convergence, derivative/property, archive, and provenance checks.
Independent method accuracy, spectroscopy identification, and research
qualification remain separately gated. Neither an approved archive nor a
successful file transfer establishes them.

Licensed engine binaries and archives remain outside the checkout and never
become calculation artifacts. The job removes its local archive and installation
on exit. Only scientific results, diagnostics, registries, and installation
metadata enter the private evidence artifact.
