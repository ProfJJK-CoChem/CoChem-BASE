# Deploy CoChem-BASE for student research through Classroom50

Use **one persistent private BASE workspace per student or research group**.
Students create their own monomer or complex starting XYZ files in Avogadro 2,
upload them through BASE and interact with the ecosystem through BASE. They
receive no separate TOPOS/TORQ repository and run no terminal installation code.
Codespaces supplies VS Code and the interface; Actions runs the calculations.
Classroom50 creates assignment repositories and collects submitted course work.

This guide is for an instructor who is new to GitHub. The student-only
instructions are in [Student research without coding](Student_Research_No_Code.md).
The detailed access explanation is in [BASE-managed module setup](Ecosystem_Modules_Setup.md).
Before class-wide rollout complete the [student deployment pilot](Student_Deployment_Pilot.md).

The instructions require the BASE source containing **CoChem setup and
updates**, working XYZ uploads and **Run on GitHub Actions**. The earlier
`v1.0.1` release used an export/manual-dispatch route; its acceptance evidence
does not by itself validate this newer no-code route. Use the reviewed release
or course revision that actually contains the controls described here.

## 1. Know what each service does

| Term | Meaning in this course |
| --- | --- |
| Organization | Your shared GitHub account, here `ProfJJK-CoChem`, that owns course repositories and shared settings. |
| Repository | A versioned folder of files. Each student/group gets one private BASE research repository. |
| Template | The instructor's starter repository. Classroom50 copies its files to create an assignment repository; it does not copy secrets. |
| Classroom50 | The class roster, assignment links, submission collection and feedback service. |
| Codespace | A student's remote VS Code workspace with a browser interface. BASE's setup runs automatically when it is created. |
| Actions | GitHub's separate calculation workers. BASE submits a request and retrieves the matching worker result. |
| Team | A group of GitHub users whose repository access you manage together. |
| Secret | A credential stored through GitHub settings, never in a source file. Organization secret policies determine which assignment workflows can use it. |
| Commit | A saved version of repository files. It records an application revision or student submission; it is not a completed calculation. |

A course layout can use these names:

| Item | Example |
| --- | --- |
| Organization | `ProfJJK-CoChem` |
| Classroom | `Computational Chemistry Research` |
| Classroom slug | `chem-research` |
| Assignment | `CoChem vdW Research Workspace` |
| Assignment slug | `vdw-research` |
| Private template | `ProfJJK-CoChem/CoChem-vdW-Research-Template` |
| Default branch | `main` |

Use individual repositories when each student has independent data. Use a
Classroom50 **Group** assignment when students deliberately share one research
project and its data. A persistent semester workspace avoids rebuilding the
application for every weekly calculation. Report milestones can use folders
and your rubric inside that workspace.

Keep course assignments and approved analysis source under the same organization
for the supplied Codespaces access declarations. A different source owner
requires a reviewed same-owner mirror/authentication configuration; a student's
Read access alone does not extend a Codespace token to another organization.

## 2. Confirm Classroom50 organization setup

If Classroom50 already opens your organization and its token check passes,
skip initial setup and leave the working service token alone.

1. Open <https://classroom50.org/> and choose **Sign in with GitHub**. Authorize
   the course organization. An organization owner must approve the application
   if your organization restricts OAuth applications.
2. On **Classroom 50 organizations**, choose **Set up new organization**, find
   `ProfJJK-CoChem`, and select **Set up → Run setup**.
3. Read the results. Classroom50 creates its private `classroom50`
   configuration repository, sets up collection workflows/Pages and adjusts
   organization policies and an initial $0 paid Actions cap. Review these
   organization-wide effects when the organization also holds research code.
   Keep student assignment Pages off.
4. Choose **Next: service token → Set a token → Generate new access token**.
   GitHub opens Classroom50's pre-filled token form. Use your teaching
   organization as **Resource owner** and cover future assignment repositories
   as prescribed by Classroom50, normally **All repositories**.
5. Retain the official management permissions: repository Contents, Actions,
   Workflows and Administration with read/write access, Metadata Read and
   organization Members Read. Generate the token and paste it only into
   Classroom50's **Paste token** field, then **Save token → Done**.
6. Open Classroom50 **Settings → Service token → Test token**. Require success;
   use **View run** to inspect a permissions error. Complete required
   organization approval and set an expiry/rotation reminder.

This credential is `CLASSROOM50_SERVICE_TOKEN`. It is for classroom management,
not engine/source download. It must not be placed in student repositories or
reused under a CoChem download-secret name.

## 3. Confirm Codespaces and calculation allowances

Your Education Team account can support the course organization. The student
interface and course calculations nevertheless have different payers.

1. Open GitHub → `ProfJJK-CoChem` → **Settings → Codespaces → General**.
   Enable the intended students' access to private course repositories. Choose
   **User ownership** if students use their own allowance. Review effects on
   existing Codespaces before changing an organization-wide ownership policy.
2. Have the pilot student check personal **Settings → Billing & Licensing**
   and active Education benefits. They must confirm the payer at Codespace
   creation. A two-core Codespace uses two core-hours per elapsed hour.
3. Open **Organization Settings → Actions → General**. Allow the reviewed
   course workflows and actions they use. If an allowlist is enabled, include
   the workflows' checkout, setup-python, upload/download-artifact and
   Classroom50 requirements.
4. Keep **Send secrets and variables to workflows from fork pull requests**
   and **Send write tokens to workflows from pull requests** disabled. Neither
   is required for the BASE student calculation route.
5. Open **Organization Settings → Billing & Licensing → Budgets and alerts**.
   Review your existing paid-usage stop policy; do not create duplicate
   budgets. GitHub Team ordinarily includes 3,000 standard-runner Actions
   minutes monthly **shared by the organization**. Verify the entitlement
   GitHub actually displays for your account.

A calculation in an organization-owned assignment consumes that organization's
Actions allowance even when a student starts it. The student's Codespaces
allowance cannot pay for it. Measure one pilot's setup/calculation minutes
before scheduling simultaneous class work. Closing a browser does not stop a
Codespace; students should use **Stop current codespace**.

## 4. Prepare the private course template through GitHub's website

CoChem-BASE is a GitHub template repository. The instructor can copy it through
the website without asking students to clone or assemble application files.
Template generation copies the default branch, not an arbitrary release tag.

1. Open `ProfJJK-CoChem/CoChem-BASE`. Confirm its default branch contains the
   reviewed student-entrypoint source described at the beginning of this guide.
   Record the source commit from the latest commit link. A maintainer should
   align the starter with the approved release before course deployment.
2. Choose **Use this template → Create a new repository**.
3. Choose owner **ProfJJK-CoChem**, name **CoChem-vdW-Research-Template**,
   visibility **Private**, and leave **Include all branches** off. Create it.
4. Open the new repository → **Settings → General** and enable **Template
   repository**. Confirm its default branch is `main`.
5. Confirm `.devcontainer`, `.github/workflows`, `scripts`, `.docs` and
   `Start_Here.ipynb` are present. Preserve BASE's automatic setup, workflows,
   compatible version catalog, runtime isolation and private port configuration.
   Do not copy licensed archives, machine-specific registries or credentials
   into this repository.
6. Add your instructions with **Add file → Create new file**. Name the file
   `RESEARCH_GUIDE.md`, enter your assignment and choose **Commit changes**.
   Specify the scientific question, permitted sizes/resources, methods,
   fragment/state requirements, report milestones and rubric. Tell students
   explicitly that **they provide their own starting XYZ files**.
7. Add `COURSE_SETUP.md` the same way. Record the BASE source/release, approved
   engine manifests, required capabilities, pilot results and update policy.
   Keep credential values out of it. Link both course guides from the README
   using GitHub's pencil/edit button and **Commit changes**.

For research files, recommend project-specific inputs, optimized structures,
small results and reports. BASE manages uploaded originals and calculation
artifacts itself. Do not require students to create Python scripts.

### Keep upstream release testing out of ordinary student commits

The current BASE workflow automatically reserves the full release suite for
the canonical BASE repository or an explicit manual test run. A student's
report push in an assignment copy does not launch that three-platform release
suite. No instructor YAML edit is required.

For a deliberate installation test, open the assignment's **Actions** tab,
select the relevant acceptance workflow and choose **Run workflow**. Follow
the pilot's bounded resources. Keep the student calculation workflow enabled
on the assignment's approved default branch; it is the route used by the GUI.

Keep the initial starter consistent for assignment acceptance. Compatible fixes
can later reach existing workspaces through BASE's recorded GUI update channel;
changing the template alone does not update an accepted assignment's files.

## 5. Create the classroom and research assignment

1. In Classroom50 open the configured organization. On **My classrooms**,
   choose **Create classroom** and enter your classroom name/slug/term.
2. Open that classroom → **Assignments → Assignment**.
3. Under **Details**, enter the assignment name and slug. Choose **Individual**
   for the first pilot, or **Group** for a shared project.
4. Under **Repository setup → Start with a template → Template repository**,
   choose `ProfJJK-CoChem/CoChem-vdW-Research-Template`. Leave **Include all
   branches** off. Keep **Feedback pull request** on if you want inline feedback.
5. Under repository **Advanced settings**, choose **Private**, **GitHub Pages:
   Off** and student **Write (push)** access. Students need no repository Admin.
6. Under **Submission and grading → Grading**, choose **Manual (enter scores
   by hand)** and enter your maximum points. Your rubric evaluates the
   chemistry, not Python coding or whether a process merely exited green.
   Manual grading preserves the template's calculation workflows.
7. Choose **Submission type → Every push to the default branch** for a simple
   website/VS Code submission route. Do not require command-line submission
   tags for this course.
8. Set the due date/time in **Schedule and access**, checking its displayed
   local timezone. Leave **Lock assignment** off for the pilot. A due date
   marks lateness; it does not prevent pushes by itself.
9. Choose **Create assignment**. An organization owner must resolve any
   private-template permission warning before student acceptance.

For an older assignment that already enabled an autograder, disable its
built-in autograder explicitly and check the effect on existing repositories
before changing grading mode. Do not add fake scientific tests to make an
automatic grade appear valid.

## 6. Enroll one pilot student

1. Open the classroom's **Roster**. Use the arrow beside **Upload roster → Add
   member**, choose **Student** and enter the student's GitHub username.
2. For someone already in the organization, use Classroom50 organization
   **Members → select student → Actions → Add to classroom**. Reinviting an
   existing organization member does not enroll them in this classroom.
3. Have the student accept the organization invitation and sign into
   Classroom50 using their own account.
4. Open the assignment → **Share → Copy accept link** and share it with that
   enrolled student through your course channel.
5. The student chooses **Accept assignment**, waits for the checklist and
   selects **Open repository**. Record the actual `OWNER/REPOSITORY` name.

A share link alone is not enrollment. Do not ask the student to fork BASE when
acceptance reports missing membership; correct their invitation/roster instead.

## 7. Check your existing secret policies—usually no copies are needed

You have already granted the student team Read access to the engine
repositories and configured organization secrets. **Do not create duplicate
repository secrets merely because a student repository is new.** Check which
repositories the organization secret allows to use it.

1. Open GitHub → `ProfJJK-CoChem` → **Settings → Secrets and variables →
   Actions**.
2. Inspect `PRIVATE_ORCA_ASSET_CREDENTIAL`, `PRIVATE_CFOUR_ASSET_CREDENTIAL` and
   `COCHEM_SOURCE_READ_TOKEN` using their edit/update controls.
3. If **Repository access** is **All repositories** and covers private course
   repositories on your plan, the new assignment is already covered. No
   additional repository-secret copy is required.
4. If it is **Selected repositories**, add the new assignment to each needed
   secret's list and save. Repeat the **access-list grant**, not the value copy,
   for each newly accepted assignment.
5. If it is **Public repositories**, it does not cover this private assignment.
   Choose the approved private/selected policy.
6. Inspect the assignment's **Settings → Secrets and variables → Actions** for
   stale same-name repository secrets. Those override organization values and
   can explain access failures despite a correct organization binding.

The download tokens also need their own source-repository selection,
**Permissions → Add permissions → Contents → Read-only**, expiry and required
approval. Token scope controls what can be read; secret policy controls which
workflow repositories can use the token. Student/team Read access does not make
an assignment's default Actions `GITHUB_TOKEN` read separate private archives.

Students never create or paste these credentials. They should be authorized
users of the archive/source access that their editable assignment workflows
receive. See the [module access guide](Ecosystem_Modules_Setup.md) for the exact
policy table and credential boundaries.

## 8. Start the student's no-code interface

1. Confirm the classroom team has **Read** access to approved upstream
   BASE/TOPOS/TORQ source. The upstream BASE permission enables compatible
   update discovery; students still interact only with their assignment. Your existing engine-team grants can remain; the interface-only
   Codespace does not need to install a licensed binary locally.
2. Preserve BASE's same-owner Codespaces repository declarations and automatic
   post-create/post-start lifecycle. Students authorize these permissions when
   creating their Codespace.
3. Have the student open their accepted assignment → **Code → Codespaces →
   Create codespace on main**, choose the supported two-core machine and
   confirm the personal payer.
4. Wait for automatic setup. Open **Ports → 8866 — CoChem Voilà dashboard →
   Open in Browser**, visibility **Private**.
5. Require the rendered **CoChem setup and updates** status to show the
   required analysis components ready. BASE installs them automatically.
   A component failure disables its dependent operations and explains the
   prerequisite. Geometry ingestion and independent functions remain usable.
6. Use **Retry setup** after correcting a reported access/setup problem.
   Students do not run `pip`, Git or Python commands to fix setup.

New requested repository permissions require a **new Codespace**, not just a
rebuild. Before replacement, synchronize/download the student's research files.
An ordinary compatible fix using existing permissions uses BASE's update panel.

## 9. Pilot student-supplied structures and actual Actions calculations

Run the engine's authentic acceptance workflow once as instructor in the
pilot repository, then test the student route personally using the student's
identity and their own structure. Installer success alone is not chemistry.

1. Have the student upload a small monomer or complex they made in Avogadro 2
   using **Upload .xyz**. Test both input types, multiple starting files,
   structure selection and a meaningful invalid-file error. Retain the
   original-file hashes and displayed identity.
2. Choose **GitHub Codespaces** as interface and **GitHub Actions** as
   calculation environment. Confirm the actual assignment repository/branch
   were identified. The student must not enter a PAT.
3. Have the student choose the reviewed engine, charge, multiplicity, method
   and operation. For an engine installation check a tiny water HF/STO-3G
   calculation is acceptable; it is not the vdW research protocol.
4. Choose **Run on GitHub Actions**. BASE sends a data-only request and records
   a unique correlation identifier. The student does not commit a JSON file
   or manually edit/dispatch a workflow.
5. Test **Refresh calculation status**, then **Retrieve and inspect results**
   after actual success. Require the run, source, request and file checks to
   match. Retain **Download calculation bundle**.
6. Test supported analyses with genuine result data and inspect their tables
   and figures. A disabled NBO, Wiberg, population or scan function requires
   its actual provider/data prerequisite; it is not accepted merely because
   a button exists.
7. Test cancellation on one small calculation and failure recovery without
   losing the student's original geometry or other completed results.
8. Have the student submit their report using VS Code **Source Control →
   Commit → Sync Changes**. Confirm it appears in GitHub. In Classroom50,
   collect the submission, read it and enter the rubric score/feedback.

Licensed provisioning can take longer than a tiny calculation. Do not launch
repeated duplicate requests while the existing run prepares its engine. The
browser can close after GitHub accepts the run; result retrieval occurs later.

The generic classroom workers impose bounded atom, core, memory and time
limits. Plan a reviewed research worker for larger systems/long searches rather
than silently lowering the assigned scientific standard. ORCA and CFOUR remain
optional and strongly recommended; unavailable dependent choices must explain
why they cannot be selected.

For advanced ORCA protocols, BASE now has scientific-data upload controls for
authentic R2 reference packages and geometry-bound native READ Hessians, plus
an explicit active-space T9 form. The assignment's ordinary student **Write**
access lets the GUI store larger inputs automatically in a separate data-only
input branch; it keeps the default source branch untouched. The Actions worker
uses its own read-only identity to retrieve the exact sealed input blob and
checks its request, geometry and full file inventory before native validation.
Do not reduce the student to repository Read access if this intake route is
required. Students still enter no token and execute no terminal commands.

Pilot the actual reference-dependent calculation separately from a small
installation check. A valid archive checksum cannot establish CCSD(T)/CBS
geometry accuracy, a Hessian's stationarity, or the correctness of a chosen
active space. Retain the native scientific evidence and any explicit limits.

## 10. Apply bug fixes while students keep working

1. Have maintainers test their TOPOS/TORQ fix and its BASE compatibility.
2. Publish the tested compatible catalog with maintained canonical BASE
   source. Each GUI check freezes an exact source commit and its provider pins.
   A release-only course can select stable hotfixes; a course can also use the
   explicit instructor approval file described in the [module guide](Ecosystem_Modules_Setup.md#optional-course-approval-channel-for-rapid-fixes). A changed module `main` branch alone
   must not silently change an already recorded calculation.
3. Announce the affected behavior and required update. Pilot it in one course
   workspace first.
4. Students use **CoChem setup and updates → Check for updates → Apply
   compatible updates → Restart interface**, then reopen the dashboard.
   BASE installs into managed external storage and retains version records,
   previous valid installations, original uploads and completed results.
5. If an update fails, use the offered rollback/retry path and preserve the
   reported error. Never tell students to manually install another module.
6. Announce any new repository permission separately. Update the assignment
   configuration as required and arrange a new Codespace only for that case.

The template controls new assignment copies. The compatible runtime update
channel controls existing workspaces. Its default follows maintained canonical
BASE source with exact commit recording; the optional stable-release or course
approval policies let you restrict adoption. BASE and the Actions worker must record
and use compatible exact versions for each newly submitted calculation; older
results keep their original versions.

For an explicit course approval, follow the module guide's matching
**COCHEM_COURSE_CHANNEL** Actions variable setup. The GUI's course configuration
and the worker's protected approval must refer to the same canonical approval
file. Add new assignments to that variable's selected-repository access list
when applicable. The default maintained-source route needs no extra approval
variable.

## 11. Roll out after the pilot passes

Record the real student account, assignment, Codespace/payer, source revisions,
upload hashes, run URLs, retrieval evidence, update preservation check and
Classroom50 submission. Instructor-run hosted jobs and local containers are
valuable separate checks; they are not a student's actual Codespace pilot.

Share the assignment with the full roster. For **Selected repositories** secret
policies, add each new assignment to the needed secret access lists. For an
applicable **All repositories** policy this step is automatic. Keep the
student-only guide prominently linked from the course instructions.

## Official references

- [Classroom50 teacher guide](https://github.com/foundation50/classroom50/blob/main/wiki/Web-Teacher-Guide.md)
- [Classroom50 assignment templates](https://github.com/foundation50/classroom50/blob/main/wiki/Assignment-Templates.md)
- [GitHub organization Actions secrets](https://docs.github.com/en/actions/security-for-github-actions/security-guides/using-secrets-in-github-actions#creating-secrets-for-an-organization)
- [GitHub Codespaces repository permissions](https://docs.github.com/en/codespaces/managing-your-codespaces/managing-repository-access-for-your-codespaces)
- [GitHub Codespaces billing](https://docs.github.com/en/billing/managing-billing-for-your-products/managing-billing-for-github-codespaces/about-billing-for-github-codespaces)

Current Classroom50's teacher documentation was checked for **Manual (enter
scores by hand)** and template/roster settings. The deployment's actual proof is
its retained pilot evidence, not a documentation date.
