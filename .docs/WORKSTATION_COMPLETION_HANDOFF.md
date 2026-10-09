# Workstation handoff: finish CoChem-BASE for student research

Prepared 2026-10-09. This is the working brief for the agent running on the
instructor's local workstation. **Complete the implementation and genuine
acceptance below; this document does not declare the unfinished work complete.**

## Assignment and starting point

Finish CoChem-BASE as the canonical installation, setup, ingestion and GUI entry
point for the CoChem ecosystem. Students obtain **BASE alone**, create private
personal research projects, open VS Code in GitHub Codespaces, upload their own
scientific inputs and run calculations through GitHub Actions using BASE's
buttons. Classroom50 supplies course instructions, collection and feedback.
Students must not type commands, write Python, edit JSON/YAML, handle credentials
or obtain TOPOS/TORQ repositories separately. Maintainer commands below are for
the workstation agent, never the student handout.

The starting published main revision is
[`ebc3a11b7c53e3ddf33cf0bc56e72ba99384a82b`](https://github.com/ProfJJK-CoChem/CoChem-BASE/commit/ebc3a11b7c53e3ddf33cf0bc56e72ba99384a82b).
Its code producer is C33 `8946f53ab1d9261eef4eb9c5b117c9936b49eabf`.
The final three-document commit passed a clean source audit; all other 2,189
tracked blobs and modes matched C33. Fetch and inspect actual current main before
starting: other agents are improving TOPOS and TORQ concurrently. Preserve local
changes and user inputs; do not reset them to this historical starting revision.

ORCA 6.1.1 and CFOUR 2.1 are **optional and strongly recommended**. Missing,
invalid or failed optional installations must disable only dependent selections
and operations. BASE ingestion, GUI and independently available free routes must
continue. An unavailable provider is never a successful calculation.

## Read the complete specifications before each code change

Read these documents in full, then research the applicable sections again before
editing their implementation:

1. [Chunk 17 architecture](SRS_Chunk_17_CoChem_BASE_Architecture.md): primary
   specification, all sixteen requirements, all twenty-four WBS items and all
   eight verification criteria, including literal physical thresholds.
2. [BASE proposal additions](SRS_Chunk_Proposal_CoChem_BASE_Architectural_Review.md):
   all sixteen additional vectors. Its requirement numbers have different
   meanings from the identically numbered Chunk 17 requirements.
3. [Task 1 subsystem specification](task1_subsystems_architectural_specification.md),
   [level-2 WBS](task1_level2_wbs_breakdown.md) and
   [traceability matrix](task1_5_3_traceability_matrix.md): full heterogeneous
   ingestion, serialization, execution, GUI and project-delivery obligations.
4. [Method Matrix](../Method_Matrix.md), [user manual](../CoChem_User_Manual.md)
   and [current conformance trace](SRS_Student_1_1_Conformance_Trace.md).
5. [Personal-project App deployment](Personal_Project_App_Deployment.md),
   [student research workflow](Student_Research_No_Code.md),
   [actual student pilot](Student_Deployment_Pilot.md),
   [ecosystem setup](Ecosystem_Modules_Setup.md) and
   [Classroom50 collection](Classroom50_Assignment_Deployment.md).

The existing trace indexes **108 obligations**: 16 Chunk 17 + 16 proposal +
24 WBS + 8 verification + 17 Task 1 L3 + 6 subsystem + 21 ingestion/GUI rows.
Mapping an obligation is not implementation or acceptance. Independently check
every original requirement against actual code and evidence; this backlog is
an initial audit result, not permission to omit other requirements. Retain all
108 IDs and historical evidence rows. Classify missing behavior, unavailable
scientific providers, physical validation, platform/service prerequisites and
project governance separately. Do not fabricate Council votes or signatures.

Student monomer/complex XYZ is one input path. Preserve full molecular format
and multi-record ingestion, isotope/state/unit identity, conformer pools,
periodic cells and PAW data, genuine Hessians/native outputs, spectroscopy,
trajectory/property archives and name/SMILES starting guesses. A starting guess
is not a calculated minimum or measured result.

## What is genuinely verified at the starting revision

| Evidence | Observed result and limit |
| --- | --- |
| C33 complete local source-bound profile | 3,062 collected; **3,056 actual call passes**, zero failures, collection errors or deselection; four reviewed optional call skips and two physical Slurm setup skips. All 782 origin records valid; 58 initial-only records are startup observations, not final execution proof. Source/copies/registry unchanged; admitted owned processes reaped. The raw run reported 10,697 warnings. |
| [C33 hosted run 37878684516](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/37878684516) | 221 controls on each Linux/macOS/Windows worker; three fresh installed wheels, 602 RECORD rows/601 hashed members each; 1,641 bounded regressions; genuine xTB/PySCF chemistry; eleven-phase DEGRADED_OPERATIONAL CPU setup; rendered/reused dashboard. Eight ZIP digests and 1,026 member hashes read back. Optional ORCA/CFOUR were absent in this free-engine lane. |
| Actual required native calls in the complete profile | R2 five-leg execution, T9 single-point fallback and CREST/GOAT union passed. They do not certify R2 physical accuracy, every requested fallback operation or every molecule. |
| Dedicated local ORCA/CFOUR campaign | Eight ORCA and ten CFOUR cases passed, with 840 retained artifacts/40 origin records. CFOUR analytic/finite-difference gradient error was about 3.7742e-9 versus a 3e-6 gate; OpenMP 1/2 energy difference was zero versus 1e-10 Eh. This is the Linux CPU, OpenMP/non-MPI CFOUR build. |
| C29 local full/READ browsers | Genuine rendered intake, selections, reload/kernel cleanup, native ORCA optimization/frequencies and Hessian isotope reanalysis passed on unchanged runtime/UI bytes. These are local maintainer browser results, not actual student Codespaces or newly executed C33 browser results. |
| Current provider campaign | TOPOS accepted seven of nine operation kinds; frequency/RRHO remains unaccepted. TORQ accepted three cases/two operation kinds with five genuine PySCF SCFs, bounded scans and AO Lowdin-Wiberg exports. NBO/NAO and full multidimensional PES remain unavailable/unaccepted. |
| Bounded H2 PES example | Genuine two-electron, one-dimensional interpolation: paired RMSE/max 1.1893/3.7264 cm-1 and standalone RMSE/max 3.1767/8.2429 cm-1 on the recorded domain. This does not establish universal 10 cm-1 accuracy, extrapolation, vibrations, nonzero triples or experimental accuracy. |

The complete acceptance JSON had SHA-256
`9002524785b88e295016e24f3b1cacdfd7184093b7fe2f38944ab3137f01faa3`;
its independent readback had
`005a1eed9eef3015d5efd9b05f4344cfb4ba7a9d94fee9f918314703a0d741c4`.
The final main source audit had
`2aca44bd51830c50bb81f0e0a76037ced97204f33280b1e5a20451045415cffd`.
Exact producers, scopes and earlier failed attempts remain in the conformance
trace; retain them rather than rewriting history as success.

**Evidence portability:** most historical raw receipts are in the cloud's
`/workspace/cochem-runtime` or `/tmp`, not in this Git repository or on the local
workstation. A named path/hash does not transfer a file. Obtain required raw
evidence privately with unchanged hashes/producers, or rerun the acceptance.
GitHub artifacts also have retention limits. Do not copy credentials, licensed
archives/binaries/basis installations or unreviewed environment dumps into
public source or evidence bundles. Two disposable current provider environment
bodies were retired with metadata/source/wheels/results retained; they are not
restorable whole-environment archives. Build and audit fresh local providers.

## Priority 1: complete BASE access and update behavior

### A. Implement withdrawal, rotation cleanup and current authorization

The workstation review found a real missing lifecycle, not a failed chemistry
test. [course_access.py](../src/cochem_base/interfaces/course_access.py)
`provision_project()` verifies membership and selected installation at enrollment,
then writes fresh opaque Actions secrets and a Codespaces source reader. Clearing
an unselected engine's variable does not delete its old credential. There is no
deprovision function or controller revoke mode. Rotation leaves older secret
labels stored. `verify_calculation_project()` checks current private/nonfork
personal ownership, but does not recheck current team membership/enrollment.
[run_student_research.py](../scripts/run_student_research.py) uses that identity
check. The [controller workflow](../.github/workflows/course_project_access.yml)
supports enrollment/maintenance, not withdrawal/reconciliation.

Implement an instructor-controlled access lifecycle without executing student
source in the controller. Track only controller-owned labels/settings. Preserve
working access until a replacement is verified, then clean old owned credentials
and stale bindings. Support selected-engine withdrawal, project deprovisioning,
membership removal and installation removal; handle partial API failures and
re-enrollment explicitly. Protect unrelated student secrets/settings and inputs.
Define and enforce how new downloads/jobs authenticate current authorization.
Short-lived/project-scoped access may be needed: deleting a copied shared reader
does not invalidate copies outside that store, and issuer-side shared-reader
revocation affects every recipient. App uninstall cannot erase already downloaded
files. Do not promise a revocation capability that the chosen credentials cannot
provide. Keep licensed absence operationally optional.

Acceptance must include actual local protocol/encryption controls and actual
GitHub selected-project grant, rotation, old-label cleanup, withdrawal, denial,
team/App removal and re-enrollment. Verify both secret stores and existing/fresh
Codespaces behavior; retain the precise scope. Extend
[access controls](../tests/base/test_course_project_access.py) and
[Lab access UI controls](../tests/ui/test_course_access_widget.py).
An actual local HTTP peer is protocol evidence, not live GitHub acceptance.

### B. Coordinate GUI, module and hosted-worker updates

The [devcontainer](../.devcontainer/devcontainer.json) follows
`canonical-default-branch`; provisioning separately writes the personal project's
`COCHEM_APPROVED_BASE_SHA`. Updating the controller's approved SHA alone does not
update previously enrolled projects. GUI updates can therefore precede hosted
worker approval and produce an honest refusal instead of a usable updated route.

Complete an instructor-managed, compatible update lifecycle across existing
projects, GUI runtime, approved worker, module catalog and saved jobs. Check
[student_setup.py](../src/cochem_base/interfaces/student_setup.py),
[run_student_research.py](../scripts/run_student_research.py) and
[module-distribution.json](../scripts/module-distribution.json). The current
documented maintenance route re-provisions each enrolled project; verify it
genuinely and improve automatic coordination where necessary. Maintain explicit
compatible starter hashes and versioned request contracts. Failed updates must
retain the last valid runtime and preserve originals/results. Exercise approval
changes, old pending jobs, interrupted installs, restart, rollback, and user-file
conflicts through BASE. Students use Check for updates/Apply/restart buttons.

Coordinate provider revisions with the TOPOS/TORQ agents. Current reviewed pins
are TOPOS `b157b7e210aee5bdfa09c22270d77d794f52cdde` and TORQ
`4ce8eecba56e91e27c6abb32473b2ee4d44767c4`; re-read the current manifest before
changing them. Review actual callable interfaces, dependency policies, wheel
members, embedded BASE scientific binding and all required operations before
pinning a newer commit. A newer geometry-only adapter must not remove existing
research operations. Keep CURE/EHS/EVAL/LABS/PLAY/SEED/SHIFT deferred as the user
authorized; enable them only when their access and relevant requirements are
actually addressed.

## Priority 2: run the real student deployment and licensed hosted route

Use the step-by-step [App guide](Personal_Project_App_Deployment.md). Register
the instructor App and configure a private organization controller with Issues
enabled, student-team Read access and instructor-only administration. Install the
App on the organization and only the consenting student's selected private
project. Use the documented Contents read, Secrets/Variables/Codespaces secrets
write and organization Members read permissions. Keep the signing PEM private
and controller-only; read-only source/engine readers stay in private settings.
Check the controller's Actions policy/billing and its approved exact worker SHA.
Do not enable secrets or write tokens for fork pull requests.

Organization secrets do not inherit into personal projects. The App must
separately provision Actions and Codespaces access. Team Read access is not a
cross-repository workflow credential. Do not expose private reader labels/values
in public docs; consumers use the existing generic private mapping keys. Student
Actions and user-owned Codespaces use the applicable student's actual allowance;
organization controller usage is separate. Education/team membership does not
prove a payer or allowance. Check actual GitHub billing rather than inventing it.

Pilot with a real student account and private/nonfork personal project. Students
use BASE Lab access and browser buttons; create a **fresh Codespace after
successful provisioning**. A rebuild does not substitute for newly granted
permissions. Record actual identity/owner, selected App installation, controller
receipt, Codespaces creation/machine/payer, accepted source and request/run IDs.

Complete every check in [Student_Deployment_Pilot.md](Student_Deployment_Pilot.md):

- Both licensed engines absent: render, full supported ingestion and a genuine
  free calculation work; dependent choices are disabled. Test one engine present,
  both present, invalid archive/hash/version, expired access and failed install.
- Real student uploads across the full input routine; isotope/state/units/frame
  selection retained. Malformed/unsupported input gives an actionable error
  without execution or loss of earlier valid inputs.
- BASE automatically installs the approved modules; authentic required operations
  work, and unavailable operations remain visibly gated.
- Run small genuine ORCA and CFOUR calculations through GUI submission, monitoring,
  cancellation of a separate run, request-bound artifact retrieval and report
  export. Verify exact executable/version/archive hashes, MPI/OpenMP settings,
  fresh job authority, convergence and owned cleanup.
- Inspect real tables/figures and download the correct bundle. Perform compatible
  update, restart and rollback with original/result hashes unchanged.
- Exercise the implemented withdrawal/rotation lifecycle from Priority 1.
- Submit a real private-project report through the selected Classroom50 process;
  observe authorized instructor collection and feedback. Private repository
  visibility is not established by course membership alone.

Use [student_research.yml](../.github/workflows/student_research.yml) for the
normal GUI route and [student_entrypoint_acceptance.yml](../.github/workflows/student_entrypoint_acceptance.yml)
for the bounded maintainer route. Also replay
[ORCA acceptance](../.github/workflows/orca_acceptance.yml) and
[CFOUR acceptance](../.github/workflows/cfour_acceptance.yml) through the new access
route. Instructor-run workflows do not establish student identity/permissions.
The prior cloud connection received 403 for Codespaces/settings operations;
that is an access prerequisite to resolve locally, not proof of a software fix.

## Priority 3: complete scientific capabilities and their BASE integration

| Work package | Current shortfall | Required completion and evidence |
| --- | --- | --- |
| TOPOS minima, frequency/RRHO and isomer populations | Current provider frequency/RRHO campaign is unaccepted; two starts of the same water structure do not establish distinct-isomer populations. | Use sufficient resources and genuinely qualified stationary minima. Integrate completed upstream operations through BASE. Compare distinct real isomers with matched method, state, temperature and standard state; verify energy differences, electronic/Gibbs labels, population normalization, diagrams, tables and exports. Retain strict stationarity and native output evidence. |
| TORQ scans and orbital products | Bounded scans and AO Lowdin-Wiberg are accepted on limited cases; NBO, NAO-Wiberg and full multidimensional exploration are not. | Coordinate genuine provider operations and separately required analysis components. Preserve named-observable distinctions. Verify actual multidimensional scan coordinates/energies, potential-energy diagrams, NBO/Wiberg tables and diagrams, source/method conventions and GUI/Actions retrieval. Never rename a Lowdin result as NBO/NAO. |
| Product B | Chunk 17 section 4.2 is a literal requirement. Current periodic adapter provides neutral closed-shell QE PBE/PAW SCF; no band-gap, cell optimization or spin/SOC route. | Integrate reviewed genuine providers into BASE schemas, GUI, worker and reports. Inspect [periodic.py](../src/cochem_base/calc/periodic.py), [periodic_execution.py](../src/cochem_base/calc/periodic_execution.py) and input controls. Current code forces `is_opt=False`, `calculation='scf'`, `nspin=1` and rejects SOC PAW. Accept real gap/cell/spin/SOC outputs with correct units/state/PAW provenance. Independently test the specified 0.1 eV gap/0.01 Angstrom lattice bounds on defined reference systems. An SCF banner does not fulfill them. |
| CFOUR/VPT2 and anharmonic handoffs | BASE alone is not the ecosystem's complete anharmonic solver. Current [CFOUR request support](../src/cochem_base/calc/cfour_execution.py) excludes VPT2, open shell and correlated optimization/frequency. | Coordinate the downstream producer; complete typed BASE installation/capability/request/result/Hessian/state handoffs. Accept genuine requested operations before enabling selections. Harmonic reweighting is not VPT2 or anharmonic B0. Preserve optional-engine absence. |
| T9 continuation | Genuine CASSCF/NEVPT2 single-point fallback is accepted; a requested optimization/frequency/VPT2 is explicitly left incomplete. | Complete genuine operation-specific continuation through an approved provider if advertised. Retain explicit active-space rationale and spin/state checks; a successful replacement single point cannot complete the original different operation. |
| R2 accuracy/warnings | Five-leg execution passed but residual-gradient/counterpoise-ordering warnings remain; independent physical accuracy is unverified. | Compare identical state/geometries/settings using independent or tighter numerical treatments. Check all five legs, ghosts/electrons, all-frame frozen drift, reference provenance and signed correction. Investigate numerical/RI/COSX/VV10 hypotheses without asserting an unproved cause. Free-coordinate convergence does not erase the frozen-bond derivative warning. See [R2 evidence](ORCA_Scientific_Acceptance.md). |
| Independent geometry/isotope targets | Configured tolerances and harmonic replay do not prove proposal REQ-BASE-010 or Chunk 17 VR-08. | Establish the specified 1.19 mAngstrom/0.068% geometry/rotation bounds against independent references. Complete 13C/D/18O projection versus independently repeated SCF comparison at the specified 0.001% rotational drift, while production mass projection itself performs zero new SCF. Preserve nuclei, units, frames and tensor provenance. |
| PES accuracy | Earlier artificial EMT standalone error and bounded H2 interpolation cannot certify every PES or a universal experimental 10 cm-1 bound. | Retain original analysis corrections and error definitions. Use genuine trained-domain/held-out reference calculations for the actual supported systems, report independent validation and domain limits, and refuse unsupported accuracy claims. Coordinate multidimensional sampling with TORQ rather than fabricating energies. |

BASE owns installation, validation, capability gates, GUI and handoff/report
integration even when the underlying solver belongs to another module. A
missing provider is unfinished ecosystem capability, not a reason to silently
omit its literal specification. Coordinate with sibling agents instead of
duplicating or inventing their scientific kernels.

## Priority 4: complete optional distributions and native host acceptance

Read [deferred_acceptance.json](../ci_tools/deferred_acceptance.json). The four
current optional call deferrals are ABCluster 3.4 `rigidmol`, the reviewed patched
generic-path CREST distribution, isolated AIMNet CPU and compiled Psi4 1.10.2.
Provision authentic distributions with required patches/libraries/model locks,
audit their actual executables/interpreters and run their real probes. The two
Slurm setup skips require a physical allocation. Do not make them green by
changing skip reasons, accepting a fabricated scheduler or weakening assertions.

Preserve local Windows/WSL2, Linux, macOS and HPC routes while completing Actions.
The current licensed assets are Linux x86-64: use WSL2 for local Windows Linux
engines; macOS local science needs a matching native build. Do not copy cloud
registries across hosts. Read current platform locks and audit native dependencies.
Verify four-tier detection, the literal <500 ms ingress/<1 s hardware targets,
actual GPU/VRAM/AVX/NUMA where present, process suspend/cancel/owned cleanup,
Slurm/PBS staging/worker lifecycle and distributed FileLock/SWMR ownership with
the specified timeout. Three-OS engineering/wheel checks do not establish native
licensed science or every scheduler/filesystem combination. Unavailable hardware
must remain unavailable; obtain the required host rather than inventing results.

## Workstation preparation and maintainer acceptance commands

Use the existing checkout and inspect `git status --short`, HEAD and origin/main.
Keep work in small independently reviewed commits. On Windows, use the WSL2
Linux filesystem for Linux engine jobs. Use a tested Python 3.12 environment,
current project dependency declarations and external artifact/environment roots.
The prior cloud's `/workspace/cochem-env`, silos, activation scripts, licensed
runtimes, credentials and raw receipts are **not local prerequisites already
installed on this workstation**. Discover or create actual local equivalents.

Budget CPU/RAM/disk and engine MPI/OpenMP before running. Default setup requires
50 GB free workspace storage. The cloud used an explicit 1 GB bounded profile;
that did not pass the default policy. Retain separate core/UI, quantum, classical
and ML environments and their actual locks/origins/pip consistency. In particular,
core JAX 0.8.1 and the reviewed ML JAX 0.7.2 were separate requirements, not an
invitation to replace one with the other. Preserve TLS/signatures/checksums and
the old accepted rollback while building a new provider environment.

Repository-supported dashboard preparation and service commands are:

```bash
# Maintainer only; replace /absolute/CoChem_Artifacts with an external local root.
python3.12 scripts/hosted_dashboard.py setup --artifacts /absolute/CoChem_Artifacts --min-disk-space-gb 50
python3.12 scripts/hosted_dashboard.py start --artifacts /absolute/CoChem_Artifacts
python3.12 scripts/hosted_dashboard.py check --artifacts /absolute/CoChem_Artifacts
```

Inspect actual setup outcomes, a rendered functional response and errors. A PID
or open port is insufficient. Use the script's `stop`/`restart` for owned services.
Create fresh all-eleven Stage 0 authority for each execution host/job after
provisioning licensed or changed providers:

```bash
# Run from the prepared BASE interpreter; artifact directory is new and external.
python cli.py setup --all --artifact-dir /absolute/new-job-authority --json
```

Never use skip-heavy, skip-Eckart or skip-IOPS to claim complete setup. Re-audit
executable hashes, installed locks/import origins, pip consistency, resources
and module seals after changes. Use the resulting registry rather than a guessed
or copied cloud authority.

The following implemented entrypoints require an actual prepared environment
and fresh external output paths; placeholders are **not runnable defaults**:

```bash
python -B -I -S ci_tools/base_ci.py audit --expected-revision <reviewed-commit> --output <external-audit>
python -B -I -S ci_tools/base_ci.py all --expected-revision <reviewed-commit> --output <external-full> --timeout 7200
python -B scripts/verify_release_ci.py regressions --expected-revision <reviewed-commit> --output <external-bounded>
python -B scripts/verify_release_ci.py wheel --expected-revision <reviewed-commit> --output <external-wheel>
python scripts/verify_orca.py --registry <fresh-registry> --output <external-orca-report>
python scripts/verify_orca_scientific.py --registry <fresh-registry> --pyscf-python <audited-pyscf-python> --output <external-orca-science>
python scripts/verify_cfour_scientific.py --registry <fresh-registry> --output <external-cfour-science>
python scripts/accept_student_research.py --root <verified-module-root> --registry <fresh-registry> --output <external-provider-report>
```

Supply genuine R2 reference artifacts where required by the actual native test;
it requires both `COCHEM_R2_REFERENCE_MANIFEST` and `COCHEM_R2_DIMER_XYZ`, bound
to genuinely matched reference and dimer files. Use the current tests and
registry to discover all other prerequisites. A declared path is not a reference
calculation. Do not import an untrusted source tree or mutate a sealed runtime
to make these helpers pass.

Use the real Chromium browser harness for full intake and genuine hosted jobs:

```bash
python tests/ui/student_entrypoint_browser_acceptance.py \
  --url <actual-voila-url> --chromium <actual-chromium> --artifacts <external-browser> \
  --hosted --repository <student/private-project> --branch main --engine orca \
  --execution-origin codespaces --codespace-evidence <actual-codespace-record> \
  --intake-manifest <verified-full-format-manifest> --reload-count 3 --require-stable-source
```

Repeat for CFOUR with a different output root. `--execution-origin` is a declared
context, not proof by itself; retain the actual Codespaces and student identity
record. `--allow-unavailable-modules` is UI-only evidence and cannot substitute
for required hosted/provider execution. Use the harness's authentic READ/R2
input options and native-Hessian mode for their specific acceptance paths.

Final release checks require a **clean committed source**, exact reviewed SHA
and reviewed infrastructure ring, with all writers frozen. Preserve user
untracked/ignored data and use a separate owned clean clone for acceptance;
do not delete unrelated files to qualify the checkout. CI verifies the ring;
never refresh its hashes automatically to conceal changes. Review legitimate
participating-byte changes independently before approving new digests. Retain
actual per-node setup/call/teardown, source origins, copied/source/registry
stability and owned-process cleanup. A pytest zero exit alone is not the outer
gate. Do not replace real tests with mocks, fake native results, arbitrary model
weights, unexpected skips or narrowed selectors. Raw scanner patterns require
contextual classification; physically retired legacy resolves removed findings
but does not authorize deleting valid adversarial or physical acceptance tests.

## Definition of finished and publication

Complete all required BASE behavior, genuine downstream integration and literal
SRS acceptance. The supported student route must work from a fresh independent
personal project through actual Codespaces setup, full input validation, real
Actions chemistry, scientific reports and Classroom50 collection without student
code. Exercise documented failure/recovery paths, updates and access lifecycle;
preserve originals and earlier results. Optional licensed absence is an accepted
behavior, never a pass for an engine-dependent calculation.

Have an independent reviewer reconstruct the requirement/evidence mapping and
verify actual source, outputs, thresholds and student service records. Keep
unavailable, unrun, failed, deferred and passed outcomes distinct. Do not declare
all SRS points complete while required capabilities or literal thresholds remain
unimplemented/unverified, or guarantee flawless behavior for untested inputs.

After affected targeted checks pass, freeze/commit the final source and run the
required complete profile, hosted controls/wheels/science and actual student
pilot on that approved revision. Broaden or repeat tests only for changed paths,
new failures or unresolved concerns. Publish sanitized durable validation and
deployment records, compatibility/source pins, release notes and student guides
in GitHub. Push reviewed commits normally to main; inspect current tag/release
state before publishing the intended stable version. Historical recorded stable
1.0.1 and current 1.1 candidate are not interchangeable; do not move old tags.
Update the course-approved worker and existing enrolled projects coherently.

For each remaining item, leave the requirement ID, actual source commit,
reproduction, code/config change, native/browser/hosted evidence and independent
verdict. A documentation edit or additional passing unrelated test is not closure.
If the host lacks a necessary physical engine/hardware/API permission, finish
independent work and state the precise external prerequisite; do not conceal it.

## Cloud snapshot publication boundary

The reusable cloud install/start instructions were saved and read back in draft
revision 29. Only startup instructions changed; install script, repository list,
network and credential requirements were preserved. Saving a draft did not
publish an environment snapshot. This session exposed no snapshot-publication
tool; the product's environment settings **Publish** action is required.
GitHub main publication and cloud snapshot publication are separate operations.
The local workstation does not need that snapshot to begin this handoff.
