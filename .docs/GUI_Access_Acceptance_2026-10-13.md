# CoChem GUI and GitHub access acceptance — 2026-10-13

This record covers the interface and access repairs prompted by the instructor's
failed Codespaces experience. See the [quick guide](GET_STARTED.md) for user
instructions and the [workstation handoff](WORKSTATION_COMPLETION_HANDOFF.md)
for remaining scientific, platform and student-deployment work. This is not a
complete SRS or stable-release certificate.

The principal tested source is
[`9f9beadfb86a4eacb582bf3e100e31a3cdcb6d2e`](https://github.com/ProfJJK-CoChem/CoChem-BASE/commit/9f9beadfb86a4eacb582bf3e100e31a3cdcb6d2e).
The subsequent message/guide-test correction is
[`4cc545aa18edfda980e1b25e7011be9c5d17b6e4`](https://github.com/ProfJJK-CoChem/CoChem-BASE/commit/4cc545aa18edfda980e1b25e7011be9c5d17b6e4).
Evidence below identifies its producer; earlier results are not silently
attributed to the later revision.
The finalizer correction is
[`ade50d7549222a1b3180cb71e6661222b6aa7817`](https://github.com/ProfJJK-CoChem/CoChem-BASE/commit/ade50d7549222a1b3180cb71e6661222b6aa7817).
It includes nested native manifests in the outer file inventory; strict result
verification and licensed-file filtering are unchanged.
The final interface/reader producer is
[`60760ae70d53cd4828f6218118e2efc2dfbf8295`](https://github.com/ProfJJK-CoChem/CoChem-BASE/commit/60760ae70d53cd4828f6218118e2efc2dfbf8295).
It keeps sealed results unchanged during Hessian inspection, retains the default
live-producer locking, rechecks inspected source hashes and adds readable report
headers. Exported JSON/CSV schemas and numerical values are unchanged.

## What changed

- The dashboard leads with setup, files and calculations. Long help is collapsed;
  TOPOS/TORQ show controls relevant to the selected operation. Complete scientific
  ingestion remains available.
- Existing instructor projects use their configured access. Personal-project
  invitations accept complete URLs; invitation clearing, input removal/undo/
  restoration and comparison reset correct mistakes while retaining originals.
- A short **CoChem project setup check** Actions job supplies approved software
  settings without requiring the Codespace login to read the Variables API.
  Configuration and download checks remain distinct from successful chemistry.
- The App configures the selected project's Codespaces permissions. The App's
  added Contents write permission needs installation-owner approval; students
  create a new Codespace and authorize the displayed project permissions.
  Older project workflow files require an instructor update.
- Saved results can be opened repeatedly without adding temporary files to
  their verified bundles. Report headings show readable names and units;
  numerical energies remain on one line in the narrower view.

## Observed results

| Check | Actual result and boundary |
| --- | --- |
| Local Voilà/Chromium visual and keyboard review | 23 captured states at 1,440 and 768 pixels; seven keyboard disclosure interactions; zero overflowing controls, truncated buttons, console errors or page errors. Thirteen console warnings were retained. Actual XYZ upload, removal and undo kept the original bytes. Invitation save/clear used example link shapes without GitHub submission. The frozen visual files match the subsequent `9f9bead` UI files. |
| Canonical local browser at `9f9bead` | Three genuine uploads accepted, invalid input rejected, monomer roles and internal distances retained in a starting complex, custom labels preserved, and files/states/fragments recovered after a fresh kernel without reupload. All 316 observed source files unchanged; old kernel retired; no page/request failures. TOPOS/TORQ were absent in this UI-only run. No hosted calculation or student Codespace was exercised. |
| [Hosted xTB calculation 38401217925](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/38401217925) at `9f9bead` | Genuine GFN2-xTB 6.7.1 water optimization and verified retrieval: energy −5.070544447821 Eh, five optimization iterations and eight native gradient evaluations. Two cores, 512 MB/core; maximum gradient component 1.5813149583169e−8 Eh/bohr. All 250 result files verified, including 249 manifest members plus the manifest; original XYZ preserved. This was the instructor's repository via the production Actions client, not a student-identity/browser submission or experimental-accuracy proof. |
| [First hosted CFOUR calculation 38402944125](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/38402944125) at `9f9bead` | Workflow completed successfully and its report records a real HF/STO-3G single point, −74.96306310764554 Eh. **Client retrieval was refused:** `native/publication-manifest.json` was an unlisted additional file. The client imported no result. This remains a failed return path; the separate corrected run below establishes the repair. |
| [Corrected hosted CFOUR calculation 38405425754](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/38405425754) at `ade50d7` | Genuine CFOUR 2.1 HF/STO-3G water single point and strict production-client retrieval passed. Energy −74.96306310764554 Eh agrees with native SCF output; HDF5 energy, coordinates and gradient agree with native records. All 78 files verified, including 77 manifest members and the outer manifest. Original XYZ and single-point pairwise distances retained; nested native manifest hash bound. No licensed runtime/basis distributed. Two cores, 512 MB/core and a 300-second native timeout. This is instructor-repository integration, not a student-browser pilot or experimental-accuracy acceptance. |
| [First engine access check 38402717092](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/38402717092) at `9f9bead` | CFOUR archive access was verified; ORCA archive access failed with HTTP 401. This check performed no installation or chemistry. ORCA-dependent choices remained unavailable while independent free methods and ingestion stayed usable. The later corrected-access and execution records are separate evidence. |
| [Updated engine access check 38405896179](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/38405896179) at `ade50d7` | After the instructor corrected the organization settings, both archive-access checks passed. ORCA's approved 471,531,860-byte asset digest matched. Setup check 38405861695 also received all three mapped credentials; it exposed presence only. Actual ORCA execution and private provider installation are separate checks. |
| [Hosted ORCA calculation 38406460669](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/38406460669) at `ade50d7` | Genuine ORCA 6.1.1 HF/STO-3G water single point and strict production-client retrieval passed. Native SCF energy −74.963063130293 Eh; normal termination and convergence recorded. Native output confirms two MPI processes and 512 MB/process. All 62 files verified, including 61 manifest members and the outer manifest; original XYZ, HDF5 values and nested manifest retained and checked. The same-geometry CFOUR energy differs by 2.2647455466540123e−8 Eh, below the declared 1e−7 Eh integration-consistency tolerance. This does not establish experimental accuracy. |
| [Hosted module installation 38406682907](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/38406682907) at `ade50d7` | BASE installed TORQ `4ce8eecba56e91e27c6abb32473b2ee4d44767c4` and TOPOS `b157b7e210aee5bdfa09c22270d77d794f52cdde` through its normal provider route. The exact source catalog and TORQ sidecar were checked; TOPOS imported inside its isolated environment and completed structural geometry analysis. All 16 returned files verified; original three-atom XYZ preserved. Seven deferred modules stayed uninstalled. This proves private-source installation and structural handoff, not electronic accuracy or every TOPOS/TORQ operation. |
| [Hosted CI 38400452490](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/38400452490) at `9f9bead` | Source gate, native CI controls and installed wheels passed on Linux, macOS and Windows. The bounded regression stage recorded **1,695 passes and one failed obsolete guide assertion**; the later rendered-dashboard step did not run. The workflow failed overall. `4cc545a` updates the assertion to check actual current guide links and the absence of credential-entry controls. |
| Full local profile at `9f9bead` | **3,081 passes, 15 failures, six setup errors and 20 skips** from 3,122 collected tests; the release gate failed. Native tests reported missing launch-time bindings to the existing registry/engines, and one assertion expected the obsolete guide. Source audit and all 772 source-origin records passed; source unchanged and owned processes stopped. Skips were not counted as passes. The retained failure is not relabeled as success. |
| [Intermediate hosted CI 38404026796](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/38404026796) at `4cc545a` | Source gate, CI controls and installed wheels passed on all three platforms. The workflow was cancelled by the later finalizer-fix push while the bounded lane was running. This is not a completed acceptance run. |
| [Hosted CI 38405246055](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/38405246055) at `ade50d7` | Workflow passed: source integrity, CI controls and fresh installed wheels on Linux/macOS/Windows, genuine free-engine calculations, **1,697 bounded regression passes**, and the rendered/reused dashboard check. The optional diagnosis-only lane was skipped by its documented workflow condition. |
| Corrected complete local profile at `ade50d7` | **3,117 passes, zero failures/errors/deselection, six exact reviewed external deferrals**, from 3,123 collected tests. Source audit/binding, unchanged source and process cleanup passed. The genuine registry remained unchanged. Real R2 five-leg execution passed while retaining the measured residual-gradient and counterpoise-ordering warnings; those warnings do not establish physical accuracy or a conservative counterpoise bound. This complete profile does not cover the subsequently discovered GUI repeat-open defect below. |
| First local repeat-open browser at `ade50d7` | The first genuine CFOUR result displayed successfully. **The second open failed** because read-time Hessian inspection created `native/complexes.h5.lock` inside the sealed result copy. All 78 scientific files and the original downloaded bundle stayed unchanged. This failed producer remains recorded separately from the corrected replay. |
| Final local retained-result browser, source bytes matching `60760ae` | Two fresh browser sessions strictly reopened the genuine hosted CFOUR result. All 78 original/copied scientific files, the completed submission and all 2,202 frozen snapshot files stayed unchanged. Readable headings and single-line energy were verified at 1,440/768 pixels without horizontal overflow. JSON/CSV retain −74.96306310764554 Eh and are byte-identical to exports before the presentation adjustment; the visible table shows −74.96306311 Eh. Zero page/console errors or GitHub requests. All 512 tested production/UI/notebook source hashes match committed `60760ae`; the snapshot's recorded base ancestor is `ade50d7`. The owned server stopped. This is local display/reopening of actual hosted results, not a student Codespace pilot. |
| Final reader/report focused checks | Independent reader/native-qualification/tamper checks: **43 passed**. Final report/GUI presentation selection: **44 passed**, with the existing telemetry-library warning retained. Default live locking, HDF5 SWMR, native qualification and strict manifest verification remain intact. |
| [Final hosted CI 38413426895](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/38413426895) at `60760ae` | **Passed.** Source integrity, CI controls and fresh installed wheels passed on Linux/macOS/Windows. The free-engine lane passed genuine bounded physics, all-eleven CPU setup, **1,699 bounded regressions**, and rendered/reused dashboard lifecycle checks. The optional diagnosis-only lane was skipped by its documented condition. |
| Final complete local profile at `60760ae` | **3,119 passes, zero failures/errors/deselection, six exact reviewed external deferrals**, from 3,125 collected tests. Source audit/binding, unchanged original/quarantined source, verified origins and an empty stopped/reaped owned process boundary passed. The genuine registry stayed unchanged. Actual R2 execution retained its residual-gradient/counterpoise-ordering warnings; physical accuracy remains unqualified. Raw pytest output records 10,763 warnings. |

The six deferred checks require actual ABCluster 3.4, the reviewed patched CREST
build, native Psi4, the separate audited AIMNet CPU installation, and two physical
Slurm-node setup checks. They are not counted as passes. The final profile recorded
798 valid source-origin records; 58 are explicitly startup-only observations,
not final execution proof. No source-authority errors or escaped origins were
accepted.

The first canonical browser attempt completed its functional interactions but
failed its final source comparison because the two inventories included different
helper-file sets. Its failure remains recorded. `9f9bead` made those inventories
symmetric; the corrected canonical run above passed without relaxing the
unchanged-source requirement.

## Retained evidence

These SHA-256 values identify the inspected raw records:

| Record | SHA-256 |
| --- | --- |
| Visual/keyboard receipt, `/tmp/cochem-gui-after-s350u34i/acceptance.json` | `b71404119db310ab8561331c4d28a78888ae5d55f491ac25a26927ccb89e87b4` |
| Corrected canonical browser receipt, `/tmp/cochem-gui-after-r4zyphy8/canonical-ui-smoke/compact-acceptance.json` | `f3307a90335afa6d0933c9c5339b3b101ced12b19927578ac52b0d943060fe9a` |
| Canonical browser full report in that same directory, `browser-summary.json` | `581dfc039b6f4daaf43f0c4041639e0d7347ca80ab8c2b3d1f66b84b6be3e853` |
| xTB independent result check, `/tmp/cochem-gui-hosted-chemistry-9f9bead/xtb/independent-physics-and-integrity-readback.json` | `46514f75bea16b5996cdbf7662f128893787b77ce103af1aee8a14f70f39d230` |
| Engine-access report, `/tmp/cochem-gui-hosted-chemistry-9f9bead/licensed-access-recheck/results/student-result.json` | `61c95052ecaeebda499e3bc434c38c70f70d9d104bbc1e8f2ac595d4769fa53b` |
| CFOUR refused-publication record, `/tmp/cochem-gui-hosted-chemistry-9f9bead/cfour/publication-mismatch.json` | `1c1c7fd500e44326a7cd62d5407e737845bf48527630e8eb44e17c657bbef5f7` |
| Corrected CFOUR independent result check, `/tmp/cochem-gui-hosted-chemistry-ade50d7/cfour/independent-physics-and-integrity-readback.json` | `062dafc96e3c6b5dd45e968b33e2b8ec2deb625a6a02af8c764b2e5be6098985` |
| ORCA independent result check, `/tmp/cochem-gui-hosted-chemistry-ade50d7/orca/independent-physics-and-integrity-readback.json` | `26dc78a4ce97d781f54b54fb24eead1d31dcd8330d5fde82b578b7692f25fcde` |
| Same-geometry ORCA/CFOUR comparison, `/tmp/cochem-gui-hosted-chemistry-ade50d7/independent-cross-engine-comparison.json` | `8ffc866bdafed0cba7e43ba04424d3d2e048e22e493a7955cafc91798172cb7b` |
| Corrected complete-profile receipt, `/tmp/cochem-gui-complete-ade50d7/test-acceptance.json` | `5778114fbfb8ae614e70841dcc2f787e37b3ec9fbeed6d074d0cea5f3bde5086` |
| Failed repeat-open browser receipt, `/tmp/cochem-gui-after-2nd_10or/cfour-browser-acceptance.json` | `eb3e86950238d6114aa464331f0dfeeb008f6cab7fc124cfb98552311136c869` |
| Private-module independent check, `/tmp/cochem-gui-private-module-install-ade50d7/independent-installation-and-integrity-readback.json` | `fffe7fe938b3da5869dab15089f3f57b8944d691e7a6cea6daafa97aa72d1578` |
| Final retained-result browser, `/tmp/cochem-gui-after-_zcc1q13/cfour-browser-acceptance.json` | `c639a8181c1b2737b14b422e70f1bc29376655a697148646682bf33dcca12c5d` |
| Committed source equivalence in that browser directory, `committed-source-equivalence.json` | `23f19be7945dc63aed8c0d70bdb06f614662a0533841a4d9f52f8bb99904a478` |
| Final complete-profile receipt, `/tmp/cochem-gui-complete-60760ae/test-acceptance.json` | `e0359b29762179b916b21c2eb4e10391e20386ccea40b6810b9f9d08c97e2908` |
| Final hosted bounded receipt, `/tmp/cochem-gui-hosted-ci-60760ae/cochem-evidence/bounded-regressions/test-acceptance.json` | `9a5e2c34eed9a29e71cce1ef1bd2e8a058752444951e2df8b7a939fc20c763e7` |
| Failed complete-profile receipt, `/tmp/cochem-gui-clean-release-9f9bead/test-acceptance.json` | `e56b2891cdd455769847fd09da96cef50e22726e251a6cb2194d89df79a77558` |
| Failed hosted bounded receipt, `/tmp/cochem-gui-hosted-ci-9f9bead/cochem-evidence/bounded-regressions/test-acceptance.json` | `5489b830ab29145d27de7ed55bbc85df94e79383214a3f6533523c595b1df395` |

Exact copies of the final terminal/browser/native/provider readback receipts are
published in the [portable receipt directory](evidence/2026-10-13-gui-access/README.md).
Raw per-node outcomes, native calculation files and screenshots remain separate;
local paths do not transfer with a Git commit. Obtain matching originals privately
or rerun the checks. GitHub artifacts also expire; a run link is not a permanent
copy of its evidence. No credentials or licensed engine archives belong in the
public evidence.

## Remaining deployment acceptance

Actual student GitHub App enrollment, a fresh student Codespace with authorized
permissions, and a student-owned Actions calculation remain unverified. Service
API access returned HTTP 403 in this session. Local browser tests and
instructor-run calculations do not establish that student path. The corrected
organization mappings now pass the credential-presence and engine-archive
checks. Per-provider installation and student-owned project access require
their own recorded acceptance.

Follow the [student pilot](Student_Deployment_Pilot.md), retain its actual
identity/revision/run evidence, and complete the broader backlog in the
[handoff](WORKSTATION_COMPLETION_HANDOFF.md). Full scientific accuracy, all
TOPOS/TORQ operations and all physical execution platforms are separate claims.
