# Personal private research projects with instructor-managed access

Students create a **private repository owned by their own GitHub account** from
the public BASE template and name it after their research project. Their
Codespace runs the BASE interface; their repository's GitHub Actions runs the
calculations. This places private-repository Actions usage on the student's
account, subject to the plan and Education benefits actually shown in their
billing settings. An organization/team membership does **not** transfer an
organization secret or the organization's allowance to a personal repository.

The instructor's GitHub App checks active lab-team membership and the approved
BASE starter, then encrypts the approved read-only access credentials directly
into the student's selected private project. Students do not create tokens,
paste tokens, run commands, install another CoChem repository or edit workflows.
ORCA and CFOUR remain optional and strongly recommended. If access, installation
or native verification fails, dependent methods stay unavailable; BASE ingestion
and independent free capabilities remain usable.

This changes repository ownership and credential delivery, not the scientific
method matrix, licensed archive checksums, Stage 0 authority, micro-silo isolation
or original-input/provenance rules. The governing specifications are
[Chunk 17](SRS_Chunk_17_CoChem_BASE_Architecture.md), the
[proposal additions](SRS_Chunk_Proposal_CoChem_BASE_Architectural_Review.md), the
[Task 1 ingestion architecture](task1_subsystems_architectural_specification.md)
and [Method Matrix](../Method_Matrix.md), especially setup 1 and §8.4.

## What you configure once as the instructor

There are three separate things: your public BASE starter, a **private instructor
controller repository inside your lab organization**, and a GitHub App installed
both on that organization and on each consenting student's selected project.
The controller runs a short access-provisioning job; chemistry runs in the
student's personal repository. The controller's small Actions usage is charged
to its organization.

### 1. Prepare the lab's existing access

1. Open your lab organization on GitHub. In **Teams**, open the research-student
   team. Confirm each participating student accepted the organization invitation
   and appears as an active team member. Keep that team's access to the approved
   private engine and module repositories at **Read**.
2. Keep licensed archives only in the approved private engine release
   repositories. The public BASE source contains archive metadata and expected
   checksums, never archives or credential values.
3. In **Organization Settings → Secrets and variables → Actions**, check that
   the existing read-only engine and module-source credentials are unexpired and
   approved for their intended repositories. You already moved these to the
   organization; do not recreate them in public BASE. Their actual labels remain
   private organization configuration.

### 2. Make the private instructor controller

1. Open the reviewed BASE version that contains this App implementation. Choose
   **Use this template → Create a new repository**. Select your **lab
   organization** as owner, use a name such as `CoChem-Project-Access`, and select
   **Private**. Create the repository. Keep it separate from every student
   project.
2. In its **Settings → General → Features**, enable **Issues**. Enrollment uses a
   data-only issue. Students do not open pull requests to provision access.
3. Give the research-student team **Read** access to this private controller.
   Students can open their enrollment issue; only instructors should have
   **Write**, **Maintain** or **Admin** access. Those are the people who can change
   the controller or run maintenance.
4. In **Settings → Actions → General**, enable the reviewed controller workflow.
   Leave **Send secrets and variables to workflows from fork pull requests**
   disabled. The access controller never runs from a pull request.
5. Do not create Codespaces for this controller. Students open their own BASE
   research project. The controller uses only the checked-out instructor source
   and two pinned encryption packages; it never installs quantum engines or
   executes student code.

### 3. Register the GitHub App

1. Open your organization **Settings → Developer settings → GitHub Apps → New
   GitHub App**. If GitHub shows this under your personal developer settings,
   choose the lab organization as the App owner when that control is offered.
   You must have permission to register/manage Apps for the organization.
2. Give the App a distinctive course/lab name. Set its homepage to your BASE
   course guide. Record the resulting **App ID** and **App slug** shown on the
   App's settings/public page. The slug is the part after
   `https://github.com/apps/`; do not guess it from its display name.
3. Disable **Active** under **Webhook**. This implementation uses GitHub's own
   instructor-controller Actions workflow, not an external webhook server. It
   needs no callback URL, student OAuth authorization, client secret or hosted
   service.
4. Under **Repository permissions**, select exactly:

   | Permission | Access | Purpose |
   | --- | --- | --- |
   | Contents | Read-only | Verify the student's actual starter against instructor-approved Git blob hashes; no source writes. |
   | Secrets | Read and write | Encrypt the approved readers into the student's selected private project's Actions secrets. |
   | Variables | Read and write | Connect opaque private secret labels to the BASE workflows and set the approved worker SHA. |
   | Codespaces secrets | Read and write | Encrypt the module-source reader and course discovery settings into that same private project's Codespaces secrets. |
   | Metadata | Read-only | GitHub's required repository identification permission. |

5. Under **Organization permissions**, select **Members → Read-only**. This lets
   the controller confirm active membership in your research-student team. Do
   not grant administration, workflow/source write, Actions write or user-level
   Codespaces permissions.
6. Under **Where can this GitHub App be installed?**, allow **Any account**.
   Students own their projects personally, so an App restricted to your
   organization alone cannot serve them. The controller still refuses anyone
   who is not an active member of your configured lab team.
7. Create/save the App. Under **Private keys**, click **Generate a private key**.
   GitHub downloads a PEM file. Its entire content belongs only in the private
   instructor organization's App-key secret in step 5 below. Never commit it,
   upload it to an issue, put it in BASE or send it to students.

### 4. Install the App on the lab organization

1. In the App settings, choose **Install App**, select the lab organization and
   choose **Only select repositories**.
2. Select the private controller. Approve the listed permissions. Organization
   membership read is the only organization-level access the controller uses.
3. The App does not need installation on engine/module asset repositories to
   download them: the instructor's existing read-only readers do that. It does
   not issue a broad organization administration token to students.

### 5. Configure the private controller through GitHub Settings

In the private controller, open **Settings → Secrets and variables → Actions →
Variables**. Create the following nonsecret repository variables using **New
repository variable**. The actual private engine/source reader labels are
entered only here, not in public source or instructions.

| Variable | Value to enter |
| --- | --- |
| `COCHEM_ACCESS_CONTROLLER_REPOSITORY` | Your controller as `organization/repository`. |
| `COCHEM_ACCESS_ORGANIZATION` | Your lab organization's GitHub name. |
| `COCHEM_ACCESS_TEAM_SLUG` | The research team's URL slug, from `/orgs/organization/teams/slug`. |
| `COCHEM_ACCESS_APP_ID` | The App's numeric ID. |
| `COCHEM_ACCESS_APP_SLUG` | The exact App slug from its public page URL. |
| `COCHEM_ACCESS_BASE_REPOSITORY` | The reviewed canonical BASE repository as `owner/repository`. |
| `COCHEM_ACCESS_APPROVED_BASE_SHA` | The full 40-character commit SHA of the approved BASE worker. Open its commit page and use **Copy full SHA**. |
| `COCHEM_ACCESS_ALLOWED_STARTER_SHAS` | Optional space-separated full SHAs of compatible earlier starters you explicitly approve; maximum eight. Leave empty initially. |
| `COCHEM_ACCESS_COURSE_CHANNEL` | Optional canonical approval data path such as `.cochem/course-channels/course.json`. The explicit approved worker SHA takes precedence; leave this empty for the normal pinned worker route. It is not a branch name. |
| `COCHEM_ORCA_ACCESS_SECRET` | The actual existing private organization reader's secret label for ORCA. Leave empty to keep ORCA unavailable. |
| `COCHEM_CFOUR_ACCESS_SECRET` | The actual existing private organization reader's secret label for CFOUR. Leave empty to keep CFOUR unavailable. |
| `COCHEM_SOURCE_ACCESS_SECRET` | The actual existing private organization module-source reader's secret label. Required for automatic private TOPOS/TORQ installation. |

Then open **Organization Settings → Secrets and variables → Actions**:

1. Create an organization secret named `COCHEM_ACCESS_APP_PRIVATE_KEY` containing
   the complete PEM private key, including its BEGIN/END lines. Restrict selected
   repository access to the **private controller only**.
2. Edit each existing engine/source reader's selected-repository policy so the
   private controller can use it. This does not make it available to personal
   student repositories. The App deliberately encrypts the permitted reader
   into each enrolled private project after its checks succeed.
3. Keep reader permissions limited to downloading the approved private assets
   or module source. The students receive read-only asset/source readers, never
   the App key or a source/organization administration credential.
4. Confirm the organization's Actions billing/settings allow the short controller
   job to run. A billing failure can prevent it from starting any step.

The public workflow resolves a private label through a variable, using forms
such as `secrets[vars.COCHEM_ORCA_ACCESS_SECRET]`. The actual organization-specific
reader label and every credential value remain outside public source/help.
Private project owners can inspect their own secret/variable labels, but students
do not need to handle labels or enter credential values.

### 6. Give students a browser invitation

Provide the **App install link**, the **private controller repository link** and
your reviewed BASE template link in the course handout/Classroom50 assignment.
BASE's **Lab access** panel accepts the controller repository and exact App slug
as nonsecret invitation details and creates the enrollment links for the current
student project. There is no student token field or terminal step.

Classroom50 can hold the roster, instructions, feedback and student project
URLs. It does not change the owner/payer of a personal GitHub repository and does
not transfer your organization's secrets to it. Do not select an
organization-owned assignment repository if this course specifically intends to
use each student's personal Actions allowance.

## What each student does in the browser

1. Accept the lab organization/team invitation. Sign into the same personal
   GitHub account that will own the research project.
2. Open the instructor's approved BASE template. Choose **Use this template →
   Create a new repository**, select **your personal account** as owner, name it
   after your project and choose **Private**. Do not create a fork, make it public
   or put it under the lab organization for this route.
3. In your private project, choose **Code → Codespaces → Create codespace**. Wait
   for the BASE dashboard to open. The first Codespace can render BASE and ingest
   inputs while private provider/engine access is unavailable. In **Lab access**,
   enter the instructor's access repository and exact App slug from the course
   invitation; choose the optional engines you want to request.
4. Open **Authorize lab app** in that panel (or the instructor's App install
   link). Choose your personal account,
   choose **Only select repositories**, select that private project, review the
   requested permissions and install. Do not choose all repositories.
5. Open **Request project access** in BASE's **Lab access** panel. BASE has already filled in a
   small data-only issue identifying your project and selected optional engines.
   Click **Submit new issue** in the private instructor controller. No token,
   program or command belongs in this request.
6. Wait for the controller's success comment. It states which optional components
   were authorized. A failed job is not an authorization. If it fails, your
   instructor checks the controller's Actions log for the controlled error and
   corrects App installation, team membership, approved source or access policy.
7. In **your private project**, choose **Code → Codespaces → Create codespace**.
   Use the reviewed default branch and the instructor's recommended machine.
   A fresh Codespace receives the repository's newly encrypted Codespaces source
   access; organization Actions secrets are not its environment. If you made a
   Codespace before enrollment, create a fresh one after provisioning rather than
   assuming a rebuild supplies previously missing permissions/secrets.
8. Wait for BASE's automatic setup and the Voilà dashboard. BASE installs TOPOS
   and TORQ into isolated private runtime directories and shows their actual
   capabilities. You never open/install their repositories yourself.
9. Select **GitHub Actions** as the calculation environment. In **Lab access**,
   refresh the actual engine access check. A verified downloadable archive is
   provisionable, not yet an installed or scientifically accepted engine; the
   requested calculation job downloads it, checks the pinned SHA-256 and version,
   and runs fresh Stage 0/native checks. Missing engines disable their dependent
   selections.
10. Upload your own Avogadro 2 starting geometries, or another supported SRS input.
   Select the retained structure/frame, molecular state and reviewed calculation.
   Click the BASE calculation button. Monitor the linked request-bound Actions
   run, retrieve its result bundle through BASE and inspect genuine tables and
   figures. Uploads, original hashes and earlier results remain separate from
   runtime updates.
11. Use VS Code's graphical **Source Control** controls to save your research
    inputs/reports in your private project, and submit the project/result link
    through the instructor's Classroom50 collection instructions. No terminal
    commands are required.

## Updates and credential maintenance

Students use BASE's reviewed update controls, not Git commands. For a new tested
course worker, the instructor updates `COCHEM_ACCESS_APPROVED_BASE_SHA` in the
private controller. Keep each compatible existing starter SHA in
`COCHEM_ACCESS_ALLOWED_STARTER_SHAS` while those student projects remain active;
the controller verifies its exact executable blobs but permits added student
data outside executable/configuration namespaces. Template copies have new Git
history, so ancestry is deliberately not used as proof.

In the private controller's **Actions → CoChem private project access controller
→ Run workflow**, choose its default branch, enter a student project as
`owner/project` and select optional engines. The same membership, ownership,
private-repository, selected-installation and approved-source checks run again.
Only an instructor with controller write/maintain/admin access can use this
maintenance route. It writes fresh encrypted reader labels, updates the private
workflow bindings and refreshes the separate Codespaces source reader; it never
changes student source, uploads or results. Refresh students' Codespaces after
source-access rotation before the next module update. Expired asset/source
readers must first be renewed in your private organization configuration.

## What must pass before course rollout

Use one actual student-owned private project as a pilot. Keep its identity,
repository owner/private setting, selected App installation, current full source
SHA and actual controller run URL. Verify its fresh Codespace installs private
TOPOS/TORQ without student commands. From the dashboard, verify optional engine
access and run a bounded genuine ORCA and CFOUR calculation through the student's
Actions, retrieve the associated artifacts and confirm native values/provenance.
Also verify that an unselected/unavailable engine leaves BASE usable and its
dependent calculation unavailable. Check the payer/usage records in the
student's account; an Education plan does not promise unlimited Actions minutes.

The local transport/cryptography tests establish implementation behavior; they
do not establish a real App installation, live student secrets, hosted chemistry,
Codespaces service access or a completed student pilot. These require the App
registration, private controller configuration and actual service checks above.

GitHub references: [App installation tokens](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app),
[App JWT authentication](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-json-web-token-jwt-for-a-github-app),
[Actions repository secrets](https://docs.github.com/en/rest/actions/secrets),
[Codespaces repository secrets](https://docs.github.com/en/rest/codespaces/repository-secrets),
[Actions variables](https://docs.github.com/en/rest/actions/variables),
[Codespaces repository permissions](https://docs.github.com/en/codespaces/managing-your-codespaces/managing-repository-access-for-your-codespaces),
[Actions billing](https://docs.github.com/en/billing/managing-billing-for-your-products/managing-billing-for-github-actions/about-billing-for-github-actions),
[Codespaces billing](https://docs.github.com/en/billing/managing-billing-for-your-products/about-billing-for-github-codespaces).
