# CoChem-BASE 1.0.1 SRS closure and student release record

The baseline is [SRS Chunk 17](SRS_Chunk_17_CoChem_BASE_Architecture.md) plus
[BASE proposal additions](SRS_Chunk_Proposal_CoChem_BASE_Architectural_Review.md),
subject to the agreed BASE responsibility: ingestion, setup, GUI, audited
native execution, result storage and faithful ecosystem handoffs.

This release brings the CFOUR/module integration and four remaining connected
BASE corrections into one student source distribution. Existing `v1.0.0`
remains immutable and predates these additions. Publication and final validation
are established by the actual GitHub release entry and its attached validation
report/checksums when available; the revision-specific results below identify
the science and test evidence independently of publication.

## Connected BASE corrections

| Requirement | Correction in this pass | Acceptance record |
| --- | --- | --- |
| Chunk 17/proposal 009 | Supported ORCA DFT optimization connects measured gradient/energy/last-step convergence to genuine DEFGRID1 → DEFGRID2 → DEFGRID3 jobs, with actual geometry and immutable GBW/MOREAD state carry. Stronger explicit grid, tier, metal, R2 and frequency minima remain in force. | Genuine hosted three-stage ORCA grid progression passed with seventeen retained Cartesian-gradient evaluations; source equivalence and the complete-profile boundary are recorded below. |
| Chunk 17 003 | ORCA binds actual printed Cartesian gradients to native Bohr geometry/energy and a retained hashed transcript. xTB uses native `--grad` at each real BASE BFGS evaluation; CFOUR already uses native analytic-gradient BFGS evaluations. Coordinate-only records remain explicit when derivatives are unavailable. | Actual xTB GFN2/GFN-FF and isotope-labelled Chain derivative publication passed; hosted ORCA completion retained seventeen/seven/eleven gradient evaluations across its three native cases. |
| Chunk 17 004 | Dynamic exact nuclides accept `13C`/`C-13`/`C13` and D/T; canonical identities survive XYZ/SMILES ingress, alignment, telemetry, GUI/conformer inputs and immutable handoffs. Electronic decks use true element labels; selected-isotope harmonic NPZ preserves the unchanged Cartesian Hessian. | Focused ingress/handoff/GUI contracts, genuine D/T Chain data, hosted ORCA/CFOUR isotope-labelled harmonic/Hessian-ingestion cases and the complete profile passed. |
| Proposal 006 | Safe native runner, exported core broker and object broker share exclusive UUID JSON-LD crash persistence: exact raw stderr tail, prelaunch executable/input identities, child cwd/thread/resource context, honest source identity and canonical hash/read-only file protection. CLI uncaught-exception handling preserves traceback and closes HDF5. | Actual Linux signal/strict-encoding/crash/lifecycle, concurrent SWMR and complete-profile cases passed; all three platform CI controls passed. |

Automatic grid advancement retains the functional/basis and validates native
SCF, gradient and quintuple optimizer convergence for each stage under one
operation deadline and host authority. Fixed HF/correlated and frequency/R2
policies keep their applicable minima. Private `.opt` optimizer state is not
invented into a Cartesian Hessian; genuine supplied Hessian READ validation
remains separate.

Selected-isotope harmonic analysis reweights the actual Cartesian Hessian
without another SCF. Native/principal spectra and selected-isotope spectra
remain distinct. Unknown/nonphysical nuclides are rejected; ghost centers
remain the specialized counterpoise adapter's responsibility.

ORCA transcript evidence records native printed precision (geometry `1e-6`
Bohr, gradient `1e-9` Eh/Bohr) and exact retained UTF-8/LF section hashes and
offsets. It does not claim that the selected transcript is byte-for-byte the
entire stdout. xTB trial evaluations are labeled as evaluations rather than
invented optimizer iteration numbers. Both routes preserve native input/output
identity and reject derivative/geometry mismatch.

Crash records retain at most 256 actual raw stderr bytes without padding,
plus hashes of implicit CFOUR inputs/basis data rather than licensed contents.
Git object ID and SHA-256 of the Git commit object are separate fields; missing
Git identity stays unknown. Recorded CPU/RAM is an observed host snapshot, not
a per-job peak claim. Immutable crash JSON is retained by the ORCA/CFOUR
calculation workflows.

The obsolete exported telemetry helper's global SWMR prohibition is retired
in favor of the canonical committed-row storage policy. The complete canonical
profile, source-integrity gate and cross-platform package checks must establish
the release's final revision rather than inherit older test counts.

## Licensed engines remain optional

ORCA and CFOUR are **optional and strongly recommended**. Failed optional
installation records an unavailable capability, leaves BASE and installed free
engines usable, and disables dependent local choices. A workflow specifically
requesting that licensed engine must fail truthfully when it is unavailable.
Remote request preparation is distinct from successful remote installation and
completed chemistry.

The approved CFOUR 2.1 runtime verifies its archive hash, complete file inventory,
native dependencies, launcher/helper/basis identities and actual version. Fresh
Stage 0 binds this seal to the execution host. Native work directories and
child-scoped runtime libraries prevent one engine's installation from changing
another engine's library search paths.

Accepted CFOUR operations are closed-shell HF single points, BFGS optimization
using native analytic gradients, native harmonic derivatives, and
MP2/CCSD/CCSD(T) single points. Geometry-bound Hessian NPZ, raw scientific files,
provenance and HDF5 records support later result inspection and isotope
reanalysis. This build uses OpenMP; MPI is disabled.

[Hosted CFOUR acceptance 37704401496](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37704401496)
**passed** at `7144f82478aa88ae21966ba8a6c19f97bc33004b`: ten genuine
energy/optimization/harmonic/derivative/thread-comparison cases plus one
`18O`/D2O input-isotopologue harmonic and geometry-bound Hessian ingestion case.
The separate [student-style CFOUR calculation 37704003113](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37704003113)
passed on the application-equivalent `80dfec3` source. Its tested inputs,
resources and artifacts remain run-specific. Earlier CFOUR acceptance is
historical evidence; it is not added to the current case or canonical counts.

[Hosted ORCA acceptance 37703993551](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37703993551)
**passed** on `80dfec3`, including actual serial/parallel physical pytest
acceptance and three SRS completion cases: measured DEFGRID1/2/3 progression,
isotope-labelled harmonics/Hessian ingestion, and xTB native-gradient
optimization. These cases retained seventeen, seven and eleven genuine
Cartesian-gradient evaluations respectively. The
[student ORCA calculation 37704000193](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37704000193)
also passed.

Source comparison verified 2,101 identical production/workflow/test blobs
between `80dfec3` and reviewed `7144f82`. The three changes concern CI transport
and fixture preservation plus removal of an invalid CFOUR-only acceptance
assertion; that assertion is unreachable in the ORCA path. The redundant
`7144f82` ORCA run was cancelled and is not claimed as a passed calculation.

Complete instructor/student procedures are the
[Classroom50 assignment deployment guide](Classroom50_Assignment_Deployment.md),
[ORCA/Classroom50 guide](GitHub_Classroom_ORCA_Setup.md),
[CFOUR guide](CFOUR_Actions_Setup.md) and
[module guide](Ecosystem_Modules_Setup.md). Course copies need current source
and independently granted approved access; template files do not copy secrets.

## Revision-specific validation and publication

| Gate | Actual result |
| --- | --- |
| Complete-profile source | `583a6d22db0fab0fdd54d2659ceac87ba82fa48a`; application/workflow bytes match accepted `7144f82`/`80dfec3`. The final merged source commit and tag are identified by the actual GitHub release notes and attached validation report. |
| Canonical complete local profile | At exact `583a6d2`: **1,829 collected, 1,827 passed, two exact physical Slurm deferrals, zero failures or unexpected skips**, 10,672 retained warnings, 879.89 seconds. Audit and test gates passed, with no coverage errors. Earlier incomplete/failed attempts are retained and are not acceptance results; older 1,532-pass and 733-pass runs are historical. |
| Source/input integrity and strict gate | The complete local profile preserved all **1,368** audited source/input snapshots, matching the frozen Git blob; `source_changed` is empty. Source audit, outcome accounting and test gates passed at `583a6d2`. Hosted source integrity and corrected focused GUI/source checks also passed. |
| Hosted public controls/free-engine/dashboard/package checks | [Run 37706334481](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37706334481) passed at `583a6d2`: source integrity, Ubuntu/macOS/Windows CI controls and isolated wheel checks, **883 bounded regression tests** with no failures, skips, deferrals, coverage errors or source changes; all 1,368 source-snapshot entries matched the frozen Git blob. Real free-engine/derivative checks, all eleven Stage 0 phases and rendered dashboard lifecycle passed. The earlier [869-test run at `7144f82`](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37704370113) remains separately retained. |
| Actual ORCA and CFOUR chemistry on closure source | Local native ORCA three-test and CFOUR one-test selections passed at `7144f82`. Hosted CFOUR ten main cases plus one input-isotopologue case passed at that revision; hosted ORCA serial/parallel plus three SRS completion cases and both student engine jobs passed on application-equivalent `80dfec3`. Overlapping selections are not added to the complete profile count. |
| Fresh local devcontainer lifecycle | Exact configured Python 3.12 Bookworm image, fresh environments and artifact volume: package version 1.0.1, strict `13C` CLI JSON, PySide/VTK imports, all eleven Stage 0 phases, rendered Voilà lifecycle, and genuine xTB GFN-FF/GFN2/Hessian checks passed with ORCA/CFOUR absent. All 2,104 tracked files remained unchanged at `80dfec3`; application/GUI/devcontainer bytes match `7144f82` and `583a6d2`; later changes affect CI transport/selection and one GUI acceptance test. This is local container evidence, not a student Codespace. |
| Fresh isolated release wheel/sdist checks and hashes | Reviewed wheel builds/installations passed on Ubuntu, macOS and Windows, including hosted `583a6d2` checks. For final merged-source assets, verify the attached validation report's actual build/content-inventory results and compare downloaded files with the release's `SHA256SUMS.txt`. These attachments establish final asset identity and validation when present. |
| GitHub tag/release and attachments | Publication is verified through the actual [v1.0.1 release](https://github.com/ProfJJK-CoChem/CoChem-BASE/releases/tag/v1.0.1) and [tag release API](https://api.github.com/repos/ProfJJK-CoChem/CoChem-BASE/releases/tags/v1.0.1): require a non-draft release, its tag resolving to the merged source recorded in the notes/report, and successfully uploaded source/wheel/sdist/validation/checksum assets. The actual notes and attached report establish source/tag identity and published assets. Preserve `v1.0.0`; a URL alone is not publication evidence. |

Each run retains its actual source identity, accepted outcomes, explicit
external deferrals and unchanged-source evidence. Overlapping focused/bounded
tests are not added to the canonical count. Download/installation, parsing,
browser interaction and physical chemistry establish different facts.

## Chain, R2 and source metadata

The current `583a6d2` correction changes only a GUI acceptance test and the
hosted test selection. Native optimizer evaluations each retain their own
`result.json`; the GUI acceptance now resolves the final published result
through its execution manifest and checks genuine gradient records and hashes.
The corrected focused selection passed 14 tests. Application, GUI, engine,
workflow and devcontainer source is unchanged. Independent comparison verified
all 511 production/UI/native-workflow/source-integrity paths identical to
`7144f82` and `80dfec3`. Across the full tree, 2,102 tracked files match
`7144f82`; only the two CI/test files differ. Native and fresh-container proofs retain
their actual tested revisions and verified application equivalence.
The complete-profile result above is from the finished run against that exact
frozen candidate; focused and hosted selections overlap and are not added to
its test count.

Native isotope-labelled Chain execution passed for D/T input and published six
actual Cartesian gradient vectors with retained nuclear identities. This used
the `80dfec3` application source, which matches the reviewed `7144f82` and
`583a6d2` code.
R1/R2 frozen-monomer, checkpoint and counterpoise policy remain connected; the
complete current profile passed their combined behavior. Previously accepted
finite-basis R2 references retain their explicit residual-gradient and
non-rigorous-energy-bound limitations in the
[scientific acceptance record](ORCA_Scientific_Acceptance.md).

Stale tracked `CoChem_BASE.egg-info` and `cochem_base.egg-info` metadata were
removed and generated `*.egg-info` is ignored. Source version comes from
`pyproject.toml`; isolated installations must report the actual distribution
version `1.0.1`. The fresh container generated only ignored package metadata,
and every tracked source byte remained unchanged.

## Remaining external deployment and ecosystem scope

A real student-identity Classroom50 assignment and fresh Codespace require an
accepted assignment, student organization/team access, personal Codespaces
authorization/allowance and approved assignment Actions access. The available
integration authenticated as the instructor, found no student assignment or
existing Codespace, and received HTTP 403 on repository Codespaces permissions
and machine checks. The [pilot checklist](Student_Deployment_Pilot.md) records
the course deployment evidence needed. Local devcontainer execution and
upstream Actions jobs do not certify this institution-specific student route.

Physical GPU, Slurm/NUMA, distributed filesystems and additional Windows/WSL/macOS
chemistry remain deferred to the supplied hosts. Cross-platform Python package
checks do not establish native scientific acceptance.

Full TOPOS/TORQ scientific solvers, multidimensional PES, VPT2/anharmonic `B0`,
open-shell/correlated CFOUR derivatives and advanced periodic bands/cell/spin-SOC
are provider scope. The seven user-deferred source-access modules remain
deferred; source-only/defective module packaging does not become complete by
being listed in BASE. The accepted module adapters expose their reviewed
geometry operations and explicit pending states.

Actual small-molecule calculations establish the documented benchmark and
integration domain. Configured convergence limits, a harmonic spectrum or one
successful PES interpolation do not certify universal experimental accuracy.
