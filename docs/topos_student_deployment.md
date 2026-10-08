# Install and test TOPOS from the BASE interface

BASE, TOPOS and TORQ form a mandatory package set. BASE's module installer accepts
the **reviewed complete kit**, verifies its exact source/wheel/helper identities,
and creates an independent noneditable environment. The complete TOPOS interface
then runs in that environment with its own authenticated BASE registry. It does
not import whichever TOPOS source directory happens to be beside BASE.

Installing the package and executing a pathway are distinct checks. Missing
engines, scientific inputs, references or resource allocations remain explicit
failures. An imported GOAT result is a starting state, not proof of a completed
CoChem calculation or publication eligibility.

## Prepare the student's project and package set

1. Follow [private student projects](../.docs/Private_Student_Projects.md) to create
   the student's personal private BASE project and authorize the student's own
   GitHub CLI account. Codespaces supplies the interface; calculations in that
   project's Actions use the student's own allowance. Organization secrets do
   not transfer into personal repositories. Approved licensed assets use the
   [private staging pathway](private_student_engine_staging.md).
2. Download the [student installation prerelease](https://github.com/ProfJJK-CoChem/CoChem-TOPOS/releases/tag/v0.1.0-student-preview.20261008), verify its published `SHA256SUMS`, and extract the complete mandatory kit outside the source checkout. This candidate is for deployment testing; its retained scientific gate identifies outstanding native and reference qualification. Obtain the instructor-reviewed kit whose source and wheel
   identities match the installed BASE catalog. Keep the extracted kit outside
   every source checkout. A wheel downloaded independently, a checkout of an
   arbitrary newer `main`, or a newly calculated checksum is not a replacement
   for the reviewed kit. [Kit requirements](../.docs/Ecosystem_Modules_Setup.md#mandatory-kit-installation)
   explain the required source and installation evidence.
3. Open the BASE interface. In **Module installation and execution**, choose
   **CoChem-TOPOS**, set the external **Module storage** directory, provide the
   **CoChem kit directory**, and click **Install selected recipient**. This
   selection installs all three mandatory distributions and runs BASE setup.
   Retain a failed setup log instead of treating a failed install as available.
   If BASE was installed before this deployment update, refresh BASE setup first
   so its noneditable distribution includes `scripts.gui_module_controller`.
   The notebook invokes that installed controller in an isolated child; updating
   a source checkout alone does not update the execution controller.
4. Refresh module availability. Set **TOPOS interface port** (8501 by default)
   and click **Open complete TOPOS interface**. BASE verifies the sealed
   installation, actually renders the installed app, then starts its loopback
   HTTP service. The button presents the appropriate local or Codespaces link.
   In Codespaces keep port 8501's forwarded visibility **private**.

The private project and approved branch entered in BASE are supplied explicitly
to TOPOS's remote settings. Its remote BASE source pin comes from the verified
kit, rather than an installed version string. Generic free-engine dispatch uses
the compatible `topos_compute.yml` workflow. The complete private Actions route
below uses `topos_calculation.yml` and separately staged engine assets.
GitHub authentication remains in the controller; scientific subprocesses exclude
account, source and archive credentials.

Codespaces' default BASE profile is an interface for private Actions staging.
Opening the full TOPOS app additionally requires the mandatory kit's audited
runtime. For local calculations choose a configured Linux host; Windows users
run the Linux setup and engines in WSL2. Native Windows cannot run Linux engine
archives. Selecting an HPC environment does not create a scheduler allocation.

## Calculate and use previous work

The complete TOPOS interface provides calculation, external-input, method-matrix,
review and export controls. Select the exact scientific purpose, engine, method,
time tier, CPU/GPU allocation and recipe inputs. Inspect capability diagnostics
before submitting. Matrix routes retain their original matrix identity and
scientific differences for explicitly reviewed alternative methods.

Use **External input** to drop a single XYZ or a retained GOAT/CREST XYZ ensemble
into the canonical intake. Declare molecular charge, multiplicity, atom identities
and fragment states, record the original program/parameters and provenance, and
inspect the preview before staging. The intake preserves the original bytes,
records their digests, and creates a queued canonical run. **Resume** picks up that
run through the same validated scientific workflow as a normal request.

An external geometry can start energy, gradient, optimization, frequency,
thermochemistry, association, search or an explicitly selected matrix recipe.
An ensemble supplies retained search starting states. Advanced steps requiring a
single geometry require an explicit frame selection. Existing calculations do not
silently waive stationary-point, spin, units, atom-order or native-evidence checks.
Provide recipe-specific starting ensembles, monomer references and derivative
inputs through their typed fields; the original source files remain attributable.

## Run the complete request on the student's personal Actions allowance

1. In the complete TOPOS interface, prepare or ingest the scientific starting
   states and select the exact request. Download **request for BASE private
   Actions runner**. This named export keeps the chemistry, settings, matrix
   inputs, starting frames and resources, and explicitly assigns local execution
   to the Actions worker. A regular request export is also retained separately.
2. Return to BASE, select **GitHub Actions**, enter the student's own private
   project and approved branch, and select **Complete TOPOS request** under
   **Private Actions pathway**. Drop the JSON or select its file path.
3. Set the receiver wall-clock bound to cover the complete declared calculation
   budget. This worker supports CPU calculations with one or two threads,
   64–4096 MiB and at most four hours. Larger allocations, GPU/model provisioners
   and HPC calculations require their appropriate configured execution host;
   the interface does not silently lower resources or substitute methods.
4. Keep the actual installed mandatory module and reviewed kit selected in
   **Module installation and execution**. For each required licensed engine,
   provide its independently reviewed distribution descriptor and file SHA-256.
   Free requests need no licensed descriptor; a composite requiring both engines
   needs both. A wrong, missing or unrelated descriptor blocks submission.
5. Click **Stage privately and submit**. The installed provider validates the
   entire typed request and source-selected engine recipe before repository
   mutation. BASE commits the original request, stages and reads back the complete
   kit in a private draft release, and stages each licensed engine through its
   existing private receipt protocol. Authentication stays with the student's
   authorized account; the runner uses only its own project authorization.
6. Retain the returned task UUID. **Refresh owned run**, **Cancel owned run**,
   **Download owned results**, **Select observed owned run**, and **Review
   staged-asset repair** operate on the exact project, source, task and observed
   run. A successful API dispatch is not a completed calculation. Retain failures
   and verify the scientific snapshot and method-specific gates in the results.
7. After the exact owned run finishes, **Clean completed staged assets** closes
   kit admission, checks for active consumers, and removes the task's own kit and
   licensed staging releases. This does not delete the lab's distributions or
   the retained local scientific results.

The request checksum is independent of its staging controls. The workflow binds
the actual private repository IDs, committed Git source, full request bytes,
allocation, mandatory source pins, kit checksum and each separate engine receipt.
It revalidates the installed source-selected recipe before scientific execution.
Queue-inclusive requests use the authenticated GitHub run creation time; queue,
provisioning, setup and verification consume the original budget. The provider
retains the unchanged request and records the remaining invocation allocation.
An exhausted allocation creates a timed-out record with no native attempts.

Hosted artifacts contain verified committed scientific exports and controlled
diagnostics. Licensed runtimes, archives, basis distributions and private kit
transport files are excluded. Publication remains a separate human review gate.

The **Review and export** controls inspect immutable run records, record decisions,
freeze a reviewed ensemble, produce a TOPOS-to-TORQ handoff, verify an actual
consumer receipt, and create a local research archive. A TORQ handoff does not run
a torsional solver automatically. Use the separately reviewed TORQ consumer
environment and its supported entry points; the tested mandatory package pin does
not acquire every capability from a later TORQ `main`.

For the separately reviewed TORQ interface, select **CoChem-TORQ** in BASE's
module panel, install its catalog-selected interface environment, and click
**Open TORQ student interface**. BASE verifies that environment and starts an
owned Jupyter service (port 8888 by default). The authenticated link appears only
inside the private BASE interface; keep forwarding visibility private. **Stop
TORQ interface** stops that owned service and removes its private connection file.
TOPOS handoff publication and actual TORQ solver execution remain separately
reviewed operations with their own required inputs and native evidence.
If a managed TOPOS producer is installed in the same BASE module storage, BASE
verifies its full mandatory receipt and shows its exact Python path. For
**Reviewed TOPOS ensemble JSON**, copy that path into TORQ's **TOPOS Python**
field, inspect the original ensemble, and explicitly choose a member. The path
does not approve a calculation. Missing managed producers leave the explicit
out-of-band producer choice available; a present invalid receipt blocks the
launcher instead of advertising an unverified interpreter.
In a student's personal private BASE project, the installed TORQ interface's
native Actions submissions use the BASE `calculation.yml` controller and that
owner's Actions allowance. It resolves the separately reviewed TORQ scientific
source from the immutable BASE module catalog and keeps the approved plan bound
to the actual installed interface. The current native runner supports its
declared PySCF protocols; licensed engine calculations use their dedicated
receipt-bound pathways. A Git checkout approval tied to another controller
commit must be reviewed again instead of silently reused.

Keep the BASE session open while its TOPOS service runs. **Stop TOPOS interface and
its jobs** stops the owned service and its child calculations; retained inputs,
snapshots and outputs remain outside the source checkout. An interrupted run can
be reviewed and resumed through its immutable records rather than overwritten.

## Equivalent installed BASE commands

From the supported installed BASE Python, using actual external directories:

```sh
python -I -B -m scripts.manage_modules install --modules topos \
  --root /external/modules --ecosystem-kit /external/reviewed-kit --json
python -I -B -m scripts.manage_modules verify --modules topos \
  --root /external/modules --json
python -I -B -m scripts.module_dashboard --root /external/modules --port 8501 \
  --remote-repository STUDENT/PRIVATE_PROJECT --remote-ref main
```

The last command remains in the foreground. Ctrl+C stops its owned service.
Omit the remote options for a local-only session. The typed request/XYZ module
execution route also remains available from BASE's GUI and
`scripts.run_module_handoff`; it preserves the complete request without copying
the full TOPOS interface into BASE.

## Retain evidence from deployment testing

Record the actual three source pins, kit hashes, installation receipt, authenticated
eleven-phase setup result, browser rendering log, request, engine/CPU/GPU allocation,
native outputs and final run status. GUI rendering and package installation do not
certify the method matrix or accuracy. Licensed native acceptance, a real student's
private Actions lifecycle and full scientific reference campaigns require their
own actual retained results.
