# Set up the lab App for private student projects

**This guide is for the instructor. Students do not register Apps, create tokens
or run installation commands.** Once you finish this setup, a student creates a
private `CoChem-[target molecule name]` project and uses BASE's buttons to request
access. BASE prepares TOPOS/TORQ itself. ORCA and CFOUR remain optional and
strongly recommended; unavailable engines disable only their dependent choices.

**Already at GitHub's New GitHub App form? Go directly to
[step 3: every registration field](#3-register-the-github-app).** The Homepage
URL is `https://github.com/ProfJJK-CoChem/CoChem-BASE`.

This setup uses GitHub pages, forms and Actions. You do not need to buy a domain,
create a website, run a web server or write Python/YAML. Have this guide open in
one tab and GitHub in another. Settings are saved in several different places;
each step below names the correct account or repository.

## What you configure once as the instructor

| Item | Plain-language meaning | Where it lives |
| --- | --- | --- |
| BASE template | The prepared starting copy students receive. | Public `ProfJJK-CoChem/CoChem-BASE`. |
| Access controller | A private project containing the job that checks a student's request and sets up that student's calculation access. | A repository in your lab organization; this guide uses `ProfJJK-CoChem/CoChem-Project-Access` as its example name. |
| Lab GitHub App | The permission granted to that setup job to prepare selected student projects. | Registered by the lab; installed on the lab organization and each participating student's selected project. |
| Student project | The student's own research workspace and calculation history. | A private personal repository such as `student-name/CoChem-benzene-water`. |

**This lab App is separate from ChatGPT Codex Connector.** The latter gives a
coding assistant repository access. Installing it does not enable ORCA/CFOUR
for a student, and registering the lab App does not connect an assistant.

The controller name above is an example to create in step 2, not a claim that
it already exists. Reuse your existing controller if you already created one.
Record its actual name and use that consistently throughout the guide.

If you already copied a controller or student template, updating public BASE
does not update that copy. Have the maintainer update its code to the reviewed
version before the pilot; do not recreate repositories or repeat App
registration merely because this guide has changed.

Follow in order:
[1. Lab access](#1-prepare-the-labs-existing-access) →
[2. Private controller](#2-make-the-private-instructor-controller) →
[3. App registration](#3-register-the-github-app) →
[4. Lab installation](#4-install-the-app-on-the-lab-organization) →
[5. Settings and credentials](#5-configure-the-private-controller-through-github-settings) →
[6. Student invitation](#6-give-students-a-browser-invitation) →
[7. Pilot](#what-must-pass-before-course-rollout).

### 1. Prepare the lab's existing access

1. Sign in to GitHub with your **instructor account**. Check the username using
   your profile picture at the upper right. Register the App under the lab
   organization, not under the student test account.
2. Open [ProfJJK-CoChem](https://github.com/ProfJJK-CoChem), then **Teams**.
   Open your research-student team. Record the final part of its address after
   `/teams/`; this is the **team slug**. For example, a team address ending in
   `/teams/research-students` has slug `research-students`. Use your actual value.
3. In the team's **Members** view, confirm the pilot student has accepted their
   invitation and is an active member. An outstanding invitation is not active
   membership. A normal student account should not be an organization owner or
   have write access to the controller.
4. Keep the existing ORCA/CFOUR archives in their approved **private Release
   repositories**. Keep the existing read-only download credentials in the
   organization's Actions secrets. You will grant the controller access in
   step 5; do not move archives or credentials into public BASE.
5. Open the BASE version your maintainer has reviewed for this course. On the
   repository's **Code** page, open **Commits** above the file list. Find that
   reviewed commit and choose **Copy full SHA** (or open the commit and copy
   its full identifier). Record all **40 characters**. This is the approved
   BASE version, not an App ID, archive checksum or student commit number.

The instructor must be an organization owner or have GitHub's delegated App
management permission to register the organization App. If the relevant
organization settings are unavailable, an organization owner completes those
steps. Do not create a different personal App merely to get past the missing
menu.

**Check before continuing:** you have the organization name, actual team slug,
reviewed BASE repository and its full commit identifier. The student is an
active team member. Existing licensed downloads may be added now or later;
public TOPOS/TORQ source does not need a private download credential.

### 2. Make the private instructor controller

1. Open the [BASE template](https://github.com/ProfJJK-CoChem/CoChem-BASE).
   Choose **Use this template → Create a new repository**.
2. Set **Owner** to **ProfJJK-CoChem**, **Repository name** to
   **CoChem-Project-Access**, and visibility to **Private**. Leave other options
   at their defaults and choose **Create repository**.
3. Bookmark the new repository. Its example address is
   `https://github.com/ProfJJK-CoChem/CoChem-Project-Access`.
   Check the owner and **Private** label. This is the controller, not a student
   research project.
4. Open this repository's **Settings → General → Features** and ensure
   **Issues** is enabled. An issue is the student's setup request in this
   system. No separate issue template needs to be created.
5. Open **Settings → Collaborators and teams** (GitHub may place this under
   **Manage access**). Choose **Add teams**, select the research-student team
   and grant **Read**. Students need this to view the private controller and
   submit their requests. Reserve **Write**, **Maintain** and **Admin** for
   instructors maintaining the service.
6. Open **Settings → Actions → General**. Ensure Actions is enabled and the
   policy permits this repository's pinned `actions/checkout` and
   `actions/setup-python` actions. Save any change. Leave **Send secrets and
   variables to workflows from fork pull requests** disabled.
7. Open the repository's **Actions** tab. The workflow is named **CoChem private
   project access controller**. If GitHub asks you to enable workflows copied
   from a template, enable them. If you cannot find the workflow in the sidebar,
   check **Code → .github → workflows → course_project_access.yml** exists on
   the default branch. A missing file needs a maintainer update, not a new token.

**Check before continuing:** the organization owns the private controller,
Issues and Actions are enabled, the student team has Read access, and the
controller workflow is present. Do not run a chemistry workflow or create a
Codespace in the controller. The setup job runs when a real enrollment request
arrives after the remaining settings are ready.

Creating a template copy copies the current template files, not a previous
commit you happened to view. If your course uses an older reviewed BASE version,
have the maintainer prepare a matching course template and controller. The
approved source and student starter must be compatible.

### 3. Register the GitHub App

#### Open the correct form

1. In GitHub, click your profile picture → **Your organizations**.
2. Beside **ProfJJK-CoChem**, choose **Settings**.
3. In the organization settings sidebar, open **Developer settings → GitHub
   Apps**, then choose **New GitHub App**.
4. Confirm you are registering it for **ProfJJK-CoChem**. If you already created
   the lab App, open its **Edit** page and compare its settings with the tables
   below instead of registering a duplicate.

#### Fill in the general fields

| Field on GitHub | What to enter or select |
| --- | --- |
| **GitHub App name** | For this lab, try **ProfJJK CoChem Project Access**. It must be globally unique and at most 34 characters. If GitHub says it is taken, choose another distinctive lab name and record it. |
| **Description** | `Connect approved student CoChem projects to lab-provided computational chemistry resources.` |
| **Homepage URL** | **`https://github.com/ProfJJK-CoChem/CoChem-BASE`**. This is a page describing CoChem. No separate website is needed. |
| **Callback URL** | **Leave blank.** This controller does not use a student OAuth callback. |
| **Expire user authorization tokens** | Leave **checked** if shown. This is GitHub's recommended default; this controller does not use these user tokens. |
| **Request user authorization (OAuth) during installation** | Leave **unchecked**. Students grant selected-repository installation access instead. |
| **Enable Device Flow** | Leave **unchecked**. |
| **Setup URL** | **Leave blank.** BASE supplies the setup-request link separately. |
| **Redirect on update** | Leave **unchecked** if shown. |
| **Webhook → Active** | **Uncheck it.** GitHub Actions receives the issue event; no external webhook server is used. |
| **Webhook URL** | **Leave blank** after turning Active off. |
| **Webhook secret** | **Leave blank**. This is not the App private key or an engine credential. |
| **SSL verification**, if shown | Keep verification **enabled**. |

GitHub may hide fields that no longer apply after a checkbox is cleared.
You do not need a Client secret, Marketplace listing or external hosting service
for this implementation.

#### Set the permissions

Expand **Repository permissions** under **Permissions** (or **Permissions &
events**). For each row below, open its access dropdown and choose the stated
level. These are **App permissions**, not the personal-access-token form.

| Repository permission | Select | What BASE uses it for |
| --- | --- | --- |
| **Contents** | **Read and write** | Check the student's BASE starter and save the reviewed Codespaces permission settings in that project. |
| **Secrets** | **Read and write** | Save encrypted download credentials in the student's selected project's Actions settings. |
| **Variables** | **Read and write** | Save the approved BASE version and names connecting the calculation workflows to their credentials. |
| **Codespaces secrets** | **Read and write** | Supply lab invitation settings and, only when needed, access to private module source for that project's Codespaces. |
| **Metadata** | **Read-only** | Identify the repository. GitHub normally sets this automatically. |

Expand **Organization permissions** and set **Members → Read-only**. This
checks that the student belongs to the specified research team.

Leave all other repository, organization and account/user permissions at
**No access**. In particular, the lab App does not need **Actions**, **Workflows**,
**Administration** or user-level **Codespaces** access. The controller workflow
uses its own GitHub-provided permission to post the enrollment response. A
student's Codespace separately requests permission to submit calculations later.

Under **Subscribe to events**, do not select any events for the App. Webhooks
are disabled; the controller repository's Actions workflow already declares
its issue triggers.

#### Allow student accounts to install it, then create it

1. Under **Where can this GitHub App be installed?**, select **Any account**.
   Choosing only the lab account would prevent students from installing it on
   their personal projects.
2. Choose **Create GitHub App**. Resolve any highlighted form error and submit
   again. If you were editing an existing App, save the changes instead.
3. Record the App's **numeric App ID** from its settings. Do not copy **Client
   ID**; the controller requires the numeric App ID.
4. Choose **Public page** in the App's settings. Its
   address has the form `https://github.com/apps/actual-app-name`.
   Record the exact part after `/apps/`. This is the **App slug**; copy it from
   the real URL rather than guessing it from the display name.
5. On that public page, choose **Install**. Copy the full address from the
   browser's address bar when GitHub displays the installation/account chooser;
   it has the form `https://github.com/apps/actual-app-name/installations/new`.
   Keep this student installation link with your setup notes. You do not need
   to submit an installation here; step 4 below installs it for the lab.

**Any account** makes the App available for other accounts to install; it does
not make the controller, engine archives, student projects or secret values
public. The controller still checks active membership in your specified team.

#### Generate and retain the App's private key

1. In the App's settings, open **Credentials**.
2. Under **Key pairs**, choose **New key**. GitHub downloads a file ending in
   **`.pem`**. This is the App's private key: it allows the private controller
   to act as this App.
3. Save the file in your instructor-only credential storage. Record where you
   saved it. GitHub does not let you download that same private key again.
4. Do not upload the PEM to a repository, issue, assignment or this chat. In
   step 5 you will copy its complete text into a GitHub **secret**.

<details>
<summary><strong>If GitHub shows the older private-key layout</strong></summary>

On the App's **General** settings page, scroll to **Private keys** and choose
**Generate a private key**. The downloaded PEM has the same purpose. Use the
layout actually present; do not generate extra keys merely to match a menu name.

</details>

**Check before continuing:** you have the numeric App ID, actual public App
URL/slug, student installation URL and downloaded PEM. The four repository
write permissions and organization Members read permission are set; webhooks
are off; installation is allowed on Any account.

<details>
<summary><strong>If you registered the App using the previous guide</strong></summary>

Reuse the existing App. Open its **Permissions & events** settings and correct
any missing permissions, especially **Contents → Read and write**. Save the
change. GitHub asks the owner of each existing installation to accept increased
permissions; saving the App definition alone does not update an installation.
Open the installation's settings and approve the pending change before retrying
enrollment. A student then needs a new Codespace to receive changed project
permissions. Rebuilding an old Codespace does not refresh them.

</details>

### 4. Install the App on the lab organization

Creating the App and installing it are two separate steps.

1. In your lab App's settings, choose **Install App**.
2. Choose **Install** beside **ProfJJK-CoChem**, then **Only select repositories**.
3. Select **CoChem-Project-Access**, or the actual private controller name you
   chose. Review the permissions and choose **Install**. Complete organization
   approval if GitHub requires it.
4. To check later, open the organization **Settings → GitHub Apps** under
   **Third-party Access**. Find your lab App and choose **Configure**. Verify
   the controller is included and there is no pending permission approval.

The lab App does not need to be installed on the ORCA/CFOUR asset repositories;
the existing read-only download credentials provide that access. Do not enter
an **installation ID** anywhere in BASE's configuration. The controller finds
its organization and student installation IDs itself.

**Check before continuing:** the App is installed on the organization with
access to the private controller. It is not yet installed on a student project;
that happens when the student accepts the invitation in step 6.

### 5. Configure the private controller through GitHub Settings

A **variable** stores an ordinary setting, such as a repository name. A
**secret** stores a credential, such as the App private key. A variable whose
name ends in `ACCESS_SECRET` contains the **name of an existing secret**, never
the credential's value.

#### Add the seven required repository variables

Open **your private controller repository**, not public BASE and not the
student project:

1. Choose **Settings → Secrets and variables → Actions**.
2. Select the **Variables** tab beside **Secrets**.
3. Choose **New repository variable**.
4. Copy the exact **Name** from the first column below.
5. Enter its **Value** from your setup notes. Do not add quotation marks,
   backticks or a full web address where the table asks for `owner/repository`.
6. Choose **Add variable** (or **Save** if editing).
7. Repeat for all seven rows. The saved variables should appear in the list.

| Exact Name | Value to enter | Where to obtain it |
| --- | --- | --- |
| `COCHEM_ACCESS_CONTROLLER_REPOSITORY` | `ProfJJK-CoChem/CoChem-Project-Access`, if you used that name. | The private controller's address, without `https://github.com/`. Match its spelling/capitalization. |
| `COCHEM_ACCESS_ORGANIZATION` | `ProfJJK-CoChem` | Your lab organization's GitHub name. |
| `COCHEM_ACCESS_TEAM_SLUG` | Your actual research-team slug. | Step 1: the part after `/teams/` in the team's address, not its display name or a student's username. |
| `COCHEM_ACCESS_APP_ID` | Your numeric App ID. | Step 3: the lab App's settings. Not Client ID or installation ID. |
| `COCHEM_ACCESS_APP_SLUG` | Your actual App slug, without a URL. | Step 3: the part after `/apps/` in the lab App's public URL. |
| `COCHEM_ACCESS_BASE_REPOSITORY` | `ProfJJK-CoChem/CoChem-BASE` | The reviewed BASE source repository, not the controller or student project. |
| `COCHEM_ACCESS_APPROVED_BASE_SHA` | The full 40-character, lowercase BASE commit identifier. | Step 1: **Copy full SHA** from the reviewed BASE commit. Do not enter `main`, a release name, a short SHA or the new controller copy's commit. |

The approved SHA is the exact BASE code version allowed to execute a student's
calculation. Template copies have their own commit histories; their compatible
program/configuration files are checked against this approved source. Students'
added research documents are not proof of, or a substitute for, that approval.

#### Connect the existing optional download secrets by name

1. In a separate tab, open your **organization's Settings → Secrets and
   variables → Actions → Secrets**. Locate the existing engine download
   secrets. You need their **names**, not their hidden values.
2. Return to the **private controller's Variables tab**.
3. Add the following variable for each engine you intend to offer. Paste the
   corresponding existing secret's name as its value.

| Exact variable Name | Value | When to add it |
| --- | --- | --- |
| `COCHEM_ORCA_ACCESS_SECRET` | The name of the existing organization ORCA download secret. | When offering ORCA. |
| `COCHEM_CFOUR_ACCESS_SECRET` | The name of the existing organization CFOUR download secret. | When offering CFOUR. |
| `COCHEM_SOURCE_ACCESS_SECRET` | The name of the existing private-module source download secret. | Only for approved private modules. Public TOPOS/TORQ downloads do not require it. |

For an engine you are not offering, leave its selector variable absent. You do
not need to create an empty secret or obtain its archive. Do not rename existing
working organization secrets just to follow this guide. Their private names
and values do not belong in public source or course handouts.

#### Save the App private key as an organization secret

1. Open **ProfJJK-CoChem → Settings → Secrets and variables → Actions** and
   select **Secrets**. These are organization settings, not repository settings.
2. Choose **New organization secret**.
3. In **Name**, enter **`COCHEM_ACCESS_APP_PRIVATE_KEY`**.
4. Open the PEM you downloaded in a plain-text editor. On Windows, open
   **Downloads**, right-click the `.pem` file and choose **Open with → Notepad**;
   use **Choose another app → Notepad** if necessary. On macOS, use a plain-text
   editor. Do not open it in Word or upload it to an online viewer.
5. In Notepad, use **Ctrl+A**, then **Ctrl+C** to select and copy all its text.
   Paste the entire content into the secret's
   **Value** field, including the `BEGIN` and `END` lines and all line breaks.
   Paste the file's contents, not its filename or file path.
6. Under **Repository access**, choose **Selected repositories**, then select
   only the **private controller**. GitHub may open a separate selection dialog;
   confirm that selection.
7. Choose **Add secret** or **Save**. The secret name should appear in the list.
   GitHub hides its saved value; that is expected. Keep the original PEM in
   instructor-only credential storage for recovery.

#### Allow the controller to use the existing download secrets

For each engine/private-source secret named by the selector variables:

1. Stay in **Organization Settings → Secrets and variables → Actions → Secrets**.
2. Open that existing secret's edit control.
3. Check **Repository access**. If it uses **Selected repositories**, add the
   private controller while retaining the other repositories already approved.
   If an existing policy already includes this private controller, no change
   is needed.
4. Save the access policy. You do not need to replace the secret value merely
   to give the controller access.

An organization secret's access list cannot directly include a student's
personal repository. The controller uses the App to deliver encrypted,
approved read-only download access to each enrolled personal project. The
App private key stays in the controller; it is never delivered to a student.

If a same-named repository secret exists inside the controller, it takes
precedence over the organization secret. Check for an obsolete repository
copy when a known-working organization credential appears not to work; do
not assume the organization credential itself is invalid.

Finally, check that the organization's Actions policy and available usage allow
the short controller job to run. This job uses organization Actions usage.
The student's later chemistry calculations use the personal project's account;
Codespaces has a separate allowance and payer. Classroom50 does not transfer
organization secrets or allowances into personal projects.

<details>
<summary><strong>Advanced variables: leave these absent for initial setup</strong></summary>

- `COCHEM_ACCESS_ALLOWED_STARTER_SHAS`: up to eight space-separated full SHAs of
  older, compatible BASE starters a maintainer has reviewed. Used when keeping
  existing student projects supported during a course update. Do not add an
  unreviewed SHA merely to bypass a source rejection.
- `COCHEM_ACCESS_COURSE_CHANNEL`: an optional canonical approval-data file path,
  such as `.cochem/course-channels/course.json`. It is not a branch name and
  does not replace the required approved BASE SHA. Leave absent for the normal
  explicitly pinned setup.

The public workflow uses a reference such as
`secrets[vars.COCHEM_ORCA_ACCESS_SECRET]`. It resolves the configured private
secret name at runtime without placing that name or its value in public code.

</details>

**Check before continuing:** the controller has all seven required Variables,
the selected optional engine selectors, access to the organization App-key
secret, and access to the organization download secrets those selectors name.
The App is installed on the organization and the student's team has Read access
to the controller. No credential has been committed as a repository file.

### 6. Give students a browser invitation

Provide these **three complete links** in the course handout or Classroom50.
You can prepare the handout now; send it only after completing the pilot below.

| What the student needs | What to copy |
| --- | --- |
| **BASE template link** | `https://github.com/ProfJJK-CoChem/CoChem-BASE`, or the matching reviewed course template prepared by the maintainer. |
| **Instructor's setup link** | The private controller's complete URL, for example `https://github.com/ProfJJK-CoChem/CoChem-Project-Access`. |
| **Instructor's App installation link** | Your actual App page URL followed by `/installations/new`, as recorded in step 3. Do not substitute the ChatGPT Codex Connector link. |

The controller URL example works only after you create that repository with that
name. Do not send a made-up App slug or a placeholder installation link.
The installation link can also be obtained from the App's **Public page**;
check that its name/publisher identify your lab App.

Add the [student start guide](GET_STARTED.md#student-personal-project), a
course contact for setup errors and the scientific instructions for the study.
Students create **`CoChem-[target molecule name]`**, for example
`CoChem-benzene-water`, under their own account with **Private** visibility.
They obtain BASE only; BASE installs the approved analysis components.

## What each student does in the browser

Use the [complete student guide](GET_STARTED.md#student-personal-project) for
all clicks, file handling and saving. The instructor observes these milestones
in the pilot:

1. The student signs in with their own GitHub username, accepts lab membership
   and creates an independent private BASE template copy. The existing
   independent `CoChem-BASE-test` can be reused for a pilot after its owner
   makes it private and a maintainer updates its source; no duplicate is needed.
2. They open the initial Codespace, wait for automatic setup and open the
   private **8866 — CoChem Voilà dashboard** port. This workspace is initially
   for enrollment; keep research uploads for the new workspace in step 5.
3. In **Start here**, they select **Run calculations on → GitHub Actions**, open
   **Connect using an instructor invitation**, paste the two full links, select
   the optional engines and choose **Save invitation**.
4. They choose **Authorize lab app**, install it on **their personal account**
   using **Only select repositories → their private project**, then return to
   BASE and choose **Request project access → Submit new issue**. The issue is
   already filled in by BASE; leave its structured contents intact. The student
   must submit it as the project owner. An instructor's issue on the student's
   behalf is not the normal student enrollment route.
5. After a successful setup response, they stop the first Codespace and create
   a **new Codespace** for the same project. They authorize the displayed
   project permissions so BASE can submit and manage calculations. A rebuild
   does not refresh those permissions. BASE installs TOPOS/TORQ automatically.
6. They choose **Check ORCA & CFOUR**, upload their own scientific inputs and
   run an appropriately small calculation through BASE. The access check only
   verifies that an archive can be obtained; actual chemistry must be tested
   separately. Unavailable engines leave dependent choices disabled.
7. They retrieve the matching result through **Calculations → Run calculation**,
   use **Download calculation bundle**, inspect **Results**, and follow the
   [save and submit steps](GET_STARTED.md#9-save-and-submit-your-work).
   Original uploads and managed results live outside the code repository;
   **Commit/Sync Changes does not back them all up**.

## What must pass before course rollout

Use one actual student-owned private project. Record its identity and run links
privately. Instructor account access is not evidence that student access works.

1. When the student submits the BASE-generated issue, open the **private
   controller → Actions → CoChem private project access controller**.
2. Open the newest run for that request. Its **provision** job must actually run
   and succeed; a grey/skipped job is not successful provisioning.
3. Return to the student's issue. The controller should have posted a success
   response naming the project and configured optional access. This confirms
   setup, not a completed chemistry calculation. The App finds installation IDs
   automatically; none need to be copied from this response into settings.
4. Observe the student creating the **new** Codespace and BASE installing its
   components without terminal commands. Check the correct project is displayed
   and that the dashboard opens with its port private.
5. Through that dashboard, test upload, submission, status and retrieval of a
   small genuine calculation for each engine the course will use. Retain the
   native results and provenance. Also check that an unrequested/unavailable
   optional engine leaves unrelated functions usable.
6. Download the calculation bundle, confirm it matches the submitted job and
   confirm the course's report/submission route. Check the payer and available
   usage in the student's account; Education membership does not promise
   unlimited compute.

Use the [full pilot checklist](Student_Deployment_Pilot.md) to record the result.
App registration, a successful setup response, local tests or earlier instructor
calculations alone do not establish a completed student Codespace/Actions pilot.

## Find and fix a setup problem

Open the **private controller's Actions run**, select **provision**, and expand
**Validate and provision the private personal project**. Read the final
`CoChem project access:` message. If an earlier step failed, inspect that step
instead. Keep the run link and exact error; do not paste credentials into an issue.

| What you see | What to check or do |
| --- | --- |
| New GitHub App asks for a Homepage URL | Enter `https://github.com/ProfJJK-CoChem/CoChem-BASE`. The callback, setup and webhook URLs are separate fields and remain blank for this implementation. |
| Required webhook URL | Clear **Webhook → Active**, then leave the URL blank. |
| App cannot be installed on the student's account | Set the lab App's installation availability to **Any account**, then use its real installation link. |
| Student gets a 404 opening the private controller | Check their signed-in username, active lab membership and their team's Read access to the controller. Private repositories can appear as 404 when access is absent. |
| No controller run appears | Check Issues and Actions are enabled, the workflow exists on the default branch and the student submitted/reopened/edited the BASE-generated issue. An ordinary comment does not start a run. |
| The provision job is skipped | Check the controller is private, organization-owned, on its default branch, and `COCHEM_ACCESS_CONTROLLER_REPOSITORY` exactly matches its `owner/repository`. |
| Incomplete controller configuration or invalid App ID | Check all seven required repository variables. App ID is numeric; approved BASE SHA is the full lowercase 40-character identifier. |
| Signing key unavailable or invalid | Check the App-key secret's selected-repository access includes the controller; its value must contain the complete PEM, not its path. Check for a stale repository secret overriding the organization secret. |
| App not installed / GitHub refused the access request | Check both installations: lab organization/controller and student account/selected project. Check pending permission approvals and that App ID and private key belong to the same App. HTTP 403 alone does not prove an engine download token is invalid. |
| Accept the lab organization/team invitation | Check the student is active in the exact team specified by `COCHEM_ACCESS_TEAM_SLUG`. |
| Students may enroll only their own repository | Submit the request while signed in as the personal project owner. Use instructor maintenance only for its documented purpose below. |
| Select an active private personal project | Verify personal ownership, **Private**, not archived, and created with **Use this template**, not Fork. |
| Starter is not an instructor-approved BASE revision | The maintainer must compare the student's program files with the approved BASE version, update the starter or explicitly approve a reviewed compatible version. Do not remove the check. |
| Contents permission needs Read and write | Change the App permission, accept the increased permission at the affected installations, then retry enrollment. |
| Project setup update refused | Check for a simultaneous project change or branch rules that prevent the App saving the reviewed Codespaces configuration. Resolve the specific restriction with the maintainer; do not force-push or disable every rule. |
| Setup succeeds but an optional engine remains unavailable | Check its selector variable names the correct existing organization secret and that the secret's access includes the controller. Then inspect the student's **Check ORCA & CFOUR** run; archive metadata, download authorization and actual execution are distinct checks. |
| Public TOPOS/TORQ downloads have no source token | Public source does not need one. Inspect the actual module installation result; do not create a private-source credential just to remove a warning. |
| Billing or usage blocks the controller | Check the lab organization's Actions allowance/policy. Changing the student Codespace's payer does not fix the organization's controller job. |

After correcting setup, ask the student to **close and reopen the same enrollment
issue**, or edit its existing BASE-generated body without changing its required
structure. Those events retry setup using the original student's authorship;
adding a comment does not. Confirm a new controller run actually starts.
There is no need to create repeated requests or repeat App registration.

## Updates and credential maintenance

Students use **Start here → CoChem tools and updates → Check for updates →
Apply compatible updates** for managed application updates. They do not edit
workflow code or use Git commands to repair access.

<details>
<summary><strong>Instructor: change the approved BASE version and support existing projects</strong></summary>

After a maintainer tests a new course version, update
`COCHEM_ACCESS_APPROVED_BASE_SHA` in the **private controller's Variables tab**.
Keep each explicitly reviewed, compatible older starter SHA in
`COCHEM_ACCESS_ALLOWED_STARTER_SHAS` while those projects remain active (maximum
eight). The controller checks program/configuration file contents, not commit
ancestry, because template copies have new histories. Added student documents
outside protected code/configuration paths are retained.

A missing/outdated student workflow needs an instructor update to the actual
files in that project's default branch. Update the complete compatible
workflow/script set, including `.github/workflows/student_project_setup.yml`
and `scripts/check_student_project_setup.py`, then recheck project setup.
BASE's **Check for updates** manages the external installation; it does not
publish replacement project workflow files.

</details>

<details>
<summary><strong>Instructor: retry setup or rotate access for an enrolled project</strong></summary>

1. Renew an expired reader in the organization's secret settings first, retaining
   the intended repository access policy. Do not enter its value into a variable.
2. Open **private controller → Actions → CoChem private project access controller**.
3. Choose **Run workflow**, select the controller's default branch, and enter
   the actual student project as `owner/project` in **project_repository**.
4. In **engines**, enter `orca cfour` for both, `orca` or `cfour` for one, or
   clear the field for neither. Choose **Run workflow** to submit.
5. Inspect the run's outcome. The manual route requires instructor
   Write/Maintain/Admin access and still checks student membership, ownership,
   private visibility, selected App installation and approved starter. It does
   not establish that the student completed their own enrollment interaction.

Manual runs have no enrollment issue to comment on; read the Actions result.
They refresh encrypted access and the reviewed project Codespaces settings,
not scientific input files. A changed permission or private-source credential
requires a **new Codespace** before relying on it; preserve local uploads and
completed bundles first.

</details>

<details>
<summary><strong>Scope, existing evidence and architecture references</strong></summary>

BASE is the student's entry point and installs the canonical approved TOPOS/TORQ
sources automatically. The public source route does not require the lab's
private-source credential. This guide does not certify every method or module.
The [13 October acceptance report](GUI_Access_Acceptance_2026-10-13.md) records
instructor-repository licensed calculations; the
[current pilot status](Student_Deployment_Pilot.md) records separate student
access limitations. Registration and local protocol tests do not prove a live
lab deployment. A fresh, real student pilot is still required.

The governing requirements are [SRS Chunk 17](SRS_Chunk_17_CoChem_BASE_Architecture.md),
[proposal additions](SRS_Chunk_Proposal_CoChem_BASE_Architectural_Review.md),
[ingestion architecture](task1_subsystems_architectural_specification.md) and
[Method Matrix](../Method_Matrix.md). The access setup does not relax scientific
validation, immutable input preservation or separation of code and research data.

</details>

## Official instructions used for this walkthrough

The registration fields and private-key menus were checked against GitHub's
documentation on 18 October 2026. GitHub may show older menu labels; the specific
private-key alternative above is included for that reason.

- [Registering a GitHub App](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app)
- [Managing App private keys](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/managing-private-keys-for-github-apps)
- [Installing your own GitHub App](https://docs.github.com/en/apps/using-github-apps/installing-your-own-github-app)
- [Sharing the App's public page and installation link](https://docs.github.com/en/apps/sharing-github-apps/sharing-your-github-app)
- [Reviewing installed GitHub Apps and repository access](https://docs.github.com/en/apps/using-github-apps/reviewing-and-modifying-installed-github-apps)
- [Actions secrets and organization repository-access policies](https://docs.github.com/en/actions/security-for-github-actions/security-guides/using-secrets-in-github-actions)
- [Actions configuration variables](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-variables)
- [Codespaces repository permissions and new-workspace requirements](https://docs.github.com/en/codespaces/managing-your-codespaces/managing-repository-access-for-your-codespaces)
- [Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
- [Codespaces billing](https://docs.github.com/en/billing/concepts/product-billing/github-codespaces)
