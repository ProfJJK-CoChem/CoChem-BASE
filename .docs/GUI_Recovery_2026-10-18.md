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

## Corrections published

| Commit | Change and scope |
| --- | --- |
| `7d5cebdb88365e70ecdc77390eda570e08ebf306` | Clear xTB spin-state rejection, readable optional configuration label, two corrected GUI-layout test expectations, and student-guide labels matching the controls. The xTB check itself and all scientific handoff assertions remain unchanged. |
| `a02998c18639871dfca011c09777eb6e034b282e` | Public TOPOS/TORQ submission and installation no longer require a private-source credential. Optional authentication, exact source pins, source/wheel/environment verification, real installation failure and licensed-engine restrictions remain. |
| `5d0c801d01070b7b3311ef2a5b342a9e84483bc7` | The negative-access test records and asserts actual HTTP requests, replacing an empty log-discarding helper rejected by the source audit. No production behavior changed. |

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
- The request-log correction passed the **five affected tests** and the
  unchanged static test-source gate.
- Fresh Chromium/Voilà acceptance on exact `7d5cebd` passed the canonical
  input/removal/undo/restart checks and **16 desktop/mobile views**. Source and
  original input hashes stayed unchanged. No browser errors were observed.
  Seventeen runtime warnings remain recorded: Jupyter shared-version warnings
  and WebGL readback warnings. No new chemistry or student account access is
  established by this visual pass.
- The clean source audit for final code `5d0c801` passed. Complete local and
  hosted profiles are being run on that same source; their terminal receipts
  must be reviewed before describing this as a fully validated release.

The earlier hosted run
[`39088443391`](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/39088443391)
on `d423c02` remains failed: 1,770 bounded tests passed and three old layout
expectations failed. The earlier `a02998c` source audit also remains failed;
pytest was not started because of the empty HTTP logging helper. Neither is
converted into a pass by a later correction. Test selections overlap; do not
add the focused counts into a claimed unique-test total.

## Work still needed

1. **Canonical module ownership.** BASE still packages downstream module
   namespaces and maintains TORQ scan/bond-analysis science in its adapter.
   Follow the [source-bound audit and module-agent handoff](Module_Ownership_Audit_2026-10-18.md).
   Coordinate the canonical TORQ API and TOPOS runtime compatibility before
   removing active dependents or changing source pins. Preserve BASE's own
   SRS-required ingestion and conformer processing.
2. **Actual student project.** Use a private independent template copy owned
   by the student's GitHub account. A public fork is a different repository
   type and does not satisfy the current licensed-access setup. The
   [student pilot](Student_Deployment_Pilot.md) records the no-terminal route,
   account identity, App consent, Codespaces permissions, actual calculation
   and result retrieval. Instructor access is separate evidence.
3. **Accessibility and scientific qualification.** Native Explain controls
   expose disclosure semantics. Existing advanced Show/Hide widgets work by
   keyboard, but explicit expanded-state ARIA relationships and broader
   assistive-technology acceptance remain. The scientific/provider/platform
   backlog in the [workstation handoff](WORKSTATION_COMPLETION_HANDOFF.md)
   remains applicable; this recovery does not certify complete SRS conformance.
