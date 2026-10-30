# Managed dashboard restart routing and preflight

This work was started on 19 October and continued on 30 October 2026. The setup
service passes the selected runtime environment and recorded port to the existing
owned launcher. Missing server receipts retain port 8866; recorded ports must be
integers, excluding booleans, in 1–65535. Invalid receipts fail before a child is
created. Runtime integrity and exact command, PID creation-time and process-session
ownership checks remain mandatory.

A reviewed release now uses the validated original assignment interpreter as its
verifier, including a shared environment outside the artifact directory. Older
installations without that receipt retain the existing `ui-env` default. Candidate
interpreters, including directory aliases into `BaseRuntime`, cannot verify
themselves. Restart also validates the selected Stage 0 authority **before**
stopping the current interface.

## Actual controls

The final complete `test_student_setup.py` and `test_hosted_dashboard_runtime.py`
selection passed **56 tests**, with zero failures, errors or skips. The
[JUnit receipt](final-preflight-controls.xml) has SHA-256
`03711eef3796571a15178a5d3ddb22390e43bea6f900c43ddafc3fa965d95093`.
[Source and report hashes](validation-summary-2026-10-30.json) bind these results
to the four reviewed files. The retained 49-case and 55-case runs overlap this
result and must not be added to it.

These controls use real Python children, isolated Git/package builds, installed
candidate integrity failures and real process/listener boundaries. The initial
four child-routing cases and ten invalid-port cases failed before the port and
environment correction. Two installed-candidate cases reproduced the missing
shared verifier. A separate negative case reproduced an aliased candidate verifier.
The new preflight regression failed because the old launcher changed the server
receipt before rejecting an invalid target. Earlier failed reports remain in the
maintainer evidence directory; this does not substitute a scientific backend.

## Actual local browser and process evidence

The [earlier positive browser receipt](earlier-browser-restart-receipt.json) records
Chromium upload, genuine setup-service/owned-launcher restart on custom port 8874,
and recovery of the retained source hash in the browser. Five retained input and
result-fixture files were byte-identical; the server PID changed while its port
and shared interpreter remained correct. There were zero browser page errors.
The [before](earlier-before-restart.png) and [after](earlier-after-restart.png)
screenshots are authentic. This run preceded the final preflight ordering change.
The retained result is an explicit text fixture, not a calculated scientific result.

A deliberately invalid Stage 0 registry in the owned local test profile reproduced
the [old failure](preflight-red.json): restart exited with failure after stopping
the actual Voilà service and removing its receipt. The [corrected behavior](preflight-green.json)
retained the same live PID, creation time and exact receipt. The existing browser
continued displaying its verified original input while the target authority was
invalid, as captured in the [screenshot](failed-preflight-preserved-page.png).
Original registry bytes and its read-only mode were restored after each check.
No student project or unrelated server was used for this negative test.

The final-source positive rerun did start its new server on the correct port and
interpreter, but its same-browser reload [failed a bounded 120-second retained-table
check](browser-final.log). Read-only inspection of that exact kernel showed the
worker had finished, the Refresh button was enabled on the server, and both
retained inputs and their correct table HTML existed. The browser still showed
stale disabled/empty widgets. [Kernel state](kernel-widget-state.json) and
[thread stacks](kernel-recovery-stacks.json) retain this diagnosis. This failure
is not counted as a pass and does not demonstrate data loss. GUI synchronization
requires separate investigation.

A subsequent [fresh browser session](fresh-browser-recovery.json) recovered both
retained inputs and their correct hashes, with an [authentic screenshot](fresh-browser-recovery.png).
The [final service observation](final-service-observation.json) records the new
server identity, requested runtime/port and the earlier five retained files still
unchanged. This fresh-session success does not erase the failed same-session reload.

## Scope and remaining limits

All browser/process evidence here is a maintainer's local Linux runtime, prepared
with full eleven-phase Stage 0 and the explicit 1 GB bounded-workload storage floor.
The GUI Restart button is enabled only after a selected update; these local
positive runs invoked its genuine setup service directly and inspected browser
recovery. They do not establish the complete GUI update/restart-button flow,
student identity, actual Codespaces, Windows, macOS, HPC, hosted chemistry or
scientific accuracy.

Independent review covered the port/shared-verifier changes. The root reviewer
then reviewed the final four-file diff, found no new blocking defect, and
independently parsed the final 56-pass, zero-skip JUnit receipt. The verifier still
imports implementation code from the current launcher source/import environment.
A failure after successful preflight and shutdown is not given automatic rollback
by this patch. Student readiness and full SRS conformance remain unaccepted.

The owned port-8874 server was stopped with the existing authenticated launcher.
[Cleanup](cleanup.json) found no live owned service or kernels and retained all
checked input/result-fixture hashes. The exited server remained a dead zombie
owned by its external parent; it was not reported as a live service.
