# Classroom50 and ORCA on GitHub Actions: instructor and student setup

This guide prepares a private ORCA 6.1.1 archive for a CoChem-BASE repository,
then verifies that GitHub Actions can run real serial and parallel calculations.
Start with the student steps if your instructor has already prepared the course.
The browser computer can run Windows, macOS or Linux: the calculations in this
guide run on GitHub's Ubuntu Linux x86-64 runner.

ORCA and CFOUR are **optional, strongly recommended** engines. BASE's ingestion,
inspection, setup and available free-engine calculations work without them. A
missing licensed engine or failed optional installation disables its dependent
calculations. A dedicated ORCA or CFOUR calculation still requires its selected
engine and fails honestly when that engine is unavailable. For the separate
CFOUR archive, access credential and compatibility requirements, see the
[CFOUR setup guide](CFOUR_Actions_Setup.md).

The primary course arrangement is **[Classroom50](https://classroom50.org/) with
an instructor-managed GitHub organization**. Classroom50 is the free,
open-source alternative to GitHub Classroom supported by the Fifty Foundation.
It creates and manages the course's GitHub assignment repositories. CoChem's
GitHub Actions workflows install ORCA and run the chemistry inside those
repositories. The instructor provisions archive access; students do not need
individual archive-read tokens when that organizational setup is complete.

The Classroom50 steps below follow its [official web teacher guide](https://github.com/foundation50/classroom50/blob/main/wiki/Web-Teacher-Guide.md),
[student guide](https://github.com/foundation50/classroom50/blob/main/wiki/Web-Student-Guide.md)
and [assignment template guide](https://github.com/foundation50/classroom50/blob/main/wiki/Assignment-Templates.md).
Classroom50 login and grading credentials are separate from CoChem's narrowly
scoped `PRIVATE_ORCA_ASSET_CREDENTIAL`.

For private TOPOS, TORQ and other module source, also follow
[Ecosystem modules setup](Ecosystem_Modules_Setup.md). Module source uses
`COCHEM_SOURCE_READ_TOKEN` in Actions; it does not replace the ORCA archive
credential. Leave **Send secrets and variables to workflows from fork pull
requests** disabled. The course's manual calculation workflows do not need it.

## Student quick start

Your instructor supplies a **Classroom50 assignment acceptance link**. Sign in
at <https://classroom50.org/> using **Sign in with GitHub**, accept the course
organization invitation, open the assignment link, and select **Accept
assignment → Open repository** after its setup finishes. Classroom50 creates
your assignment repository in the instructor's organization. If you see **Not a
member yet**, ask the instructor to add you to the roster before trying again.

Use the repository you just accepted, unless your instructor specifies a
separate managed calculation repository. You do not need to download ORCA to
your laptop for the Actions route.

### Open the CoChem interface

If your instructor enables Codespaces for the course:

1. In **your accepted assignment repository**, select the instructor-approved
   branch, then **Code → Codespaces → Create codespace on [approved branch]**.
   Confirm GitHub identifies **your personal account** as the payer when the
   course uses your student allowance. Authorize the requested read access to
   the course's module repositories. Resume an existing course Codespace only
   if its repository permissions have not changed; new permissions require a
   new Codespace.
2. Wait for container creation and the terminal setup tasks to finish. The
   repository's `.devcontainer` configuration installs the dashboard, completes
   its setup and starts Voilà automatically; the first creation takes longer
   than reopening an existing environment.
3. Open the editor's **Ports** tab. Find **8866 — CoChem Voilà dashboard** and
   select **Open in Browser**. Keep the port's visibility **Private**, and stay
   signed into your approved GitHub account. Do not make the dashboard public.
4. If the dashboard did not start after setup completed, open a terminal at the
   assignment repository root and run:

   ```bash
   python3 scripts/hosted_dashboard.py start
   python3 scripts/hosted_dashboard.py check
   ```

   `start` reuses an already healthy dashboard. `check` verifies that its page
   rendered; it does not run a chemistry calculation. If setup is missing or a
   command reports an error, retain that message and contact the instructor
   before repeating installation. Then return to **Ports → 8866 → Open in
   Browser**.

Alternatively, open the interface on your own computer. Install Python 3.12,
then clone **your assignment repository** using the HTTPS URL under its
**Code → Local** menu. Open a terminal in that checkout. In Windows PowerShell:

```powershell
.\Launch_CoChem_Windows.bat --native
```

On Linux or macOS:

```bash
./Launch_CoChem_Mac_Linux.sh
```

The launcher installs the interface dependencies and starts Voilà. Follow its
printed browser address if a browser does not open automatically. The launcher's
`--check` option only checks prerequisites; it does not install, open or test the
GUI. See the [source-launch instructions](../README.md#launch-the-interface-from-source)
for more detail, using the assignment checkout rather than cloning upstream
BASE. No local ORCA installation is required to export Actions jobs.

Codespaces hosts the interface while Actions hosts the chemistry. The Codespaces
configuration and lifecycle have local validation; an actual hosted Codespace
rebuild remains a separate course deployment check.

### Verify the course calculation environment

1. In the open CoChem setup screen, choose **GitHub Actions** as the calculation
   environment, enter your course repository as `OWNER/REPOSITORY` and the
   instructor-approved branch, and follow the guide link. This choice exports
   portable requests; it does not install ORCA on your interface computer.
2. Check that the repository contains `scripts/orca-distribution.json` and
   `.github/workflows/orca_acceptance.yml` on its default branch. If this is a
   new course copy, wait for the instructor to finish setup before starting it.
3. Open **Actions**. Enable workflows if GitHub asks and the instructor has
   approved this copy. Select **ORCA private archive access**, choose **Run
   workflow**, select the approved branch, and run it once. A green check proves
   access and checksum verification only. If the workflow or Run workflow
   button is absent, use the troubleshooting table below.
4. Select **ORCA 6.1.1 calculation acceptance → Run workflow**, choose the same
   approved branch and run it once. The job installs MPI, verifies ORCA,
   prepares BASE, and calculates water with one and two processes. Keep the
   Actions page open; initial installation includes compilation and can take
   tens of minutes. Avoid starting duplicate runs.
5. Open the completed run. The calculation step must pass. At the bottom of the
   run's summary, download the artifact named
   `orca-6.1.1-acceptance-<run-id>-<attempt>`. The run ID is the number in
   the run page's URL. Download and retain the evidence promptly: the workflow
   requests **14 days** of artifact retention. Keep the run URL with your lab
   notes. Archive-access success alone is not a successful chemistry test.
6. Confirm the calculation evidence reports normal ORCA termination, SCF
   convergence and serial/parallel energy agreement within `1e-8 Eh`. The
   calculation inputs, engine outputs, acceptance JSON and `results.xml` are
   retained for inspection. Ask the instructor to review a red run before
   retrying or changing the installation.
7. Follow your assignment's calculation instructions after acceptance passes.
   The installation test is a small HF/STO-3G water calculation; its success
   does not validate every method, molecule, or a downstream module's science.

Students using instructor-provisioned access normally do not create a token.
If you cannot see repository Settings, send the instructor the run URL and
error text. Do not send a token, an archive download URL containing credentials,
or the ORCA binary in a discussion, issue or chat.

### Run your assignment calculation

Use this route after the repository's ORCA acceptance has passed. The acceptance
workflow checks the installation; the **ORCA calculation** workflow runs your
submitted molecular calculation.

1. Open the CoChem interface and select **GitHub Actions** as the calculation
   environment. Enter the course repository and approved branch in its setup
   panel. Open **No Code Matrix**, enter your molecule's XYZ coordinates,
   charge and multiplicity, choose **ORCA**, and select the method and basis
   requested by your assignment. Set **Project Name**, **Actions operation**
   (Single point, Optimization, Harmonic frequencies, or Optimize + harmonic
   frequencies), and **Calculation timeout (s)**. Coordinates
   are in ångströms. Check that the charge and spin state describe the intended
   molecule before exporting.
2. Select **Prepare GitHub Actions job**. Download the generated
   `<project>-orca-job.json` file using **Download ORCA job JSON**. This export contains the calculation settings,
   not an ORCA executable, a token, or paths to your laptop's installation.
   Preparing the file does not start a calculation on either your laptop or
   GitHub.
3. Open the approved course calculation repository in GitHub. If `jobs/` does
   not exist yet, select **Add file → Create new file**, enter
   `jobs/water-orca-job.json` as the complete filename, and paste the complete
   contents of the downloaded JSON into the editor. GitHub creates the folder
   when you commit the file. Once `jobs/` exists, you can open that folder and
   use **Add file → Upload files** for later exported requests. Commit using
   the course's review procedure. If review is required, wait for the input to
   reach the instructor-approved branch before starting a job.
4. Select **Actions → ORCA calculation → Run workflow**. Select the approved
   branch containing the committed input. In **job_file**, enter its repository
   path, for example `jobs/water-orca-job.json`. Do not enter a laptop file path,
   a URL, or the contents of the JSON file. Leave **cores** at `2` and
   **maxcore_mb** at `512` unless your assignment specifies another supported
   value. Start one run.
5. Open the run and follow its setup and calculation steps. The workflow starts
   a fresh runner, installs the approved ORCA/MPI runtime and creates a registry
   for that runner. A successful calculation must finish the actual engine
   execution and result validation steps.
6. Download `orca-calculation-<run-id>-<attempt>` from the run's summary.
   Download it promptly and save it with your lab records: this workflow
   requests **14 days** of artifact retention. In `student-job/`, inspect `calculation-report.json`, the original
   `submitted-job.json`, and the validated settings in `validated-job.json`.
   The `calculation/` directory contains ORCA input/output and `result.json`;
   `complexes.h5` preserves the scientific record. Keep these with the run URL.
   Read the final energy in hartrees and confirm the requested operation
   converged; an error log or partial output is not a completed result.
7. If a job fails, retain its evidence and show the instructor the run URL and
   the relevant error. Correct the input or configuration, commit the change,
   and create a new run so that each result remains tied to a specific input
   and source revision.

If your instructor uses a centrally managed calculation repository, submit the
exported JSON through the assigned course process. The instructor reviews it
and carries out the commit/run steps; you do not need that repository's token
or permission to change its workflows. Your computer does not need to remain
awake after GitHub accepts the workflow run.

For your first practice run, you can use the committed
`examples/jobs/water-single-point.json` directly as **job_file**, without a GUI
export. `examples/jobs/water-optimization.json` supplies a geometry optimization;
`examples/jobs/water-harmonic.json` adds harmonic frequencies after optimization.
These use HF/STO-3G water for learning the workflow; this method and basis do not
establish research-grade accuracy.

For equilibrium harmonic frequencies, use **Optimize + harmonic frequencies**
unless you already have an appropriately optimized geometry. **Harmonic
frequencies** evaluates the supplied coordinates; that selection does not
certify that the geometry is a stationary point.

The course workflow accepts embedded molecular ORCA jobs up to **50 atoms**, a
**256 KiB** JSON file, **1 or 2 processes**, **1–1024 MB per process**, and at most
**1800 seconds of calculation time**. The default is 2 processes and 512 MB per
process. Installation time is separate from that calculation timeout. These
limits do not make every 50-atom method/basis combination affordable: follow the
instructor's bounded examples. External Hessian/checkpoint files, Recipe R2
references, T9 recovery, periodic calculations and VPT2 are not accepted by this
student workflow. Unsupported scientific operations are rejected rather than
converted into a different calculation.

Save the input and the results requested by your instructor in the assignment
repository, and submit through the course's Classroom50 process. A green ORCA
workflow is a calculation result, not automatically a Classroom50 score or a
completed assignment submission. Automatic grading requires a separately
configured course grading rule.

## Instructor setup

Complete this section once for the archive, then repeat the repository access
and test steps for every course calculation repository.

### 1. Choose where course calculations run

| Arrangement | Setup responsibility | Credential consequence |
| --- | --- | --- |
| Private repositories in the course organization, with students authorized to obtain the ORCA archive | Instructor provides selected repositories with asset-read access and approved source/workflows. | Anyone able to edit and run workflows in a repository with a secret can potentially use that secret. Grant access only to people permitted to obtain the archive. |
| Instructor-managed calculation repository with reviewed changes | Instructor retains write control, reviews submitted inputs, starts or approves calculations, and shares permitted results. | Student-editable code must not execute in a job that receives an instructor-only credential. Keep credential-bearing jobs under instructor control. |
| Student-owned repositories | Each student configures an authorized asset source and its token, or the instructor deliberately provisions permitted access to that repository. | An organization secret is not automatically shared into a student's personal repository. A token cannot grant access its owner does not have. |

The first arrangement is convenient for a class when every participating user
is permitted access to the archive. Choose the second if credentials or
distribution access must remain instructor-only. Secret masking in logs is
not an access boundary against someone who can change the workflow or the code
it executes. A required review protects access only when the reviewer checks
the exact code and inputs that will run and GitHub's branch/environment controls
prevent bypass.

Keep the archive private, obtain it through the official ORCA distribution
process, and grant access within your institution's applicable ORCA terms.
This guide does not grant permission to redistribute a licensed archive.

Before enrolling a class, check the organization's Actions policy, billing or
included minutes, spending controls and runner limits. Each fresh job downloads
the archive and builds its runtime. Pilot one student repository before
starting many simultaneous jobs.

### Use students' Codespaces allowance and the organization's included Actions minutes

Codespaces and Actions have separate usage allowances. For this course,
students own their Codespaces; the organization does not sponsor Codespaces or
authorize paid Actions overages.

| Service | Account whose allowance is used |
| --- | --- |
| User-owned Codespace opened from an organization assignment | The student's personal account. Verified GitHub Education students currently receive up to 180 core-hours per month; a two-core Codespace uses two core-hours for each running hour. Check the actual allowance in the student's billing page. |
| GitHub-hosted Actions job in a private organization assignment | The organization that owns the repository, regardless of who clicks Run workflow. GitHub Team currently includes 3,000 standard-runner minutes per month shared across the organization, not 3,000 minutes for each student. Artifact storage also uses the organization's allowance. |

1. Open the course organization's **Settings → Codespaces → General**.
2. Under **Codespace ownership**, select **User ownership**. Enable Codespaces
   access for the intended members if the private repositories require it.
   If changing an existing organization-owned arrangement, tell students first:
   existing Codespaces can transfer to their accounts and start using their
   personal allowance.
3. Have the pilot student check the payer shown when creating a Codespace.
   Students can inspect their remaining usage in their own **Settings →
   Billing & Licensing**. Stop Codespaces when finished; retained Codespaces
   continue to use storage. Commit and push work before deleting one.
4. Open **Organization Settings → Billing & Licensing → Budgets and alerts**.
   Retain the course's $0 paid-usage limit for Actions and its enforced stop
   setting. Check existing budgets rather than creating overlapping limits.
   Review the organization's included usage before scheduling a class run.
   Jobs may stop when that shared allowance is exhausted; a student's remaining
   personal allowance does not cover an organization-owned repository's jobs.

Classroom50 does not change GitHub's payer rules. GitHub Education Team status
provides the Team plan's included Actions allowance; it does not make private
Actions runs unlimited. Keep course examples bounded and retain results within
the artifact retention period. See GitHub's [Codespaces ownership guidance](https://docs.github.com/en/codespaces/managing-codespaces-for-your-organization/choosing-who-owns-and-pays-for-codespaces-in-your-organization),
[student benefits](https://docs.github.com/en/education/about-github-education/github-education-for-students/about-github-education-for-students)
and [Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions).

### Set up the Classroom50 course and assignment

1. Use a GitHub organization on the **Team or Enterprise plan**, as required by
   Classroom50. Its official guide links the GitHub Education program through
   which verified educators can obtain Team-tier organizations without charge.
   Sign in at <https://classroom50.org/> with **Sign in with GitHub**, granting
   the application access to the course organization according to your
   institution's policy.
2. If the organization is new to Classroom50, choose **Set up new organization
   → Set up → Run setup**. Follow **Next: service token**, then **Done**.
   Classroom50 creates its private `classroom50` configuration repository and
   configures organization Actions, policies, Pages and an initial $0 Actions
   spending cap. Review those settings and available included minutes before
   assigning chemistry runs. An existing configured organization uses **Open**.
3. The service token requested by Classroom50 is
   **`CLASSROOM50_SERVICE_TOKEN`**, used by its grading/collection tools. Follow
   Classroom50's own service-token instructions for it. **Do not reuse it as
   `PRIVATE_ORCA_ASSET_CREDENTIAL`**, and do not replace it with the ORCA reader token:
   the two credentials have different repositories, permissions and purposes.
4. On **My classrooms**, select **Create classroom**, enter the course name,
   slug and optional term, and create the classroom. Add staff through the
   classroom's **Settings → Staff and roles** if needed.
5. Prepare a reviewed CoChem course template **inside this organization**, with
   the approved BASE source, `scripts/orca-distribution.json`, ORCA workflows,
   examples and this guide on its default branch. Mark it under GitHub
   **Settings → General → Template repository**. Do not put the ORCA archive or
   credentials in it. Classroom50 can grant the classroom team access to a
   private template in the same organization; a private template in a different
   organization is not the supported student copy route.
6. In Classroom50, open **Assignments → Assignment**. Fill in **Details**. Under
   **Repository setup → Start with a template**, choose **Template repository**
   and enter the course template's `OWNER/REPOSITORY`. Retain **Private**
   repository visibility in advanced settings. Choose the intended individual
   or group arrangement. Use the reviewed default branch; Classroom50 copies
   that branch unless **Include all branches** is selected.
7. Configure **Submission and grading** for the course. CoChem's ORCA workflows
   are manual calculation workflows; do not treat their success as a numerical
   assignment grade. Classroom50 documents a template-with-own-CI mode under
   **Autograded → Do not use the built-in autograder**, which leaves the
   template's workflows in place and collects submitters without scores. Use
   the appropriate course grading arrangement and inspect the resulting pilot
   repository before rollout. Select **Create assignment** when ready.
8. Open **Roster**. Use **Upload roster** for the class, or its adjacent menu's
   **Add member** for one pilot student. Students must receive and accept the
   organization invitation before accepting an assignment. On the assignment's
   submissions page, use **Share → Copy accept link** and distribute it through
   your course's normal channel.
9. Have the pilot accept the assignment. Add the newly created assignment
   repository to the ORCA secret's selected-repository access list as described
   below. Run the access check, physical acceptance and example calculation
   using the pilot's actual permissions. Only then roll out the remaining
   repositories; repeat secret access setup as each is created.

Classroom50 assignment creation copies source files; it does not grant the new
repository access to the ORCA archive secret. Template changes also do not
automatically replace all source in already accepted assignments. Classroom50
documents that `.github/` may be refreshed from the template on submission,
while starter code is not; keep workflow/script revisions compatible and test
course updates in the pilot before distribution. Do not add a template
`autograde.yaml` that conflicts with Classroom50's own generated autograder.

### 2. Obtain the correct archive and record its checksum

For this workflow use exactly:

```text
orca_6_1_1_linux_x86-64_shared_openmpi418.tar.xz
```

This is the ORCA 6.1.1 Linux x86-64 shared build for Open MPI 4.1.8. A macOS,
ARM64, Windows or differently linked MPI build is not interchangeable. The
archive is about 472 MB in decimal units and expands to about 16.25 GiB; the
installer also requires 4 GiB of free reserve. The workflow prepares storage on
its disposable GitHub-hosted Linux runner and checks actual space before
extraction.

If the file is on Google Drive, download the original `.tar.xz` file first.
Do not extract, recompress or rename its contents before hashing. On Windows,
open **PowerShell** and run, adjusting the folder if necessary:

```powershell
$orcaArchive = Join-Path $env:USERPROFILE 'Downloads\orca_6_1_1_linux_x86-64_shared_openmpi418.tar.xz'
Get-Item -LiteralPath $orcaArchive | Select-Object Name, Length
(Get-FileHash -LiteralPath $orcaArchive -Algorithm SHA256).Hash.ToLowerInvariant()
```

WSL is not required to calculate this hash. On Linux, WSL or macOS:

```bash
# Linux / WSL
sha256sum orca_6_1_1_linux_x86-64_shared_openmpi418.tar.xz

# macOS
shasum -a 256 orca_6_1_1_linux_x86-64_shared_openmpi418.tar.xz
```

Record the 64-character checksum independently before upload. The reviewed
CoChem archive has checksum
`a0bc1d6d2c3c00620367bbc5dbf2b3a7018abc92d1ff65f06cec46f75350b9be`.
Use that value only for that exact reviewed archive. A different checksum must
be investigated against the original download, not changed merely to make a
failed run green.

### 3. Upload a private Release asset

1. Create a **private** repository owned by the course organization, for example
   `YOUR-COURSE/CoChem-ORCA`, initialized with a README.
2. Open that repository's **Releases** page and select **Draft a new release**
   or **Create a new release**. Create tag `orca-6.1.1` and title `ORCA 6.1.1`.
3. In the release editor, attach the original archive in the area for uploading
   release assets. Publish the release and verify that the `.tar.xz` appears
   under **Assets**. A Git tag without an attached published release asset is
   insufficient.
4. Keep repository access limited to authorized users. Do not include the
   archive in the course source repository or an Actions artifact/cache.

The normal Git push limit is 100 MiB per file. Uploading through a repository's
**Add file** page or committing the archive into Git is the wrong path. Release
assets have a separate limit of less than 2 GiB per file; this approximately
472 MB archive fits. You do not need Git LFS for this procedure.

Worked example used for CoChem's integration:

| Setting | Value |
| --- | --- |
| Asset repository | `ProfJJK-CoChem/CoChem-ORCA` |
| Release tag | `orca-6.1.1` |
| Asset filename | `orca_6_1_1_linux_x86-64_shared_openmpi418.tar.xz` |
| SHA-256 | `a0bc1d6d2c3c00620367bbc5dbf2b3a7018abc92d1ff65f06cec46f75350b9be` |

This is a private worked example, not a public download service or a credential
shared with every CoChem user. A new course must arrange its own authorized
access or private mirror of the approved archive.

### 4. Create an archive-read token using the current GitHub controls

The token owner must already have access to the asset repository and must be
eligible under the organization's token policy. Creating a token does not add
repository membership or grant a license.

1. Open your personal GitHub **Settings → Developer settings → Personal access
   tokens → Fine-grained tokens → Generate new token**. The direct starting page
   is <https://github.com/settings/personal-access-tokens/new>.
2. Enter a descriptive name, for example `CoChem course ORCA reader`, and choose
   an expiration date suitable for the course and organization policy.
3. Set **Resource owner** to the organization owning the private archive.
   For the worked example this is `ProfJJK-CoChem`.
4. Under **Repository access**, choose **Only select repositories**, then select
   the **asset repository**, for example `CoChem-ORCA`. Selecting `CoChem-BASE`
   instead will not permit the archive download.
5. Under **Permissions**, click **Add permissions**. In the list containing
   **Actions**, **Contents**, **Deployments** and other entries, select
   **Contents** directly. Set the added Contents permission to **Read-only**.
   There is no extra “Repository permissions” submenu to find in this UI.
   Leave unrelated write and administration permissions unselected. GitHub may
   include the required Metadata read permission automatically.
6. Generate the token. If GitHub marks it **Pending**, an organization owner
   must approve it under the organization's personal access token settings
   before private downloads work.
7. Copy the token directly into GitHub's secret form in the next step. Do not
   paste it into the notebook, source files, terminal history or chat.

GitHub's [release-asset API documentation](https://docs.github.com/en/rest/releases/assets?apiVersion=2026-03-10#get-a-release-asset)
specifies **Contents: read** for private release-asset downloads. The
[permissions reference](https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens?apiVersion=2026-03-10)
uses “repository permissions” as a documentation category, not an instruction
to find an additional UI menu. **Actions** permission is not required to read
the ORCA release asset.

The [prefilled form for the worked example](https://github.com/settings/personal-access-tokens/new?name=CoChem%20ORCA%20asset%20reader&target_name=ProfJJK-CoChem&contents=read&expires_in=90)
sets the resource owner, Contents read permission and requested expiration.
You still need to select `CoChem-ORCA` and generate the token. Use your own
owner when hosting the archive elsewhere.

### 5. Make the secret available to the calculation repository

For one repository:

1. Open the repository that will run the calculations, such as a student's
   private course repository or the instructor's calculation repository.
2. Select **Settings → Secrets and variables → Actions → Secrets → New
   repository secret**.
3. Enter the name **`PRIVATE_ORCA_ASSET_CREDENTIAL`** exactly.
4. Paste only the token as its value, without quotes or a `Bearer` prefix, and
   select **Add secret**. To replace an existing value, use that secret's
   update control. Reissuing a token does not update a saved Actions secret.

For several authorized repositories in the same organization, an organization
owner can instead create an **Actions organization secret** with the same name
and grant it to **Selected repositories**. This is the primary route for this
course:

1. Open the course **organization's Settings**, not your personal account
   settings or the asset repository's settings.
2. Select **Secrets and variables → Actions → New organization secret**.
3. Name it **`PRIVATE_ORCA_ASSET_CREDENTIAL`** and paste the newly generated token as the
   value.
4. Under **Repository access**, choose **Selected repositories**, then select
   the instructor calculation repository or each authorized student calculation
   repository. Save the secret.
5. After creating a new course repository, return to this access list and add
   it. Run the pilot acceptance using an actual student account with the same
   rights as the rest of the class.

Check the organization's plan: GitHub documents that
organization-level secrets are not available to private repositories on GitHub
Free. Where that applies, configure a repository secret for each authorized
repository or use an appropriate organization plan.

**Secrets are not copied with template source code, and a new assignment or
fork does not automatically receive this secret.** Access to an organization
secret is controlled separately. If an old repository secret with the same
name exists, it can override the organization secret; replace or remove the
stale repository value. A personal student repository is outside the course
organization's secret policy.

The built-in `GITHUB_TOKEN` normally has access to its own repository. It does
not automatically read the separate private archive repository. Do not replace
this token with a broad account token merely to avoid configuring asset access.

### 6. Pin the approved distribution in the course source

Review `scripts/orca-distribution.json` in the course calculation repository.
Its `repository`, `release_tag`, `archive_name` and `sha256` must identify the
approved published asset. For a private mirror of the identical archive, change
the repository location and retain the verified filename, checksum and versions.
Keep `orca_version` at `6.1.1`, `openmpi_version` at `4.1.8`, `platform` at
`Linux`, and `architecture` at `x86_64` for this workflow.

Commit and review the manifest alongside the workflow. Do not turn an unverified
download response into the expected checksum. Repository variables are not a
substitute for reviewing and pinning the distribution manifest. Archive access,
physical acceptance and student jobs all read this same manifest; obsolete
`ORCA_ASSET_*` or `ORCA_RELEASE_TAG` repository variables do not configure any
of these routes.

Make sure the workflow files are on the repository's **default branch** before
expecting GitHub to show manual **Run workflow** controls. Configure Actions to
allow the reviewed workflows and required actions. The licensed acceptance
workflow does not run on untrusted pull requests. In **Organization Settings →
Actions → General → Fork pull request workflows**, leave **Send secrets and
variables to workflows from fork pull requests** disabled, and keep **Send
write tokens to workflows from pull requests** disabled. If a repository has
separate controls, keep the same settings there. Save the policy. Fork pull
requests can run permitted tests without these credentials; run private module
installation and ORCA jobs from the reviewed course branch. Never add
`pull_request_target` simply to make a fork receive this secret.

### 7. Run the access check, physical acceptance and course pilot

Follow the student steps above in one pilot repository before distributing the
course. These are separate checks:

| Check | What a pass establishes |
| --- | --- |
| ORCA private archive access | The job's credential can retrieve the selected archive and its SHA-256 is correct. |
| MPI installation | Pinned Open MPI 4.1.8 compiles and a genuine two-rank C++ collective executes. |
| ORCA provisioning | The complete approved archive is verified, extracted safely, and reports the required ORCA version. |
| BASE Stage 0 | The runner receives a fresh host-specific registry through all eleven setup phases. |
| ORCA calculation acceptance | Genuine serial and two-process water calculations converge through BASE; energies and published records agree. |
| Course pilot | Your approved student repository, permissions and assignment instructions work for an actual student account. |

A green BASE unit-test run or archive check does not replace the physical ORCA
acceptance. Keep the run URL, tested commit, artifact and instructor approval
in the course release record. Run a pilot again after changing the binary,
runtime, manifest, workflow, permissions or accepted BASE revision.

### 8. Maintain and retire access

Schedule token rotation before expiry. Save the replacement in the relevant
Actions secret, run the access and physical acceptance checks, then revoke the
superseded token. At the end of the course, remove repositories from secret
access, revoke credentials that are no longer needed, and review collaborator
access to the archive repository. Do not attach the licensed binary to result
artifacts. For a larger installation, a narrowly installed GitHub App can
replace the personal token after its access and workflow integration have been
tested; the current guide uses the fine-grained token route.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Classroom50 says Not a member yet or the assignment is unavailable | The instructor must add the student to the correct classroom roster and the student must accept the organization invitation. Classroom membership and the ORCA secret's repository access are separate setup steps. |
| Classroom50 grading works but ORCA download fails | `CLASSROOM50_SERVICE_TOKEN` supports Classroom50 collection/grading. CoChem requires the separate `PRIVATE_ORCA_ASSET_CREDENTIAL` and an approved distribution manifest. |
| `Contents` is visible alongside Actions and Deployments | Select **Contents** directly under **Add permissions**, then choose **Read-only**. There is no additional menu step. |
| Organization is absent from Resource owner | Confirm the token owner belongs to that organization and its policy allows the requested fine-grained token. Ask an organization administrator to provision access; do not select an unrelated owner. |
| Token is Pending | Have the organization owner approve it. A pending token does not provide the required private repository access. |
| Missing `PRIVATE_ORCA_ASSET_CREDENTIAL` | Add the secret to the repository actually running the job, or include that repository in the organization secret's access policy. |
| `release not found`, HTTP 404 or private asset access denied | Confirm the release is published with the exact archive asset. Check token owner, asset repository selection, Contents read access, expiry, organization approval and the saved secret value. Private GitHub resources can return 404 when access is missing. |
| Access check passes but full installation downloads a different location | Current access, acceptance and calculation workflows all read `scripts/orca-distribution.json`. Check that both runs use the same approved revision; update older workflow copies instead of changing obsolete repository variables. |
| SHA-256 mismatch | Stop the installation. Compare with the independently hashed original and check for the wrong asset or a changed upload. Do not disable verification. |
| Workflow or Run workflow button is absent | Confirm the workflow is present on the default branch, Actions is enabled, and your account can run it. Ask the instructor if the repository is managed centrally. |
| Workflow cannot check out the source | Check repository access and revision. A classroom copy must execute its own reviewed source. Reusing a private BASE action/workflow from another repository requires separate source-sharing authorization; the ORCA-only token does not grant BASE source access. |
| Out of disk space | The compressed archive expands to over 16 GiB and needs the install reserve plus build/setup space. Use the supported disposable Ubuntu runner and retain the disk preflight report. Do not delete workstation/HPC directories using hosted-runner cleanup commands. |
| MPI version mismatch, missing library or parallel failure | Use the exact Linux x86-64/Open MPI 4.1.8 archive and shared runtime. Retain the MPI build/provisioning report and failed ORCA output. A working serial calculation does not establish parallel readiness. |
| Run is queued, disabled or billing-limited | Check organization Actions policy, available runner capacity and usage/budget with the instructor. Repeatedly starting runs does not increase capacity. |
| Red chemistry acceptance after successful download | Download the evidence artifact and identify the failing input/output and error. Report its run URL and tested commit. Do not mark a skipped or failed calculation as passed. |
| Token changed but access still fails | Update the saved repository/organization secret, check for a stale repository secret overriding an organization value, and start a fresh run. |

## Local, WSL, macOS and HPC remain separate choices

Selecting Actions does not replace CoChem's other calculation environments.
For Linux or WSL, configure a compatible local ORCA/MPI installation. macOS
requires its corresponding official build and architecture. On HPC, use the
site's permitted binary and compatible MPI environment inside the allocation.
Native Windows users can use the Linux build inside WSL2, not directly in
PowerShell. Generate a fresh Stage 0 registry on each execution host; do not
reuse an Actions runner's paths or resource limits.

For technical provisioning details and recorded acceptance status, see
[ORCA Actions setup](ORCA_Actions_Setup.md). The classroom guide explains setup;
it does not certify platform or downstream-module acceptance that has not run.

## Official references

- [Classroom50 application](https://classroom50.org/)
- [Classroom50 official source and project identity](https://github.com/foundation50/classroom50)
- [Classroom50 quickstart](https://github.com/foundation50/classroom50/blob/main/wiki/Quickstart.md)
- [Classroom50 web teacher guide](https://github.com/foundation50/classroom50/blob/main/wiki/Web-Teacher-Guide.md)
- [Classroom50 web student guide](https://github.com/foundation50/classroom50/blob/main/wiki/Web-Student-Guide.md)
- [Classroom50 assignment templates](https://github.com/foundation50/classroom50/blob/main/wiki/Assignment-Templates.md)
- [Fine-grained token management and prefilled forms](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)
- [Permissions required for fine-grained tokens](https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens?apiVersion=2026-03-10)
- [Release asset download permissions](https://docs.github.com/en/rest/releases/assets?apiVersion=2026-03-10#get-a-release-asset)
- [Using secrets in GitHub Actions](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets)
- [Creating and managing releases](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)
