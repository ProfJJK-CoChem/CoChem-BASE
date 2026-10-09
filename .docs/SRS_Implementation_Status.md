# BASE SRS conformance — implementation and release evidence

Baseline: [Chunk 17](SRS_Chunk_17_CoChem_BASE_Architecture.md) **plus** [BASE proposal additions](SRS_Chunk_Proposal_CoChem_BASE_Architectural_Review.md), as selected by the user. Requirement numbers below belong to Chunk 17; the proposal uses the same numbers for different obligations. Its sixteen vectors and additional workflow obligations are tracked separately.

The user's scope clarification governs this pass: **BASE owns ingestion, setup, GUI and validated ecosystem integration**, within the 20-module system. Domain solvers belonging to future modules are not standalone BASE implementation obligations. BASE must faithfully validate their inputs, describe missing capabilities, preserve handoff evidence and avoid reporting unexecuted science as success. See [alpha scope and fixture corrections](BASE_Alpha_Scope.md).

The last recorded published stable version is 1.0.1. The student no-code entry point,
broader ingestion corrections and instructor-managed personal-project access are
**1.1 release-candidate work**, tracked in [PR 10](https://github.com/ProfJJK-CoChem/CoChem-BASE/pull/10),
the [complete obligation trace](SRS_Student_1_1_Conformance_Trace.md) and the
[student workflow](Student_Research_No_Code.md). The current reviewed candidate
is C33 `8946f53ab1d9261eef4eb9c5b117c9936b49eabf` on
`codex/no-code-student-entrypoint`. These receipts bind code producer C33; verify
the published main ref independently. All 502
production-source members, GUI, scientific providers, workflows, default pins
and browser harness retain C29 bytes and modes. The CI source observer, runner,
selected tests, profiles and reviewed infrastructure ring have later corrections.
C29's actual local FULL and separate READ browsers passed; their source-specific
results are bound to unchanged runtime bytes, not relabelled as C33 executions.

Earlier complete C29/C30/C31 producers remain failed: C29 had nineteen failed
controls and eleven child authority errors; C30 had eleven strict source-binding
refusals after test-child bytecode writes; C31 passed all 3,043 executed calls but
failed the outer gate on a truncated initial source receipt. C31 prevented the
bytecode writes, C32 added atomic receipt publication and eight genuine controls,
and C33 added bounded native Windows directory retirement and five actual
lifecycle controls after C32's preserved WinError32 failure. C33's focused
sixteen controls passed, and collection retained all 3,049 earlier nodes plus
thirteen genuine new controls. Its complete **3,062-node local profile is accepted**: 3,056 executed calls
passed, none failed, and six exact reviewed external prerequisites remain deferred
(four optional call skips and two physical Slurm setup skips). All 782 source
records are parser-valid with zero authority errors/escapes; original/copied
sources and the genuine reused C27 registry stayed unchanged, and the admitted
owned boundary was emptied/reaped. Fifty-eight initial-only records retain their
explicit startup-only scope rather than being counted as final execution proof.

The latest fully accepted bounded hosted run, C33 37878684516, passed all three
221-control native jobs, three installed wheels, 1,641 bounded regressions,
genuine free-engine calculations, eleven-phase CPU setup and rendered/reused
Voilà. All eight published ZIP digests and 1,026 member hashes were independently
read back. C23's eighteen direct native ORCA/CFOUR calculations retain their Linux
CPU/source scope. Current TOPOS acceptance remains resource-limited at seven of
nine operation kinds, with frequency and RRHO unaccepted; TORQ's three cases use
five genuine PySCF calculations over two operation kinds. Current hosted licensed
archive access and actual student App/Codespaces acceptance remain external.
These results establish neither a stable tag nor complete SRS acceptance;
historical counts and failures retain their original producers.

The current review covers molecular formats and all contained records, isotope/state identity, conformer pools, periodic cells/PAW inputs, measured Hessians, spectroscopy, trajectory/property archives and native result ingestion. Student monomer/complex geometry is one supported research path, not the complete ingestion specification. BASE manages the approved module installations, source updates, execution routes and result interface; students use its GUI rather than install module repositories or execute setup code.

Local runnable acceptance, downstream scientific acceptance and platform acceptance remain distinct. ORCA 6.1.1 and the approved CFOUR 2.1 runtime have genuine historical Linux CPU and hosted calculations; see [ORCA setup](ORCA_Actions_Setup.md) and [CFOUR setup](CFOUR_Actions_Setup.md). Both engines remain optional and strongly recommended: missing installations disable dependent local operations while BASE and installed free engines remain usable. Current native/browser evidence is explicitly bound to unchanged runtime bytes; the exact C33 immutable complete profile passed its source/test/process gate with six reviewed external deferrals. Unavailable NBO/NAO, VPT2/anharmonic and additional Product B providers remain unavailable; placeholders do not fulfill their physical acceptance. GPU, Slurm, other native platforms and a real student-identity Classroom50/fresh Codespace pilot retain their separate acceptance. See the [deployment checklist](Student_Deployment_Pilot.md).

An earlier hosted 1.1 attempt was stopped before execution by organization
billing/spending limits, and the recorded Codespaces creation attempt returned
HTTP 403. Those are historical service observations, not the current candidate's
acceptance result. Subsequent maintainer-hosted setup/free-engine work is distinct
from a live personal-project App enrollment and a real student's fresh Codespace.
The [1.0.1 closure record](Release_1_0_1.md) and [1.0.0 record](Release_1_0_0.md)
remain historical. Authorization or deferral does not turn an unexecuted check
into a pass.

The previous snapshot (994 passed, 4 skipped, 1 failed) and its strict-scan counts are historical evidence under `/workspace/cochem-runtime/evidence/srs-pass2/`. This pass corrects the failed PES analysis, withdraws misleading fixture evidence, replaces legacy interface shells with versioned capability/handoff contracts, and replaces duplicated CI pipelines. Current-run counts and evidence follow below.

Instructors should follow the [personal-project App deployment guide](Personal_Project_App_Deployment.md)
for the reviewed BASE template, automatic private access and one-student pilot.
The [Classroom50 guide](Classroom50_Assignment_Deployment.md) covers course
instructions and collection separately. Public release checks and actual
institution/student acceptance retain distinct evidence.

## Current student deployment and implementation boundary — 2026-10-09

The selected deployment is an independent **private BASE template copy owned by
one student's personal account**. Its Codespace supplies VS Code/Voilà and its
Actions jobs use that account's applicable allowance. Classroom50 supplies course
roster, instructions, submission collection and feedback; it does not transfer
repository ownership, billing or organization secrets to a personal account.
Students receive BASE alone, provide their own full-range scientific inputs and
use its upload/setup/calculation/result/update controls without terminal commands
or direct module repositories.

The [instructor-managed GitHub App](Personal_Project_App_Deployment.md) uses an
instructor-writable private controller and data-only enrollment. Its implemented
checks bind active course-team membership, personal ownership, private nonfork
project identity, selected App installation and reviewed executable starter
blobs. The App writes encrypted project readers and private mapping variables
`COCHEM_ORCA_ACCESS_SECRET`, `COCHEM_CFOUR_ACCESS_SECRET` and
`COCHEM_SOURCE_ACCESS_SECRET`; public workflows resolve those mappings without
publishing the instructor's stored labels or values. The module reader is
separately encrypted in the repository Codespaces secret store under the generic
runtime API `COCHEM_SOURCE_CREDENTIAL`. Actions secrets do not enter Codespaces
automatically. The instructor App signing key never enters student projects.
Live App configuration/enrollment and student-identity service checks still need
the [actual deployment pilot](Student_Deployment_Pilot.md).

BASE automatically installs and seals the approved TOPOS/TORQ environments and
routes their supported operations through the canonical `student_research`
workflow. The obsolete separately pinned TOPOS calculation workflow is retired.
Local native TOPOS energy/search/matrix/optimization cases and TORQ scan/Wiberg–Löwdin
cases, with real report exports, have retained revision-specific receipts. NBO/
NAO and other unavailable providers remain disabled rather than being counted as
implemented scientific results. Two matched water starts do not establish
populations of distinct physical isomers.

The final CI implementation now checks clean committed Git bytes, an immutable
expected revision and the reviewed infrastructure ring before application/test
execution. Ignored or untracked executable/import/configuration material is
refused; accepted source is copied to an external private quarantine. Import
origins, real test outcomes, unchanged source and owned-process termination are
part of its fail-closed evidence. Approved worker audits bind the instructor's
worker SHA rather than an unrelated student's submission SHA. Historical C17
source/three-platform CI controls retain their frozen Git tree. C27's three-platform controls, wheels and bounded hosted science passed (E51/E52);
C29's bounded hosted route passed (E66), while complete C29/C30/C31 producers
remain failed (E65/E69/E73). Later causal corrections and C33 focused/collection
results are E67–E78; C33's bounded hosted route passed (E79). The complete C33
profile is accepted (E80). These receipts bind code producer C33; verify the
published main ref independently. Publishing main creates neither a stable tag
nor external student/platform acceptance.

Hardware/resource evidence now requires actual declared or measured observations;
missing CPU/RAM/VRAM does not receive invented default capacity. BASE prepares
its private workspace automatically and keeps original inputs, calculations and
runtime updates outside application source. The free acceptance workflow installs
the actual declared Scribe dependency extra before testing its compressor.
ORCA/CFOUR access remains optional for general BASE; only their dependent methods
are unavailable when provisioning fails. Archive checksums and native execution
checks remain separate from App access provisioning.

### Current C33 candidate and acceptance boundary

The current candidate retains C29's production, GUI, browser harness, native
science, adapters and default provider pins. C29's canonical selected-Hessian
label parser and exact original UUID/SHA acknowledgement preserve every original
recovery field, physical threshold, geometry, confinement, hash and isotope guard.
Its FULL browser passed in 295.320s and separate READ in 56.420s; the original
C27 delimiter failure, C28 recovered-role failure and incomplete recovery
diagnostic remain preserved. The added acknowledgement is a stronger protocol
check, not a proved production race fix.

The complete C29 profile failed with 3,023 passes, nineteen failures and six
external-prerequisite skips out of 3,048 collected nodes. C30 fixed stale cache/
catalog contracts and genuine stdin source observation; its full run still failed
with 3,032 passes, eleven source-binding refusals and six skips out of 3,049.
The causal replay identified fifteen bytecode files written by isolated test
children, and C31's explicit `-B` prevented those writes without an exemption.
C31 then passed all 3,043 executed calls, but its outer gate failed on a truncated
initial source receipt. C32's atomic publication retains exclusive final-file
semantics and never exposes a partial initial receipt before the body. Its eight
new controls passed on all three hosted platforms, but an unchanged Windows
interruption control failed with WinError32 during owned-directory deletion.
C33's five genuine lifecycle controls and the original interruption controls
pass natively on all three platforms. The old handle owner remains unproved;
persistent sharing violations remain visible within the unchanged 3s budget.

C33's current 222-entry infrastructure ring SHA-256 is
`33931b6e67fc16fceeffa69d47b9d2cc329e06d660c90f2786fe2eeffd362858`.
The unchanged default manifest SHA-256 is
`e5cee7540a0e686a14a3a3332e6717ff7c7b878da3b7fd9adc0c48ad76079c69`:
scientific BASE C22 `d5cf1a844b81e84db22d66ff93fb7febfed22032`, TOPOS
`b157b7e210aee5bdfa09c22270d77d794f52cdde` and TORQ
`4ce8eecba56e91e27c6abb32473b2ee4d44767c4`. C27's BASE caller also
preserves validated fragments and fragment states during provider revalidation;
its interface is not byte-identical to C22's caller. Historical expert kits and
intercepted-GUI allowances remain separate from the canonical route. See
[incoming-main review](Incoming_Main_11c7399a_Review.md).

| Check | Actual source-bound result and limit |
| --- | --- |
| Strict source and complete profile | Exact C33 source-bound focused acceptance passed sixteen genuine controls. Collection contains 3,062 nodes: all previous 3,049 in order plus thirteen actual atomic/directory cases, zero executed collection bodies, collection errors or deselection (E78). The full all-node profile ran with a 7,200s budget and is independently **accepted** (E80): 3,056 call passes, zero failures/collection errors/deselection, four reviewed optional call skips and two physical Slurm setup skips. All 782 parser-valid source records have zero authority errors/escapes; 58 initial-only observations remain explicitly startup-only. Original/copied source and reused genuine C27 registry stayed unchanged; the admitted owned boundary emptied/reaped. These validation receipts bind code producer C33; the published main ref requires independent readback. Publishing main does not create a stable tag or establish external acceptance. Prior complete C29/C30/C31 failures remain failed (E65/E69/E73). The canonical audit's zero contextual blockers is distinct from independent all-system physical acceptance. |
| Current setup authority | Actual C27 eleven-phase Linux CPU setup completed in 92.402s: nine passed, phases 2/9 degraded, consistent origins and scratch bindings, unchanged source. Registry SHA-256 `2245921002505978e2627760123f8ea15bd5d93a8376f24769d087f2a236eca2`. Existing four valid silos were verified under an explicit 1GB floor; C33's complete-profile producer explicitly reuses this authority. Neither record proves fresh downloads, the default 50GB policy, GPU or student Codespaces acceptance (E50). |
| Direct licensed native calculations | C23 ORCA8/CFOUR10 passed, with 840 immutable artifacts/40 origin records, empty owned roots and unchanged source/registry. Frozen R1 grids preserve full gradients and warnings. CFOUR finite-difference error `3.774153128910385e-9 Eh/bohr` passed `3e-6`; one/two OpenMP energy difference zero passed `1e-10 Eh`. No CFOUR MPI/VPT2 or universal accuracy claim (E46). These receipts retain C23 producer identity. |
| Current TOPOS provider | Actual C27 caller/C22 SCI and installed pair were sealed and reverified, including all 571 scientific Python members. Nine accepted controller cases cover seven of nine operation kinds. The original xTB minimum/stationarity refusal, HF final-density refusal, wB frequency 300s timeout and capacity-interrupted RRHO remain unaccepted. Diagnostic frequencies do not establish qualified ZPE/RRHO or distinct-isomer populations (E53–E56). |
| Current TORQ provider | Separate readback passed three actual cases over two operation kinds using five existing PySCF SCFs, zero ORCA/separate version probes. Native/report size and SHA checks passed; the original erroneous export-count assertion remains failed and preserved. AO Löwdin-Wiberg is not NBO/NAO (E57). |
| Retained scientific and test bytes | The two inactive generated dependency environments were retired after typed member inventories, 915 raw metadata copies and outside-byte verification; dependency bodies have no whole-environment archive or current-runnable claim (E58). Separately, inactive C29/C30/C31 pytest fixture trees have complete private PAX/gzip archives verified for every regular byte, type, mode, UID/GID, nanosecond mtime, symlink, hardlink and FIFO before duplicate retirement; standalone failed/native evidence stayed unchanged (E68/E72/E76). The separately creator-bound old pytest235 failed generation has the same complete byte-restorable preservation, with all five other old generations/current pointer unchanged (E77). |
| Actual browser | Actual C29 FULL passed in 295.320s with all 56 source-authority records, 17 uploads/10 molecular frames, five authenticated kernel retirements, zero browser errors and fresh native HF/STO-3G Hessian plus 18O CSV/SVG reanalysis without another electronic calculation. Separate READ passed in 56.420s with all 32 authority records, no missing finals/live owners and unchanged source/registry (E63/E64). C33 runtime/browser bytes remain identical to that producer; the CI source observer/runner and ring are different. Neither route establishes a student App/Codespace or hosted chemistry pilot. Original browser failures retain E59/E60. |
| Current completed hosted route | [C33 run37878684516](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37878684516) succeeded: 221 actual controls on each Ubuntu/macOS/Windows worker, three installed wheels with 601 hashed RECORD members reverified each, 1,641 bounded regressions, genuine xTB/PySCF science, all eleven CPU setup phases and rendered/reused Voilà. Optional ORCA/CFOUR were unavailable in this DEGRADED_OPERATIONAL free-engine lane. All eight published ZIP digests and 1,026 member hashes were independently verified without extraction; actual PR checkout and C33 share the exact Git tree. Owned boundaries emptied and original/copied sources stayed unchanged. This is bounded hosted acceptance (E79), separate from the accepted complete local profile E80. |
| Original failures and causal corrections | C24/C25/C26 macOS failures, C27/C28 browser failures, complete C29/C30/C31 failures and C32 WinError32 remain failed and preserved. Current corrections retain every original physical, identity, ownership and test assertion. C33's actual CreateFileW handles demonstrate temporary sharing-violation release, persistent WinError32 refusal after 3s and unchanged foreign bytes; both original communicate-entry interruption controls pass (E78/E79). No unidentified old handle owner is inferred. |
| Scientific execution versus accuracy | Required native R2/T9/CREST–GOAT calls have genuine execution evidence in historical full producers. R2's counterpoise-ordering warning and frozen-bond residual `0.0046012636 Eh/bohr` remain visible with accuracy unverified. Its free Cartesian maximum/RMS components are `2.43e-7`/`9.10e-8 Eh/bohr`; no sign/deck/provenance defect was found. Neither an execution pass nor an approximate numerical/nonvariational explanation certifies experimental accuracy or proves a physical cause without comparison runs. |
| External student deployment | Live instructor App/private controller, selected personal project enrollment, a real student's fresh Codespace, personal hosted chemistry/retrieval/Classroom50 collection and current hosted licensed archive access remain external prerequisites. Missing optional access leaves free BASE usable. Actual GPU/Slurm and other physical host/provider combinations retain separate scope. |

E42–E49 preserve the preceding source-specific observations; E50–E80 add confirmed
evidence in the [complete trace](SRS_Student_1_1_Conformance_Trace.md), including
actual current hosted and complete-profile producers. C22's immutable-artifact
publication correction and thirteen genuine controls retain the original C20
runtime-lock defect. C23's accepted direct native rerun does not erase it.
The complete-profile result is established by E80, with all six external
prerequisites still deferred. No stable tag, full SRS/physical accuracy certificate
or real student pilot follows from that engineering acceptance or publication.

### Historical C17 evidence and later corrections

The historical C17 candidate is `4d4834dcac8a07786e691ba667cbb8d66e650925`, Git tree
`d2da15c9169a9c23b4e34c70e5a1d7e0a364b911`. Its reviewed infrastructure ring has
216 entries, SHA-256
`fa68242f8cd0f4b27214ed9aa5535cfe861f6219c8d36e6bb481ac5e970f3ffe`.
The accepted source snapshots contain 2,176 tracked files. Counts below describe
separate checks and are not added into a complete-profile total.

| Check | Recorded C17 outcome and scope |
| --- | --- |
| Strict release source audit | Zero production/CI or contextual selected-test blockers. Its 418-pattern whole-repository inventory included four entries from two selected physical Slurm-prerequisite nodes; it was not wholly unselected or accepted scientific coverage. |
| Hosted engineering controls | [Run 37829834106](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37829834106): 207 unique controls passed on **each** Ubuntu, macOS and Windows worker; zero failures, skips or deselections, complete setup/call/teardown outcomes and unchanged source. |
| Fresh installed wheels | All three hosted platform checks passed clean wheel installation, CLI, isotope database and real dry-run deck checks. No chemistry was executed by these wheel checks. |
| Eleven-phase local setup | Actual Linux CPU setup completed in 134.83 s: nine phases passed and phases 2/9 were explicitly degraded. All phase/final scratch paths agree; original source remained unchanged. Existing valid core/UI/calc/ML silos were verified, rather than reported as freshly downloaded. The explicit 1 GB disk floor does not qualify the default 50 GB policy, GPU or a student Codespace. |
| Provider prerequisite at C17 | The genuine TOPOS receiver test-tooling wheel prerequisite was installed and dependency closure verified; it was not native chemistry. That C17 record did not accept the complete default-provider campaign. Later current provider/native results and remaining refusals are E53–E58. |
| Hosted bounded regression and browser qualification | The C17 hosted bounded run collected 1,579 tests: 1,575 passed, four failed, zero skipped. Two native SWMR child processes timed out at 12 s and two tests required official PAW inputs. Dashboard validation was skipped and not executed. The C17 local complete profile never started. Later complete-profile/browser outcomes retain their own source; an earlier browser fixture is not completion. |
| Hosted free-engine setup and calculations | Hosted all-eleven-phase setup, real isolated xTB/PySCF numerical checks and fresh calculation-silo authority passed. The scientific worker is C16 `68496c225fc90ff13f0ec6ff7c97570737917615`; these passed stages did not establish bounded-regression/dashboard acceptance. The earlier C15 run was cancelled after approximately 35 minutes and supplies no accepted final regression count or dashboard claim. |
| Current hosted licensed engines | No C17 ORCA/CFOUR hosted replay is accepted. Prior current-candidate archive-access attempts were blocked; historical licensed native/hosted receipts below retain their own revisions. Missing optional access disables dependent operations while free BASE remains usable. |
| Personal-project App/student pilot and stable publication | Not established by maintainer tests. Live App enrollment, actual fresh student Codespace, personal-project chemistry/retrieval/collection and a stable published tag need separate records. |

The hosted checkout was synthetic merge
`c9a15c17894c66e2074e6a6073cd1387267ddbd9`, whose Git tree exactly equals C17.
Receipts are retained under `/tmp/cochem-hosted-c17-4d4834dc/` in
`c17-pr-tree-proof.json`, `c17-all-hosted-control-outcomes.json`,
`c17-native-admission-causal-proof.json` and `c17-pr-installed-wheels.json`.
The terminal hosted result is `c17-terminal-hosted-validation.json`, SHA-256
`11efccfe03ab12e2623dcae6caa11a98445f32f45384c173af0f6dccb8e16e04`.
Its failed bounded regression is separate from the passed engineering, wheel
and free-engine stages. The causal proof SHA-256 is
`ffde3be2202a1f0a6b6518282773ba9106b00b0677e74654499e94c14bef3430`.
The fresh setup receipt is
`/tmp/cochem-current-fresh-stage0-evidence-4d4834d/acceptance.json`; its registry
SHA-256 is `4edbe79b607bb6f07a9340710e602951bcf10d85bfed93edf03be03aa0cf230f`.
These local receipts are retained review evidence, not public signed release assets.

The TOPOS canonical receiver prerequisite receipt is
`/workspace/cochem-runtime/evidence/c17-canonical-topos-receiver/installation-acceptance.json`,
SHA-256 `c877dc87790edb7f00678fb1fca7d3b344ae816ca1be0f5141e801f5c8fb2217`.
Its genuine wheel SHA-256 is
`2ed5684cbe8f8b7153a806bacf19b4b94de3b2847bd1b67f7723566f4020571e`;
137 active dependency edges/76 distributions were verified, with no changes to
existing distribution metadata. This is a test-tooling prerequisite, not a
substitute for BASE's isolated scientific-provider acceptance. Historical hosted
free-engine/setup stages and failed/unaccepted regression/dashboard stages are
separately observed in the run above. The tracked-tree public hygiene receipt at
`/tmp/cochem-hosted-c17-4d4834dc/public-hygiene-tracked-tree.json`, SHA-256
`6d09ffc06fa3be603c34bcc7de97e392f8f1565ebc28ff203865841f4d658557`,
records no credential values, former public stored labels or licensed archives
among the 2,176 tracked paths.


The current advertised CLI preflight verifies the complete typed Stage 0
authority, actual core/UI silos, sealed default modules and available executable
identities; empty directories cannot establish readiness. Invalid or absent
optional licensed engines retain an unavailable/invalid capability while free
BASE remains usable. Assignment restart/rollback rejects redirected authority.
Unsafe prefix-based scratch deletion and destructive in-place silo reset are
removed: cleanup refuses unsupported destructive flags and never deletes an
accepted runtime or unrelated process's files. The targeted CLI receipt records
ten genuine filesystem/native-process/Stage 0 checks; two subsequent actual
creator/authority checks cover the shared runtime guard. These targeted counts
are not a frozen complete-profile result.

Forty-one obsolete legacy test/helper files were physically retired after
consumer review. Their deleted findings are resolved; the old 559-flag count is
historical. Valuable optional/native/domain coverage was retained and is not
silently counted as canonical acceptance. C17's 418-pattern whole-repository
inventory included four selected physical Slurm-prerequisite entries. The later
reviewed development inventory is 371 patterns, with 74 selected raw patterns
and zero contextual selected blockers; exclusion alone does not resolve a
retained finding. The original retirement receipt is
`c14-legacy-inventory-independent-classification/authorized-retirement-after.json`
under `/workspace/cochem-runtime/evidence/`; exact retired source is retained in
Git. Native cleanup/control receipts preserve real earlier failures and PID
observations, along with the subsequent 34-pass and corrected five-pass targeted
checks, rather than turning a stopped attempt into a pass.

The later ten-file test-only reconciliation physically removed invented
CREST/Windows/WSL observations and fake execution callbacks. It preserved unique
controls and used actual damaged executables, directory collisions, child
environment/path resolution, six real CLI invocations and two real async
diagnostic-child handshakes. Their independent freeze receipt is
`/workspace/cochem-runtime/evidence/c17-exact-mocked-case-retirement-builder/freeze.json`,
SHA-256 `903d4bc3fe6b317a9d0e9e2031500f86a2c2b5218555a7cadc7ceea91f2b06e7`.
Targeted development checks are not chemical or complete-profile acceptance.
Mobile copied-asset checks executed zero tests because AnyWidget was absent;
native WSL/Windows priority, CREST-without-xTB and retained legacy-import
prerequisites remain explicitly unverified.

An actual C17 R1 admission failed because a full constrained Cartesian gradient
was compared against the optimizer's allowed-motion convergence gate. The raw
maximum Cartesian component was `0.011692 Eh/bohr`, while the actual constrained
optimization
reported maximum/RMS active gradients about `3.1e-9`/`1.6e-9` and energy change
about `-2e-10 Eh`. The correction preserves physical derivatives/telemetry and
uses the appropriate active-coordinate stationarity; final native qualification
is now supported by the bounded C23 rerun, while other systems retain their own
acceptance. Historical failed outputs
are retained rather than rewritten as success. The read-only comparison is
`/tmp/cochem-c17-dedicated-native-4d4834d-20261008b/orca/r1-grid-failure-diagnosis.json`,
SHA-256 `6243e239c981394bea511f5ec00a4ee0dbc0c2da00286f279dd09702c2fea729`.

### Historical candidate checks

The [C8 hosted run 37779175927](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37779175927)
has mixed outcomes and is not a passing complete candidate gate. Source integrity,
164 controls on each of Ubuntu/macOS/Windows, fresh wheel checks, all eleven
real setup phases and genuine xTB/PySCF calculations passed. The bounded
regression stage failed during collection with zero executed tests because its
Scribe prerequisite was absent. The revised workflow installs the declared Scribe extra. The later C17
engineering/wheel results and unaccepted regression result are recorded above.
The hosted synthetic merge
`5b7e4330ac51d4fe246f6fc3dbfdd76f9fde9969` had tree
`777d3d9f102ac5678dec69e60f4d1db29476768d`, identical to C8 `f44f709`.
The retained binding is `hosted-c8-bounded-ci-f44f709/source-merge-binding.json`;
`review.json` records the distinct outcomes. Those successful stages do not
qualify the later source/quarantine/App changes or a student account.

Retained local evidence includes the fresh default-module receipt at
`/workspace/cochem-runtime/evidence/student-default-final-3ce9206/acceptance.json`
(C6 controller/catalog, C5 science), six genuine TOPOS cases at
`student-topos-c5-final-native/acceptance.json`, report exports at
`student-topos-final-3ce9206-reports/acceptance.json`, and TORQ scan/report records
at `student-torq-final-3ce9206-native/acceptance.json`. These are exact earlier
candidate receipts, not a final combined-candidate pass or a student App pilot.
The public credential/workflow migration's targeted development receipt is
`public-workflow-private-binding-validation-20261008.json`; its 229 tests and
separate actual restart-isolation check likewise do not supply a final release
count. Final evidence will identify the immutable candidate SHA, pass/fail/skip
counts, fresh wheel digest, browser scope and actual service run URLs.

## Historical 1.0.1 validation and gap closure

The 2026-10-07 final SRS audit identified four connected BASE gaps: automatic
measured-gradient grid progression, authentic live derivative records, general
isotope-label ingress/handoff and persisted native-runner crash provenance.
Their implementation and revision-specific acceptance are tracked in the
[1.0.1 closure record](Release_1_0_1.md). The following complete-profile result
belongs to that historical 1.0.1 source, not the revised 1.1 candidate.

The complete-profile source is `583a6d22db0fab0fdd54d2659ceac87ba82fa48a`.
Its application/workflow/devcontainer source matches accepted `7144f82` and
`80dfec3`; the correction changes only a GUI acceptance test and hosted selection.
[Hosted CFOUR acceptance 37704401496](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37704401496)
passed ten genuine native cases plus an `18O`/D2O input-isotopologue harmonic
and Hessian-ingestion case. The [student-style CFOUR job](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37704003113)
passed on application-equivalent `80dfec3`. The approved build is OpenMP-enabled
and MPI-disabled; VPT2, open-shell and correlated derivatives remain separately
scoped providers.

[Hosted ORCA acceptance 37703993551](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37703993551)
passed physical serial/parallel checks and three genuine SRS completion cases:
three-grid progression, labelled harmonic/Hessian ingestion and native xTB
optimization. They retained seventeen, seven and eleven Cartesian-gradient
evaluations. The [student ORCA calculation](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37704000193)
also passed on `80dfec3`. Source comparison verifies 2,101 identical
production/workflow/test blobs to `7144f82`; the only helper differences do not
change the ORCA scientific path. A redundant cancelled run is not acceptance.

[Hosted public CI at `583a6d2`](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37706334481)
passed source integrity, Ubuntu/macOS/Windows controls and isolated-wheel
checks, **883 bounded regressions** with no failures, skips, deferrals, coverage
errors or source changes; all 1,368 source-snapshot entries matched the frozen
Git blob. Real
free-engine/derivative checks, all eleven Stage 0 phases and rendered dashboard
lifecycle also passed. The [earlier 869-test hosted run](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37704370113)
at `7144f82` remains separately retained. The complete canonical profile at
exact `583a6d2` passed **1,827 tests** out of **1,829 collected**, with **two
exact physical Slurm deferrals**, **zero failures or unexpected skips**, and
10,672 retained warnings in 879.89 seconds. Audit/test gates passed with no
coverage errors; all 1,368 source/input snapshots matched the frozen Git blob
and remained unchanged. Evidence is retained under
`/workspace/cochem-runtime/evidence/srs-1.0.1-complete-final-v3/` in
`summary.json`, `test-acceptance.json` and the actual pytest XML report.
Independent comparison confirms all 511
production/UI/native-workflow/source-integrity paths identical to accepted
`7144f82`/`80dfec3`. The corrected focused GUI selection passed 14 tests;
it resolves the final manifest-bound result while validating genuine derivative
records. Earlier incomplete/failed profiles are retained, not reported as
passes. Verify final merged-source builds, uploaded assets and non-draft
`v1.0.1` publication through the actual release entry and attached validation
report/checksums described in the [release record](Release_1_0_1.md); the
passing profile does not itself establish publication.

A genuinely fresh local configured Bookworm container passed the version-1.0.1
interface, all eleven Stage 0 phases, strict isotope CLI JSON and real free-xTB
energy/Hessian checks with ORCA/CFOUR absent. Its 2,104 tracked files remained
unchanged. The captured `80dfec3` application/GUI/devcontainer bytes match
`7144f82` and `583a6d2`; subsequent changes affect only CI transport/selection
and a GUI test. This local evidence does not
replace the real student-identity [deployment pilot](Student_Deployment_Pilot.md).
Native D/T Chain execution also retained six genuine Cartesian gradient
vectors and isotope identity. Stale checked-in package metadata is removed;
source and installed version checks now use the canonical release metadata.

## Historical 1.0.0 acceptance — 2026-10-07

The complete canonical profile passed **1,532 tests**, with **2 exact physical
Slurm skips**, **0 failures**, **1,534 collected** and **10,672 retained warnings**
in **950.50 seconds**. The source audit passed, all collected-node outcomes were
accounted for, and no audited source/input bytes changed during execution.
The remaining skipped checks require an actual Slurm allocation; they are not
successful platform acceptance. Real R2 and CREST/GOAT checks now execute.
Evidence: `/workspace/cochem-runtime/evidence/base-1.0.0-final-v4/`, against
`e2aaca60fefc4d1fd716aea176d54df9c1794d39`. The earlier 1,469-pass v2 and
1,477-pass v3 (`190e5c5`) runs on 2026-10-07 remain historical; this result
includes the final review corrections.

The retained-source inventory at that historical revision contained **565
source-pattern flags**, separate from its passing canonical source gate. Two additional detections
relative to the 563-flag snapshot refer to the same POSIX-only Git timeout/FIFO
guard; that test executed successfully on Linux. These are static patterns,
not fabricated-result defects. Deleted legacy findings are resolved, and the
dated 559-flag inventory below remains historical.

[Actual hosted ORCA acceptance](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37613653904)
passed at `1cfa49a84d45da7c60ffd1fa0d6eae3889dbe049`, including fresh private
archive installation, all eleven Stage 0 phases and genuine serial/two-rank
calculation publication. The separate [student optimization/frequency run](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37616684042)
passed at `0a9effe`, including actual two-process ORCA derivatives and result
publication. [Bounded hosted CI](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37624167721)
passed for the `e2aaca60` source tree, using the identical-tree GitHub merge
checkout `a438644d`: source integrity, 164 controls per operating system, all
three wheel/CLI jobs, 537 bounded regressions, native launcher diagnostics,
real Linux xTB/PySCF calculations, Stage 0 and dashboard lifecycle. A 479-test bounded local selection and isolated
wheel installation also passed at `01cca5b`; overlapping selections are not
added to the canonical count. The full local profile tested the final
`e2aaca60` implementation. Changes made solely to publish that historical
1.0.0 snapshot were documentation only; later CFOUR/module/1.0.1 changes include
production code and require their own revision-specific acceptance.
The [release record](Release_1_0_0.md) preserves exact revision boundaries,
evidence paths and outstanding publication checks.

## Historical BASE alpha acceptance — 2026-10-06

The canonical `ci_tools/base_ci.py all` run on **2026-10-06** passed both gates:

- **1,189 tests passed, 4 external checks deferred, 0 failed**, from 1,193 collected tests in **391.21 seconds**. The 10,669 warnings are retained in the log, not suppressed. Deferrals are the actual ORCA R2/reference calculation, ORCA/CREST union and two physical Slurm-node checks.
- **Zero blocking findings** across production/CI source, selected-test source, mass policy and source/data airgap. The runner verified complete per-node outcomes and **no audited source change during testing**.
- The retained test-source inventory at that historical snapshot had **559 automated flags in 121 existing test files**. **No flags refer to deleted legacy files; those items are resolved.** This includes 42 conditional-skip references in selected tests and 517 flags outside the profile. It is not a count of 559 confirmed code defects or an unfinished backlog for deleted code. See [current CI review](SRS_AST_Review.md) and the machine-readable audit.
- Actual Chromium acceptance passed **30 checks**, including xTB, PySCF, CREST, QE, isotope exports and verified future-module handoff download, with no page errors or failed requests. The separate focused GUI selection passed 52 tests; overlapping selections are not added to the canonical count.
- The **complete reusable installation script was rerun successfully**. All eleven setup phases republished genuine authority, retaining native xTB/CREST/g-xTB/MOPAC/QE and isolated PySCF/MACE. Explicit four-silo selection fixes the former lightweight-default capability loss. Setup remains truthfully degraded for unavailable licensed/host capabilities and the explicitly reduced disk workload profile.

Evidence is retained under `/workspace/cochem-runtime/evidence/base-alpha-2026-10-06/`: `summary.json`, `source-audit.json`, `pytest-outcomes.json`, `pytest.xml`, `test-acceptance.json`, source snapshots, actual setup/install logs and independent scientific-boundary review. CI-control-only acceptance separately passed 157 tests with no skips. The workflows at that revision passed `actionlint`; hosted execution had not been accepted at that snapshot. These counts are historical, not the final 1.0.0 suite count.

A subsequent reporting clarification reproduced the affine error scaling, removed the demo’s misleading “spectroscopic grade” display and verified **20 focused PES tests**, the actual numerical demo and the canonical source audit. It did not tune the fitter or change either energy-error result. The prior full-suite snapshot remains retained unchanged. Follow-up evidence: `/workspace/cochem-runtime/evidence/pes-and-retirement-clarification/`.

## Chunk 17 requirement traceability

| Requirement | Current implementation and evidence | Remaining scope |
|---|---|---|
| 001 — OS/hardware ingress | Measured Linux/cgroup CPU, RAM, instruction capabilities and bounded GPU discovery. Registry records unavailable capabilities instead of inventing them. C17 hosted engineering controls and installed wheels passed on Linux/macOS/Windows. | Native licensed-engine science, Windows/WSL and macOS deployment combinations, actual student Codespaces and GPU measurements remain separate acceptance. |
| 002 — micro-silos | All eleven Stage 0 phases execute. Core/UI/PySCF/ML package locks, interpreter isolation, import origins and `pip check` are verified before final registry publication. Partial phases cannot publish a completed master. | Accelerator variants and native platform combinations. This workspace explicitly uses a 1 GB free-disk workload profile; it does not meet the default 50 GB policy on its 32 GB filesystem. |
| 003 — canonical SWMR telemetry | Canonical committed-row `complexes.h5` telemetry publishes geometry/energy/gradient with nuclear identity. ORCA intermediate gradients bind the immediately preceding native Bohr geometry/energy to retained selected-output transcript hashes and offsets; declared print precision is retained. xTB optimization now uses genuine native `--grad` evaluations through BASE BFGS, recording each evaluation and raw evidence instead of inventing Cartesian derivatives from a gradient norm. CFOUR native BFGS likewise records actual analytic-gradient evaluations. | An evaluated trial geometry is labeled as an evaluation, not a completed optimizer iteration. Coordinates without an available derivative remain explicitly coordinate-only. Full search-engine artifact and distributed-filesystem coverage requires its own provider/host acceptance. |
| 004 — dynamic masses | Dynamic Mendeleev validates `13C`/`C-13`/`C13`, D/T and exact physical nuclides. Canonical prefix identity survives XYZ/multiframe and SMILES ingress, COM/Eckart alignment, geometry/Hessian/result handoffs, SWMR nuclide/mass attributes, GUI selectors and conformer seeds. Electronic decks serialize true element labels. | Unknown/nonphysical nuclides are rejected; ghost centers use their specialized counterpoise adapter rather than general XYZ ingress. Complete third-party/legacy provider coverage still requires its own acceptance. |
| 005 — COM/Eckart ingress | Native calculations, TOPOS and Chain normalize ingress using exact isotope masses; proper rotation and residual gates are tested. Quantum decks retain sufficient coordinate precision after normalization. | Verification of every imported tensor/state frame and each external engine's independently rotated output remains required. |
| 006 — graph/geometric conformer sieve | WL graph/isomorphism, atom mapping, mass-weighted alignment, stricter Chunk 17 RMSD/rotation gates and proposal energy agreement `<0.05 kcal/mol`. Actual CREST plus ORCA GOAT water union passed, including HDF5 publication and durable promotion. | This bounded two-engine ingestion check does not implement the future TOPOS domain solver. |
| 007 — R1 frozen monomers | Wilson bond/angle/dihedral and linear-bending handling; all-frame monomer drift checks. Historical ORCA water-dimer R1 optimization passed with maximum monomer drift `6.1213138e-7 Å`. Current grid promotion distinguishes the original physical gradient from its allowed-motion component. | The failed C17 constrained-admission attempt and later correction are recorded above; Current bounded C23 native acceptance is indexed below; complete C33 source-bound profile acceptance is E80; other physical hosts remain unaccepted. `r2SCAN-3c` retains its published composite basis. One successful case does not certify every system’s coordinate or rotational accuracy. |
| 008 — R2 production | Actual ORCA canonical CCSD(T)/TZ-QZ reference generation, independent PySCF energy comparison and accepted five-leg R2 execution. Source hashes, atom mapping, gradients, trajectory drift and achieved convergence are retained. Signed counterpoise ordering and residual-gradient warnings remain explicit. | The bounded accepted run is recorded in [scientific acceptance](ORCA_Scientific_Acceptance.md); it does not claim a rigorous counterpoise energy bound. A finite-basis CBS estimate is not exact-CBS geometry certification. Higher-order R2 frequency/VPT2 providers remain downstream work. |
| 009 — grid lifecycle | Supported native ORCA DFT optimizations connect measured-gradient/energy/last-step convergence to DEFGRID1 → DEFGRID2 → DEFGRID3 execution. Actual geometry and immutable GBW state carry forward under one operation budget and fresh authority. Explicit grid, high-tier, transition-metal, R2 and frequency minima are preserved; fixed HF/correlated jobs do not acquire an invented DFT grid. | Stage progression does not establish universal empirical integration/rotational accuracy. A private native `.opt` is not converted into a portable Hessian; an explicitly supplied genuine geometry-bound Hessian retains its READ validation. |
| 010 — quintuple convergence | Required thresholds are emitted; achieved-value parsing rejects absent, incomplete, nonfinite or failed convergence. Chain cannot override geometry/resource policy through arbitrary raw blocks. | Actual coordinate and rotational-error targets need independent physical reference data. Configured tolerances cannot guarantee those errors for every molecule. |
| 011 — Hessian discipline | XTB2/Lindh/READ policy, forbidden exact initial Hessians, safe identifiers, unique basenames and geometry-bearing Hessian validation. Actual ORCA checkpoint consumption and compound execution passed, including native MO projection, Hessian initialization, per-stage convergence and unchanged source hashes. | The compound acceptance validates native execution; it does not automatically import compound stages into Chain HDF5. Other external wavefunction formats and CFOUR retain their own acceptance. |
| 012 — dispersion | B3LYP/PBE0 require D3BJ/D4, including isolated molecules. VV10 plus empirical dispersion is rejected. Real B3LYP-D4 and wB97M-V calculations passed through DEFGRID1/2/3 with retained convergence/refinement evidence. | The measured combinations do not certify all functionals, molecules or empirical accuracy targets. |
| 013 — spin and T9 fallback | Inclusive 10% relative spin rejection and real isolated PySCF CASSCF/NEVPT2 recovery. Actual stretched H3 ORCA `<S²>=1.591697` was rejected and explicit CAS(3,3)/NEVPT2 recovered the doublet (`<S²>≈0.75`). CLI, GUI and Chain preserve the recovery contract. | Active spaces remain explicit. Single-point recovery does not complete an interrupted optimization/frequency request. Open-shell CFOUR diagnostics require its provider. |
| 014 — isotope transformations | Actual ORCA water Hessian ingestion and simultaneous 18O/D2 substitutions passed library/GUI parity without new electronic calculations. Isotope-labelled native requests retain the unchanged Cartesian Hessian and selected exact masses/frequencies in geometry-bound NPZ; native/principal spectra are separately validated and identified. | Harmonic mass projection does not supply VPT2 `B0`; missing anharmonic corrections stay unknown. Minimal-basis examples establish integration, not experimental frequency accuracy. |
| 015 — subprocess lifecycle | Actual Linux children/grandchildren, cancellation, affinity, owned-process cleanup and crash handling; C17 actual three-platform CI controls preserve complete native engineering outcomes. TORQ no longer kills unrelated descendant processes at shutdown; CLI cleanup refuses unsafe prefix/reset deletion. | Physical licensed-engine jobs, actual Slurm/PBS/GPU execution and each scheduler/filesystem topology need their own acceptance. |
| 016 — strict CI boundary | Historical C17 clean Git/ring source audit has zero production/CI or contextual selected blockers; its actual three-platform controls ran in private quarantine with complete outcomes and unchanged-source checks. C27 source inventory has 371 whole-repository patterns/74 selected raw patterns and zero contextual blockers (E50); current C33 three-platform bounded acceptance is E79, with C27 evidence retained E51. | Physically retired files/cases resolve their removed findings. C17's 418 patterns included four selected physical Slurm-prerequisite entries. Inventory or development audits are not accepted coverage; complete C29/C30/C31 gates failed (E65/E69/E73). Current C33 focused/collection, bounded hosted and complete source-bound profile checks passed (E78–E80), with six reviewed external prerequisites still deferred. Historical [audit snapshots](SRS_AST_Review.md) retain their original counts. |

## Additional proposal vectors

| Vector | Implementation/evidence | Outstanding acceptance |
|---|---|---|
| 1 — code/data separation | External artifact roots, source/symlink write guards and locked atomic configuration updates. | Native platform/filesystem coverage. |
| 2 — Golden Registry authority | Engine execution binds actual executable/package/interpreter/resources. Current CLI preflight checks complete Stage 0 authority and sealed runtime/modules; assignment restart/rollback rejects a redirected authority. | Complete C29/C30/C31 profile/source gates remain failed (E65/E69/E73). C33 source-bound focused, bounded hosted and complete profile checks passed (E78–E80), with actual unchanged source/copy/registry and owned cleanup; six external prerequisites remain deferred. Checksums detect drift; they are not independent auditor signatures or physical engine success. |
| 3 — eleven-phase setup | Exact C17 Linux CPU setup completed in 134.83 s with nine passed/two degraded phases, verified current silo authority and consistent selected scratch; measured observations are retained. Fake timings/default capacity and premature publication removed. | Explicit 1 GB qualification floor, absent GPU/HPC and existing-silo reuse do not prove default 50 GB/fresh every-platform installation or a student Codespace. |
| 4 — atomic I/O/SWMR | Ten-second canonical locks, atomic registry replacement and committed HDF5 rows; actual readers/writers and recovery tests. | Full legacy archive migration and real distributed filesystems. |
| 5 — process groups/NUMA | Audited CPU/NUMA selection and owned process handles; C27 hosted native engineering controls passed on Ubuntu/macOS/Windows (E51/E52). Unsafe advertised cleanup/reset routes now refuse destructive operations. | Actual multi-socket cluster NUMA, physical engine jobs and scheduler/filesystem validation remain separate. |
| 6 — crash forensics | Active native runners share an exclusive UUID JSON-LD recorder: exact raw stderr tail before text decoding, prelaunch executable/input hashes, actual cwd/thread/timeout/affinity controls, measured host resources, distinct Git object ID/object SHA-256, package/recorder identity and canonical record hash. Records use read-only file permissions and are retained in licensed calculation artifacts. The CLI arms uncaught-exception JSONL/traceback and emergency HDF5 closure. | File/hash integrity is not an independent audit signature. Missing Git identity is explicit; CPU/RAM values describe the host at recording rather than invented per-job peak usage. Additional native-platform physical acceptance remains separate. |
| 7 — resource guard/LTTB | Production Scribe now uses the canonical cgroup/available-memory/registry guard; `RESOURCE_GUARD=0` cannot bypass it. Prompt compression retains actual moments and at most 500 samples. | Authenticated remote API and GPU model acceptance. |
| 8 — constants | Shared CODATA conversion exports and required rotational conversion; discrepant formatter/propagation/Chain copies corrected. | Third-party numerical libraries retain their own documented versions. |
| 9 — quadrature | Chunk 17's three-stage sequence is connected to supported native ORCA DFT optimization and measured convergence; explicit stronger minima remain authoritative. | Bounded genuine stage/refinement acceptance does not establish every rotational/integration error target for arbitrary molecules. |
| 10 — stationary convergence | Emission and achieved-value gates are connected to execution. | Universal sub-mÅ/rotational accuracy is not established by thresholds alone. |
| 11 — Wilson freezing | Real derivative/nullspace mathematics, complete fragments and live trajectory integrity; historical R1/R2 frozen-monomer acceptance is retained. Constrained grid promotion separately records raw, normal-reaction and allowed-motion derivatives. | Bounded C23 native replay passed; additional molecules and external solver/host combinations retain their own physical acceptance. |
| 12 — chained Hessians | Structured policy, checkpoint presence/content checks, output geometry agreement and actual ORCA checkpoint/compound state-transfer acceptance. | Compound stages are not automatically imported into Chain HDF5 by the deck-generator acceptance. CFOUR state transfer requires its scientific provider. |
| 13 — dispersion | Common sanitizer covers standalone and Chain inputs; actual B3LYP-D4/wB97M-V grid series passed. | Additional solver combinations and systems. |
| 14 — CREST/GOAT union | Actual CREST plus ORCA GOAT water union, graph/RMSD/rotation/energy gates, HDF5 publication and promotion passed. | Additional systems and future TOPOS domain acceptance. |
| 15 — multireference escalation | Real configured CASSCF/NEVPT2 execution after typed spin rejection. | Workflow-specific active spaces and completion of requested higher-order tasks. |
| 16 — principal isotope masses | Dynamic exact nuclides through ingress, alignment, telemetry and immutable handoffs; selected-isotope spectra and principal/native baselines remain explicitly distinct. | Complete external scientific-provider/format coverage. |

The proposal workflow's **MACE-OFF24m ↔ g-xTB fallback is now executed**, not merely recommended: both directions ran on actual CPU backends, retained measured energies/gradients, recorded both attempts and wrote canonical telemetry. Corrupt checkpoint evidence aborts instead of being hidden by a fallback. Heavy libraries stay inside the ML silo. The exact official OFF24 medium v0.2 checkpoint is distinct from OFF23.

## Scientific and integration acceptance boundaries

1. **The PES failure had real implementation and analysis defects; a new quantum protocol now passes its bounded target.** The historical Cu/Ag/Au EMT example used the artificial target `1.02 * E_EMT - 0.005 eV` and placed all 150 holdout geometries beyond its training Cu–Ag separation range. Correct fitting/provenance reduced its paired correction RMSE to 6.271842 cm⁻¹, but its standalone extrapolation RMSE remained 319.863926 cm⁻¹ (0.915 kcal/mol). These are energy errors, not vibrational frequencies; that example remains uncertified and cannot provide independent quantum accuracy evidence. The new actual ORCA H2 protocol instead uses 128 RHF/STO-3G baseline points, 32 canonical CCSD(T)/cc-pVTZ correction pairs and 31 fresh holdout geometries excluded from both training sets over 0.55–1.80 Å. Unchanged model defaults give paired RMSE **1.189292656 cm⁻¹** (maximum **3.726415424 cm⁻¹**) and standalone RMSE **3.176715694 cm⁻¹** (maximum **8.242899532 cm⁻¹**), meeting the unchanged 10 cm⁻¹ threshold for both metrics. Denser independent baseline sampling addressed interpolation error; the model was not tuned on holdouts. This two-electron one-dimensional interpolation does not certify nonzero triples contributions, vibrational frequencies, extrapolation, experimental agreement or arbitrary molecules. Full provenance is in `/workspace/cochem-runtime/evidence/quantum-pes-2026-10-07/dual-resolution-acceptance.json`.
2. **CFOUR native execution is accepted within a defined provider boundary.** BASE provisions and seals the approved runtime, authorizes isolated native jobs and accepts closed-shell HF single points/optimization/harmonics plus MP2/CCSD/CCSD(T) single points. Geometry-bound harmonic Hessians support downstream ingestion and isotope reanalysis. VPT2, open-shell and correlated derivative operations remain explicit provider handoffs. Missing adapters must not fabricate energies, anharmonic corrections, isotope `B0`, convergence or completed operations. Historical broad CFOUR configuration is preserved as pending input handoff; it is not a second weaker execution path.
3. **Supported TOPOS/TORQ operations are connected through BASE.** Automatic sealed installation, native provider dispatch, scientific comparisons and result tables/figures have bounded local receipts. Further domain algorithms belong to their modules, and unavailable NBO/NAO, higher-order or other unsupported providers remain explicit. BASE does not claim every possible PES domain operation or platform from those receipts.
4. **Product B now has direct BASE ingestion examples.** Ordered CIF and periodic JSON with fractional or Cartesian coordinates and explicit Angstrom/Bohr units preserve the periodic frame, original source hash and canonical converted structure hash. Singular/left-handed cells, duplicate lattice-equivalent sites, disorder/partial occupancy and invalid PAW inputs are rejected. The real registered QE PAW GaAs single point remains connected. Advanced bands, SOC, cell optimization and empirical accuracy claims need their scientific providers and benchmark evidence; ingesting a cell or executing one SCF does not certify them.
5. **CI must preserve failures as evidence.** Obsolete duplicated workflows and misleading physical fixtures are retired with recorded replacements. The current source gate checks initial Git/ring integrity and refuses source-capable untracked material before running tests in an external quarantine. Actual owned process cleanup, origin checks, complete node evidence and unchanged before/after source are required. Missing/zero-test evidence, source changes and unexpected skips fail acceptance. Deleted legacy findings are resolved; historical inventories do not become an executed current profile.
6. **External acceptance requires actual execution evidence:** ORCA 6.1.1 hosted serial/two-rank acceptance has passed, with its run linked above. The separate student optimization/frequency workflow also passed. Ubuntu/macOS/Windows controls, wheel/CLI checks and native launcher diagnostics passed in bounded hosted CI; this does not certify native ORCA science on Windows/macOS. Actual student Codespaces, GPU/Slurm, deployment filesystems and additional native physical calculations remain deferred; CFOUR Linux/hosted native acceptance is recorded above. Source-level Slurm staging now prepares a real validated, hash-bound request and performs fresh Stage 0 within the compute allocation; those tests do not claim a physical cluster run.

## Reproduction and retained evidence

```bash
source /workspace/cochem-runtime/activate.sh
python -B -m pip check
# Maintainer-only: requires a clean reviewed commit and current execution registry.
# Use a fresh external evidence path; preserve failed attempts.
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python -B ci_tools/base_ci.py all --output /tmp/cochem-base-alpha-evidence
# Wider historical inventory, not an alpha acceptance substitute:
python ci_tools/anti_spoof_linter.py . --strict --json > /tmp/cochem-strict-repository-inventory.json
```

The commands above are maintainer reproduction, not student setup. Historical second-pass logs, JUnit, strict scans and a source manifest are retained together in `/workspace/cochem-runtime/evidence/srs-pass2/`. Session evidence also includes `/workspace/cochem-runtime/stage0-complete-audit.json`, `/workspace/cochem-runtime/topos-second-pass/`, `/workspace/cochem-runtime/mlff-second-pass/`, `/workspace/cochem-runtime/gui-srs-pass/` and `/workspace/cochem-runtime/chain-pass2-jt1upcd8/`. Runtime artifacts remain outside the repository. The self-contained cloud install script completed successfully, including all free-engine/ML checks and all eleven Stage 0 phases. The environment setup draft is saved for review; a fresh published/restored environment is a separate acceptance step. The repaired hosted lifecycle also completed setup twice in a separate external environment, passed 27 native CLI/lifecycle checks, all five workflow syntax checks, and actual Chromium interactions. That earlier local lifecycle report did not establish hosted acceptance; subsequent run-specific outcomes are recorded in ORCA_Actions_Setup.md.

A historical full-repository collection attempt discovered **4,416 tests and 237 collection errors** (`/tmp/cochem-all-collection-pass2.log`). These include missing sibling interfaces, legacy import paths and tests that import heavy libraries directly into BASE even though those libraries are installed in their required silos. This is not evidence that every low-compute test ran. An isolated built-wheel check imports the shipped CLI, GUI, frontend adapter, native setup service and provenance implementation without checkout paths or `.pth` processing.

This audit records implementation and measured evidence. It does not manufacture council approvals, scientific signatures, experimental reference data or a blanket conformance certificate.


## ORCA Actions integration follow-up

The user supplied the ORCA 6.1.1 private release and independently calculated
SHA-256 and authorized commit/push and hosted calculation acceptance. The pinned
installer, MPI runtime build, reusable action and real serial/parallel BASE CLI
acceptance are documented in [ORCA Actions setup](ORCA_Actions_Setup.md). ORCA
MPI rank/thread oversubscription was fixed in native, TOPOS, R2 and Slurm paths.

The historical prepublication canonical local run passed **1,241 tests**, with the
same **4 external deferrals** and no failures, collected-node omissions,
unexpected skips or source changes. This superseded the earlier alpha count at that revision;
it is now superseded by the 1,532-pass profile above and did not establish hosted ORCA execution. Evidence:
`/workspace/cochem-runtime/evidence/orca-actions-prepublication/`.

## Real ORCA and Classroom50 evidence — 2026-10-07

The strict local report
`/workspace/cochem-runtime/evidence/orca-scientific-acceptance-strict.json`
passed frozen R1 water-dimer optimization, the B3LYP-D4 and wB97M-V three-grid
series, and actual contaminated ORCA H3 rejection followed by explicit isolated
PySCF CAS(3,3)/NEVPT2 recovery. It preserves actual inputs/output hashes and
records `scientific_accuracy_established=false`.

The CREST plus ORCA GOAT water union passed in 155.19 seconds, including HDF5
publication and promotion. Canonical CCSD(T)/TZ-QZ reference energies were
independently reproduced with PySCF; the bounded H2 finite-basis CBS-estimate
geometry is not an exact-CBS or experimental accuracy certificate. Detailed
R2 convergence/counterpoise evidence is retained in
[scientific acceptance](ORCA_Scientific_Acceptance.md).

The real ORCA water Hessian passed library/GUI parent and 18O/D2 isotope parity
without a new SCF, with unchanged input-hash, rigid-mode, geometry-rejection and
missing-anharmonic-data checks. Evidence:
`/workspace/cochem-runtime/evidence/orca-hessian-gui-parity/acceptance.json`.
Actual Chromium also verified the Classroom50 Actions job download with no page
or request errors; its report explicitly states that no hosted calculation was
performed by the export test:
`/workspace/cochem-runtime/evidence/classroom-actions-ui/browser/browser-summary.json`.

Actual ORCA checkpoint and two-step compound execution passed in
`/workspace/cochem-runtime/evidence/orca-state-transfer-resource-final/validated-acceptance.json`.
The checkpoint job consumed genuine XYZ/GBW/Hessian inputs without changing their
hashes and satisfied all five geometry limits. The compound job verified native
MO projection, per-step resources and achieved SCF convergence. This native
deck-generator check does not automatically import compound stages into Chain
HDF5 or certify arbitrary downstream state-transfer providers.

The accepted five-leg R2 publication is retained at
`/workspace/cochem-runtime/evidence/r2-physical-2026-10-07/accepted-r2-publication.json`.
Its maximum internal monomer drift is `8.257453875e-7 Å` against `1e-6 Å`;
its signed counterpoise correction is `-8.39272e-7 Eh`. The report explicitly
states that the measured energy interval is not a rigorous physical bound and
retains the observed residual-gradient warning.

The current instructor/student procedure is the
[personal-project App guide](Personal_Project_App_Deployment.md) and
[student no-code workflow](Student_Research_No_Code.md), with
[Classroom50 collection](Classroom50_Assignment_Deployment.md) separate.
The [older organization-owned ORCA course guide](GitHub_Classroom_ORCA_Setup.md)
retains its explicitly different ownership/billing scope. Current candidate
checks and historical complete-profile counts are recorded above. Final publication must identify the
reviewed revision and source equivalence to these tested revisions; neither the historical
1,189/1,241 counts nor overlapping targeted selections replace that evidence.
