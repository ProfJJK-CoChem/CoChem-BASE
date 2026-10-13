# Start using CoChem

**CoChem-BASE is the only CoChem project you open.** It sets up TOPOS and TORQ
and shows their tools in the same interface. You provide your own scientific
files, including starting structures made in Avogadro 2.

## Already in the dashboard? Start with these three steps

1. **Start here → Run calculations on → GitHub Actions.** Your current GitHub
   project should already be selected. Choose **Check ORCA & CFOUR** and wait
   for the result beside each engine.
2. **Your files → Upload scientific inputs.** Select your file, then its
   structure/frame if it contains several. Choose **Use selected starting
   geometry** and confirm the molecule's charge and multiplicity.
3. **Calculations.** Choose the assigned operation, engine and method, review
   the settings, then select **Run on GitHub Actions**. When it finishes, use
   **Retrieve and inspect results** and open **Results**.

If step 1 reports missing access, use the appropriate setup below. Repeatedly
clicking Run will not correct missing access. Your original uploaded files stay
available if a calculation cannot be submitted.

## Choose the setup that matches your project

| What you opened | What to do |
| --- | --- |
| The instructor's existing CoChem-BASE repository | Follow [Use the instructor's repository](#use-the-instructors-repository). No student invitation is needed. |
| A private project owned by your personal GitHub account | Follow [Student personal project](#student-personal-project). Use the two links your instructor provides. |
| You are preparing access for a class or lab | Follow [Instructor: prepare student access](#instructor-prepare-student-access). Do this once before student enrollment. |

A **repository** is a project folder stored on GitHub. Its owner appears before
the slash in its name: `owner/project`. A **Codespace** is the VS Code workspace
that displays CoChem. **GitHub Actions** is the service that runs a calculation
on another computer. These are separate: ORCA does not need to be installed in
the Codespace to run an Actions calculation.

## Use the instructor's repository

<details>
<summary><strong>Show the instructor-repository steps</strong></summary>

1. Open the existing project on GitHub, such as `ProfJJK-CoChem/CoChem-BASE`.
   Choose **Code → Codespaces → Create codespace**. Approve the project
   permissions GitHub requests so CoChem can start and cancel Actions jobs,
   then wait for setup.
2. In VS Code's **Ports** panel, open **8866 — CoChem Voilà dashboard**. Keep
   its visibility **Private**.
3. In **Start here**, choose **GitHub Actions** and **Check ORCA & CFOUR**.
   Use the existing-repository access route. Do not enter student invitation
   links just because they appear in a different setup option.
4. Follow the status beside each engine. If it is available, return to the
   three steps at the top of this page. The calculation job installs and checks
   the selected engine before running it.

**If you administer this repository and an engine is unavailable:** open its
GitHub **Actions** tab and the check linked by CoChem. The failure identifies
whether the archive cannot be downloaded, installation failed, or the project
configuration is incomplete. The private archive must be a GitHub **Release
asset** in a repository the instructor's download credential can read.
Organization-level credentials must also be permitted for this calculation
repository. Having Read access to the archive repository in your browser is
not enough to give an Actions job that access.

<details>
<summary><strong>Instructor: connect existing organization download credentials</strong></summary>

If you already stored the ORCA/CFOUR download credentials in your GitHub
organization, you do not need to copy them into this repository.

1. Open the organization's **Settings → Secrets and variables → Actions →
   Secrets**. Open the existing ORCA download secret and ensure its repository
   access includes the project that will run the calculation.
2. Open the **Variables** tab on that same organization settings page. Create
   or edit `COCHEM_ORCA_ACCESS_SECRET`. Set its value to the **name** of your
   existing ORCA download secret, exactly as shown in step 1. Do not put the
   secret's hidden value here: variables are ordinary settings.
3. Give that variable access to the same calculation project. BASE uses this
   setting to find the download credential when an Actions job starts.
4. Repeat for CFOUR using `COCHEM_CFOUR_ACCESS_SECRET` and the name of its
   existing download secret.
5. Return to CoChem and choose **Check ORCA & CFOUR**. If the check fails, open
   its run link to see whether GitHub denied the download or the engine package
   could not be prepared.

These organization settings cover organization-owned projects only. Use the
App setup below for student-owned projects. The
[ORCA setup guide](ORCA_Actions_Setup.md) and
[CFOUR setup guide](CFOUR_Actions_Setup.md) cover archive/version checks and
expired download access. Students do not enter credentials in CoChem.

</details>

</details>

## Student personal project

<details>
<summary><strong>Show the student setup steps</strong></summary>

Your instructor needs to supply **three links**: the BASE template, the lab's
private access-setup repository and the lab's GitHub App installation page.
If they have not supplied them, the instructor must finish the next section
before this route can work. Do not invent a repository name or App name.

1. Accept your lab's GitHub organization/team invitation. Use the same GitHub
   account for the remaining steps.
2. Open the instructor's BASE template link. Choose **Use this template →
   Create a new repository**. Select **your personal account** as owner,
   name the project and choose **Private**. This creates your own copy.
3. In that project choose **Code → Codespaces → Create codespace**. Let BASE
   setup finish, then open the private **8866 CoChem Voilà dashboard** in VS
   Code's **Ports** panel.
4. Open **Start here → Connect using an instructor invitation**. Paste the
   complete access-setup repository URL into **Instructor's setup link** and
   the App URL into **Instructor's App installation link**, then choose
   **Save invitation**. These are web addresses, not passwords.
5. Open **Authorize lab app**. GitHub asks which projects the App may configure.
   Choose your personal account, **Only select repositories**, then **only
   this project**. Review the permissions and install.
6. Return to CoChem and choose **Request project access**. GitHub opens a
   prepared request page in the instructor's access-setup repository. Choose
   **Submit new issue**. The form is already filled in.
7. Wait for the success comment on that request. It says which components
   have been enabled. If it reports a failure, send its link to your instructor.
8. After success, stop the initial Codespace and create a **new Codespace**
   from your private project's **Code → Codespaces** menu. Approve the
   permissions GitHub shows for this project; they let CoChem submit files
   and start/cancel its Actions jobs. Rebuilding the old Codespace does not
   refresh these permissions. Do this before starting your research work
   in the initial workspace.
9. Let automatic setup finish. CoChem installs its modules for you. Open the
   dashboard, choose **GitHub Actions**, then **Check ORCA & CFOUR**. Continue
   with your own inputs when the required engine is available.

An **App** is GitHub's permission-based way for the instructor's setup service
to configure your selected project. The **access-setup repository** holds
those setup requests; it is not a second research project you must install.

Classroom50 supplies course instructions and collects project/report links.
It does not transfer the organization's credentials or usage allowance to your
personal project. Personal projects use the Actions allowance shown in the
student's GitHub account. Codespaces has its own usage allowance.

</details>

## Instructor: prepare student access

<details>
<summary><strong>Show the one-time instructor setup</strong></summary>

**Giving a student team Read access to ORCA/CFOUR is not the whole setup.**
GitHub Actions also needs access when it starts a calculation. An organization
secret is available only to permitted repositories owned by that organization;
it does not automatically reach a student's personal project.

For personal projects, the lab App supplies the approved access automatically.
The instructor must first:

1. Prepare the reviewed BASE template and private ORCA/CFOUR Release assets.
2. Set up the private access-setup repository and register the GitHub App.
3. Configure the App with the lab team, approved BASE version and private
   download access. The current App needs **Contents: Read and write** to
   prepare each selected project's Codespaces permissions. Follow the
   [one-time instructor App setup](Personal_Project_App_Deployment.md#what-you-configure-once-as-the-instructor).
4. Give students the **template URL**, **access-setup repository URL** and
   **App installation URL**. Send full clickable links, not a “slug.”
5. Enroll one real student first. Confirm their new Codespace installs the
   modules and that their own Actions account runs and returns one small
   calculation for each engine the course requires. Use the
   [student deployment pilot](Student_Deployment_Pilot.md) before wider rollout.

This repository contains the App integration, but publishing BASE does not
register a lab's App or configure its private credentials. Those GitHub settings
must be completed by an instructor who can administer the lab.

<details>
<summary><strong>Example invitation links and what they mean</strong></summary>

These are examples of the link shapes, not working invitations:

| Field in the invitation | Example shape | Purpose |
| --- | --- | --- |
| BASE template | `https://github.com/LAB/CoChem-BASE` | Create the student's private research project. |
| Access-setup repository | `https://github.com/LAB/CoChem-Project-Access` | Submit the prepared access request. |
| App installation | `https://github.com/apps/LAB-APP/installations/new` | Allow the lab App to configure only that student's selected project. |

Older interfaces asked for **Instructor access repository** and **Instructor
lab App slug**. The first meant the access-setup project; the second meant the
part after `github.com/apps/` in the App's address. Neither meant the ORCA or
CFOUR archive repository, an engine path, an access token or a chemistry input.
The current interface accepts the full links so you do not need to extract
those pieces yourself.

</details>

</details>

## Correct a mistaken choice

- **Wrong invitation:** choose **Clear invitation** under **Connect using an
  instructor invitation**, then paste the two correct links and choose
  **Save invitation**. Clearing it
  does not uninstall a GitHub App or revoke access already granted on GitHub.
- **Wrong uploaded file:** select it under **Your files** and choose **Remove
  from list**. Its original file and past calculation records are retained.
  Choose **Undo remove**, or open **Show removed inputs**, select the file and
  choose **Restore selected input** to make it available again.
- **Wrong reference attachment:** in **Calculations → Fragments / Frozen**,
  choose **Clear R2 reference** or **Clear starting Hessian** for the attachment
  you want to stop using. The original scientific file is retained.
- **Wrong results selected for comparison:** choose **Clear comparison
  selection** in **Results**. Saved calculations and reports remain available.
- **Wrong file or frame selected:** choose the correct file/frame and use
  **Use selected starting geometry** again. Recheck charge and multiplicity.
- **Wrong calculation submitted:** choose **Cancel calculation** for that run
  and confirm cancellation before submitting a corrected one. Removing an
  input from the list does not cancel a running calculation.

## Understand a setup message

| Message or situation | Meaning and next action |
| --- | --- |
| ORCA/CFOUR has not been checked | Choose **Check ORCA & CFOUR** in **Start here**. Wait for its linked check to finish. |
| ORCA/CFOUR is unavailable | That project's calculation job could not obtain or prepare that engine. Follow its linked check; an instructor corrects download access or the engine package. Other independent features remain usable. |
| “Course approval” or “approved BASE version” | The instructor's choice of the tested CoChem software version for calculations. It is not approval of a molecule, method, assignment or individual calculation. |
| “Variables read access” in an older interface | The interface tried to read GitHub project settings that its current login could not read. Being the repository owner does not mean the Codespace's temporary login has every permission. The current interface checks these settings through a short Actions job instead. Use the current interface and run **Check ORCA & CFOUR**; no extra Variables-read permission or access-token entry is required for that check. |
| An Actions workflow is missing or out of date | The instructor must update the CoChem workflow files in this project's default branch. **Check for updates** updates the managed installation, not these project files. Students do not edit workflow code. |
| Codespaces cannot start an Actions job | After the instructor updates the project's Codespaces permission settings, save your work, create a **new Codespace** and authorize the project permissions GitHub requests. A rebuild does not change the old Codespace's permissions. |
| Project configuration could not be checked | Open the linked Actions check in that same project. If Actions cannot start, the repository owner checks its Actions permissions and usage allowance. If the check starts and fails, give the instructor the run link and visible error. |
| A TOPOS or TORQ choice is unavailable | Automatic setup has not made that operation available, or a required input is missing. Read the nearby reason; use **Retry setup** after an access problem is corrected. |

The initial project-settings check is a short Actions job and may take about
a minute; it only checks configuration, not a chemical calculation.

A successful download check means an engine can be obtained. The calculation
still has to install it, validate its files and finish the chemistry successfully.

<details>
<summary><strong>Where to go after setup</strong></summary>

| CoChem section | What it is for |
| --- | --- |
| **Start here** | Check setup, select where calculations run, and get updates. |
| **Your files** | Upload, inspect, select, remove and restore scientific inputs. |
| **Calculations** | Set up energies, optimizations and enabled TOPOS/TORQ research operations. |
| **Spectra and properties** | Inspect supplied outputs and perform supported isotope/property analyses. |
| **Periodic structures** | Prepare cell-based calculations when assigned. |
| **Results** | Inspect returned calculations, tables, figures and downloads. |

See the [research guide](Student_Research_No_Code.md) for full supported input
formats, conformer comparison, measured outputs, reference files, reporting and
updates. You can use XYZ, MOL/SDF, MOL2, PDB, QCSchema, conformer pools, periodic
structures, Hessians and supported numerical/native-output files. A monomer or
complex XYZ is just one starting point.

ORCA and CFOUR are optional and strongly recommended. Their absence must not
block ingestion or independent free calculations. Scientific methods remain
available only when their required engine, module and input checks succeed.

</details>
