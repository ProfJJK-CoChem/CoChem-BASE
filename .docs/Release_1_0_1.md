# CoChem-BASE 1.0.1 SRS closure and student release record

The baseline is [SRS Chunk 17](SRS_Chunk_17_CoChem_BASE_Architecture.md) plus
[BASE proposal additions](SRS_Chunk_Proposal_CoChem_BASE_Architectural_Review.md),
subject to the agreed BASE responsibility: ingestion, setup, GUI, audited
native execution, result storage and faithful ecosystem handoffs.

This release brings the CFOUR/module integration and four remaining connected
BASE corrections into one student source distribution. Existing `v1.0.0`
remains immutable and predates these additions. Publication and final validation
are recorded below only when actual results are available.

## Connected BASE corrections

| Requirement | Correction in this pass | Acceptance record |
| --- | --- | --- |
| Chunk 17/proposal 009 | Supported ORCA DFT optimization connects measured gradient/energy/last-step convergence to genuine DEFGRID1 → DEFGRID2 → DEFGRID3 jobs, with actual geometry and immutable GBW/MOREAD state carry. Stronger explicit grid, tier, metal, R2 and frequency minima remain in force. | Pending final revision-specific execution evidence. |
| Chunk 17 003 | ORCA binds actual printed Cartesian gradients to native Bohr geometry/energy and a retained hashed transcript. xTB uses native `--grad` at each real BASE BFGS evaluation; CFOUR already uses native analytic-gradient BFGS evaluations. Coordinate-only records remain explicit when derivatives are unavailable. | Actual xTB GFN2/GFN-FF water evaluations passed; final revision-specific integrated acceptance is recorded below. |
| Chunk 17 004 | Dynamic exact nuclides accept `13C`/`C-13`/`C13` and D/T; canonical identities survive XYZ/SMILES ingress, alignment, telemetry, GUI/conformer inputs and immutable handoffs. Electronic decks use true element labels; selected-isotope harmonic NPZ preserves the unchanged Cartesian Hessian. | Focused ingress/handoff/GUI contracts passed; final native and integrated acceptance is recorded below. |
| Proposal 006 | Safe native runner, exported core broker and object broker share exclusive UUID JSON-LD crash persistence: exact raw stderr tail, prelaunch executable/input identities, child cwd/thread/resource context, honest source identity and canonical hash/read-only file protection. CLI uncaught-exception handling preserves traceback and closes HDF5. | Actual Linux signal/strict-encoding/crash/lifecycle and concurrent SWMR cases passed; final integrated acceptance is recorded below. |

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

[Hosted CFOUR acceptance 37694454874](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37694454874)
passed 10 genuine cases, including finite-difference/analytic-gradient checks,
one/two-thread comparisons and artifact round trips. The
[student-style calculation 37692395742](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37692395742)
passed optimization and harmonics. These tested earlier integrated revisions;
the final release runs below identify acceptance of the new closure code.

Complete instructor/student procedures are the
[ORCA/Classroom50 guide](GitHub_Classroom_ORCA_Setup.md),
[CFOUR guide](CFOUR_Actions_Setup.md) and
[module guide](Ecosystem_Modules_Setup.md). Course copies need current source
and independently granted approved access; template files do not copy secrets.

## Revision-specific validation and publication

| Gate | Actual result |
| --- | --- |
| Final source revision | Pending final reviewed commit. |
| Canonical complete local profile | Pending final run; older 1,532-pass and 733-pass bounded results are historical. |
| Source/input integrity and strict gate | Pending final run. |
| Hosted public controls/free-engine/dashboard/package checks | Pending final run. |
| Actual ORCA and CFOUR chemistry on closure source | Pending final run. |
| Fresh local devcontainer lifecycle | Exact Python 3.12 Bookworm image plus the new setup script passed native PySide/VTK imports, all eleven Stage 0 phases, rendered Voilà start/check/repeated start, and genuine xTB GFN-FF/GFN2/Hessian calculations with ORCA/CFOUR absent. This tested the `cc1ef4b` dashboard source plus the new script, not a real student Codespace or the complete final source profile. |
| Fresh isolated release wheel/sdist checks and hashes | Pending final build. |
| GitHub tag/release and attachments | Pending publication; only actually uploaded assets count as published. |

Each run retains its actual source identity, accepted outcomes, explicit
external deferrals and unchanged-source evidence. Overlapping focused/bounded
tests are not added to the canonical count. Download/installation, parsing,
browser interaction and physical chemistry establish different facts.

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
