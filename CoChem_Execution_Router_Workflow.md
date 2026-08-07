**Template C — Workflow**  
**Workflow goal**  
To architect the Core Execution Router (calc/cochem\_calc\_execution\_router.py). This module acts as the definitive execution switchboard for the CoChem pipeline. It polls the Golden Registry (cochem\_system\_config.json) and dynamically forks workloads between the local SubprocessBroker (for workstation-level tasks guarded by OOM/Thermal protections) and the remote HPC scheduler (generating and dispatching .sbatch payloads).  
**Stage map**

* **Stage 1.0:** Registry Polling & Execution Path Resolution  
* **Stage 1.1:** Local Dispatch (SubprocessBroker Handoff)  
* **Stage 1.2:** HPC Dispatch (SLURM Template Rendering & Submission)

**Detailed stage segments**  
**Stage 1.0 — Registry Polling & Execution Path Resolution**

* **Purpose:** To read the immutable hardware and routing rules defined during Stage 0 and determine the safest path for the incoming computational payload.  
* **Inputs:** Raw computational request (e.g., Engine name, target input file, working directory).  
* **Outputs:** A validated routing directive ("subprocess" or "sbatch").  
* **Files created or modified:** Reads \~/CoChem\_Artifacts/Registry/cochem\_system\_config.json.  
* **Key dependencies:** json, pathlib.  
* **Key scientific or logic checks:** \* Checks cfg\["execution"\]\["default\_engine"\]. If missing, assumes "subprocess" as a safe local fallback.  
  * Verifies that the requested target engine (e.g., orca, mace) is listed as "status": "ready" in the registry before proceeding.  
* **Failure risks:** Race conditions if the registry is actively being rewritten by a micro-silo update.  
* **Suggested validation tests:** Feed the router a mock ORCA job with the JSON artificially set to "default\_engine": "sbatch" to verify the fork triggers correctly.  
* **Estimated coding size risk:** Low.  
* **Context safety note:** Keeps logic at $O(1)$ complexity by relying purely on dictionary key lookups.

**Stage 1.1 — Local Dispatch (SubprocessBroker Handoff)**

* **Purpose:** To execute workloads natively on the local workstation or Codespace, utilizing the existing cochem\_core\_subprocess\_broker.py for zombie thread reaping and OOM preemption.  
* **Inputs:** Executable path (from registry), execution directory, environment variable overrides.  
* **Outputs:** Synchronous execution exit code.  
* **Files created or modified:** N/A (Handled by the broker).  
* **Key dependencies:** core\_engine.cochem\_core\_subprocess\_broker.  
* **Key scientific or logic checks:** Isolates the MPI paths dynamically to prevent system library contamination during execution.  
* **Failure risks:** Broker timeout or failure to inherit the correct Conda silo bindings.  
* **Suggested validation tests:** Pass a benign sleep 5 command to the broker and ensure it returns an exit code of 0\.  
* **Estimated coding size risk:** Low.  
* **Context safety note:** By treating the existing SubprocessBroker as a black box, we avoid rewriting complex signal-trapping logic in the router.

**Stage 1.2 — HPC Dispatch (SLURM Template Rendering & Submission)**

* **Purpose:** To bypass local execution limitations by injecting the computational payload into the pre-configured .sbatch template generated in Stage 0.2b, submitting it to the cluster queue.  
* **Inputs:** Target payload command, cluster limits from registry (cores, memory, wall-time).  
* **Outputs:** SLURM Job ID (parsed from sbatch stdout).  
* **Files created or modified:** Generates an ephemeral {job\_name}\_submit.sbatch script in the working directory.  
* **Key dependencies:** subprocess, string formatting (f-strings or Jinja2).  
* **Key scientific or logic checks:**  
  * Safely interpolates {n\_cores}, {mem\_mb}, and {payload\_command} into the template string.  
  * Invokes subprocess.run(\["sbatch", target\_sbatch\]) and parses the stdout for tracking.  
* **Failure risks:** Scheduler rejection due to invalid partition requests or exceeding node memory limits.  
* **Suggested validation tests:** Execute a dry-run where the sbatch command is printed to stdout instead of submitted, validating the string interpolation logic.  
* **Estimated coding size risk:** Medium.  
* **Context safety note:** Prevents the Python kernel from blocking for 24+ hours while a cluster job runs. Natively enables "fire-and-forget" scalability.

**Context risk points**

* Attempting to rewrite or duplicate the SubprocessBroker logic inside this router would violate the DRY (Don't Repeat Yourself) principle and heavily pollute the context window. The router must remain purely an *interface* that hands off execution.

**Save-point recommendation for external reference**  
Save this mapping as CoChem\_Execution\_Router\_Workflow.md in the root repository. It explicitly defines the operational boundaries between local Workstation testing and HPC scale-up.  
**Next safest segment to implement**  
Do you authorize proceeding to **Coding Mode** to implement the unified calc/cochem\_calc\_execution\_router.py (encompassing Stages 1.0, 1.1, and 1.2 in a single, robust Python class)?