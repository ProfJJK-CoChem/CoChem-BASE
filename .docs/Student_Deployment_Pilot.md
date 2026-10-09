# Accept the actual no-code student research deployment

The selected deployment passes only when a student uses their own independent
private personal BASE project, its App-managed access, a fresh Codespace and the
ordinary GUI route. Source installation,
locally rendered Voilà and instructor-run Actions are separate evidence. Do not
infer student permissions from the instructor's access.

Follow the [personal-project App deployment guide](Personal_Project_App_Deployment.md),
[Classroom50 collection guide](Classroom50_Assignment_Deployment.md) and
[student no-code guide](Student_Research_No_Code.md). Students supply their own
scientific inputs; Avogadro 2 monomer/complex XYZ is one route. The full specified
molecular/native/periodic ingestion suite remains part of BASE acceptance. They receive BASE alone and never
run terminal installation commands or open underlying module repositories.

## Before student acceptance

The instructor should record:

- Reviewed BASE starter/runtime source and compatible module catalog.
- Course organization/team, reviewed public BASE template, private instructor
  controller and Classroom50 collection arrangement.
- Personal project owner, private/nonfork status, selected App installation and
  actual enrollment/controller receipt. No signing key, credential values or
  private reader labels in the pilot record.
- Private mapping-variable presence for each approved reader; Actions and
  Codespaces are separately provisioned stores. Organization secrets cannot
  inherit into a personal project.
- Active student team membership and permitted private-source/engine Read access.
- Personal Codespaces/Actions payer, current Education benefits and usage limits;
  organization entitlement covers controller/collection administration only.
- Approved scientific protocol and a bounded test that fits the worker.

ORCA/CFOUR are optional and strongly recommended. With both absent, BASE must
still render and ingest data. Dependent calculations are unavailable; a job
explicitly requesting an unavailable engine must not be reported successful.

## Required actual student checks

| Check | Student action | Evidence required |
| --- | --- | --- |
| Project creation | Use the approved BASE template to create a Private repository owned by the student's personal account | Real owner/private/nonfork metadata and exact compatible starter; a template copy has independent Git history. |
| App consent and enrollment | Install the instructor App only on that project and submit BASE's data-only enrollment | Active team membership, selected installation, controller run URL and complete provisioning receipt; public/fork/foreign-owner/unapproved requests refuse. |
| Classroom50 enrollment | Accept the course invitation and follow collection instructions | Real student identity, organization/class membership and actual private project/report submission link. |
| Fresh Codespace | Create on the approved private project's branch after access provisioning | Actual Codespaces record, student identity, creation time, machine/payer and separately provisioned source access. No inherited organization-secret or cross-owner scoped-token assumption. |
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
| Submission | Save/sync a report with VS Code buttons and use the instructor's Classroom50 collection process | Report exists in the personal project and is actually accessible to the authorized instructor; private-project collection/feedback is observed, not inferred from organization membership or the App provisioner. |

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

## Current candidate and service boundary

The instructor-managed App controller, encrypted Actions/private-variable
bindings and separate Codespaces source-reader delivery are implemented in
current source. Existing workflow migration has local parser/actionlint and
credential-isolation evidence. That is not a live App installation or a successful
student enrollment. The instructor must register/configure the App and verify its
actual selected-project permissions before this pilot can pass.

The current reviewed candidate is C33
`8946f53ab1d9261eef4eb9c5b117c9936b49eabf` on
`codex/no-code-student-entrypoint`. These receipts bind code producer C33; verify
the published main ref independently. Production,
GUI, scientific-provider, workflow, default-pin and browser-harness bytes/modes
retain C29. The CI source observer/runner, selected tests/profiles and reviewed
ring have later corrections. C29 FULL browser passed in 295.320s and separate
READ passed in 56.420s, retaining those exact producer identities rather than
being relabelled as C33 browser runs.

Complete C29/C30/C31 producers remain failed. C29 had nineteen failed controls
and eleven source-authority errors; C30 had eleven source-binding refusals after
isolated test-child bytecode writes; C31 passed 3,043 executed calls but failed
its outer gate on a truncated initial receipt. C31 prevented the actual bytecode
writes, and C32 added atomic receipt publication. C32's original Windows
WinError32 owned-directory failure remains preserved. C33's sixteen focused
controls passed, including actual temporary/persistent native directory handles
and unchanged interruption controls. Collection retains all 3,049 earlier nodes
plus thirteen new controls. The exact **3,062-node complete profile is independently accepted**: 3,056 call
passes, zero failures, four reviewed optional call skips and two physical Slurm
setup skips. All 782 source records are parser-valid with zero authority errors/
escapes; 58 initial-only observations retain startup-only scope. Original/copied
source and the reused genuine C27 registry stayed unchanged, with an empty reaped
owned boundary. This actual terminal source/test/process result is separate from
the student App/Codespaces pilot and physical accuracy acceptance.

The latest fully accepted bounded [C33 hosted run37878684516](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37878684516)
passed 221 actual controls on each Ubuntu/macOS/Windows worker, three clean
installed wheels with 601 hashed RECORD members verified each, 1,641 bounded
regressions, genuine free-engine calculations, all eleven CPU setup phases and
rendered/reused Voilà. All eight artifact digests and 1,026 member hashes were
independently verified without extraction; actual PR checkout and reviewed C33
have identical Git trees. Setup is honestly DEGRADED_OPERATIONAL with optional
ORCA/CFOUR absent. Actual Windows sharing violations remained visible after the
unchanged 3s budget when the real handle persisted; temporary release and original
interruption controls passed. The old C32 handle owner remains unproved.
This maintainer result does not establish student App/Codespaces consent,
private licensed access, whole-profile or physical accuracy acceptance.

C23 ORCA8/CFOUR10 direct native Linux CPU calculations passed with independent
readback of 840 immutable artifacts/40 origin records. Current C27 installed
TOPOS/TORQ and scientific BASE C22 member/source/registry authority were
reverified. TOPOS remains resource-limited at seven of nine operation kinds:
nine accepted controller cases, but minimum-qualified frequency/RRHO unaccepted.
Original xTB stationarity refusal, HF strict-density refusal, wB 300 s frequency
timeout and capacity-interrupted RRHO remain retained. Do not teach those records
as accepted equilibrium populations or thermochemistry. TORQ separately accepted
three cases over two kinds/five PySCF SCFs and genuine reports; AO Löwdin-Wiberg
is available within its convention, while NBO/NAO is unavailable.

Only the two inactive generated provider dependency environments were retired
to recover scratch capacity. Complete installed-member hashes, 915 raw metadata
copies and unchanged outside source/wheel/scientific bytes remain; there is no
whole environment-body archive or claim that those acceptance installations are
still runnable. Separately, inactive C29/C30/C31 pytest fixture trees and the creator-bound old pytest235 failed generation have complete private byte-restorable archives verified before duplicate retirement. Their raw failures/native evidence remain unchanged; this preservation is distinct from retired dependency bodies. Student BASE installation remains its automatic setup route.
The original C27 full browser reached native harmonic output but failed an
engineering label parser. C28 then failed a recovered-role display check despite
intact retained originals; its recovery diagnostic did not reproduce that role
issue but remained failed for a missing early-kernel final receipt. C29 keeps
every original 5 s field/scientific/hash/path/isotope assertion and adds the
exact selected-original UUID/SHA acknowledgement before checking fields. It is
a stronger protocol check, not a proved production race fix. Its actual FULL
browser passed: 17 uploads/10 molecular frames, five authenticated kernel
retirements, zero browser errors, all 56 source-authority checks and fresh
native HF/STO-3G harmonic Hessian/18O CSV/SVG reanalysis without another electronic
calculation. Separate READ passed with all 32 authority records and zero browser errors;
complete C29/C30/C31 producers subsequently failed and retain no full acceptance.
Their three required native R2/T9/CREST–GOAT calls passed execution checks, but
R2 retains its counterpoise-ordering warning, frozen-bond residual and unverified
physical accuracy. Current C33 focused/hosted results establish their stated
engineering scope; the complete local producer E80 also passed its source/test/
process gate with six reviewed external deferrals, preserving all original failed
producers and scientific limits. Exact original failed and accepted records are in the
[implementation record](SRS_Implementation_Status.md) and
[complete trace](SRS_Student_1_1_Conformance_Trace.md).

Live instructor App/controller setup, selected personal-project enrollment,
a real student's fresh Codespace, personal hosted chemistry/retrieval and
Classroom50 collection remain external pilot checks. Current hosted licensed
asset authorization also remains unverified after the recorded access failure.
Organization secrets and team membership cannot automatically deliver readers
into a student-owned personal repository; the configured App performs separate
Actions/Codespaces provisioning. Students use BASE/VS Code controls without
terminal commands. Missing optional engines leave BASE/free-engine routes usable.
Actual GPU, Slurm/PBS and other physical provider/platform combinations retain
separate acceptance.

The historical C17 candidate is `4d4834dcac8a07786e691ba667cbb8d66e650925`.
Its strict source gate and [hosted run 37829834106](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37829834106)
accepted 207 unique engineering controls on each Ubuntu/macOS/Windows worker,
with zero failures/skips/deselections and unchanged source, plus three fresh
installed-wheel checks. The synthetic checkout
`c9a15c17894c66e2074e6a6073cd1387267ddbd9` shares C17 Git tree
`d2da15c9169a9c23b4e34c70e5a1d7e0a364b911`. These are maintainer engineering
checks and do not exercise student App consent or chemistry permissions.

Actual C17 Linux setup completed all eleven phases in 134.83 s: nine passed,
phases 2/9 degraded, existing four isolated silos verified and selected scratch
consistent. It used an explicit 1 GB qualification floor, not the default 50 GB
policy or a new student Codespace. The receipt is
`/tmp/cochem-current-fresh-stage0-evidence-4d4834d/acceptance.json`; registry
SHA-256 `4edbe79b607bb6f07a9340710e602951bcf10d85bfed93edf03be03aa0cf230f`.

That C17 hosted bounded regression collected 1,579 tests: 1,575 passed and four
failed, with zero skips. Two native SWMR child processes timed out at 12 s
and two needed official PAW inputs; dashboard validation was skipped/not
executed. The C17 local complete profile never started. Its terminal receipt is
`/tmp/cochem-hosted-c17-4d4834dc/c17-terminal-hosted-validation.json`, SHA-256
`11efccfe03ab12e2623dcae6caa11a98445f32f45384c173af0f6dccb8e16e04`.
Those historical outcomes do not qualify later changed science or student delivery.

Historical maintainer-hosted eleven-phase/free-engine setup, isolated xTB/PySCF
numerical checks and fresh calculation-silo authority passed; the scientific
worker is C16 `68496c225fc90ff13f0ec6ff7c97570737917615`. Current hosted
licensed-archive access remains a separate prerequisite, without an accepted
current ORCA/CFOUR hosted replay. Personal-project chemistry still needs the real student
pilot, whichever available engine the approved protocol uses. The cancelled C15 science
run supplies no accepted final count or dashboard proof. Earlier source-specific
successes and actual failed/aborted attempts remain retained. Current result
receipts, publication and this real student pilot must be accepted separately;
none is established by a maintainer's successful installation or wheel.


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

## Scoped intake trace and historical browser proof

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

The earlier source-specific local browser record on 2026-10-08 is
`student-no-code-browser-local/browser-v19/browser-summary.json`, SHA-256
`0095e849198e19ee8a9478c41cdb635a71891a32d664209ec25dc70a4a3ccd9f`.
It passed seventeen scientific-file uploads, ten molecular frame selections,
three source-bound Hessian reanalyses and three authenticated kernel reloads
with zero browser HTTP, transport or JavaScript errors. An earlier six-reload
record independently retired all seven previous kernels, including a scientific
input recovery reload. The focused immutable-input/transport suite passed 66
tests without skips.

This historical record is **locally rendered browser acceptance**; it does not
qualify later changed browser/UI source. Current C29 FULL/READ evidence is separate E63/E64. It explicitly records
no new native engine execution, no installed-provider acceptance and no actual
student account, GitHub Actions or Codespaces service acceptance. Separate
native worker and hosted records must establish those claims. A source fixture
that originated in a real calculation does not turn a later tensor preview into
a new engine job, an equilibrium certificate or an experimental accuracy test.

## Deployment record

Keep one small JSON/Markdown record per pilot with:

- Student username, personal project owner/private/nonfork identity, selected App
  installation, private controller run and Classroom50 collection record.
- Actual Codespace identity, creation time and source-access provisioning status.
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
