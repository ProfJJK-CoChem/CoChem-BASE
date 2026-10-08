# BASE-managed ecosystem setup for a Classroom50 course

CoChem-BASE is the **only application repository students receive**. BASE
installs its required analysis components automatically, keeps them in isolated
managed environments and exposes their supported operations through its own
interface. Students do not clone TOPOS/TORQ, run package installers or enter
credentials. Their normal procedure is in the
[student research guide](Student_Research_No_Code.md).

This page is for the instructor/administrator. Source access, package
installation and successful scientific execution are separate checks. A
repository that can be downloaded does not automatically supply every operation
in its scientific plan.

## Understand the two execution environments

| Route | Identity and credential | What happens |
| --- | --- | --- |
| Codespaces interface | Student's project identity plus the App-provisioned Codespaces source reader; same-owner declarations serve the alternate organization route | BASE prepares its GUI and managed analysis components without student terminal commands. |
| Actions calculation | Student's private project workflow plus App-provisioned encrypted repository credentials | A fresh worker obtains the approved engines/source and executes the requested operation. |
| Local Linux, WSL, macOS or HPC | User/site-authorized setup | The same BASE installation and capability contracts apply, with local execution authority. |

Actions secrets do not automatically enter Codespaces. Read access granted to
a student team is not a replacement for a cross-repository Actions credential.
The classroom management credential, `CLASSROOM50_SERVICE_TOKEN`, serves
Classroom50 itself and must not be reused for CoChem source or engine downloads.

## Instructor: authorize private student projects

The primary deployment uses personal-owned private project copies so chemistry
runs consume the student's personal Actions allowance. Follow the complete
[GitHub App deployment guide](Personal_Project_App_Deployment.md). The instructor
configures the private controller once; students consent to App installation on
the selected private project. Students do not handle access tokens.

The controller supplies encrypted repository secrets and these generic binding
variables. Only private settings contain the chosen credential labels:

| Public binding key | Permitted download |
| --- | --- |
| `COCHEM_SOURCE_ACCESS_SECRET` | Approved private module source |
| `COCHEM_ORCA_ACCESS_SECRET` | Approved private ORCA release archive |
| `COCHEM_CFOUR_ACCESS_SECRET` | Approved private CFOUR release archive |

Actions consumers use `secrets[vars.<binding key>]`. An absent optional-engine
binding records unavailable access and disables its dependent calculations.
Module installation requires its own authorized source route. Runtime source
credentials are stripped before package builds and scientific subprocesses.

Organization Actions secrets **cannot be inherited by personal repositories**.
For an alternate organization-owned assignment, matching organization secrets
and binding variables can cover selected private repositories. Existing coverage
means no duplicate repository-secret copy is required. When using selected
policies, add each new repository to both the variable and secret access lists.
A same-name repository secret overrides an organization value.

Team Read access gives permitted users access to private repositories. It does
not reveal stored secret values or extend an assignment's scoped `GITHUB_TOKEN`.
Readers require narrowly scoped **Contents: Read-only**, appropriate expiry and
any required organization approval. Classroom50's management credential remains
separate from source and engine access.

Keep **Send secrets and variables to workflows from fork pull requests** and
**Send write tokens to workflows from pull requests** disabled. Public BASE
source carries generic configuration APIs, not the privately stored labels or
credential values. Do not publish native engine archives in source or artifacts.

## Instructor: enable automatic Codespaces installation

For personal projects, the App separately provisions an encrypted repository
Codespaces secret under the generic runtime name `COCHEM_SOURCE_CREDENTIAL`.
The [deployment guide](Personal_Project_App_Deployment.md) explains the App's
Codespaces-secret permission and enrollment checks. Use an initial Codespace's
**Lab access** controls to request enrollment. After the controller reports
success, stop that initial Codespace and create a **fresh Codespace** before
research uploads. BASE uses this scoped source reader for
cross-owner module setup and preserves it for compatible GUI updates/restarts.
Package builds and scientific subprocesses do not inherit source credentials.

Actions secrets do not automatically enter Codespaces. Additional-repository
permissions cannot extend a personal project's token to an organization owner.
Validate the automatic route with a fresh student Codespace; students do not
repair installation by running terminal commands.

The following team/declaration procedure applies to the alternate **same-owner
organization assignment** arrangement:

1. Open your organization → **Teams** and select the classroom's student team.
   Confirm students accepted their organization invitation and are members.
2. Open each approved analysis repository, initially upstream BASE, TOPOS and TORQ, then
   **Settings → Collaborators & teams → Add teams**. Give the student team
   **Read**, not Write or Admin.
3. Open **Organization Settings → Codespaces → General**. Enable the intended
   members' use of private course repositories and choose **User ownership**
   when students will use their personal allowance. Review effects on existing
   Codespaces before changing an organization-wide ownership policy.
4. Preserve the course template's supplied `.devcontainer/devcontainer.json`,
   its automatic lifecycle scripts and private port 8866. Its repository
   declarations request `contents: read` for same-owner upstream BASE/TOPOS/TORQ. The upstream BASE
   permission supports compatible update discovery; students still use only their
   assignment repository. BASE's
   automatic setup must be enabled in the reviewed course configuration.
5. Have the pilot student create a **fresh Codespace**, approve the requested
   permissions and open the dashboard. Require visible setup success for each
   required component; do not substitute terminal installation for a failed
   automatic setup.

Codespaces' additional-repository declarations support repositories with the
**same owner** as the assignment. Keeping course assignments and analysis
source in `ProfJJK-CoChem` fits that constraint. For a different course owner,
provide approved same-owner source mirrors and a reviewed catalog/authentication
configuration before rollout. Team read access alone does not extend the
Codespace's repository-scoped token to another owner.

Changed requested permissions require a **new Codespace**. Rebuilding an old
one does not grant those new permissions. Ordinary compatible component updates
using existing authorized repositories use the GUI's update controls.

## Instructor: publish compatible bug fixes during the course

The course can continue to receive fixes while students retain their own
research files. Use a reviewed compatibility catalog/channel rather than an
unrecorded `main` installation. The default channel is maintained canonical BASE source: each check resolves
its current default-branch HEAD to an exact commit before fetching it. A course
can instead select the latest stable release or an explicit instructor approval
file:

1. The component maintainer fixes and tests the upstream implementation.
2. Review its package, BASE adapter/API compatibility and scientific acceptance
   for affected operations. Record the exact source commit and required
   dependencies/capabilities in the BASE update catalog.
3. Publish the tested compatible catalog with canonical BASE source, publish
   a stable BASE hotfix for a release-only course, or update the exact approved
   source commit in the configured course approval file. Announce the affected behavior and required
   update to the class.
4. Students select **Check for updates → Apply compatible updates** inside
   BASE. They do not pull module source or type commands. Each installed
   revision is recorded so old and new results remain distinguishable.
5. Test one actual course workspace before class-wide adoption. Failed installs
   must preserve the last valid installation, original student inputs and
   existing results; unsupported operations stay disabled.
6. If the application itself changes, use the offered safe interface update
   and restart path. A template change alone does not update accepted copies.
   Preserve course files and respect modified-file conflicts rather than
   overwriting student work.

### Optional course approval channel for rapid fixes

An instructor can approve an exact tested BASE commit instead of following
the maintained canonical BASE default branch. All modes retain exact immutable
commits and the provider pins carried by that BASE manifest; students never
pull module branches themselves.

In the **course template**, use GitHub **Add file → Create new file** to add
`.cochem/course-runtime.json`:

```json
{
  "schema_version": "cochem.course-channel/1",
  "repository": "ProfJJK-CoChem/CoChem-BASE",
  "path": ".cochem/course-channels/chem-research.json"
}
```

In the **canonical BASE repository**, an authorized maintainer publishes the
corresponding approval data file `.cochem/course-channels/chem-research.json`:

```json
{
  "schema_version": "cochem.course-approval/1",
  "repository": "ProfJJK-CoChem/CoChem-BASE",
  "approved_base_revision": "REPLACE_WITH_THE_FULL_TESTED_40_CHARACTER_COMMIT",
  "label": "Instructor-approved computational chemistry course update"
}
```

The placeholder is not valid configuration. Replace it with the complete commit
SHA shown on the reviewed BASE source commit page. The manifest at that exact
source revision determines TOPOS/TORQ revisions. Keep approval changes restricted
to trusted maintainers and retain the acceptance evidence. Students still use
**Check for updates → Apply compatible updates → Restart interface**.

Match the **Actions worker approval** to this course policy. This extra step is
only needed for an explicit course approval; the default maintained-source
route needs no additional Actions variable.

For personal projects, the instructor's App controller provisions the approved
worker variable into each enrolled project. Update the private controller policy
and re-provision when changing course approval; students do not edit it. The
following manual variable instructions apply to organization-owned assignments:

1. Open the course organization on GitHub. Choose **Settings → Secrets and
   variables → Actions → Variables → New organization variable**.
2. Name it **COCHEM_COURSE_CHANNEL**. Set its value to the approval data path,
   such as **.cochem/course-channels/chem-research.json**, matching `path` in the
   course template exactly. It is a public configuration path, not a token.
3. Choose repository access that includes the private assignment repositories.
   For **Selected repositories**, add each accepted assignment as it is
   created. A variable stored only in the upstream BASE repository does not
   carry into template copies.
4. Check **Settings → Secrets and variables → Actions → Variables** in each
   pilot assignment for an older repository variable of the same name. A
   repository variable takes precedence over the organization variable;
   remove the stale override or match its value to the course policy.
5. Submit a fresh pilot calculation and inspect the recorded worker approval
   and exact worker source revision before distributing the update.

For one assignment, the equivalent path is **assignment repository → Settings
→ Secrets and variables → Actions → Variables → New repository variable**.
An instructor can instead set **COCHEM_APPROVED_BASE_SHA** to one complete
tested SHA. That fixed variable takes precedence over the course channel, so
use only one approval mechanism and keep it aligned with the GUI policy.
Otherwise a GUI-selected older course revision can correctly be rejected by
Actions as unauthorized. Students do not edit either variable.

BASE reads the moving approval file as data, then fetches the approved immutable
source. It must recheck approval before applying; an approval that changed
between checking and applying requires a new check. If no course channel is
configured, BASE resolves the maintained canonical default branch to an exact
commit, and rejects an application if that approved branch identity changes
between checking and applying. For a release-only course, use this template
configuration instead:

```json
{
  "schema_version": "cochem.course-channel/1",
  "repository": "ProfJJK-CoChem/CoChem-BASE",
  "channel": "stable-release"
}
```

Existing accepted assignments need the course configuration file as well; changing the template
only affects subsequent copies.

An update must not relabel an old calculation as having run with a new version.
Installation receipts and per-calculation provenance retain exact revisions.
Student access to source does not require students to view its repository or
understand its Python internals.

## Capability and scientific evidence gates

BASE's distribution catalog includes other ecosystem repositories whose
packaging, source access or adapters may still be unavailable. A source-only
component may be downloadable yet have no runnable installation. A package may
install successfully yet offer no accepted BASE operation. These states must be
shown truthfully and must not prevent independent supported BASE operations.

The seven source modules explicitly deferred by the instructor—CURE, EHS,
EVAL, LABS, PLAY, SEED and SHIFT—are not required for this course entrypoint.
Do not retry them automatically or describe them as installed.

TOPOS/TORQ scientific functions such as ensemble workflows, potential-energy
scans and NBO/Wiberg analysis require their supported provider implementation
and genuine result data. BASE may render accepted tables/figures or report
missing prerequisites. It must not invent analysis values to fill a panel.
The acceptance record must identify which exact operations actually ran.

## Allowances

Student-owned Codespaces and chemistry workflows in personal-owned private
projects use the student's own applicable allowances. The instructor-private
App-enrollment and Classroom50 administration workflows use organization minutes.
An alternate organization-owned assignment's chemistry also uses organization
minutes, even when a student submits it. Verify current Education benefits,
entitlement and displayed payer; personal Codespaces core-hours do not transfer
to Actions. Retain the existing paid-usage stop policies unless their owner
deliberately changes the budget.
