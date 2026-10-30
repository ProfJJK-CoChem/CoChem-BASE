# First-semester workspace: implementation and bounded verification

This is a progress record, not student-release approval or a claim of complete
SRS conformance. The actual student account/Codespace and current hosted ORCA/
CFOUR pilot remain unverified. New commits are local because current GitHub
authentication/publication is blocked.

The [curated evidence](evidence/beginner-workspace-20261030/README.md) links the
original test receipts, actual screenshots, browser records and failed history.
Its manifest records original paths and hashes. Raw native outputs remain in
the separately referenced external artifact rather than the source tree.

## Student-facing changes

The default workspace has four numbered steps: **Setup**, **Add your molecule**,
**Run assigned calculation**, and **Read and save results**. The header keeps
the current input, charge, spin, selected scientific goal, help and Stop
available across those pages. Advanced
scientific tools and settings open through named disclosures. Desktop browser
observations at 1024×768 and 1440×1000 showed the first upload control without
scrolling. The 320-pixel view still needs additional vertical scrolling; this
is not an all-width above-the-fold or accessibility certification.

Offline **Help search** and contextual help cover 42 topics, including isomers,
chirality, charge, spin and spectra. **Teach me more** explains why, when, where
and how. The authored inventory contains 287 control-guidance records; this is
not a count of simultaneously visible controls or evidence of student
comprehension. Search handles the spelling “chiralty”. Help distinguishes
conformers from configurational isomers, R/S from optical rotation, calculated
vibrations from experimental spectra, and optimization from minimum/lowest-
energy qualification. Reading help does not change scientific settings.

The first-lab guide and notebook introduction now point to those exact controls.
Notebook code cells and metadata were preserved. Students still need the
intended molecule, state and method from their assignment; the interface does
not infer scientific intent from an error or silently substitute an engine.

Input ingestion now disables **Use selected starting geometry** while the
actual upload/scan is pending and checks that condition in the callback. Valid
and rejected uploads preserve the earlier draft and original files. A completed
displayed-summary download is explicitly a text summary, not the native output
bundle or a complete provenance backup.

## Startup and restart correction

Actual `Start_Here.ipynb` previously showed an empty file selector/table and
disabled Refresh after same-tab service restart, although the matching Python
kernel and widget models held the retained data. A custom diagnostic notebook
had not reproduced this timing. Its earlier pass was not accepted as proof of
the canonical notebook lifecycle.

Commit `71f4c88ff0d3958043dccb1d4239f03361ede873` arms 15 fixed input-library
models before the asynchronous scan. Each model's first genuine frontend
display acknowledgement sends only its current backend-owned display fields:
HTML text, button availability, or selector option labels. It never replays
selection indices, scientific values or student drafts. There is no sleep,
forced scan or global state replacement. The declared widget range is
`ipywidgets>=8.1,<9`, with explicit feature/major-version checks; actual browser
and installed-runtime qualification here uses 8.1.9. Other supported-range
versions and platforms are not independently qualified by this record.

The actual canonical notebook's same-tab restart passed on that commit:
the owned server PID/create-time and kernel changed; the same tab automatically
showed five retained inputs and an enabled Refresh control; matching frontend
and backend model fields agreed. Actual binary WebSocket traffic was decoded.
Original assignment bytes/mode, retained input/result bytes, authority records
and prior failed evidence were preserved, and owned restart processes stopped.

This was a direct supported service restart with genuine local authority.
The GUI's managed-update restart button was correctly disabled and was not
claimed clicked. Full managed update/rollback and a real student Codespace
restart remain separate acceptance work. One old-kernel unload request failed
during intentional server downtime; console warnings and that failure remain
in the original record. This is not a zero-console/request-error claim.

The completed canonical-notebook browser run also verified uploads, malformed
input recovery, a genuine 128-frame ingestion busy state, help/keyboard use,
advanced routes, all 15 own-model acknowledgements, and preserved scientific
selections. A separate neutral-water GFN2-xTB screening optimization completed
with energy −5.070544447821 hartree. All 14 recorded native/sidecar hashes and
the actual 452-byte downloaded displayed summary were independently checked.
The earlier saved +1/doublet draft remained unchanged. This is an authentic
local calculation, not minimum, physical-accuracy, licensed-engine, hosted or
student-account qualification. This run had zero page/request failures and
17 retained console notices.

The 16-fixture browser lane passed its actual uploads, ten molecular-frame
selections, native spectroscopy parsing, supplied-Hessian isotope reanalysis,
bounded NPZ/HDF5 preview, typed periodic/PAW request and SMILES starting-guess
checks. Original hashes were recovered after reload. It performed no native
engine calculation and claimed no physical/equilibrium accuracy. Its terminal
browser summary exists, but the original outer wrapper's exit was not
observed after tool detachment. The later process-boundary/authority/source/
preservation audit is explicitly posthoc; it is not a manufactured original
wrapper-success receipt. The current owned-service boundary was empty.

## Request scheduling

Commit `0eda4f8fae381879ac638973e49ca47372efd016` adds a read-only admission job
which validates the exact request, approved canonical worker, capabilities,
resources and current private project before emitting an allowlisted route.
Engine probes and scientific calculations then use separate job-level
concurrency groups. The worker rechecks the route and existing protections
before provisioning or execution. Admission failures publish only strictly
bound, sealed failed-request diagnostics.

The three existing dispatch inputs are unchanged. Existing student workflow
files must receive this update. GitHub's one-active/one-pending limit still
makes more than two science submissions nondurable; this change does not
provide FIFO/eventual execution or prove cohort scheduler capacity. Admission
also consumes runner time. Actual hosted scheduling remains untested here.

## Exact committed-source checks

All five selected profiles ran against clean commit
`71f4c88ff0d3958043dccb1d4239f03361ede873` under the existing source quarantine
and infrastructure checks. The original checkout and copied source stayed
unchanged; source-origin checks passed and owned process boundaries were empty.

| Selected profile | Passed | Failed/skipped | Duration |
| --- | ---: | ---: | ---: |
| Infrastructure controls | 221 | 0/0 | 32.975 s |
| Startup widget comms | 4 | 0/0 | 15.954 s |
| Scientific input library | 23 | 0/0 | 237.206 s |
| Actions request/workflow contracts | 254 | 0/0 | 63.071 s |
| Affected interface controls | 155 | 0/0 | 452.729 s |

These are 657 selected engineering passes, not the entire SRS profile. Seven
control child records and three kernel comm child records are explicitly
startup-only; they do not establish finalizer observations. No skipped or
deferred check was counted as a pass.

A fresh isolated installed wheel also passed its bounded helper/help checks:
559 hashed RECORD members and all 11 UI Python members matched the producer;
the widget/packaging metadata and installed 8.1.9 runtime were verified;
42 help topics and representative aliases worked with zero network attempts.
The wheel SHA-256 is
`ee300d5fb6df20eced387a30149958c858eb1ffe1a3df2b9c32edb4d451786c9`.
This was a hash-locked widget runtime plus BASE installed without its full
scientific dependency closure; it is not automatic student-install acceptance.

Earlier failed profiles remain failed in their original records: 368 passes/
two missing-PAW-prerequisite failures on the earlier candidate, and 25 passes/
two such failures in a development run. The official pinned PAW files were
verified and supplied through the configured data path. The later 23-case
committed-source intake profile passed without changing scientific assertions
or the files' bytes. Earlier browser/observer failures also remain retained.

## Work still required

Confirm predictable cancellation for all
owned calculation/check routes, including advanced native TOPOS and local
geometry analysis. The local completed-calculation card is present, but its
automatic integration into the separate scientific comparison/report route
remains unfinished; the captured empty report-area wording also needs correction.
Continue the full scientific backlog and its unchanged
thresholds, including genuine NAO/NBO distinctions, multidimensional scans,
periodic properties and licensed/hardware-dependent validation.

Restore supported GitHub access, reconcile current remote main normally, and
publish reviewed changes. Finish the existing private App/controller settings,
approved BASE revision and licensed-engine access; verify Actions billing and
permissions. Obtain actual student account/Codespace consent and perform the
real ORCA/CFOUR student pilot, native-output retrieval, updates and preservation.
Canonical module publication and compatible managed installation still need
their own proof. No public/student readiness claim follows from repository
access, local tests or the earlier maintainer-owned Actions runs.
