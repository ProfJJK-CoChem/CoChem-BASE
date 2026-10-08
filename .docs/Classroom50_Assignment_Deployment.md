# Deploy a CoChem assignment through Classroom50

For student-owned private projects using personal Actions minutes, follow the
[private student project guide](Private_Student_Projects.md). Organization secrets
do not transfer to personal repositories. Configure the private
`COCHEM_ORCA_ASSET_CREDENTIAL` and `COCHEM_CFOUR_ASSET_CREDENTIAL` variables to
select existing authorized secrets; their identifiers are never fixed in public
YAML. Any credential name in examples below is a placeholder, not the name of
an existing lab secret. Organization-owned course assignments remain a separate
route using organization Actions minutes.

Follow these steps as the instructor, then have **one enrolled student** complete
the pilot before sharing the assignment with the full class. The pilot verifies
the student's assignment permissions, a fresh Codespace, real Actions chemistry
and result retrieval. An instructor's successful upstream calculation does not
establish those student-specific permissions.

This guide uses the current [Classroom50](https://classroom50.org/) web app,
rather than the former GitHub Classroom interface. Its official teacher,
student and template documentation was checked on **2026-10-08 UTC**; references
are listed at the end.

## 1. Choose the course names and released source

The example configuration is:

| Item | Example |
| --- | --- |
| GitHub organization | `ProfJJK-CoChem` |
| Classroom name | `Computational Chemistry — Fall 2026` |
| Classroom slug | `chem-fall-2026` |
| Assignment name | `Lab 01 — Water energy and vibrations` |
| Assignment slug | `lab01-water` |
| Private course template | `ProfJJK-CoChem/CoChem-Lab01-Template` |
| Template/assignment default branch | `main` |
| Approved BASE source | Published release `v1.0.1` |
| Example student repository | `ProfJJK-CoChem/chem-fall-2026-lab01-water-USERNAME` |

Use your actual classroom and assignment names. The organization must have
GitHub **Team or Enterprise**; an eligible Education Team organization meets
that requirement. You must be an organization owner for its initial setup and
the permission grants below.

Before copying source, open the BASE [Releases page](https://github.com/ProfJJK-CoChem/CoChem-BASE/releases).
Use `v1.0.1` **after it is published**. A preparation branch or draft release is
not the released classroom baseline. Record the release's exact source commit.

Keeping assignments, the private template, TOPOS and TORQ in `ProfJJK-CoChem`
matches BASE's supplied Codespaces repository declarations. If you use a
different course organization, put its private template **inside that course
organization**. Codespaces cannot authorize cross-owner repositories through
`customizations.codespaces.repositories`: use approved same-owner module copies
with a reviewed manifest, or separately authorized user authentication. Merely
granting a student read access to an upstream module does not extend a
Codespace's default token to another organization. See
[private-module setup](Ecosystem_Modules_Setup.md#instructor-prepare-students-codespaces-access).

## 2. Set up the organization in Classroom50

Skip the initial setup if your organization already shows **Open** and its
settings/token checks pass.

1. Open <https://classroom50.org/> and select **Sign in with GitHub**. Authorize
   access to the course organization. If the organization restricts OAuth
   applications, its owner must approve Classroom50 for that organization.
2. On **Classroom 50 organizations**, select **Set up new organization**, find
   `ProfJJK-CoChem`, then select **Set up → Run setup**.
3. Read each setup result. Classroom50 creates the private `classroom50`
   configuration repository, installs its workflows, enables its GitHub Pages
   publication, and configures organization member privileges, Actions,
   rulesets and an initial **$0 paid Actions spending cap**. It reports settings
   that need manual correction. For an existing research organization, review
   these changes because organization settings also affect its other
   repositories. The course below leaves student assignment Pages disabled.
4. Select **Next: service token**. In the service-token form select **Set a
   token**, choose an expiry covering the course, then **Generate new access
   token**. GitHub opens a pre-filled token form.
5. Set its **Resource owner** to the teaching organization and **Repository
   access → All repositories** so that repositories created later are covered.
   Retain Classroom50's pre-filled permissions. Its current official integration
   guide specifies repository **Contents**, **Actions**, **Workflows** and
   **Administration** with read/write access, automatic **Metadata: Read**, and
   organization **Members: Read**. These permissions belong to Classroom50's
   management/collection service; the CoChem download tokens below remain
   separate read-only credentials.
6. Generate the service token. Paste it only into Classroom50's **Paste token**
   field and select **Save token**. Classroom50 stores it as
   `CLASSROOM50_SERVICE_TOKEN` in its `classroom50` repository. Select **Done**.
7. Open the organization's Classroom50 **Settings → Service token → Test
   token**. Require a passing result; use **View run** for missing-permission
   errors. Complete required organization token approval if applicable. Set a
   rotation reminder for its expiry. Do not place this token in an assignment
   or reuse it as an engine/source download credential.

## 3. Confirm payer and Actions policy

For this deployment, the student pays for their **personal Codespace** using
their available student allowance; the organization owns and pays for the
assignment repository's **Actions jobs**. Starting an Actions run from a
student account does not transfer its cost to that student's personal account.

1. In GitHub, open **Organization Settings → Codespaces → General → Codespace
   ownership** and choose **User ownership**. Review existing Codespaces before
   changing this setting: an ownership change can transfer them to students'
   personal accounts. Each pilot student must confirm their account is shown
   as payer when creating the Codespace.
2. Check **Organization Settings → Actions → General**. Allow the reviewed
   course workflows and the GitHub actions they use. If you use an allowlist,
   it must permit `actions/checkout`, `actions/setup-python` and
   `actions/upload-artifact`, plus Classroom50's required workflows. Follow
   Classroom50's setup diagnostics for its workflow-sharing settings.
3. Keep **Send secrets and variables to workflows from fork pull requests** and
   **Send write tokens to workflows from pull requests** **disabled**. The
   manual calculation route uses the student's own approved assignment branch
   and does not need either setting.
4. Open **Organization Settings → Billing & Licensing → Budgets and alerts**.
   Review the existing $0 paid-usage cap and stop behavior established during
   setup; do not add a duplicate budget. GitHub Team currently includes
   **3,000 standard-runner Actions minutes per month shared by the organization**,
   plus its plan's shared artifact storage. Verify the allowances shown for
   your account. The $0 cap allows included usage and stops paid overages after
   included usage is exhausted.
5. Have the pilot student check their own **Settings → Billing & Licensing**
   and active Education benefits for Codespaces. Allowance is measured in
   core-hours, so a two-core Codespace running for an hour uses two core-hours.
   Stop it when idle; retained Codespaces also consume storage. Student
   Codespaces allowance does not pay for organization Actions jobs.

Use one pilot to measure actual course setup time and minutes before scheduling
simultaneous class runs. Private licensed archives stay private; making
assignment repositories public is not a substitute for a course usage plan.

## 4. Create a dedicated private assignment template

Classroom50 copies a template's **default branch**, not an arbitrary tag. Use a
dedicated, fork-free template initialized from the released source. Freeze it
for this assignment so that early and late accepters receive the same starter
files. This also avoids cross-organization fork OAuth restrictions.

On Windows, open **Ubuntu/WSL2** for the following commands. These are Bash
commands, not PowerShell commands. Install `git`, `gh` and `python3` if missing:

```bash
sudo apt-get update
sudo apt-get install --yes git gh python3
gh auth login --hostname github.com --git-protocol https --web --scopes workflow
gh auth setup-git
```

Authorize the instructor's account with access to BASE and permission to create
repositories in the course organization. The extra `workflow` scope permits
uploading the copied Actions workflow files; it belongs to this instructor
setup login, not the read-only archive/source tokens. Do not paste a token into a command.
Use a new working directory and new repository names; these commands intentionally
fail rather than overwrite an existing clone or repository. Run them in order
and **stop if any command fails**:

```bash
mkdir cochem-lab01-preparation
cd cochem-lab01-preparation
git clone --branch v1.0.1 --depth 1 https://github.com/ProfJJK-CoChem/CoChem-BASE.git CoChem-BASE-v1.0.1
git -C CoChem-BASE-v1.0.1 rev-parse HEAD
mkdir CoChem-Lab01-Template
git -C CoChem-BASE-v1.0.1 archive HEAD | tar -x -C CoChem-Lab01-Template
cd CoChem-Lab01-Template
git init --initial-branch=main
```

Copy the printed upstream commit into the course setup record. `git archive`
copies tracked release files, including `.github`, `.devcontainer`, `.docs`,
source, tests, examples and licenses, without its Git history or local artifacts.
Do not copy ORCA/CFOUR executables, their distribution archives, registry files
from another machine, tokens or runtime environments into the template.

### Keep release verification manual in course copies

Upstream's `CoChem BASE bounded CI` performs three-platform release checks on
every `main` push. Running that release gate for every student lab commit uses
the organization's shared minutes unnecessarily. **Only in the course copy**,
open `.github/workflows/cochem_base_ci.yml` and replace its top-level trigger
block with:

```yaml
on:
  workflow_dispatch:
```

Remove that file's `push` and `pull_request` trigger entries; preserve its name,
permissions and **all jobs**. Do not change the upstream BASE workflow or the
manual ORCA, CFOUR, free-engine, or module calculation workflows. The instructor
can still start the complete bounded gate through **Actions → CoChem BASE
bounded CI → Run workflow** when reviewing a course update. This is a documented
course configuration change; record the template commit separately from the
upstream release commit. It does not constitute a new release certification.

### Add the assignment instructions and publish the template

1. Add `LAB01.md` with your molecule, methods, operations, due date, expected
   files and grading rubric. Keep BASE's README and guides, and add a prominent
   README link to `LAB01.md`.
2. For a first deployment, use the committed **neutral singlet water HF/STO-3G**
   examples. Request one single point, then optimization plus harmonic
   frequencies; this is an integration/teaching example, not a claim of
   research-grade accuracy. Specify `2` cores and `512` MB per core, with one
   run at a time. Follow the stricter engine-specific operation limits in the
   [ORCA](GitHub_Classroom_ORCA_Setup.md) and [CFOUR](CFOUR_Actions_Setup.md)
   guides.
3. Have students retain their submitted JSON, native input/output, final
   `calculation-report.json`, `result.json`, run URL, source commit, HDF5 record
   and harmonic Hessian bundle when applicable. Specify which small permitted
   result files go into their repository and which larger files are retained
   in your institution's approved storage.
4. Add `COURSE_SETUP.md` with the upstream tag/commit, the manual CI adaptation,
   approved engine manifests, assignment instructions and pilot observations.
   Include no credential values.
5. Keep `.devcontainer/devcontainer.json`, lifecycle scripts, workflows and
   distribution manifests compatible with the release. Do not add
   `.github/workflows/autograde.yaml`: Classroom50 owns that file when its
   built-in grader is enabled.
6. Commit and create the private template:

   ```bash
   git add .
   git commit -m "Prepare CoChem water lab from BASE v1.0.1"
   gh repo create ProfJJK-CoChem/CoChem-Lab01-Template --private --source . --remote origin --push
   git rev-parse HEAD
   ```

   If Git asks for a commit author, open GitHub **Settings → Emails**
   (<https://github.com/settings/emails>) to choose your verified commit email
   or the exact GitHub-provided private `noreply` address. Configure it only for
   this new repository, replacing both placeholders, then retry the commit:

   ```bash
   git config user.name "YOUR INSTRUCTOR NAME"
   git config user.email "YOUR VERIFIED OR GITHUB NOREPLY EMAIL"
   git commit -m "Prepare CoChem water lab from BASE v1.0.1"
   ```

   Continue to `gh repo create` only after the commit succeeds. If an existing
   CLI login refuses to push workflow files, refresh that instructor login with
   `gh auth refresh --hostname github.com --scopes workflow`, approve the browser
   request, then retry. Record the new template commit.
7. In GitHub, open the new repository's **Settings → General** and select
   **Template repository**. Verify `main` is its default branch and the
   `.github`, `.devcontainer`, `scripts`, `examples/jobs` and `.docs` directories
   are present. The repository is a fresh source copy, not a fork.

## 5. Create the classroom and one pilot assignment

1. In Classroom50, open the configured organization. On **My classrooms**,
   select **Create classroom**. Enter the example classroom name, slug and
   optional term, then create it. Add TAs through **Settings → Staff and
   roles** if needed. An unlisted classroom link is optional and does not make
   its published metadata private.
2. Open the classroom's **Assignments** page and select **Assignment**.
3. Under **Details**, enter the assignment name/slug and a short description
   pointing to `LAB01.md`. Choose **Individual** for the pilot. Each student
   receives their own repository. Use a group assignment later if your course
   explicitly requires shared work.
4. Under **Repository setup → Start with a template**, choose **Template
   repository** and enter `ProfJJK-CoChem/CoChem-Lab01-Template`. Leave **Include
   all branches** off. Keep **Feedback pull request** on if you want inline
   feedback.
5. Under the repository **Advanced settings**, choose **Private**, keep
   assignment **GitHub Pages: Off**, and retain student **Write (push)** access.
   Students do not need repository Admin for this individual assignment.
6. For the first pilot, use Classroom50's documented **own CI** arrangement:
   **Submission and grading → Grading: Autograded → Built-in autograder: Do not
   use the built-in autograder**. This preserves the template's own workflows
   without injecting Classroom50's grading workflow. It records submissions
   without automatically assigning scores. Grade the pilot manually using your
   stated rubric/LMS. The label `Autograded` here does not turn CoChem's
   calculation workflows into a numerical grader.
7. Choose **Submission type → Every push to the default branch** for the
   simplest browser-based pilot. Since the built-in grader is off and the
   course release gate is manual, committing lab work does not automatically
   launch those grading/release calculations. If you later choose tagged
   submission, give students explicit `submit/*` tag or `gh student submit`
   instructions.
8. Under **Schedule and access**, set your due date/time and verify its local
   timezone. Leave **Lock assignment** off when the student should accept.
   Leave the release date unset for an invitation-only pilot, or set it when
   you want the assignment listed for all enrolled students. A due date marks
   late submissions; it does not block pushes or replace **Close submission**.
9. Select **Create assignment** as an organization owner. Classroom50 grants
   its classroom team read access to a private template in the same
   organization. If a TA created the assignment and a permission warning
   appeared, an owner must save it before students accept.

Automatic scientific grading is a separate course feature. Enable the built-in
grader only after writing and testing assignment-specific checks and reviewing
their credential/resource access; a green calculation by itself is not a grade.

## 6. Enroll the pilot student and share the acceptance link

1. Open the classroom's **Roster**. Select the arrow beside **Upload roster →
   Add member**. Choose **Student**, enter the pilot's GitHub username, then
   select **Add member**.
2. If the student is already a member of the organization, enroll them through
   Classroom50's organization **Members** page: select the student, then
   **Actions → Add to classroom**. Inviting an existing organization member
   again does not enroll them in this classroom.
3. On **Roster → Share**, copy the **Classroom onboarding link**. Have the
   student accept their organization invitation and sign into Classroom50
   using their own GitHub account.
4. On the assignment's submissions page select **Share → Copy accept link**.
   Share it with the enrolled pilot through your normal course channel.
   Sharing a link alone does not enroll someone.
5. The student opens the link, checks the signed-in account, then selects
   **Accept assignment**. Wait for its setup checklist to finish; select **Open
   repository**. Record the actual `OWNER/REPOSITORY` and its source commit.

If acceptance says **Not a member yet** or **This assignment isn't available to
you**, correct the invitation/classroom enrollment rather than creating a fork.

## 7. Give the new assignment access to its approved Actions secrets

The three CoChem download credentials already working in BASE do not copy with
its source. Each new assignment must be authorized to use them.

| Actions secret | Purpose |
| --- | --- |
| `PRIVATE_ORCA_CREDENTIAL` | Read the approved private ORCA release archive |
| `PRIVATE_CFOUR_CREDENTIAL` | Read the approved private CFOUR runtime archive |
| `COCHEM_SOURCE_READ_TOKEN` | Read the approved private CoChem module source |

1. In GitHub, open the course **Organization Settings → Secrets and variables
   → Actions → Secrets**.
2. Edit an existing organization secret with the exact name, or choose **New
   organization secret** if that credential currently exists only in BASE.
   Enter its value only in GitHub's secret form using your securely retained
   original. GitHub cannot reveal a saved repository secret so it can be copied;
   if you no longer have the original, regenerate the approved read-only token
   and rotate its affected secrets.
3. Under **Repository access**, choose **Selected repositories**, select the
   newly accepted pilot assignment and any approved instructor testing
   repository, then save. Repeat for each credential the assignment uses.
   Selecting repositories in the token controls what it can **read**; selecting
   repositories in the organization secret controls what can **use it**.
4. Confirm each credential is unexpired, approved if the source organization
   requires approval, and has **Contents: Read-only** for its designated source
   repositories. GitHub's fine-grained token editor places **Contents** under
   **Permissions → Add permissions**. The archive/source readers do not need
   Actions write or Codespaces management permission.
5. As the instructor, check the assignment's **Settings → Secrets and variables
   → Actions** for an obsolete repository secret with the same name. A
   repository value overrides an organization value. Correct stale duplicates
   before testing.
6. Repeat the selected-repository grant each time a student accepts and
   Classroom50 creates a new assignment repository. Selecting the template
   alone does not grant access to future copies. Students should not create
   or enter instructor archive tokens.

Authorize only participants permitted to access the private module/engine
distribution. Anyone able to change and run code in a credential-bearing
workflow can use that credential. If archive access must remain instructor-only,
run licensed jobs in an instructor-controlled calculation repository and review
student input there; keep the assignment/Codespace as the interface and submit
permitted results through the course process. Secret masking does not substitute
for that access boundary.

ORCA and CFOUR remain **optional, strongly recommended** for BASE. An assignment
without their access must still open the dashboard and use installed free
engines; dependent local methods are unavailable. A job explicitly selecting
ORCA or CFOUR must require that engine and fail truthfully when it cannot be
provisioned. See the engine guides for their pinned archive identity and setup.

## 8. Give the student Codespaces and module access

Actions secrets do not automatically become Codespaces credentials. The
recommended Codespaces route uses the student's own authorized GitHub identity.

1. For modules required by the course, reuse Classroom50's classroom team in
   **ProfJJK-CoChem → Teams**. In each approved module repository, open
   **Settings → Collaborators & teams → Add teams** and give that course team
   **Read** access. Start with `CoChem-TOPOS` and `CoChem-TORQ`; do not grant
   write access merely to allow downloading.
2. Check the template's `.devcontainer/devcontainer.json` before acceptance.
   Its supplied `customizations.codespaces.repositories` already requests
   `contents: read` for those two repositories under `ProfJJK-CoChem`. Retain
   the container image, lifecycle scripts, volume, ports and VS Code settings.
   Add other same-owner repositories explicitly only when the course needs
   them and the student already has read access.
3. If permissions/configuration were corrected after acceptance, update the
   assignment's configuration as well. A changed template does not replace all
   starter code in an already accepted repository.
4. Have the student open **their accepted assignment repository**, choose the
   approved `main` branch, then **Code → Codespaces → Create codespace on main**
   (or **New with options**). Use the smallest supported machine, normally two
   cores. Confirm the payer is the student's personal account and authorize
   the requested module read permissions.
5. Create a **new** Codespace after a repository-permission change. Rebuilding
   an older Codespace does not apply newly requested repository permissions.
6. Wait for `postCreateCommand` setup to complete. Open **Ports → 8866 — CoChem
   Voilà dashboard → Open in Browser**. Keep visibility **Private**. The
   dashboard must render; a forwarded port alone is not acceptance.
7. In the Codespace terminal at the assignment root, check its dashboard:

   ```bash
   python3 scripts/hosted_dashboard.py start
   python3 scripts/hosted_dashboard.py check
   ```

   `start` reuses a healthy dashboard; `check` verifies the rendered page. Keep
   actual setup errors and resolve them before repeating installation.
8. If modules are required, check source access and perform the explicit
   supported install/verify steps from the [module guide](Ecosystem_Modules_Setup.md#student-check-your-source-access):

   ```bash
   git ls-remote https://github.com/ProfJJK-CoChem/CoChem-TOPOS.git HEAD
   git ls-remote https://github.com/ProfJJK-CoChem/CoChem-TORQ.git HEAD
   "$COCHEM_ARTIFACT_DIR/ui-env/bin/python" scripts/manage_modules.py install --modules topos torq --root "$COCHEM_ARTIFACT_DIR/Modules" --json
   "$COCHEM_ARTIFACT_DIR/ui-env/bin/python" scripts/manage_modules.py verify --modules topos torq --root "$COCHEM_ARTIFACT_DIR/Modules" --json
   ```

   A read check does not establish installation, and installation does not
   validate every module calculation. Keep the approved module pins. The seven
   explicitly deferred source modules and other catalog entries without usable
   packaging/adapters are not required for this pilot.

   Use BASE's managed `ui-env` Python for module commands; the VS Code
   interpreter setting does not change the terminal's default `python3`.

## 9. Run real chemistry in the accepted pilot repository

Perform installation acceptance once in the pilot before assigning many jobs;
the student should then personally run the small assignment calculation. Do
not start duplicate acceptance runs while a runtime installation is compiling.
ORCA provisioning builds the compatible MPI runtime and can take tens of
minutes before a small molecular calculation starts. Watch the existing run's
steps rather than starting another run because chemistry has not started yet.

1. As the instructor, check the pilot repository's **Actions** tab. Required
   workflows must be on its default branch. Enable Actions if its policy
   requires it. Confirm source manifests still point to the approved private
   asset releases; do not change checksums to silence errors.
2. For ORCA, run **ORCA private archive access** first if checking credential
   access, then **ORCA 6.1.1 calculation acceptance → Run workflow → main**.
   Require actual chemistry and serial/parallel agreement, not just archive
   download success. Retain `orca-6.1.1-acceptance-<run-id>-<attempt>`.
3. For CFOUR, run **CFOUR 2.1 calculation acceptance → Run workflow → main**.
   Require its physical calculation/derivative checks. This approved build
   tests OpenMP, not MPI. Retain
   `cfour-2.1-acceptance-<run-id>-<attempt>`.
4. If the course uses modules in Actions, run **CoChem ecosystem modules** with
   **action: install**, **modules: topos torq**. Inspect `installations.json` and
   require success for every selected module. For the supported handoff check,
   use **action: geometry_analysis**, the same modules and
   **xyz_file: examples/jobs/water.xyz**. Retain its artifact; a successful
   source-only fetch is not scientific execution.
5. Have the student run **Actions → ORCA calculation → Run workflow** in their
   own accepted repository, selecting `main` with:

   | Input | First practice value |
   | --- | --- |
   | `job_file` | `examples/jobs/water-single-point.json` |
   | `cores` | `2` |
   | `maxcore_mb` | `512` |

   For optimization followed by harmonic frequencies, use
   `examples/jobs/water-harmonic.json`. The ORCA job uses processes; enter a
   repository-relative job path, not a Windows path or pasted JSON contents.
6. If CFOUR is assigned, have the student run **CFOUR calculation** with
   `examples/jobs/cfour-water-single-point.json`, `2` cores and `512` MB per
   core. Use `examples/jobs/cfour-water-harmonic.json` for optimization plus
   frequencies. CFOUR's `cores` selects OpenMP threads in this build.
7. Open each completed run and require successful actual engine execution and
   result validation. Record the run URL, checked-out commit, job path and
   resource settings. A failed run's diagnostics are useful, but they are not
   accepted chemistry.

Each fresh licensed job provisions its own runtime and generates a fresh
Stage 0 registry. No ORCA/CFOUR installation is needed on the student's laptop
or Codespace for this Actions route. The browser can close after GitHub accepts
the run. Avoid repeating installation acceptance in every student repository;
each student's actual bounded calculation independently checks their runtime
access and execution.

## 10. Test the complete GUI export and result retrieval

After the committed example passes, have the pilot export and run one request
through the interface. This establishes the GUI-to-Actions path as well as the
existing example path.

1. In Voilà's **Seamless Install** panel, choose **GitHub Actions** as calculation
   environment. Enter the **actual accepted assignment `OWNER/REPOSITORY`** and
   `main`, not `ProfJJK-CoChem/CoChem-BASE`.
2. Open **No Code Matrix** and enter these water coordinates in ångströms:

   ```text
   O 0 0 0
   H 0 -0.757 0.587
   H 0 0.757 0.587
   ```

   **First select the assigned engine**: **ORCA (course Actions workflow)** or
   **CFOUR (course Actions workflow)**. Selecting GitHub Actions can retain a
   previously selected local free engine; choose the remote engine before its
   method controls. Set **Charge: 0** and **Multiplicity: 1**. For ORCA then
   select **Step 0 Gate: Screening (no product accuracy claim)**, **Theory Tier:
   T2**, **Method: HF/STO-3G**, **Basis Set: STO-3G** and **Solvation: None**.
   CFOUR automatically selects its screening configuration and locks the
   product gate; choose **Theory Tier: T2**, **Method: HF**, **Basis Set: STO-3G**
   and confirm **Solvation: None**. Confirm **CBS pair: Not supplied** and leave advanced recipes and
   external recovery files unselected. These explicit choices avoid the GUI's
   default Product A/DFT/solvated settings. Choose **Optimize + harmonic
   frequencies**, project name `lab01-water`, and **Calculation timeout (s):
   600** for ORCA or **1200** for CFOUR.
3. Select **Prepare GitHub Actions job**, then **Download ORCA job JSON** or
   **Download CFOUR job JSON**. Export prepares a request; it does not dispatch
   a calculation or install the engine locally.
4. Commit the exported JSON to the approved assignment branch, for example
   `jobs/lab01-water-orca-job.json`. In GitHub's browser, use **Add file → Create
   new file** with that full filename and paste the complete JSON if `jobs/`
   does not exist; otherwise **Add file → Upload files** is sufficient. Follow
   the instructor's review process.
5. Run the matching **ORCA calculation** or **CFOUR calculation** workflow with
   that committed repository-relative `job_file`. Use the same approved
   resources. Require actual convergence and accepted output.
6. At the bottom of the completed run's summary, download
   `orca-calculation-<run-id>-<attempt>` or
   `cfour-calculation-<run-id>-<attempt>`. These workflows request **14-day
   retention**, so download and archive the permitted scientific results
   promptly. The archive is a calculation artifact, not an engine installer.
7. Inspect `student-job/calculation-report.json`, `submitted-job.json`,
   `validated-job.json`, native calculation input/output and final result in
   `calculation/`, plus `complexes.h5` and the harmonic Hessian bundle when
   present. Retain the entire downloaded scientific artifact locally so paths
   and provenance files remain together. Confirm the operation matches what
   was requested and the energy is in hartrees.
8. To inspect the result back in Codespaces, upload the downloaded artifact ZIP
   through the Codespace's Explorer into a folder such as `course-downloads/`.
   Extract it into the artifact volume, replacing `ACTUAL-ARTIFACT.zip` with
   the uploaded filename:

   ```bash
   mkdir -p "$COCHEM_ARTIFACT_DIR/CourseResults/Lab01"
   python3 -m zipfile -e course-downloads/ACTUAL-ARTIFACT.zip "$COCHEM_ARTIFACT_DIR/CourseResults/Lab01"
   rg --files "$COCHEM_ARTIFACT_DIR/CourseResults/Lab01" | rg '(complexes[.]h5|hessian[.]npz)$'
   ```

9. In **Data Inspector (Ab-Initio)**, put the printed HDF5 path into **Log / H5
   File**, select **HDF5 SWMR Store → Read HDF5 (SWMR)**, and confirm datasets,
   units and source details render. For harmonic results, select **Isotopic
   Re-analysis**, enter the `.npz` path in **Hessian bundle**, then **Load
   geometry and Hessian**. Confirm geometry and source/hash loaded before
   attempting assigned isotope reanalysis. Result inspection does not require
   a local ORCA or CFOUR installation.
10. Save the input, report, run URL, source commit and your scientific
    interpretation to the course's specified submission locations. Keep large
    files in approved storage if needed; do not commit licensed archives,
    executables, distribution basis libraries or tokens.

## 11. Submit, collect and review the pilot

1. Have the student commit and push their `LAB01.md`/report and permitted
   result files to the accepted repository's **default branch**. For this
   pilot's **Every push** submission setting, pushing saves/submits the work.
   If using browser upload, commit through the course's approved branch/review
   process and confirm the changes reached the default branch.
2. The instructor opens Classroom50's assignment **Submissions** page and
   selects **Collect now**. Inspect **View run** if collection fails. Require
   the enrolled student's repository/commit to appear as submitted, then open
   its repository or **View feedback PR** to review the lab.
3. Apply your stated manual rubric/LMS grading for this **own CI** pilot.
   No built-in-autograder score is expected. A green ORCA/CFOUR job is evidence
   of chemistry execution, not automatically a score or final submission.
4. Record each pilot check below separately in `COURSE_SETUP.md` or your private
   instructor record. Do not mark all passed from a single green job.

   | Pilot check | Evidence |
   | --- | --- |
   | Student enrollment and acceptance | Student identity, accepted invitation, assignment repository and commit |
   | Fresh student Codespace | Creation time, personally owned payer, authorized repository permissions, setup outcome |
   | Interface | Rendered Voilà page, structure ingestion and optional-engine absence behavior |
   | Modules, when assigned | Read-access result, pinned installation/verification and supported handoff report |
   | Actual licensed chemistry | Successful run URL, source commit, input/resources and physical result report |
   | GUI export | Exported JSON committed to assignment and successfully executed |
   | Retrieval and inspection | Downloaded artifact and rendered HDF5/Hessian inspection |
   | Submission and review | Default-branch lab commit, successful Classroom50 collection and feedback |

5. Have the student commit/push all work, then **stop the Codespace**. Delete it
   when it is no longer needed to release storage; its uncommitted local files
   would otherwise be lost.

## 12. Roll out to the full class and maintain the template

1. Correct any pilot failure before enrollment rollout. Keep its final
   template, assignment and runtime/source manifest commits in the setup record.
2. On **Roster**, use **Upload roster** for the remaining students, review the
   preview, and send/share the classroom onboarding link. Existing organization
   members must be enrolled through **Members → Actions → Add to classroom**.
3. Share the assignment acceptance link. Add **each newly created assignment**
   to the selected repositories for its required organization Actions secrets.
   Give its student the approved team/module read access.
4. Give students the short instructions in Steps 8–11, your `LAB01.md`, and the
   [ORCA](GitHub_Classroom_ORCA_Setup.md) or [CFOUR](CFOUR_Actions_Setup.md) guide.
   Stagger initial jobs to stay within runner capacity and included usage.
   Students run assigned bounded calculations rather than full release
   acceptance suites.
5. Keep this assignment template frozen. When updating BASE, create a new
   reviewed course template/revision and repeat the pilot. Changing a template
   does not automatically replace all source in previously accepted copies.
   Classroom50's `gh student submit` refreshes `.github/` and `.gitignore` from
   its template, so do not distribute workflow changes that depend on scripts
   students' older copies do not have.
6. Review actual Actions/artifact usage, token expiry and student Codespaces
   allowance during the course. Retain permitted scientific evidence before
   artifact expiry and rotate credentials through their approved forms.

## Troubleshooting the first deployment

| Symptom | Correct check |
| --- | --- |
| Organization missing in Classroom50 | OAuth organization authorization/approval and Team/Enterprise plan |
| Private template rejected or acceptance returns 404 | Template flag, at least one commit, same organization, owner-saved assignment/team read grant |
| Student not allowed to accept | Classroom roster enrollment plus accepted organization invitation; sharing a link is insufficient |
| No **Run workflow** button | Reviewed workflow exists on default branch, Actions enabled, student has Write, correct workflow selected |
| ORCA/CFOUR download gets 401/403/404 | Assignment selected for correct organization secret, source token repo access/expiry/approval, stale repository secret override, actual published asset |
| Codespace cannot read a module | Student's team Read access, same-owner declaration and fresh Codespace permission authorization |
| Codespace starts but dashboard does not render | Completed setup log and `python3 scripts/hosted_dashboard.py check`; private port 8866 |
| ORCA/CFOUR absent locally despite working Actions | Expected for an interface-only Codespace; remote jobs provision independently, local dependent methods remain unavailable |
| Jobs cannot start due to usage | Organization included Actions allowance/budget/capacity; student personal Codespaces quota is separate |
| Green calculation but no Classroom50 grade | Own CI mode supplies no built-in score; submit/collect lab work and apply the stated rubric |
| Updated template but old student code | Existing accepted source is an independent copy; update compatible scripts/configuration explicitly and repeat pilot |

Send an instructor the run URL and relevant error text when asking for help.
Never include a credential value or licensed runtime. A failed run should retain
its diagnostics rather than be reclassified as a passed scientific result.

## Official references

Verified on 2026-10-08 UTC:

- [Classroom50 web teacher guide](https://github.com/foundation50/classroom50/blob/main/wiki/Web-Teacher-Guide.md)
- [Classroom50 web student guide](https://github.com/foundation50/classroom50/blob/main/wiki/Web-Student-Guide.md)
- [Classroom50 assignment templates](https://github.com/foundation50/classroom50/blob/main/wiki/Assignment-Templates.md)
- [Classroom50 GitHub integration and service-token permissions](https://github.com/foundation50/classroom50/blob/main/wiki/GitHub-Integration.md#4-fine-grained-pat-for-score-collection)
- [GitHub Codespaces ownership and payer](https://docs.github.com/en/codespaces/managing-codespaces-for-your-organization/choosing-who-owns-and-pays-for-codespaces-in-your-organization)
- [GitHub Codespaces repository access and fresh-permission rules](https://docs.github.com/en/codespaces/managing-your-codespaces/managing-repository-access-for-your-codespaces)
- [GitHub Actions billing and repository-owner allowance](https://docs.github.com/en/billing/concepts/product-billing/github-actions)

This guide describes the deployment procedure. It does not record a completed
student pilot; retain the actual course observations in the
[student deployment checklist](Student_Deployment_Pilot.md).
