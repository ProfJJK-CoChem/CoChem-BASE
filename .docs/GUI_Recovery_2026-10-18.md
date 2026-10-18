# GUI recovery, public module access and remaining release work

This record distinguishes the published corrections, newly repeated checks and
remaining ecosystem work. The [interface research and SRS trace](GUI_Usability_Research_2026-10-18.md)
describes the underlying redesign. The [module ownership audit](Module_Ownership_Audit_2026-10-18.md)
records a separate architectural defect that these corrections do not resolve.

## Workspace outage and recovery

The Codex execution service returned `409 environment_offline` and
`Environment is not connected`. Its runtime status showed `starting` and
`offline`, with no reported cause. Repository visibility and Google sign-in were
not established causes. This was the development workspace connection, separate
from the student's GitHub repository and Codespace.

On recovery the service reported `running` and `connected`. The checkout was
restored to published commit `d423c02`; unpublished changes and the prior
temporary GUI evidence directories were absent. The corrections were restored
from their reviewed descriptions and tested again. Fresh evidence is identified
below; remembered results are not relabelled as new receipts.

A later command-service interruption returned `exec-server transport disconnected`
while the environment-status service still reported `running` and `connected`,
with no cause. Command access subsequently returned without resetting the
checkout. The existing full test process completed successfully. The local GUI
commit and publication receipts were then backed up to a GitHub recovery branch
before work continued. This second interruption is not evidence that repository
visibility or student authentication caused the problem.

## Corrections published

| Commit | Change and scope |
| --- | --- |
| `7d5cebdb88365e70ecdc77390eda570e08ebf306` | Clear xTB spin-state rejection, readable optional configuration label, two corrected GUI-layout test expectations, and student-guide labels matching the controls. The xTB check itself and all scientific handoff assertions remain unchanged. |
| `a02998c18639871dfca011c09777eb6e034b282e` | Public TOPOS/TORQ submission and installation no longer require a private-source credential. Optional authentication, exact source pins, source/wheel/environment verification, real installation failure and licensed-engine restrictions remain. |
| `5d0c801d01070b7b3311ef2a5b342a9e84483bc7` | The negative-access test records and asserts actual HTTP requests, replacing an empty log-discarding helper rejected by the source audit. No production behavior changed. |
| `81f5e043554d059f29fdda0f6c900e35d83b1cfe` | The GUI runtime test now checks the clearer spin rejection and recovery guidance. Exact xTB serialization and disabled-button checks remain, with added checks that the entered spin and geometry are preserved. No production code changed. |
| `cfdd8069e3812881bdf7594da38a8f8affa87617` | Complete recovery instructions stay visible, explicit traceback details collapse, calculation/update progress uses plain language, and R2 reference-upload guidance is beside the control. Exact protocol states remain in expandable details. Scientific validation, submission, cancellation and result gates are unchanged. |

Both canonical module repositories were observed as public. The ORCA and CFOUR
asset repositories were observed as private. Public source availability does
not provide licensed archive access or student calculation permissions.

## Validation and evidence

The [portable receipt inventory](evidence/2026-10-18-recovery/README.md) records
the actual producers, retained failures and checksum list.

- The restored GUI/layout changes passed **34 focused tests**, including four
  real xTB single-point/optimization cases. Independent AST review confirmed
  unchanged scientific logic and all 31 handoff-test assertions.
- Public-source and existing Actions/setup/license regressions passed **230
  tests**. The new cases first reproduced the old credential-precondition
  failure, then exercised the actual workflow installation program with real
  Git/build operations and a real HTTP 403 refusal. Both exact canonical
  module pins were fetched without supplying a source credential. The platform
  proxy prevents treating that fetch alone as proof of anonymous internet
  transport; it is also not a complete canonical-module installation.
- New hosted [run `39092523800`](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/39092523800)
  on `9ce098e` completed the real pinned TORQ/TOPOS installation and TOPOS
  structural analysis. Independent readback verified all 15 manifest-listed
  payloads and the manifest, unchanged water input, the exact worker catalog,
  both installed revisions, TORQ's sidecar receipt and TOPOS's executed provider
  against its canonical source. The three-atom geometry was valid. An optional
  source credential was available; this is not credential-free hosted evidence.
  Both licensed-engine steps were skipped. No electronic-energy, all-operation
  or student-account acceptance is implied. The
  [complete returned evidence](evidence/2026-10-18-recovery/hosted-modules/README.md)
  preserves the exported hashes and explicitly identifies unretained runtime
  hashes.
- The request-log correction passed the **five affected tests** and the
  unchanged static test-source gate.
- Fresh Chromium/Voilà acceptance on exact `7d5cebd` passed the canonical
  input/removal/undo/restart checks and **16 desktop/mobile views**. Source and
  original input hashes stayed unchanged. No browser errors were observed.
  Seventeen runtime warnings remain recorded: Jupyter shared-version warnings
  and WebGL readback warnings. No new chemistry or student account access is
  established by this visual pass.
- The corrected runtime test file passed **13 tests**, including actual xTB
  GUI optimization and owned-worker cancellation. Independent review confirmed
  that every other test function was unchanged.
- The follow-up guidance changes passed **94 focused tests** and **58 existing
  UI tests**, with no failures or skips. Two final lifecycle-label refinements
  then passed **11 label checks**. Their file hashes and distinct scopes are
  retained in the portable receipts; overlapping selections are not summed.
  Independent AST review confirmed that only four existing GUI rendering
  methods changed, alongside the labels and adjacent R2 explanation.
- Fresh Chromium/Voilà checks on frozen `cfdd806` passed **10 rendered states**
  at desktop and mobile widths. Actual water upload, complete visible spin
  guidance, blocked invalid calculation, valid export, keyboard-operated R2
  help and input-preserving navigation passed. All 2,271 source files, 70
  application import origins, the original/retained input and registry were
  verified; no owned live processes remained. There were zero browser, console,
  HTTP or request errors, with 13 JupyterLab dependency-version warnings and
  four headless WebGL warnings. The progress display replayed a retained actual
  hosted observation for rendering only. Automatic setup and remote checks
  were disabled; this does not establish student startup or new chemistry.
  The [browser receipts and screenshots](evidence/2026-10-18-recovery/gui-followup-browser/acceptance-summary.json)
  preserve that scope and the separate incomplete harness attempts.
- The clean source audit for `5d0c801` passed, but its local and hosted profiles
  failed as described below. The `81f5e04` retry was refused before pytest
  because raw result files were placed in source control. Follow-up validation
  used the corrected evidence placement and restored real-runtime discovery
  bindings; its terminal outcome is recorded below.

The corrected frozen revision `31ed7a79dbf2fafa412db33877c228e7a67569cb`
subsequently passed its complete local profile: **3,192 passed, zero failures,
zero unexpected skips and six reviewed external deferrals**, from 3,198 collected
tests. Original and quarantined source stayed unchanged, source origins were
verified, and the owned process boundary was empty on completion. The six
remaining checks require actual ABCluster, patched CREST, Psi4, AIMNet CPU and
two physical Slurm observations; they are not counted as passed. The restored
stock-CREST, CREST/ORCA union and MACE checks executed in this profile.
This is acceptance of the profile's runnable scope, not complete SRS or physical
accuracy certification. Later GUI presentation changes retain their separate
focused, browser and hosted validation identities.

Hosted [run `39159363374`](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/39159363374)
on the same `31ed7a7` revision also completed successfully: **1,777 bounded tests
passed**, with no failures or skips; **221 CI-control tests passed on each of
Linux, macOS and Windows**; all three clean-wheel checks passed. The real
free-engine calculations passed their numerical checks. Dashboard HTTP/widget
readiness and repeated startup passed; that hosted lifecycle check is not a
headless-browser interaction test.
The optional native diagnostic-tracing job was deliberately not selected and
remains skipped. These bounded checks do not replace the full local profile or
the real student pilot.

The earlier hosted run
[`39088443391`](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/39088443391)
on `d423c02` remains failed: 1,770 bounded tests passed and three old layout
expectations failed. The earlier `a02998c` source audit also remains failed;
pytest was not started because of the empty HTTP logging helper. Neither is
converted into a pass by a later correction. Test selections overlap; do not
add the focused counts into a claimed unique-test total.

Hosted [run `39091746906`](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/39091746906)
on `5d0c801` passed 1,776 of 1,777 bounded tests. Its sole failure expected the
old "Open-shell" warning text; the actual disabled-calculation assertion passed.
The test correction above preserves that refusal and checks the intended new
guidance. No source, import-origin, coverage or process-cleanup violation was
reported. All three OS control profiles passed 221 tests each, and all three
clean-wheel checks passed; those successes do not convert the overall failed
hosted run into a pass. Its final browser step did not run after the failure.

An initial local invocation for `81f5e04` used an abbreviated revision and was
refused before pytest. The retry supplied the full immutable commit ID. This
command-input error is distinct from a failed application test; its refusal is
retained rather than relabelled as executed validation.

The complete local `5d0c801` profile collected 3,198 tests: **3,188 passed,
one failed, seven were reviewed external deferrals and two were unexpected
skips**. The failure was the same stale xTB wording assertion. The restored
workspace had lost discovery bindings for its real stock CREST and MACE
installations; these two skips are not accepted deferrals. Missing CREST on
`PATH` also deferred the physical CREST/ORCA union check. The installed programs
were found and their unchanged focused checks passed: one MACE boundary check
and two stock-CREST/actual CREST–ORCA union checks, with zero skips. This restored
runtime discovery without changing deployment profiles, tests or skip policy.
Original/quarantined source, import origins and process cleanup passed. Real
ORCA R2 execution passed its execution checks, with its existing physical
qualification warnings still applicable.

The full-SHA `81f5e04` source audit rejected two `.xyz` and two `.log` evidence
files under `.docs/evidence/`. The original content review had not caught this
repository-placement rule. The four files were removed from the source tree;
the complete result bundle is retained outside source control and published in
the [evidence-only prerelease](https://github.com/ProfJJK-CoChem/CoChem-BASE/releases/tag/evidence-2026-10-18).
Fresh downloads matched all original members and the reviewed ZIP checksum.
The publication record retains the failed transport attempts separately from
the final verified API publication. The latest software release remains `v1.0.1`.
Permitted JSON reports and selection hashes remain in the
repository. The air-gap policy is unchanged; no test subprocess ran in that
refused attempt.

The recovered-workspace acceptance supplements restore
`COCHEM_TEST_MACE_SILO`, `COCHEM_TEST_STOCK_CREST_EXECUTABLE` and the actual
CREST executable directory on `PATH`. They do not provision the separately
required patched CREST distribution or satisfy other external prerequisites.

## Work still needed

1. **Canonical module ownership.** BASE still packages downstream module
   namespaces and maintains TORQ scan/bond-analysis science in its adapter.
   Follow the [source-bound audit and module-agent handoff](Module_Ownership_Audit_2026-10-18.md).
   Coordinate the canonical TORQ API and TOPOS runtime compatibility before
   removing active dependents or changing source pins. Preserve BASE's own
   SRS-required ingestion and conformer processing.
2. **Actual student project.** The chosen licensed-access route uses a private
   independent template copy owned by the student's GitHub account. A correctly
   created independent public copy can run the owner-started free-engine checks
   and become private later; another copy is not needed. Public source access
   does not grant a maintainer workflow-dispatch or Codespace permissions. The
   [student pilot](Student_Deployment_Pilot.md) records the no-terminal route,
   account identity, App consent, Codespaces permissions, actual calculation
   and result retrieval. Instructor access is separate evidence.
3. **Accessibility and scientific qualification.** Native Explain controls
   expose disclosure semantics. Existing advanced Show/Hide widgets work by
   keyboard, but expanded-state accessibility semantics and broader
   screen-reader acceptance remain. The scientific/provider/platform
   backlog in the [workstation handoff](WORKSTATION_COMPLETION_HANDOFF.md)
   remains applicable; this recovery does not certify complete SRS conformance.
