# Recovery validation receipts

These files support the [recovery report](../../GUI_Recovery_2026-10-18.md).
They are exact copies of inspected outputs from the restored workspace, not
reconstructions of the temporary files lost during the earlier disconnect.
`SHA256SUMS` records each evidence file; this README is excluded from the list.

- `gui-focused-tests.xml` and `gui-independent-review.json`: 34 focused passes
  and review of the restored GUI changes. The review preserves all scientific
  conditions and handoff assertions.
- `public-module-regressions.xml`: 230 setup/Actions/license regressions. These
  focused tests ran in the working tree on the production changes committed as
  `a02998c`; they are distinct from source-quarantined complete acceptance.
- `public-module-independent-review.json`: independent review of the actual
  submission/worker gate removal, retained private/license/source checks and
  the reproduced-before/passed-after focused cases.
- `public-module-request-log-tests.xml`: five affected tests after genuine HTTP
  request logging was added, as committed in `5d0c801`.
- `browser-acceptance-summary.json` and `browser-rendered-review.json`: fresh
  real Chromium/Voilà checks on frozen `7d5cebd`, with original/source hashes,
  actual errors/warnings, bounded scope and owned-server cleanup. Screenshots
  are direct captures of that source. The public-source gate change was tested
  separately; this browser record does not claim to test it.
- `failed-bounded-d423c02.json`: original failed hosted bounded profile from
  run `39088443391`, downloaded after workspace recovery. The three old layout
  assertions remain failures in this receipt.
- `failed-audit-a02998c.json`: original refused full invocation. Its source
  audit rejected the empty test HTTP logger before pytest could start.
- `hosted-modules/`: all 16 unchanged files returned by the new hosted
  TORQ/TOPOS installation and TOPOS structural-analysis run `39092523800`,
  together with its verified metadata, readback and hash inventory. Its README
  distinguishes the exported hashes, the optional credential that was present,
  and the structural scope from electronic or student-pilot acceptance.
  `hosted-modules-independent-review.json` records the separate readback and
  comparison against canonical provider source and unchanged publication files.

Focused selections overlap and must not be summed. Absolute paths belong to
the original execution environments; cloning these receipts does not recreate
those paths, Python installations or native engines. No credentials, licensed
distributions or student research inputs are included. Earlier October 13
scientific acceptance retains its own source identity and scope.

These records do not establish a new student's App enrollment, Codespace,
personal-repository calculation/retrieval, complete accessibility conformance,
or completed canonical-module ownership migration.
