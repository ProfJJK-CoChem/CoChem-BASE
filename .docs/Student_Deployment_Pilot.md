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
| Full scientific intake | Upload a course-relevant MOL/SDF/PDB/QCSchema file; select a specific retained frame | All records, isotope/state/unit metadata and unchanged original source hashes; valid selections survive restart. |
| Native-data inspection | Upload authentic Hessian/output/data files and inspect their labelled panels | Measured constants, original hashes, bounded arrays and missing-data/minimum qualification; no invented native execution. |
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

The optional intake manifest extends this same actual browser route to every
listed molecular format, retained multi-record selections, native spectroscopy,
geometry-bound Hessians, numerical archives, periodic structures and PAW files.
Every Hessian analysis must display the selected source checksum in its new
result, finish its background worker, and preserve its qualification. A visible
result from an earlier selection cannot establish that a later analysis ran.

Ordinary reloads also verify the standard XSRF cookie and authenticated shutdown
beacon: the prior kernel must disappear while a different kernel restores the
saved inputs. XSRF protection remains enabled. Tests record browser HTTP errors,
JavaScript errors and failed requests instead of discarding them.

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

## Scoped intake trace and recorded browser proof

The intake obligation includes the detailed
[Task 1 architectural specification](task1_subsystems_architectural_specification.md),
not just the XYZ example in Chunk 17. Its introduction specifies Tripos MOL2;
§3.1.2 specifies XYZ, MDL MOL V2000/V3000, multi-molecule SDF, PDBv3.3 and
MolSSI QCSchema v1/v2. The
[Level 2 breakdown](task1_level2_wbs_breakdown.md) §4.4 adds the energy window,
graph, atom-permutation and three-axis rotational-constant sieve conditions.

| Obligation | Connected implementation and acceptance boundary |
| --- | --- |
| All specified molecular source formats and records | `intake/structure_formats.py` is the canonical parser used by Stage 2 and the input library. Actual browser file choosers admitted XYZ, MOL V2000/V3000, two-record SDF, two-MODEL PDB, MOL2 and QCSchema v1/v2; every one of their ten frames was selectable. |
| Physical nuclear identity, isotope/state/unit handling and ghost inspection | Canonical records preserve ordered nuclides, converted coordinates, declared state and source hashes. Browser selections preserved QCSchema 18O/D identities and encoded charge/spin. Ghost centers remain inspectable with zero mass/nuclear charge and are unavailable to ordinary physical-atom methods. Numerical frame/toolchain invariants have their separate canonical tests. |
| Conformer pool lineage and scientific comparability | `interfaces/student_ingestion.py` calls the canonical `intake/conformer_engine.py` sieve. Typed GUI context supplies an explicit state and comparison protocol; producer labels alone do not establish comparability. Unknown observations remain retained and unranked. Canonical native-pool and actual-widget tests establish this path; the full-format browser record does not claim it ran a new search. |
| Original source retention, isolation and update continuity | Original bytes and sealed receipts remain outside the application source. The library verifies each input independently, reports corrupt receipts, and can recompute derived display metadata without changing the original receipt. Actual browser reload recovered all seventeen file hashes, starting roles/states/fragments and the sealed R2 package. |
| Native spectroscopy and isotope inspection | The browser parsed actual retained ORCA output, kept missing B0/corrections missing, and reweighted the actual Cartesian tensor from native `.hess`, NPZ and HDF5 sources. Each result was bound to that source's checksum. Uploaded tensors remained unqualified for physical-force-field/minimum claims. |
| Bounded numerical data and periodic inputs | Actual NPZ/HDF5 previews completed; CIF and periodic JSON were retained, and the typed form saved a request using authentic Ga/As PAW files and explicit cutoffs. Input acceptance is separate from a new periodic calculation or material-accuracy benchmark. |
| Starting-geometry construction | The browser built a SMILES water starting guess and a complex seed from its own two uploaded monomers. Internal monomer distances were preserved. Neither route claimed a measured energy or a minimum. |

The complete local browser record on 2026-10-08 is
`student-no-code-browser-local/browser-v19/browser-summary.json`, SHA-256
`0095e849198e19ee8a9478c41cdb635a71891a32d664209ec25dc70a4a3ccd9f`.
It passed seventeen scientific-file uploads, ten molecular frame selections,
three source-bound Hessian reanalyses and three authenticated kernel reloads
with zero browser HTTP, transport or JavaScript errors. An earlier six-reload
record independently retired all seven previous kernels, including a scientific
input recovery reload. The focused immutable-input/transport suite passed 66
tests without skips.

This record is **locally rendered browser acceptance**. It explicitly records
no new native engine execution, no installed-provider acceptance and no actual
student account, GitHub Actions or Codespaces service acceptance. Separate
native worker and hosted records must establish those claims. A source fixture
that originated in a real calculation does not turn a later tensor preview into
a new engine job, an equilibrium certificate or an experimental accuracy test.

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
