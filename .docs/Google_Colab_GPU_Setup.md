# Optional Google Colab GPU calculations

**Current status: student Colab calculations are unavailable while the
submission and result-verification path is completed.** Configuring a secret
alone does not enable a working GPU route. Keep using the prepared calculation
route specified by your instructor. ORCA and CFOUR remain optional and strongly
recommended; their availability is checked separately.

## For students

A GPU is a processor that can accelerate some calculations when the chosen
engine supports it. A faster computer does not make an unsuitable method more
accurate. Codespaces opens CoChem's interface; Actions can coordinate a job;
Colab would run a supported GPU calculation on another computer.

You do not need a Google API token, terminal commands, Python code, a manual
module installation or a notebook setup procedure. Your instructor prepares
provider access. Use **Help search** for **GPU** or **Colab** to read the current
explanation. If your assignment needs an unavailable route, keep your molecular
file and settings and show your instructor the displayed message. Do not change
the engine or method simply to make a run button available.

## Instructor: preserve the two credential tiers

| Credential | Where it belongs | Purpose |
| --- | --- | --- |
| Master Google/Colab credential | Instructor's protected workstation only | The local relay accesses the instructor's Colab runtimes. |
| Scoped student dispatch secret | Private access controller, then encrypted project Actions and Codespaces stores | Authenticates a limited data-only student request. It cannot call Google directly. |

Keep the existing App and working credentials. Never place the master Google
credential, its token file, or the App private key in a student project,
notebook, issue, workflow input or chat. A dispatch secret shared with students
cannot by itself prove that a result came from the provider; provider-result
verification is a separate requirement.

## Instructor: configure the existing dispatch secret in GitHub

These steps prepare credential delivery. They do not certify a provider or
bypass the current admission hold. If the named settings already exist, verify
their metadata and preserve them; do not create another App or replacement key.

1. Open the lab **organization → Settings → Secrets and variables → Actions**.
   Under **Secrets**, locate the existing scoped dispatch secret. The existing
   integration uses the logical name `COLAB_OFFLOAD_DISPATCH_TOKEN`; retain the
   actual secret name already chosen by your lab.
2. For an organization secret, choose **Repository access → Selected
   repositories** and include the private access-controller repository. The
   controller must receive this secret during its enrollment workflow. Use
   **Save** or **Update secret** as appropriate. Keep the secret value in the
   secure administrator interface; never paste it into documentation or chat.
   If the secret already exists directly under the private controller's
   **Settings → Secrets and variables → Actions → Secrets**, that repository
   secret is also supported; do not duplicate it unnecessarily.
3. Open the private controller's **Settings → Secrets and variables → Actions
   → Variables**. Set or verify `COCHEM_COLAB_ACCESS_SECRET` to the **name** of
   that existing scoped secret. This variable contains a label, not the secret
   value. The controller workflow resolves the encrypted secret by that name.
4. Complete the normal [App and project enrollment setup](Personal_Project_App_Deployment.md).
   The controller uses its existing authorized App to save encrypted project
   credentials. Organization secrets do not automatically reach a student's
   personally owned repository, even when that student belongs to the lab.
5. Verify delivery separately in the student's private project:
   **Settings → Secrets and variables → Actions** contains the controller-owned
   secret and the `COCHEM_COLAB_ACCESS_SECRET` selector. The repaired controller
   creates a unique owned Actions secret name; preserve that generated name.
   **Settings → Secrets and variables → Codespaces** contains the scoped
   `COLAB_OFFLOAD_DISPATCH_TOKEN` secret. Actions and Codespaces have separate
   stores. Inspect names and status only; students must not handle the values.
6. Follow the existing Codespaces permission/enrollment instructions when opening
   the prepared student project. Preserve existing uploads and results before
   workspace changes. Credential delivery can be successful while the Colab
   execution route remains unavailable.

If GitHub refuses a setting or delivery operation, resolve the actual
administrator permission or controller-run restriction. An HTTP 403 does not
establish that a credential is invalid. A student's Actions allowance and the
organization's private-controller allowance belong to different accounts.

## Execution connection and release checks

The selected successor uses an issue queue inside each enrolled private student
project. Its Actions workflow can request issue-write permission for that same
project; the receiver must independently have authorized access to that
project. The existing student repository token cannot write the separate
private controller's issue queue. This successor is the selected design; it is not yet implemented or qualified.
The current App setup does not grant Issues or Actions permissions implicitly.

Before enabling the option for a class, the maintainers must demonstrate:

- Verified current student/project/enrollment/source identity and a durable,
  replay-safe request, with no shell commands supplied by students.
- A supported engine-specific GPU task, actual device/backend evidence and
  native outputs. ORCA, CFOUR and xTB do not become GPU-accelerated simply by
  running on a Colab machine. Never substitute another engine silently.
- Monitoring, job-specific cancellation with terminal confirmation, verified
  result and artifact retrieval, downloads, restart and preservation of data.
- A visible unavailable state when the provider cannot run the requested task.
  Existing CPU and other prepared routes continue independently.
- Bounded execution and quota reservations. A local CU estimate is not an
  authoritative Google billing measurement.

The instructor workstation also needs the exact relay kit, required overlays
and parity reference files. Keep their source revisions and original scientific
provenance. Missing files or failed parity checks must hold startup; do not
invent reference results or reduce scientific thresholds.

Use the [student pilot](Student_Deployment_Pilot.md) and the
[Tuesday–Friday class guide](BEGINNER_FIRE_TEST_2026-11-03.md) to record actual
outcomes. An unrun GPU check remains unrun. Successful secret delivery or a
historical campaign report does not establish student readiness.
