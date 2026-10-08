# CFOUR for Classroom50, GitHub Actions and local CoChem environments

ORCA and CFOUR are **optional, strongly recommended** components of CoChem.
BASE can ingest structures, inspect data, prepare environments and use installed
free engines without either licensed engine. An absent engine or a failed
optional installation disables its dependent calculations; it does not prevent
BASE from starting. A workflow whose explicit purpose is to calculate with
CFOUR must fail if CFOUR is unavailable, so that a green run cannot be mistaken
for a completed calculation.

This guide uses the approved private CFOUR runtime already prepared for CoChem.
Students using instructor-provisioned GitHub Actions access do not create or
enter archive tokens in the interface. For the surrounding Classroom50 course
setup, start with the [course guide](GitHub_Classroom_ORCA_Setup.md). Private
module source uses the separate [ecosystem module setup](Ecosystem_Modules_Setup.md).

## The approved runtime

The reviewed settings are in
[`scripts/cfour-distribution.json`](../scripts/cfour-distribution.json).

| Setting | Approved value |
| --- | --- |
| Private asset repository | `ProfJJK-CoChem/CoChem-CFOUR` |
| Published release tag | `cfour-2.1-runtime-20261007` |
| Release asset filename | `cfour_2_1_linux_x86-64_gcc11_openmp_ilp64.tar.xz` |
| Archive SHA-256 | `19ea269fcc7a13eb059bf43d34f0ef32e07cc9bb98f4ce84bdc4d0d7b20ccd63` |
| CFOUR version | `2.1` |
| Platform | Linux x86-64; glibc 2.35 or newer |
| Compiler | GCC/GFortran 11.4.0 |
| Mathematical runtime | ILP64 OpenBLAS pthread; 64-bit Fortran integers |
| Parallel execution | OpenMP enabled; MPI disabled |
| Actions archive credential | `PRIVATE_CFOUR_ASSET_CREDENTIAL` |

The package contains the `xcfour` launcher, its companion native programs,
required runtime libraries, `GENBAS`, `ECPDATA` and a complete file inventory.
Its compiler, integer interface, libraries and basis data belong together.
Do not substitute a system LP64 BLAS library or copy only `xcfour`.
OpenMP threads are not MPI processes; this build cannot establish MPI acceptance.

The checksum applies to this exact archive. A checksum mismatch requires
investigation against the approved original file. Do not change the manifest's
checksum merely to bypass a failed installation. A different CFOUR build needs
its own reviewed identity and compatibility validation.

## Instructor: connect the private release to course repositories

The CFOUR release and `PRIVATE_CFOUR_ASSET_CREDENTIAL` have already been configured for
the upstream integration. A new course or assignment repository still needs
authorized access; copying the template does not copy secrets.

1. Confirm that the private asset repository's **Releases** page contains the
   published release and the exact archive under **Assets**. A tag by itself
   is insufficient. Keep the licensed runtime in the authorized private asset
   repository, outside the course source repository and Git history.
2. Confirm the token saved as `PRIVATE_CFOUR_ASSET_CREDENTIAL` is unexpired and has access
   to the asset repository. In GitHub's fine-grained token editor, select its
   repository owner, choose **Only select repositories → CoChem-CFOUR**, then
   **Permissions → Add permissions → Contents → Read-only**. Complete any
   organization approval required for that token. Downloading an archive does
   not require Actions or Codespaces management permission.
3. For an instructor-managed course, open the course organization's **Settings
   → Secrets and variables → Actions**. Choose **New organization secret**, or
   edit the existing `PRIVATE_CFOUR_ASSET_CREDENTIAL`. Enter the credential through
   GitHub's secret form; never put its value in source, a lab input, logs or chat.
4. Under **Repository access**, choose **Selected repositories**. Select the
   approved pilot calculation repository and course template as appropriate,
   then save. Verify your organization plan permits Actions secrets for private
   repositories. If organization secrets are unavailable, an administrator can
   configure the same named repository secret separately in each authorized
   calculation repository.
5. Each time Classroom50 creates an assignment repository, add that new
   repository to the organization secret's selected access list before its
   first CFOUR job. Secrets do not transfer from template files. An older
   repository secret with the same name overrides the organization secret;
   update or remove an obsolete repository value when correcting access.
6. Leave **Send secrets and variables to workflows from fork pull requests**
   disabled. CFOUR calculation workflows run through the approved manual route
   and do not need secrets on fork pull requests. Retain the course's required
   review and approved-branch process for credential-bearing workflows.
7. Pilot the physical acceptance and one student example in the actual course
   repository before distributing the assignment to the whole class. Retain
   the run URL, checked-out commit and scientific evidence with the course's
   setup record.

The default `GITHUB_TOKEN` in a calculation repository cannot automatically read
the separate private asset repository. `COCHEM_SOURCE_READ_TOKEN` downloads
private CoChem module source; `PRIVATE_ORCA_ASSET_CREDENTIAL` reads the ORCA archive;
`PRIVATE_CFOUR_ASSET_CREDENTIAL` reads the CFOUR archive. Classroom50's service and
grading credentials serve another purpose. Keep these access scopes distinct.

People who can modify and execute a credential-bearing workflow must be
authorized for the private archive access it provides. If student access to
the archive is not permitted, use an instructor-controlled calculation
repository with reviewed inputs and share the permitted results through the
course's process.

## What installation verifies

The shared action is
[`setup-cfour`](../.github/actions/setup-cfour/action.yml). It downloads into
runner-local storage and checks the archive SHA-256 before extraction. The
installer checks the embedded build identity and complete inventory, native
dependencies, executable permissions, basis data and launcher startup inside
an isolated directory. Successful installation exports the job's CFOUR paths
and records provenance. Runtime libraries are confined to CFOUR child processes;
the action does not replace the whole job's global `LD_LIBRARY_PATH`.

The action exposes `available`, `reason` and `installation_report` outputs.
With its default `required: 'false'`, a download or installation failure records
CFOUR as unavailable and allows general BASE setup to continue. Run a
CFOUR-dependent calculation only when `available` is `true`. A dedicated CFOUR
acceptance or calculation workflow sets `required: 'true'` and stops on failed
provisioning. This requirement belongs to that selected calculation, not to
BASE as a whole.

The separate ORCA provisioner is used by dedicated ORCA workflows and requires
ORCA for those jobs. General BASE startup and free-engine setup do not require
either licensed provisioning workflow to pass.

Provisioning success is separate from scientific acceptance. The launcher
startup probe is a genuine executable/dependency check, not a molecular energy
calculation. Fresh Stage 0 setup must discover the installed engine and record
the actual runner's executable identity, allocation and limits before chemistry
is authorized. Do not reuse a registry from your laptop, Codespace or another
Actions job.

The action removes its downloaded archive. Dedicated workflows also remove the
installed licensed runtime after execution. Retained calculation artifacts
contain permitted inputs, logs, results and provenance, not the archive,
executables, complete basis distribution or native runtime libraries.

## Run the repository's physical acceptance

1. Open the approved course repository's **Actions** page. Select **CFOUR 2.1
   calculation acceptance → Run workflow**, select the approved branch and
   start one run. If the workflow or button is absent, confirm the template
   update reached that repository's default branch and Actions is enabled.
2. Follow the source audit, private provisioning and all eleven Stage 0 phases.
   The job creates a new registry for its Ubuntu runner. Installing the runtime
   alone is not a passing calculation test.
3. Check that the actual scientific acceptance step passed. It runs BASE's
   canonical CLI with genuine CFOUR calculations: HF reference energy, analytic
   gradient and independent energy finite differences, HF optimization and
   harmonic Hessian, MP2/CCSD/CCSD(T) single points, and a one/two-thread NCC
   CCSD(T) comparison. The latter checks OpenMP reproducibility, not MPI.
4. Download `cfour-2.1-acceptance-<run-id>-<attempt>` from the completed run's
   summary. The run ID is the number in the run URL. Retain the calculation
   evidence, source commit, runtime provenance and report with the course's
   setup records. A report must identify actual native output and validation
   outcomes; a partial failed-run artifact does not establish acceptance.
5. Read the scientific report's status and numerical checks. They bind native
   input/output, gradients, Hessian and result hashes to the published results
   and HDF5 record. The reference checks reproduce this build's bounded native
   testsuite calculations; they do not certify agreement with experiment or
   universal scientific accuracy.
6. Run the student single-point example through the separate calculation
   workflow below. Recheck the pilot when changing the approved source, runtime,
   template or credential arrangement before rolling it out to the class.

For a compatible host already configured with real CFOUR and a fresh Stage 0
registry, the same scientific acceptance can be invoked locally:

```bash
python scripts/verify_cfour_scientific.py \
  --registry "$COCHEM_CONFIG" \
  --output /path/outside/checkout/new-cfour-acceptance.json
```

Use the activated BASE environment's Python. The output report must be a fresh
path outside the checkout. A failed attempt retains its genuine diagnostics and
failed report; it does not publish an accepted scientific result.

Harmonic results also include `harmonic-hessian.npz`, containing the measured
Hessian, its ordered atomic identities, native Cartesian geometry and source
hashes. This bundle supports BASE's Data Inspector and isotope re-analysis
without requiring ORCA or CFOUR to be installed on the inspection machine.

For Python callers, `cochem_base.calc.calculation_service.run_calculation` is
the validated native execution API. The historical `CFOURBridge.dispatch_cfour_job`
preserves its broader provider options as a pending handoff; it does not execute
them or publish an accepted scientific result. Use the canonical service for
the connected operations and downstream modules for additional protocols.

## Students: run a CFOUR assignment calculation

Accept your Classroom50 assignment, open its Codespace and wait for automatic
BASE setup. Open the private Voilà dashboard on port 8866. Students use BASE
only; a separate CFOUR or CoChem module checkout is not required.

1. Upload your own Avogadro 2 monomer or complex XYZ geometry through BASE.
   Declare charge and multiplicity; XYZ files do not supply those values.
2. Select **GitHub Actions**, your accepted assignment repository and the
   available CFOUR engine. Choose the supported method, basis and operation.
3. Submit through **Run with GitHub Actions**. BASE creates the request,
   submits it, monitors its actual status and provides cancellation.
4. Retrieve the completed result through BASE and inspect its native output,
   validated scientific report, structures and Hessian when requested. A
   failed job retains its diagnostics and is not labelled accepted chemistry.
5. Save your research report through VS Code's Source Control interface and
   submit according to your course. Stop the Codespace after saving your work.

Follow the [student research guide](Student_Research_No_Code.md) for the
complete interface journey. Students do not run installation scripts, edit
JSON, commit job requests or dispatch workflows manually. The instructor
provides approved runtime access through the organization Actions secret.

The molecular CFOUR adapter supports closed-shell HF calculations and supported
MP2/CCSD/CCSD(T) single points. Connected optimization and harmonic frequencies
currently use HF; VPT2 and further domain operations require an actual available
provider. The approved build uses OpenMP, not MPI. Method limitations and
physical acceptance remain explicit in the GUI and result evidence.

HF/STO-3G examples establish integration rather than vdW research accuracy.
A harmonic evaluation at supplied coordinates does not establish a stationary
point; use an appropriately verified optimization when required. Student
results retain the method, basis, electronic state, requested operation,
engine/runtime identity and source revisions.

## Codespaces: separate authentication and execution choices

An Actions secret is not automatically available in a Codespace. A student can
use the Codespace as the interface and choose GitHub Actions as the calculation
destination without installing CFOUR in the Codespace. In that arrangement the
Actions runner receives authorized archive access and measures its own limits.

For a permitted local CFOUR installation inside Codespaces:

1. Give the intended users read access to the private asset repository within
   the applicable license. Prefer their own authorized GitHub access to a
   shared instructor credential in a student-controlled terminal.
2. In the course template's `.devcontainer/devcontainer.json`, add
   `"OWNER/CoChem-CFOUR": {"permissions": {"contents": "read"}}` under
   `customizations.codespaces.repositories`, alongside other approved source
   repositories. Codespaces additional-repository permissions require the
   additional repository to have the same owner as the Codespace repository.
   Cross-organization asset access needs separately authorized credentials or
   a permitted same-organization private mirror.
3. Have the student create a **new Codespace**, authorize the requested read
   access and verify their personal account is the payer. Rebuilding an
   existing Codespace does not apply changed repository permissions. BASE's
   default devcontainer does not automatically grant CFOUR archive access.
4. Download and install the runtime using the local instructions below. Run
   fresh Stage 0 setup inside that Codespace. The Actions secret alone does not
   perform these local installation steps.

Student-owned Codespaces consume each student's personal allowance; Actions
in organization-owned assignment repositories consume the organization's shared
allowance, regardless of who starts the run. Classroom50 does not change those
payer rules. Stop Codespaces when finished and retain results within the course
workflow's artifact retention period.

## Local Linux and Windows WSL2

Use Linux x86-64 with glibc 2.35 or newer. On Windows, execute the Linux runtime
inside a compatible WSL2 Linux distribution; PowerShell is suitable for
downloading and hashing the archive but cannot run this Linux executable
natively. Verify actual host compatibility rather than assuming all WSL or
Linux versions support the build.

From an authorized Linux/WSL terminal in the reviewed BASE checkout, download
the release asset using your own permitted GitHub authentication:

```bash
gh release download cfour-2.1-runtime-20261007 \
  --repo ProfJJK-CoChem/CoChem-CFOUR \
  --pattern cfour_2_1_linux_x86-64_gcc11_openmp_ilp64.tar.xz \
  --dir /path/outside/checkout/downloads

python scripts/provision_cfour.py \
  --archive /path/outside/checkout/downloads/cfour_2_1_linux_x86-64_gcc11_openmp_ilp64.tar.xz \
  --install-root /path/outside/checkout/cfour-runtime \
  > /path/outside/checkout/cfour-installation.json
```

Replace the example paths with real directories outside the source checkout.
The download directory must exist or be creatable, and the installation root
must be a fresh path. A failed provisioner exits with an explanation and does
not create a successful installation receipt. Keep the complete approved
runtime together. The command's JSON output reports its paths and provenance.

Configure that verified installation in the same terminal before Stage 0:

```bash
export CFOUR_ROOT=/path/outside/checkout/cfour-runtime
export CFOUR_HOME="$CFOUR_ROOT"
export COCHEM_CFOUR_BIN="$CFOUR_ROOT/bin/xcfour"
export COCHEM_XCFOUR_BIN="$COCHEM_CFOUR_BIN"
export CFOUR_CMD="$COCHEM_CFOUR_BIN"
export CFOUR_EXE="$COCHEM_CFOUR_BIN"
export CFOUR_BIN="$CFOUR_ROOT/bin"
export COCHEM_CFOUR_GENBAS="$CFOUR_ROOT/basis/GENBAS"
export COCHEM_CFOUR_ECPDATA="$CFOUR_ROOT/basis/ECPDATA"
export COCHEM_CFOUR_LD_LIBRARY_PATH="$CFOUR_ROOT/lib/runtime"
export COCHEM_CFOUR_PROVENANCE="$CFOUR_ROOT/cochem-cfour-provenance.json"
export PATH="$CFOUR_BIN:$PATH"
export COCHEM_ARTIFACT_DIR=/path/outside/checkout/cochem-artifacts
export COCHEM_CONFIG="$COCHEM_ARTIFACT_DIR/Registry/cochem_system_config.json"

cochem-cli setup --all --artifact-dir "$COCHEM_ARTIFACT_DIR"
cochem-cli status --json
```

Use the activated BASE environment's `cochem-cli`, or its installed
`python -m cochem_base.cli` equivalent. The normal setup profile requires 50 GB
free storage. Bounded hosted examples explicitly select their smaller test
profile; that does not reduce storage requirements for larger chemistry jobs.
The UI's local binary panel can also accept the absolute verified `xcfour` path,
then refresh setup and engine status. Select only operations reported available
for that host. A missing licensed engine leaves the other BASE panels usable.

## macOS and HPC

The approved archive is not a native macOS or ARM64 build. Mac users can submit
to the course's GitHub Actions workflow, or install an authorized matching native
build and complete host-specific setup and physical acceptance.

On HPC, use the site's permitted CFOUR installation, compiler/library modules
and actual allocated resources. Generate the registry inside the allocation.
This OpenMP-only runtime does not grant MPI support and should not be paired
with an invented `mpirun` command. A site MPI build requires its own build,
dependencies, identities and execution evidence. Do not copy Actions absolute
paths or its CPU/RAM allocation into a local or Slurm registry.

## Troubleshooting

| Observation | What to check |
| --- | --- |
| Optional CFOUR is reported unavailable, but BASE starts | This is expected degradation. Read the installation reason; other installed engines and ingestion remain usable. |
| A dedicated CFOUR job fails during provisioning | That calculation requires CFOUR. Correct access or installation before rerunning; do not turn the failure into a successful result. |
| Private release not found, HTTP 403 or archive download denied | Token repository selection, Contents read permission, expiration, organization approval and the assignment's secret access. Check for an older same-named repository secret overriding the organization secret. |
| Archive is missing under a valid tag | Attach the exact archive to a published GitHub Release. A Git tag or source archive is not the runtime release asset. |
| Archive checksum or embedded inventory fails | Compare against the approved original. Preserve the report and investigate the changed or incomplete archive. |
| glibc, ELF architecture or native dependency verification fails | Use a compatible Linux x86-64 host or build the appropriate native runtime. Do not bypass the compatibility check. |
| `GENBAS`/`ECPDATA` missing, or companion programs not found | Restore the complete approved runtime; a copied `xcfour` alone is insufficient. |
| CFOUR disabled in the local GUI after installation | Run fresh Stage 0 on this host, confirm its registry and verified executable path, then refresh the interface's engine availability. |
| Codespace cannot read the private release | Actions and Codespaces authentication are separate. Confirm the user's repository access, devcontainer permissions and creation of a new Codespace. |
| MPI job requested for this archive | Use OpenMP threads within the audited allocation. This approved build has MPI disabled. |
| Requested method, operation or VPT2 remains unavailable | Use an actually connected and validated adapter or downstream provider. Installation cannot establish unsupported scientific capability. |

Physical acceptance reports must identify the exact source commit, archive and
runtime identities, inputs, measured results and validation outcomes. Record
actual hosted run links separately from code review or unit-test results.
