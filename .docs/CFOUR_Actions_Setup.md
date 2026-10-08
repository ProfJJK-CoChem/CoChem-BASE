# CFOUR calculations in a personal private project

The canonical student route uses a **personal private repository** for
calculations in its owner's GitHub Actions allowance and **Codespaces** for the
interface. Follow [private student projects](Private_Student_Projects.md) and
the [exact private staging guide](../docs/private_student_engine_staging.md).
Codespaces uses the student's own authorized GitHub identity to stage reviewed
assets; Actions uses its owning repository authority. No cross-owner credential
is copied into the student project. Organization-owned course repositories have
different billing and are not this personal calculation route.

ORCA and CFOUR are optional, strongly recommended engines for general BASE.
Free-engine startup remains usable without them. A dedicated CFOUR calculation
requires authentic CFOUR and fails explicitly if it is unavailable.

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

The package contains the `xcfour` launcher, its companion native programs,
required runtime libraries, `GENBAS`, `ECPDATA` and a complete file inventory.
Its compiler, integer interface, libraries and basis data belong together.
Do not substitute a system LP64 BLAS library or copy only `xcfour`.
OpenMP threads are not MPI processes; this build cannot establish MPI acceptance.

The checksum applies to this exact archive. A checksum mismatch requires
investigation against the approved original file. Do not change the manifest's
checksum merely to bypass a failed installation. A different CFOUR build needs
its own reviewed identity and compatibility validation.

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

1. Stage the exact acceptance workflow with null calculation intent and retain
   its ready receipt, SHA and task ID. Open the personal private repository's **Actions** page. Select **CFOUR 2.1
   calculation acceptance → Run workflow**, select the approved branch and
   supply those receipt inputs and start one run. If the workflow or button is absent, confirm the template
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
   template or authorized staging arrangement before rolling it out to the class.

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

1. Open your own personal private project with the reviewed BASE source.
   Use its instructor-approved branch and calculation workflow. You do not need CFOUR on your laptop for
   GitHub Actions calculations.
2. Confirm the instructor has completed the repository's CFOUR physical
   acceptance before running an assignment. A configuration record, an accessible
   release or a successful archive checksum does not establish successful
   chemistry.
3. For the first practice run, use
   `examples/jobs/cfour-water-single-point.json` directly. No file edit or GUI
   export is needed. The other committed examples are
   `examples/jobs/cfour-water-optimization.json` and
   `examples/jobs/cfour-water-harmonic.json`; the last requests optimization
   followed by harmonic frequencies. These molecular examples use HF/STO-3G
   neutral singlet water.
4. For an assigned molecule, open the Voilà interface's **Seamless Install**
   panel, select **GitHub Actions** as the calculation environment and enter
   your actual personal private repository and approved branch. Open **No Code
   Matrix** and choose **CFOUR (course Actions workflow)**. Enter the XYZ
   coordinates in ångströms, charge and multiplicity, then select the method and
   basis requested by the assignment. The bounded adapter requires multiplicity
   `1`; entering another value does not add open-shell support. HF/STO-3G is
   under tier **T2**, MP2 under **T6**, and CCSD(T) under **T8**. Select **Project
   Name**, **Actions operation** and **Calculation timeout (s)**. HF permits
   Single point, Optimization, Harmonic frequencies, or Optimize + harmonic
   frequencies; the correlated methods permit Single point only.
5. Select **Prepare GitHub Actions job**, then **Download CFOUR job JSON**.
   The downloaded `<project>-cfour-job.json` contains the validated calculation
   settings, not an executable, credential or laptop installation path. Preparing a
   request does not submit or run chemistry. In your personal private calculation
   repository, open `jobs/` and select **Add file → Upload files** to upload it.
   If `jobs/` does not exist, use **Add file → Create new file**, enter the
   complete path `jobs/<project>-cfour-job.json` and paste the entire downloaded
   JSON into the editor. Commit through the course's review process and wait
   for the input to reach the approved branch before starting a calculation.
   Alternatively, copy and edit an instructor-approved committed CFOUR example;
   keep `engine` set to `cfour` and retain `initial_hessian: "BFGS"` for
   optimization requests.
6. Stage the actual committed job with `--engine cfour`,
   `--workflow-path .github/workflows/cfour_calculation.yml` and all four
   job/resource flags from the private staging guide. Retain the exact ready
   receipt, its SHA and task ID; manual dispatch must supply all three.
   Open **Actions → CFOUR calculation → Run workflow**. Select the approved
   branch containing the input. In **job_file**, enter
   `examples/jobs/cfour-water-single-point.json` for the first practice run or
   your committed `jobs/<project>-cfour-job.json` path. Enter a repository path,
   not a laptop path or the JSON contents. Leave **cores** at `2` and
   **maxcore_mb** at `512` unless the instructor specifies another supported
   value. Start one run and wait for setup, execution and result validation.
7. Download `cfour-calculation-<run-id>-<attempt>` from the completed run promptly
   and retain its run URL, input, native output, validation report and scientific
   record. In `student-job/`, inspect `calculation-report.json`,
   `submitted-job.json` and `validated-job.json`; `calculation/` retains the
   native calculation evidence and accepted result, and `complexes.h5` retains
   the scientific record. Confirm that the requested operation and method
   completed. Partial output from a failed job is useful diagnostic evidence,
   not a completed result.
8. On failure, send the instructor the run URL and the relevant error text.
   Do not send credentials or a licensed runtime. Correct the input or
   configuration through the course review process and start a fresh run.

A green workflow is not automatically a Classroom50 assignment grade. Follow
the instructor's submission and grading arrangement. HF/STO-3G practice jobs
test the software path; they do not establish research-level accuracy or
agreement with measured vibrational frequencies.

The course workflow permits a **256 KiB** JSON input, at most **50 atoms**,
**1 or 2 OpenMP threads**, a **1–1024 MB** memory budget per allocated core,
and at most **1800 seconds** of chemistry execution. Defaults are two threads
and 512 MB per core. CFOUR receives one shared global memory request derived
from `cores × maxcore_mb`; these are not independent MPI process allocations.
Installation time is separate from the calculation timeout. Follow the
instructor's bounded examples: these limits do not make every 50-atom
method/basis combination affordable.

For equilibrium harmonic frequencies, request optimization followed by
frequencies unless you already have an appropriately optimized geometry.
Setting `is_freq` alone evaluates the supplied coordinates and does not certify
a stationary point. External checkpoints, R2 references, ORCA recipes, T9
recovery, periodic calculations and VPT2 require other connected workflows.

The current molecular CFOUR adapter is deliberately bounded: closed-shell RHF
reference, HF calculations and supported MP2/CCSD/CCSD(T) single points. Its
HF geometry optimization uses BASE's optimizer with real native CFOUR energies
and analytic gradients. Harmonic acceptance requires genuine CFOUR derivative
artifacts. The bounded input uses Cartesian basis functions, all electrons
without a frozen core, and disabled molecular symmetry. Keep those settings in
mind when comparing against a separately configured reference calculation.
VPT2, general open-shell methods and downstream spectroscopic
workflows require their separately integrated ecosystem providers and physical
acceptance. A successful small installation test does not certify those
capabilities.

## Codespaces authorization and calculations

Use the Codespace interface with the student's authorized stored GitHub CLI
identity, then stage the approved asset for the owning Actions calculation.
Follow the browser-authentication and cross-owner limits in the private guide.
No separate archive credential is placed in the personal project's Actions.
Optional local licensed installation needs its own native setup and allocation;
it is not a prerequisite for the canonical Actions calculation route.

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

## Troubleshooting and deployment boundary

| Observation | What to check |
| --- | --- |
| Dedicated CFOUR provisioning fails | Authentic source authorization, private project ownership, receipt/expiry, exact archive digest and native dependency report. |
| Archive or embedded inventory differs | Preserve the report and investigate against the reviewed original; never replace the expected hash to bypass failure. |
| Companion programs or basis data missing | Restore the complete approved runtime, not a copied launcher. |
| Codespaces cannot read the approved lab source | Verify the student's real authorized identity; a personal devcontainer declaration does not grant cross-owner access. |
| MPI requested | This approved runtime is OpenMP-only. A site MPI build requires independent provenance and acceptance. |
| Unsupported method or VPT2 requested | Use a genuinely connected and qualified adapter; installation cannot create scientific capability. |

The separate `cfour_provisioning.yml` utility uses null calculation intent and
does not establish a scientific calculation. `cfour_calculation.yml` retains
the actual bounded scientific route described above. No student private pilot
has run here. Its live staging, owning-token draft visibility, scientific run,
retrieval, cancellation and exact asset cleanup remain deployment gates.
Physical records must identify original native inputs/outputs, source, runtime,
measured quantities and validation outcomes. Earlier native evidence does not
qualify a later source or every method-matrix row.
