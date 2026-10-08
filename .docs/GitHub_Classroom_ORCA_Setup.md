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

The primary course arrangement uses **personal-owned private BASE projects**
with the [instructor-managed GitHub App](Personal_Project_App_Deployment.md).
Students authorize their selected project; the instructor's private controller
supplies its encrypted access credentials automatically. Chemistry jobs consume
the project's owner's personal Actions allowance. Students do not handle tokens.

[Classroom50](https://classroom50.org/) manages the course's organization, roster,
assignment collection and feedback. Its organization assignment repositories and
the student's personal research project are separate: accepting an organization
assignment does not transfer ownership, billing or secrets to a personal account.
The alternate organization-owned calculation arrangement is documented below.

The Classroom50 steps below follow its [official web teacher guide](https://github.com/foundation50/classroom50/blob/main/wiki/Web-Teacher-Guide.md),
[student guide](https://github.com/foundation50/classroom50/blob/main/wiki/Web-Student-Guide.md)
and [assignment template guide](https://github.com/foundation50/classroom50/blob/main/wiki/Assignment-Templates.md).
Classroom50 login and grading credentials are separate from CoChem's privately
configured archive readers.

For private TOPOS, TORQ and other module source, also follow
[Ecosystem modules setup](Ecosystem_Modules_Setup.md). Module source uses
the private `COCHEM_SOURCE_ACCESS_SECRET` binding in Actions; it does not
replace the separate ORCA archive binding. Leave **Send secrets and variables to workflows from fork pull
requests** disabled. The course's manual calculation workflows do not need it.

## Student quick start

Sign in with your own GitHub account and follow your instructor's project and
Classroom50 enrollment links. Create an independent **Private** project from the
public BASE template with your personal account as **Owner**. Follow the
[complete student enrollment steps](Student_Research_No_Code.md#start-your-workspace):
open the initial BASE dashboard, use **Lab access** to authorize the instructor's
App for this selected project, request access and wait for approval. The
[instructor deployment guide](Personal_Project_App_Deployment.md) explains the
controller configuration. Use your private research project for its Codespace
and calculation requests.

1. After successful enrollment, stop the initial Codespace and select **Code →
   Codespaces → Create codespace** to create a **fresh Codespace**. Wait for
   automatic BASE/module setup; no organization-secret inheritance or cross-owner
   repository-declaration authorization is assumed.
2. Open the private **CoChem Voilà dashboard** on port **8866** from VS Code's
   **Ports** panel. No notebook cell, terminal command or separate module
   installation is required.
3. Upload your own Avogadro 2 monomer or complex XYZ files inside BASE. Preserve
   each original, assign its role, and declare its charge and multiplicity.
4. Choose **GitHub Actions** as calculation environment and your private
   research project. Select the available ORCA method and operation,
   then submit through BASE's **Run with GitHub Actions** button.
5. Use BASE's status and cancellation controls. When the job finishes, retrieve
   its verified result package through BASE and inspect the scientific report,
   structures, HDF5/Hessian records and available diagrams.
6. Save your report through VS Code's Source Control interface and follow your
   course submission instructions. Stop the Codespace when finished.

The [full student research guide](Student_Research_No_Code.md) explains the
interface, monomer assembly, provider operations, scientific interpretation and
update controls. You do not install ORCA on your laptop or Codespace for this
route, and you do not enter the instructor's archive token.

### Verify the course calculation environment

The instructor checks the archive and physical engine acceptance once for the
course. Your actual submitted job independently verifies its own download,
engine identity, resources and physical execution. A failed or incomplete run
is displayed as such; it is not a completed scientific result.

### Run your assignment calculation

BASE submits a hash-bound data-only request directly. You do not edit JSON,
commit a job file, or open GitHub's workflow form. Installation and calculations
run on the selected Actions worker; BASE monitors the actual request and safely
retrieves its associated results. The native HF/STO-3G water examples are
installation checks, not a vdW research protocol.

Compatible updates are handled inside BASE. The student's assignment and
uploaded structures remain separate from the approved canonical scientific
worker source and module revisions used for each run.

## Instructor setup

Complete this section once for the archive, then repeat the repository access
and test steps for every course calculation repository.

### 1. Choose where course calculations run

| Arrangement | Setup responsibility | Credential consequence |
| --- | --- | --- |
| Personal-owned private BASE project — primary route | Instructor configures the private App controller once; student consents to the selected project. | App provisions encrypted project credentials and generic binding variables. Organization secrets do not inherit into the personal project. |
| Organization-owned private assignment — alternate route | Instructor grants selected-repository organization secret and variable policies. | Actions uses that organization's allowance. Template files do not copy access grants. |
| Instructor-controlled calculation service | Instructor controls scientific execution and shares permitted results. | Chemistry uses the instructor's calculation allowance rather than the student's personal allowance. |

Students should never receive or copy the instructor's PAT value. A person able
to edit and execute a project workflow can use its credential access, so enroll
only permitted users and restrict readers to the approved source and assets.
The App's private controller remains instructor-writable, validates membership
and consent, and installs access only into approved private projects.

Keep the archive private, obtain it through the official ORCA distribution
process, and grant access within your institution's applicable ORCA terms.
This guide does not grant permission to redistribute a licensed archive.

Before enrolling a class, check the organization's Actions policy, billing or
included minutes, spending controls and runner limits. Each fresh job downloads
the archive and builds its runtime. Pilot one student repository before
starting many simultaneous jobs.

### Use students' personal Codespaces and Actions allowances

Codespaces and Actions have separate allowances. A student-owned Codespace and
chemistry job in a personal-owned private project use the student's own account.
The instructor's private App-enrollment and Classroom50 administration jobs use
the organization allowance. This does not make private Actions usage unlimited;
check active Education benefits, billing limits and remaining usage.

| Service | Account whose allowance is used |
| --- | --- |
| User-owned Codespace opened from an organization assignment | The student's personal account. Verified GitHub Education students currently receive up to 180 core-hours per month; a two-core Codespace uses two core-hours for each running hour. Check the actual allowance in the student's billing page. |
| GitHub-hosted chemistry job in a personal-owned private project | The personal account owning that project; verify its current Education/Pro entitlement and usage limit. |
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
4. Have the student check personal **Settings → Billing & Licensing** for their
   private project's Actions limits and usage. For private App/Classroom50
   administration, also review existing organization budgets and included usage.
   A student's remaining allowance does not cover organization-owned jobs.

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
   an archive-access credential**, or replace it with the ORCA reader:
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

### 5. Bind private access to the calculation project

For the primary personal-project route, follow the
[GitHub App deployment guide](Personal_Project_App_Deployment.md). The instructor
configures authorized readers and a private controller; the student authorizes
the App on the selected project. The controller provisions encrypted project
secrets and sets these variables privately:

| Variable | Privately configured value |
| --- | --- |
| `COCHEM_ORCA_ACCESS_SECRET` | Stored label of the ORCA archive reader |
| `COCHEM_CFOUR_ACCESS_SECRET` | Stored label of the CFOUR archive reader |
| `COCHEM_SOURCE_ACCESS_SECRET` | Stored label of the private source reader |

The labels and credential values are not entered in public source. Public YAML
resolves the mapped secret at runtime. Students do not create PATs, copy secret
values or repair setup by running terminal commands. A missing licensed binding
leaves that engine unavailable while BASE's independent capabilities remain usable.

For an alternate organization-owned assignment, an organization owner can create
an Actions secret with an arbitrary private label and set the matching binding
variable to that label. Under **Settings → Secrets and variables → Actions**,
grant both secret and variable to **Selected repositories**. Add each newly
created private assignment to both policies. There is no need to create duplicate
repository secrets when organization policies already cover that repository.

Organization-level private-repository secrets require a supported plan such as
GitHub Team. They cannot inherit into repositories owned by student accounts.
Template files do not copy settings. A same-name repository secret overrides an
organization value; correct a stale private binding instead of printing it.

The built-in project `GITHUB_TOKEN` cannot automatically read separate private
assets. Team membership and Read access do not expose secret values or expand
that token's repository scope. Keep reader permissions narrowly scoped.

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
| Classroom50 grading works but ORCA download fails | `CLASSROOM50_SERVICE_TOKEN` supports collection/grading. CoChem uses its separate private archive binding and an approved distribution manifest. |
| `Contents` is visible alongside Actions and Deployments | Select **Contents** directly under **Add permissions**, then choose **Read-only**. There is no additional menu step. |
| Organization is absent from Resource owner | Confirm the token owner belongs to that organization and its policy allows the requested fine-grained token. Ask an organization administrator to provision access; do not select an unrelated owner. |
| Token is Pending | Have the organization owner approve it. A pending token does not provide the required private repository access. |
| ORCA archive access unavailable | Check App project enrollment and its private `COCHEM_ORCA_ACCESS_SECRET` binding; for organization-owned jobs, check matching selected-repository secret/variable policies. |
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
