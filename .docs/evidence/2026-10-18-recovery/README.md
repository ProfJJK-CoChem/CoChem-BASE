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
- `failed-bounded-5d0c801.json`: original hosted profile with 1,776 passes and
  one stale warning-text assertion failure. Source/import/process checks passed;
  the overall test result remains failed.
- `spin-guidance-test-correction.xml` and `.json`: 13 whole-file focused passes
  for the correction committed as `81f5e04`, including real native xTB GUI work.
  These working-tree receipts do not replace complete release acceptance.
- `gui-followup-source-and-test-snapshot.json` and `gui-followup-independent-review.json`:
  the five-file presentation correction committed as `cfdd806`, its exact file
  hashes and independent confirmation that scientific/state-transition methods
  and existing tests were preserved. The accompanying `gui-followup-focused.xml`
  and `gui-followup-existing-ui.xml` record 94 and 58 passes with no skips; these
  preceded two final lifecycle-label refinements. `gui-followup-final-labels.xml`
  records 11 passing checks on those final labels. The selections overlap and
  are distinct from frozen-source full validation and rendered-browser evidence.
- `gui-followup-browser/`: actual Chromium/Voilà acceptance on frozen `cfdd806`,
  including 10 rendered states at 1440/320 pixels, verified source/import/input
  integrity, cleanup, six direct screenshots and the original selection hashes.
  The reported functional checks passed with zero errors and 17 retained
  warnings. Actual prior hosted status was replayed for display only; setup and
  remote checks were deliberately disabled. Native named Show/Hide buttons
  worked with Enter/Space but lacked expanded-state ARIA attributes; full
  accessibility acceptance remains open. Incomplete external-harness attempts
  are preserved separately, not relabelled as passes.
- `failed-full-5d0c801.json` and `independent-review-5d0c801.json`: the complete
  local failed profile and independent inspection, including two unexpected
  runtime-discovery skips. Seven other skips were reviewed deferrals; these
  categories must not be combined into an accepted total.
- `full-local-31ed7a7.json` and `full-local-31ed7a7-summary.json`: the unchanged
  terminal receipts for the corrected frozen revision. Of 3,198 collected
  tests, 3,192 passed and six were reviewed external deferrals; no failure,
  unexpected skip, source-change, import-origin or cleanup error was recorded.
  This producer precedes the follow-up GUI presentation changes and cannot be
  relabelled as a full profile on those later revisions.
- `report-independent-review-pre-hosted.json`: independent comparison of the
  local full-profile receipts, follow-up GUI source/tests, six screenshots and
  the then-current 68-file evidence inventory. Its report hashes identify the
  reviewed draft before the final hosted additions; it does not certify later
  report edits or hosted outcomes.
- `hosted-31ed7a7/`: unchanged selected JSON receipts and independent review of
  completed successful run `39159363374` on exact `31ed7a7`: 1,777 bounded
  passes, 221 CI controls on each of three operating systems, clean-wheel
  checks and genuine xTB/PySCF numerical verification. The hosted dashboard
  step checked HTTP/widget readiness and repeated startup, not browser
  interaction. Optional diagnostic tracing was deliberately skipped. The
  independent review separately covers the exact-revision local full profile;
  none of these results is relabelled as a later GUI revision's full profile.
- `failed-abbreviated-revision-81f5e04.json`: the command-input refusal before
  pytest. `failed-source-audit-81f5e04.json` and its summary preserve the
  subsequent full-SHA refusal for four raw evidence files in source control.
- `mace-runtime-recovery.json` and `.xml`: the unchanged actual MACE boundary
  check passed after restoring discovery of its retained installed silo.
- `crest-runtime-recovery.json` and `.xml`: the unchanged stock-CREST identity
  and real CREST/ORCA union checks both passed after restoring their runtime
  variable and executable search path. These focused checks have zero skips;
  they do not replace the full profile or provide the separate patched CREST.
- `hosted-modules/`: 12 unchanged JSON reports selected from the 16 files returned
  by hosted TORQ/TOPOS installation and TOPOS structural-analysis run
  `39092523800`, together with verified metadata, readback and hash inventory.
  Its README links the separately published and verified complete bundle,
  including four raw files that must remain outside source control, and
  distinguishes the exported hashes, the optional credential that was present,
  and the structural scope from electronic or student-pilot acceptance.
  `hosted-modules-independent-review.json` records the separate readback and
  comparison against canonical provider source and the original complete package.
  That content review did not catch the source-placement violation subsequently
  rejected by the air-gap gate; the complete bundle is now outside source control
  and is published in the evidence-only prerelease. `hosted-modules/publication-readback.json`
  records fresh downloaded-byte verification; the original local upload refusal
  and failed hosted staging-list check remain separate from the later API publication.

Focused selections overlap and must not be summed. Absolute paths belong to
the original execution environments; cloning these receipts does not recreate
those paths, Python installations or native engines. No credentials, licensed
distributions or student research inputs are included. Earlier October 13
scientific acceptance retains its own source identity and scope.

These records do not establish a new student's App enrollment, Codespace,
personal-repository calculation/retrieval, complete accessibility conformance,
or completed canonical-module ownership migration.
