# Agent takeover: finish and validate the student deployment

Prepared 18 October 2026. This is the current entry point for a replacement
agent/environment. It supplements the [completion backlog](WORKSTATION_COMPLETION_HANDOFF.md),
not a declaration that BASE or the entire ecosystem is finished.

## Assignment and authority

The instructor has authorized the agent to implement, test, troubleshoot,
commit and push the necessary reviewed changes. Run the tests yourself. Do not
give the instructor or students a list of commands or individual tests to run.
Ask only for account sign-in, consent, unavailable administrator settings or a
scientific decision that cannot be inferred. Explain the precise blocker and
continue independent work. Never ask for credentials in chat.

Use the existing checkouts. Inspect dirty files and fetch remote state before
editing; other agents are working on TOPOS and TORQ. Preserve their changes and
student data. Do not force-push, reset independent project histories, or copy
the old workspace wholesale. Establish which credentials and tools the new
environment actually provides without printing their values.

Read [Chunk 17](SRS_Chunk_17_CoChem_BASE_Architecture.md),
[proposal additions](SRS_Chunk_Proposal_CoChem_BASE_Architectural_Review.md),
the [Task 1 specification](task1_subsystems_architectural_specification.md),
[Method Matrix](../Method_Matrix.md), and the
[108-obligation trace](SRS_Student_1_1_Conformance_Trace.md). Chunk 17 is primary;
proposal additions are also required. Their repeated requirement numbers have
different meanings. Read the relevant source specification again before each
implementation change, and retain the full trace rather than treating this
brief as a reduced specification.

## Required student experience

- BASE is the single repository students obtain. It installs the verified
  canonical TOPOS/TORQ providers and presents their operations through BASE.
- Students create private personal projects named `CoChem-[target molecule name]`.
  Codespaces hosts the VS Code/Voilà interface; Actions runs the chemistry.
  Personal repository ownership determines Actions billing. Codespaces has a
  separate payer; the organization's access-controller job uses organization
  usage. Education membership does not establish unlimited compute.
- Students supply their own scientific inputs. Monomer/complex XYZ is one
  supported route, not the entire SRS ingestion requirement.
- No student terminal commands, Python, workflow editing, manual module cloning,
  download-token entry or Codex installation is part of ordinary course use.
- ORCA 6.1.1 and CFOUR 2.1 remain optional and strongly recommended. Their
  absence/failure disables dependent selections only. Public TOPOS/TORQ source
  does not require a private-source token.
- Explain unfamiliar scientific terms on demand, keep longer help collapsible,
  and provide understandable recovery/removal controls without losing originals.
  Preserve Linux, WSL, macOS and HPC routes while fixing Actions.

## Published state at this handoff

The canonical program source before this documentation update is
`5fdf3b71aa2fb781ae9dac53f764525979d23335`. At inspection, the private controller
and independent private student test project had exactly the same complete
file tree, with their own normal commit histories. No unpublished application
changes were present. Fetch current main rather than resetting to that revision.

The App setup walkthrough now documents the actual registration/key/variable
steps. The enrollment success text no longer treats public TOPOS/TORQ as
requiring a private reader. That earlier code change passed 72 focused tests;
its corrected source hash and clean source audits were published. This
documentation handoff is not another full scientific acceptance run.

The previous maintainer can now push to the student test project and dispatch
its Actions workflows. A real project setup-check job completed, but reported
an empty approved BASE revision and false ORCA/CFOUR availability. Its successful
workflow conclusion means the diagnostic ran, not that the project was ready.
The registered lab App and private controller exist. No controller workflow
runs had occurred at the latest inspection. App installation, successful
student enrollment and genuine student Codespace/chemistry acceptance remain
unverified. Earlier push/dispatch refusals are historical, not the current
repository-access diagnosis.

Private account/project identifiers, configuration values, the original setup
report, exact run metadata and original-byte hashes are retained in
`.docs/PRIVATE_DEPLOYMENT_HANDOFF.md` and its evidence directory **inside the
private controller repository**. Obtain that repository through authorized
access; do not copy its private brief into public BASE.

## First work in the new environment

1. Read this brief, the private deployment brief, the
   [current App guide](Personal_Project_App_Deployment.md), and the
   [student pilot](Student_Deployment_Pilot.md). Check current repository heads,
   identities, visibility, permissions and the existing Actions runs.
2. Verify both kinds of access independently: repository/Actions authorization
   and actual student-account Codespace access. A cloud environment with access
   to both owners' repositories does not become the student or attach to their
   Codespace. Use the platform's supported connection if available, or run the
   agent in the student's actual Codespace. Do not copy session cookies,
   impersonate a student, bypass access checks or label local tests as Codespaces.
3. Complete the existing lab App/controller setup; do not register another App
   or create replacement tokens merely because an API returns 403. Confirm
   team membership, controller Read access, selected App installations, all
   required variables, and controller access to the existing private secrets.
   Use the current guide's **Contents: Read and write** App permission.
4. Enroll the selected private personal project through the supported route.
   A student enrollment issue must be authored by the actual project owner;
   instructor maintenance is a separate route. Account-only consent can
   require the owner. Do not post messages/issues as someone else.
5. After provisioning, use a newly created student Codespace and verify its
   actual project permissions. A rebuild is not a replacement for a new
   permission grant. Preserve existing uploads/results before workspace changes.
6. Run the actual Voilà browser tests and bounded genuine ORCA/CFOUR workflows,
   retaining native outputs, screenshots, identity, source revisions, run URLs
   and retrieved artifact hashes. Then continue the implementation backlog
   below; initial enrollment is not the whole assignment.

The existing maintainer harness is
[`tests/ui/student_entrypoint_browser_acceptance.py`](../tests/ui/student_entrypoint_browser_acceptance.py).
Inspect its current arguments and evidence requirements before using it. It can
drive real uploads and hosted jobs, retrieve results and test reloads. Claiming
Codespaces origin requires actual workspace/service evidence, not just a
command-line label. Maintain cancellation, resource limits and request-bound
retrieval. Keep test artifacts outside the application checkout.

## Work that must not disappear during takeover

Use the detailed [completion backlog](WORKSTATION_COMPLETION_HANDOFF.md) and
[ownership audit](Module_Ownership_Audit_2026-10-18.md), then recheck actual code:

- Access withdrawal, rotation cleanup, team/App removal, current authorization,
  partial-failure handling and re-enrollment remain a lifecycle work package.
  Initial credential delivery alone does not implement revocation.
- Coordinate updates across the GUI runtime, committed project workflows,
  approved calculation worker, module catalog and saved jobs. Updating BASE
  main or one approval variable does not update every existing project.
- Resolve duplicated module ownership. BASE currently installs canonical
  providers but also distributes overlapping namespaces and owns TORQ scan
  and Löwdin-Wiberg algorithms in its adapter. Qualify canonical provider
  replacements before removing superseded code. Keep BASE's SRS-required
  geometry, ingestion and conformer duties. Do not collapse isolated runtimes,
  bypass integrity checks, or blindly advance dependency pins.
- Coordinate TOPOS minima/frequency/RRHO populations and TORQ scans,
  multidimensional exploration, NBO/NAO and diagrams with their owning agents.
  A Löwdin-Wiberg result is not NBO/NAO analysis. BASE must integrate genuine
  provider capabilities and accurately disable unavailable operations.
- Carry forward Product B gap/cell/spin/SOC, downstream CFOUR/VPT2 handoffs,
  T9 operation-specific continuation, R2 physical validation/warnings,
  geometry/isotope reference thresholds and PES domain/accuracy validation.
  BASE is not required to duplicate downstream scientific solvers.
- Keep CURE, EHS, EVAL, LABS, PLAY, SEED and SHIFT deferred as the user directed.
  Keep genuinely unavailable hardware/native-engine acceptance explicit.
- Finish GUI upload/submission/status/cancellation/retrieval, scientific tables
  and diagrams, optional-engine failures, updates/restarts/rollback, original
  data preservation, and the selected Classroom50 collection route.

Do not manufacture chemistry, loosen thresholds, substitute a different
observable, invent auditor approvals, or treat a disabled test as a pass.
The historical 3,192 complete-profile passes and six external deferrals belong
to `31ed7a79dbf2fafa412db33877c228e7a67569cb`. Later tests have their own producer
revisions. The [recovery report](GUI_Recovery_2026-10-18.md) distinguishes them.
Old `/workspace` paths and hashes do not transfer files; use committed sanitized
receipts, authorized private evidence, or rerun the necessary acceptance.

## Publication and completion

Run meaningful checks for each change and the required current release profile
before declaring release readiness. Use the repository's source/integrity gates
and preserve failed evidence. A source audit alone is not scientific acceptance.
Request independent review of code and evidence.

Commit and push reviewed changes to their owning repositories, including BASE
main as authorized. Reconcile concurrent changes normally, preserving student
files and independent histories. Changes to TOPOS/TORQ science belong upstream;
update BASE pins only after compatibility and real operations are accepted.
Propagate compatible workflow/source changes to the existing private test and
controller repositories without copying their private settings into public code.
Never commit credentials, licensed archives/installations or scratch directories.

Finish with exact published SHAs, workflow links, test outcomes, evidence
locations and remaining blockers. Do not claim a flawless release or complete
SRS conformance while required behavior or acceptance remains unresolved.
