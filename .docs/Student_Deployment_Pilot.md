# Accept the actual no-code student research deployment

A deployment passes only when a student uses their own accepted Classroom50
repository, fresh Codespace and ordinary GUI route. Source installation,
locally rendered Voilà and instructor-run Actions are separate evidence. Do not
infer student permissions from the instructor's access.

Follow the [instructor deployment guide](Classroom50_Assignment_Deployment.md)
and [student no-code guide](Student_Research_No_Code.md). Students supply their
own Avogadro 2 monomer or complex XYZ files. They receive BASE alone and never
run terminal installation commands or open underlying module repositories.

## Before student acceptance

The instructor should record:

- Reviewed BASE starter/runtime source and compatible module catalog.
- Course organization, template, classroom and assignment.
- Organization Actions secret policy for each required reader: all applicable
  repositories or selected assignment grants. No credential values.
- Student team Read access, accepted membership and same-owner Codespaces
  repository declarations.
- Personal Codespaces payer/allowance and organization Actions entitlement.
- Approved scientific protocol and a bounded test that fits the worker.

ORCA/CFOUR are optional and strongly recommended. With both absent, BASE must
still render and ingest data. Dependent calculations are unavailable; a job
explicitly requesting an unavailable engine must not be reported successful.

## Required actual student checks

| Check | Student action | Evidence required |
| --- | --- | --- |
| Assignment acceptance | Accept the Classroom50 link and open the repository | Real student identity, accepted organization membership, exact assignment/revision. |
| Fresh Codespace | Create on the approved branch and authorize requested permissions | Actual GitHub Codespaces service record, student identity, creation time, machine and payer. |
| Automatic setup | Wait for BASE to render its setup status | Required modules installed/verified without student commands; failures accurately disable their operations. |
| Original ingestion | Upload their own monomer and complex XYZ, choose one of several starting files | Actual browser FileUpload, original bytes/hash, ordered nuclei/geometry and state handling. |
| Validation | Upload a malformed geometry | Visible actionable error, no unexpected execution, earlier valid originals preserved. |
| Hosted submission | Select the approved calculation and click Run on GitHub Actions | Real workflow dispatch under the available student identity, unique request ID, run URL and actual accepted source SHA. |
| Lifecycle | Refresh status and cancel a separate bounded run | Status and cancellation bound to that request/run, not the latest unrelated run. |
| Genuine result | Allow one chemistry run to complete | Actual engine output, convergence/result checks and scientific report. No synthetic output substitutes. |
| Retrieval | Retrieve and inspect results and download the bundle | Correct request/run/artifact association, file checksums, genuine data visible in GUI. |
| Research output | Run supported comparisons/analysis | Authentic tables/figures, explicit conventions and unavailable-data gates. |
| Compatible fix | Check/apply an approved update and restart | Exact old/new versions, original uploads and prior result hashes unchanged, successful rollback behavior when relevant. |
| Submission | Commit/sync a report with VS Code buttons | Report appears in GitHub and Classroom50 collection under the student's identity; instructor feedback/score recorded. |

A browser download/export alone is not a submitted calculation. An Actions run
with an instructor credential is not proof of student-token permissions. An
installed provider with no verified scientific operation is not a complete
research pipeline. A preview plot derived from no native data is not acceptance.

## Maintainer acceptance harness

`tests/ui/student_entrypoint_browser_acceptance.py` exercises an actual rendered
Voilà session through Chromium. It uses the browser's file-input API to upload
complete XYZ files and checks the resulting geometry/selection/setup controls.
It can exercise a real hosted request when a designated test repository and
its authenticated route are available. The harness is for maintainers; its
command line must not appear in student setup instructions.

Retain browser screenshots, errors, download hashes, exact source/setup reports
and actual hosted run/artifact evidence together. Distinguish UI-only acceptance
from real hosted calculation acceptance in the report. Never report an optional
hosted check as performed when no real run occurred.

## Current service boundary

Earlier cloud validation found zero existing Codespaces and received HTTP 403
`Resource not accessible by integration` from repository machine/permission
APIs. That established an integration authorization limitation, not a failed
student installation. Local tests used the configured Python 3.12 Bookworm
image, verified all eleven Stage 0 phases, rendered/repeated Voilà and genuine
free xTB calculations without licensed binaries.

For the updated student entrypoint, record current API and browser outcomes
rather than reusing that old observation. A newly created actual Codespace or
successful Actions run needs its own service record. If the available
integration cannot create or inspect a student Codespace, complete independent
functional/Actions checks and state the precise unverified student step. Do not
mark that service check passed or ask students to substitute terminal code.

## Deployment record

Keep one small JSON/Markdown record per pilot with:

- Student username, organization, classroom, assignment and Codespace identity.
- BASE runtime/starter and provider revisions and compatible-update catalog.
- Payer/machine, setup outcomes and each actually available capability.
- Uploaded filenames, source hashes, ordered element/isotope identities,
  geometry, charges, multiplicities and fragments.
- Request IDs, run URLs, checked-out source, resources and operation.
- Native calculation/result validation and retrieval/bundle hashes.
- Figures/tables, scientific conventions and explicit missing prerequisites.
- Before/after update preservation and result/source version separation.
- Submitted report, collection observation and instructor feedback.

Keep credentials and private engine archives out of the record. A successful
pilot validates this route, not every molecule, hardware platform, provider
method or experimental accuracy claim.
