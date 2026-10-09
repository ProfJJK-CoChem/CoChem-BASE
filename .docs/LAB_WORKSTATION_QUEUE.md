# Lab workstation route

Calculations that do not fit the GitHub Actions classroom worker (more than 50
atoms, more than two cores or 1024 MB per core, more than 30 minutes, or
engines other than ORCA/CFOUR) can run on the lab workstation. BASE deposits
each job in a **Google Drive folder the user assigns**; the workstation's
[job runner](https://github.com/ProfJJK-CoChem/cochem_workstation_job_runner)
picks it up, runs `cochem-cli run` on its own fast local disk when its owner is
not using the machine, and writes the status and a results archive back into
the same folder. No folder is hard-coded anywhere.

## For students (no code)

1. Choose **Calculation Environment → Lab workstation (Drive folder queue)**.
2. In the **Lab workstation** panel enter
   * **Drive folder** - either the path of a folder synced by Google Drive for
     desktop on this computer (for example `G:/My Drive/CoChem workstation`),
     or, in a Codespace, the folder's `https://drive.google.com/drive/folders/...`
     link;
   * your **Student ID**; optionally cores (`auto` = whatever the workstation
     can spare), memory and a time limit;

   then press **Assign folder**. BASE creates `inbox/`, `jobs/` and
   `cochem_workstation_folder.json` (your ID) inside it. Give the folder to
   your instructor (share it with the workstation owner) once.
3. Set up the calculation as usual and press **Send to lab workstation**. The
   app is not blocked: the job may wait while the workstation owner uses the
   machine and resumes automatically.
4. The panel lists your workstation jobs with their state (QUEUED, RUNNING,
   PAUSED, ...), queue position, any resource adjustments the workstation made,
   progress and the latest output. It checks every minute and imports verified
   results automatically; **Retrieve results** and **Cancel job** are also
   available.

## What is verified

A returned result is accepted only if

* the runner's `_runner/job_summary.json` names this exact submission and the
  SHA-256 of the submitted `calculation.json`;
* the archive matches the SHA-256 published in `status.json` (a half-synced
  download is retried, never imported);
* every BASE artifact in `base_output/` matches its `.sha256` sidecar (only
  transient scratch files or files the workstation reports as too large may be
  omitted, and they are listed); and
* BASE's own execution record says `EXECUTION_VERIFIED` (or
  `T9_FALLBACK_VERIFIED`). A workstation "COMPLETED" alone is not acceptance.

The same scientific validation as the HPC route applies before submission
(`validate_portable_calculation`): open-shell ORCA still needs a portable T9
active space, and machine-local file paths are never sent. Periodic QE inputs
and READ/R2/T9 evidence bundles are not supported on this route yet; use the
HPC or local route for those.

## Codespaces: reaching a Drive folder link

A Codespace has no Google Drive for desktop, so a folder link is used through
the Google Drive API. The instructor provides one of these Codespaces secrets:

* `COCHEM_WORKSTATION_DRIVE_CREDENTIALS` - a Google service-account key
  (JSON). Service accounts cannot own files in a personal *My Drive*, so put
  the workstation folders in a **shared drive** and add the service account to
  it as a Content manager. The workstation syncs that shared drive with Google
  Drive for desktop.
* `COCHEM_WORKSTATION_DRIVE_TOKEN` - a short-lived OAuth access token (for
  testing).

Credentials are read from the environment only; they are never written into
BASE settings, requests or results.

## Settings and environment

* Saved in `<artifacts>/StudentSetup/workstation-queue.json`
  (schema `cochem.workstation-queue/1`).
* `COCHEM_WORKSTATION_FOLDER` and `COCHEM_WORKSTATION_STUDENT` override the
  saved folder and ID (an instructor can set them as Codespaces variables).
  TOPOS and TORQ read the same variables, and TOPOS also falls back to the
  folder assigned here.

## Code

* `src/cochem_base/interfaces/workstation_queue.py` - settings, local-folder
  and Drive API transports, submission, status, verified retrieval.
* `src/cochem_base/interfaces/workstation_panel.py` - the app panel.
* Tests: `tests/base/test_workstation_queue.py` (including a loopback Drive
  API server that checks the service-account JWT signature),
  `tests/ui/test_workstation_panel.py`, `tests/ui/test_workstation_route.py`.
  A genuine end-to-end run (BASE client -> runner -> real `cochem-cli run`
  with PySCF -> BASE verification) lives in the runner repository
  (`tests/test_integration_cochem_base.py`).
