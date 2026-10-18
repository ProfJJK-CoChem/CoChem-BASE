# Start your CoChem project: a guide for students

You can follow this guide with a web browser. No programming experience is
needed. **CoChem-BASE is the only CoChem repository you create.** BASE prepares
TOPOS and TORQ and presents their tools on the same CoChem page.

You provide your own starting structures and other scientific files. Your
instructor supplies access to the lab and the calculation settings for your
study. A calculation uses a mathematical model of your molecule; its answer
needs to be interpreted using that model's assumptions and limitations.

## Before you begin

Use a laptop or desktop browser so there is room for the controls. Have your
instructor's three links ready:

| Link | What it is for |
| --- | --- |
| **CoChem-BASE template** | The starting copy used to make your private project. |
| **Instructor's setup link** | A lab page where you request access for your project. |
| **Instructor's App installation link** | A GitHub page where you allow the lab to prepare that project. |

These are ordinary web addresses. You do not need a password or access token
from your instructor. If a link is missing, ask your instructor for it before
attempting enrollment; do not guess a repository name or App name.

A **GitHub App** here is the lab's permission-based setup service. It is not a
chemistry program you install on your laptop. Your instructor must have prepared
it before these enrollment steps can succeed.

## Student personal project

Follow these steps in order the first time. Keep this guide open in one browser
tab and your project in another. Clicking a link may open another tab; return
to the CoChem tab when the instructions say to return to CoChem.

[1. Account](#1-sign-in-to-your-own-github-account) →
[2. Private project](#2-create-your-private-project) →
[3. First Codespace](#3-open-your-first-codespace) →
[4. Lab access](#4-connect-your-project-to-the-lab) →
[5. Research Codespace](#5-open-the-new-codespace-for-your-research) →
[6. Files](#6-upload-your-own-scientific-files) →
[7. Settings](#7-choose-your-calculation-settings) →
[8. Calculate](#8-run-and-retrieve-your-calculation) →
[9. Save and submit](#9-save-and-submit-your-work) →
[10. Stop and reopen](#10-stop-and-reopen-your-workspace).

### 1. Sign in to your own GitHub account

1. Open [GitHub](https://github.com/). If you have no account, choose
   **Sign up**, follow the registration screens and verify your email address.
   If you already have an account, choose **Sign in**.
2. Check your profile picture/menu near the top right and note your **username**.
   This is your GitHub account name, not your email address.
3. Accept the lab's organization/team invitation sent by your instructor.
   Complete any separate Classroom50 enrollment the course requires.
4. Use this same GitHub account for all remaining steps.

**Check before continuing:** you know your username and have the three links
listed above. A Google sign-in alone does not tell you which GitHub username
is active.

### 2. Create your private project

A **repository** means an online project folder on GitHub. A **template** is a
prepared starting copy of that folder.

1. Open the instructor's CoChem-BASE template link. The standard template is
   [ProfJJK-CoChem/CoChem-BASE](https://github.com/ProfJJK-CoChem/CoChem-BASE).
2. Near the top of the page, choose **Use this template → Create a new repository**.
   Do not choose **Fork**; this course uses an independent private copy.
3. In **Owner**, select **your own GitHub username**, rather than the lab's
   organization name.
4. In **Repository name**, enter **`CoChem-[target molecule name]`**, replacing
   the bracketed words with your molecule or complex name. Examples:
   **`CoChem-benzene`**, **`CoChem-benzene-water`** or
   **`CoChem-formic-acid-dimer`**. Use hyphens instead of spaces; do not type
   the square brackets. If your intended name already exists in your account,
   open that project and check with your instructor before creating another.
5. Select **Private**. Leave the other options at their defaults, then choose
   **Create repository**.
6. Bookmark the new project's page. A bookmark is your browser's saved link
   to a page, usually made with the star beside the address bar.

**Check before continuing:** the page shows
**your-username / CoChem-your-molecule** and a **Private** label. Its address
belongs to your account, not `ProfJJK-CoChem`. You need only this one research
repository; BASE obtains its other modules for you.

### 3. Open your first Codespace

A **Codespace** is a computer workspace provided by GitHub. It opens **VS Code**
in your browser. VS Code is the workspace window; the **CoChem dashboard** is
the page where you use chemistry buttons. You need not install VS Code locally.

1. On **your private project's page**, choose the green **Code** button above
   the file list. Choose the **Codespaces** tab.
2. Choose **Create codespace on main**. Here, `main` is the name of the project's
   primary version; keep it selected. Review the account that GitHub will bill
   and the machine choice. If GitHub asks you to agree to a charge you do not
   understand, ask your instructor before accepting it.
3. GitHub may request permissions. The original template can list instructor
   repositories that your account cannot authorize. If this happens, choose
   **Continue without authorizing**, if offered, to open the initial workspace
   with its own project access. You do not need permission to edit the
   instructor's source. If that choice is absent or creation fails, send the
   visible message to your instructor. This is
   [GitHub's documented permission flow](https://docs.github.com/en/codespaces/managing-your-codespaces/managing-repository-access-for-your-codespaces#authorizing-requested-permissions).
4. Wait while the browser workspace builds and CoChem installs. The first
   setup downloads programs and can take several minutes. A window of setup
   messages is normal; you do not need to type into it.
5. CoChem may open automatically in another tab. If it does not, find
   **Ports** at the bottom of VS Code. If Ports is hidden, use
   **View → Open View…**, type **Ports** and select it. The main menu may be
   behind the three-line menu button at the upper left.
6. In Ports, find **8866 — CoChem Voilà dashboard**. Use its **Open in Browser**
   globe icon or forwarded address to open CoChem. Keep **Port Visibility**
   set to **Private**. If there is no 8866 entry after setup finishes, save the
   setup error and ask your instructor; do not create repeated workspaces.

**Check before continuing:** you see the CoChem page with **Start here**,
**Your files**, **Calculations** and **Results** on the left.
This first Codespace is for enrollment. Wait until step 5 before uploading
research files, because a new Codespace does not copy this one's local data.

### 4. Connect your project to the lab

1. In CoChem, choose **Start here** and set **Run calculations on → GitHub
   Actions**. Open **Connect using an instructor
   invitation (personal projects)**; its button may start with **Show**.
2. Paste the complete **setup link** from your instructor into
   **Instructor's setup link**.
3. Paste the complete **App installation link** into
   **Instructor's App installation link**. Select the optional ORCA/CFOUR
   access requests that your course needs, then choose **Save invitation**.
   If you made a mistake, choose **Clear invitation** and enter the links again.
4. Choose **Authorize lab app**. On the GitHub page that opens, select your
   personal account and **Only select repositories**. Select **only your
   `CoChem-` project**, review the requested permissions and choose **Install**
   or the installation-confirmation button GitHub displays.
5. Return to the CoChem tab. Choose **Request project access**. GitHub opens
   a request page with its text already filled in. Choose **Submit new issue**.
   An **issue** here is a setup request, not a chemistry error or an assignment.
6. Wait for the lab service to post a **success comment** beneath the request.
   Read which components it enabled. If it reports a failure or no response
   arrives, send that request page's link to your instructor. Do not repeatedly
   submit the same request.

**Check before continuing:** the request has a success comment for **your
project**. Simply installing the App is not the whole enrollment process.
Organization/team membership alone does not give a personal project the lab's
calculation access. Students do not create or paste access tokens.

### 5. Open the new Codespace for your research

The lab setup gives the project permission to submit calculations. GitHub
applies the changed permissions to a **new Codespace**. Reopening or rebuilding
the first Codespace does not apply them.

1. If you uploaded anything in the initial workspace, download the original
   files and completed calculation bundles to your own computer before leaving.
2. Open [Your codespaces](https://github.com/codespaces). Find the initial
   Codespace by the **your-username/CoChem-your-molecule** repository shown
   beside it. Its generated workspace name may be different from your molecule.
3. Open its **…** menu and choose **Stop codespace**. Keep it; do not delete it.
4. Open [Create a new Codespace](https://github.com/codespaces/new). Select
   **your private `CoChem-` repository**, branch **main**, and the machine
   recommended by your instructor. Review the payer/usage information, then
   choose **Create codespace**. Authorize the requested access to your project.
   If required access is denied, send the message to your instructor.
5. Wait for automatic setup, then open the CoChem dashboard as in step 3.
   BASE installs the approved TOPOS/TORQ components itself. If setup reports
   a failure, use the nearby explanation or give the message to your instructor;
   do not install another CoChem repository manually.
6. In **Start here**, set **Run calculations on → GitHub Actions**.
   Check the displayed project is **your-username/CoChem-your-molecule**.
7. Choose **Check ORCA & CFOUR** and wait for the result beside each engine.
   A linked check opens on GitHub if you need to see its progress.

**Check before continuing:** setup has finished, the correct project is selected,
and the engine required by your study is available. The engine access check
confirms whether the program can be obtained; each calculation still installs
and verifies its engine before running chemistry.

ORCA and CFOUR are **optional and strongly recommended**. If one is unavailable,
its dependent methods cannot be selected. Other available features remain
usable. Your instructor handles engine access; you do not download licensed
archives into your project. A failed check is not a reason to change the
scientific method without your instructor's guidance.

### 6. Upload your own scientific files

For the common Avogadro 2 route, draw or prepare your molecule or complex,
then use **File → Save As…** and choose the **XYZ** format. Keep that original
file on your computer. Use distinct names for different starting arrangements.
Your instructor can help you check the intended atoms, hydrogens and structure.

1. In CoChem, choose **Your files** on the left.
2. For an ordinary structure, leave **File contents → Detect from file**.
   Choose **Upload scientific inputs**. In the file-selection window, find
   the file you saved, select it and choose **Open**.
3. Read the validation message. Select **Your uploaded file** and the intended
   **Structure / frame**. A frame is one structure within a file that contains
   several structures.
4. Choose **Use selected starting geometry**, then
   **Continue to calculation settings**. A **geometry** means the arrangement
   of atoms in space; a starting geometry is your initial guess.
5. In **Calculations**, open the **Starting structure** tab. Inspect the
   molecule displayed and check the intended atoms and arrangement. If you
   selected the wrong file, return to **Your files** and select the correct one.
   Use **Remove from list** for an unwanted upload and **Undo remove** to
   recover an accidental removal.

**Check before continuing:** the intended molecule is the selected starting
structure. Merely uploading a file does not select it for a calculation.

You can provide an individual molecule, separate monomers, a complex or other
supported scientific data. **XYZ is not the only input route.** The
[scientific input guide](Student_Research_No_Code.md#use-the-scientific-input-library)
covers molecular files, conformer collections, periodic structures, Hessians
and calculation outputs. Use its
[separate-monomer instructions](Student_Research_No_Code.md#upload-your-structures)
when your project starts from separate molecules; uploading two files alone
does not combine them into a complex.

### 7. Choose your calculation settings

1. Open **Calculations → Method and settings**.
2. Set **Total charge** and **Spin multiplicity** for your molecule. An XYZ
   file normally does not supply these values. Use values established for your
   target; ask your instructor if you do not know them. Do not assume the
   displayed defaults are correct for an ion or radical.
3. Follow your study instructions for **Scientific goal**, engine,
   **Theory family**, method, basis and **Surroundings**. Use
   **Gas phase (no solvent model)** only when the study calls for an isolated
   molecule or complex. Open **Explain…** beside a setting when needed.
4. Under **Calculate**, choose the task your study requires. Review the
   settings and any requested monomer/reference inputs. Leave advanced
   protocols alone unless your study calls for them.
5. Use the instructor's CPU and memory limits. A larger resource selection
   is not automatically a better calculation and can consume more allowance.

<details>
<summary><strong>What do the calculation settings mean?</strong></summary>

| Term | Meaning |
| --- | --- |
| Engine | The program that performs the chemistry calculation, such as ORCA. |
| Charge | The molecule's net electrical charge; this affects its electron count. |
| Spin multiplicity | A number describing the electronic spin state. It is not the number of atoms or fragments. |
| Method | The mathematical approximation used to calculate the molecule's behavior. |
| Basis | The mathematical functions used to describe the electrons for methods that need a basis set. |
| Single-point energy | Evaluate the energy of the selected atomic arrangement without moving its nuclei. |
| Optimization | Move the allowed atomic coordinates while seeking a lower-energy stationary structure. |
| Frequency calculation | Examine local curvature and vibrational behavior; it helps assess an optimized structure. |
| Scan | Evaluate a series of structures along a chosen coordinate, such as intermolecular separation. |

Open **Scientific terms** in CoChem for more definitions. Looking up a word
preserves your calculation draft. A more expensive method or a completed job
alone is not evidence that a scientific result is accurate.

</details>

**Check before continuing:** your structure, electronic state, task and settings
match the study. A small installation-test calculation is not a recommended
research method for a van der Waals complex.

### 8. Run and retrieve your calculation

1. Choose **Run on GitHub Actions** once. GitHub Actions runs the calculation
   on a separate computer. You do not need to leave your laptop calculating.
   A TOPOS or TORQ operation has its own named start button in that tab; use
   the [research guide](Student_Research_No_Code.md#read-results-and-create-your-report)
   for those tasks.
2. Wait for CoChem to show the request and its GitHub run link. Save that link.
   **Queued** means it is waiting; **running** means the job has started. If
   submission is unconfirmed, follow the displayed guidance before retrying so
   you do not accidentally launch a duplicate calculation.
3. Stay in **Calculations** and scroll below the tabs to **Run calculation**
   (called **Current calculation** when using TOPOS/TORQ).
   Choose **Refresh calculation status** to check progress. If you submitted
   the wrong task, use **Cancel calculation** for that job and wait for its
   cancellation to be confirmed. Closing a browser tab is not cancellation.
4. After the job succeeds, choose **Retrieve and inspect results** in that
   same panel. CoChem downloads and checks the returned files.
5. Still in that panel, choose **Download calculation bundle**. Your browser
   saves a ZIP file,
   usually in **Downloads** unless you chose another location. A ZIP is one
   package containing the calculation's files and records.
6. Choose **Results** on the left to inspect the available values, structures,
   tables and figures.

**Check before continuing:** you have retrieved the result and can find the
bundle on your own computer. Read the reported method, units, convergence and
warnings. A single-point energy does not prove a structure is a stable minimum;
use the analyses required by your study before drawing that conclusion.

### 9. Save and submit your work

1. On your own computer or course-approved storage, keep a folder named after
   your project. Save your original inputs, downloaded calculation bundles
   and final report there. GitHub's temporary result downloads expire, so
   retrieve and save them promptly.
2. Follow the instructor's instructions for the report and data to submit.
   To put a small finished report in your private GitHub project, return to
   its web page and choose **Add file → Upload files**. Select the course-approved
   report, such as a PDF, then choose **Commit changes** and confirm the save
   on the screen GitHub presents. Here, **commit** means save a recorded version
   of that file on GitHub.
3. Open the saved report from your repository's file list to confirm it is
   there. Use the course-approved data storage for large calculation bundles
   and original research data, rather than uploading entire runtime folders
   or engine distributions to GitHub.
4. Submit the requested report/project links through your Classroom50
   assignment. **Classroom50 is the course submission and feedback site**;
   it does not automatically copy everything from this private project.
5. Confirm your instructor can open the submission. If repository access is
   needed, use your project's **Settings → Collaborators → Add people** and
   invite the instructor's GitHub username supplied by the course. The
   instructor must accept the invitation. Do not make the project public just
   to submit an assignment.

**Check before continuing:** your saved files exist outside the Codespace and
are accessible through the course's submission route.

**Important:** CoChem keeps uploaded inputs and calculation data separately
from the program's repository. **Commit** or **Sync Changes** does not save all
of those files. Keep the original files and use **Download calculation bundle**;
do not rely on the Codespace as your only copy.

### 10. Stop and reopen your workspace

1. Finish saving. If a calculation is still running, keep its run link and
   decide whether to let it finish or cancel it through CoChem.
2. Open [Your codespaces](https://github.com/codespaces), find this project's
   current Codespace, open **…** and choose **Stop codespace**. Closing the
   browser alone does not immediately stop the workspace. Stopping a Codespace
   does not cancel a separately running GitHub Actions job.
3. Next time, return to **Your codespaces** and click the name of this same
   workspace to resume it. Open the CoChem dashboard and continue. You normally
   reopen the existing Codespace, rather than create another for every session.
4. Delete a Codespace only after saving its important files elsewhere. A new
   Codespace does not automatically inherit the old one's local research data.

Your personal project's **Actions** and **Codespaces** usage have separate
allowances. Check the usage/payer shown by GitHub; do not assume the lab or
Classroom50 pays for either service.

## Get updates and help

When the instructor announces an update, save your results first, then use
**Start here → CoChem tools and updates → Check for updates → Apply compatible
updates**. Follow the offered restart instructions. The
[update guide](Student_Research_No_Code.md#get-bug-fixes-without-losing-your-work)
explains what is preserved and when a new Codespace is required.

If CoChem reports that a project workflow is missing or out of date, send the
message and your project link to the instructor. That part needs a project-file
update by the instructor; students do not edit workflow code.

For help, send the course support contact the step number, the visible message
or screenshot, your project link and the calculation run link if available.
Never send passwords, access tokens or licensed engine archives. The table
below explains common messages. The
[research guide](Student_Research_No_Code.md) explains supported inputs,
TOPOS/TORQ operations and interpreting results.

## Correct a mistaken choice

- **Wrong invitation:** choose **Clear invitation** under **Connect using an
  instructor invitation**, then paste the two correct links and choose
  **Save invitation**. Clearing it
  does not uninstall a GitHub App or revoke access already granted on GitHub.
- **Wrong uploaded file:** select it under **Your files** and choose **Remove
  from list**. Its original file and past calculation records are retained.
  Choose **Undo remove**, or open **Show removed inputs**, select the file and
  choose **Restore selected input** to make it available again.
- **Wrong reference attachment:** in **Calculations → Monomer constraints**,
  choose **Clear R2 reference** or **Clear starting Hessian** for the attachment
  you want to stop using. The original scientific file is retained.
- **Wrong results selected for comparison:** choose **Clear comparison
  selection** in **Results**. Saved calculations and reports remain available.
- **Wrong file or frame selected:** choose the correct file/frame and use
  **Use selected starting geometry** again. Recheck **Total charge** and **Spin multiplicity**.
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

## Continue with your research

The [research guide](Student_Research_No_Code.md) explains supported input
formats, conformer comparison, calculated outputs, reference files, reporting
and updates. Molecular starting geometries are one route; BASE also accepts
conformer pools, periodic structures, Hessians and supported numerical or native
calculation outputs.

ORCA and CFOUR are optional and strongly recommended. An unavailable engine
leaves its dependent methods unavailable; ingestion and independent supported
features remain usable.

<details>
<summary><strong>Use a local computer or an institutional cluster</strong></summary>

Choose the route your instructor has prepared under **Start here → Run
calculations on**. **Local** means the computer running BASE; if you opened
BASE in a Codespace, that is the Codespace, not your laptop. Windows calculations
use the configured WSL route; Linux and macOS use their prepared native setup.
Choose **Find installed engines** to discover installed ORCA/CFOUR, or use the
instructor-provided executable paths and **Use these executable paths**.

For **HPC**, use the institution's prepared connection and scheduler settings.
Jobs may wait in a queue before running. Open **Where this interface runs** if
you need to review where the dashboard is hosted. Changing that display setting
does not move an engine installation or grant access to a remote computer.
Follow the same file selection, scientific settings and result-review steps;
use the submit button for the selected calculation environment.

</details>

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
   [upload and calculation steps](#6-upload-your-own-scientific-files).
   The calculation job installs and checks
   the selected engine before running it.

**If you administer this repository and an engine is unavailable:** open its
GitHub **Actions** tab and the check linked by CoChem. The failure identifies
whether GitHub permits access to the approved archive or the project
configuration is incomplete. This short check reads the archive's metadata;
the calculation job downloads, installs and tests the program. The private archive must be a GitHub **Release
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
   its run link to see whether GitHub denied access or could not verify the
   approved archive.
6. Public TOPOS/TORQ sources need no download credential. Only if your course
   uses private modules, repeat the setup with
   `COCHEM_SOURCE_ACCESS_SECRET` and the name of the existing private-module
   download secret. Include the calculation project in both access lists.

For the public instructor repository, an organization setting restricted to
**private repositories** does not include CoChem-BASE. Select CoChem-BASE
explicitly in the allowed repositories. If the check says Actions received no
download credential, verify these connections before replacing the credential;
the check has not yet attempted to download the archive.

If the check instead reports **HTTP 401**, GitHub rejected the stored download
credential. The instructor replaces the value of that existing organization
secret with a valid token; its name and the matching variable stay the same.
The token needs access to the engine's private repository. On GitHub's
fine-grained token page, use **Permissions → Add permissions → Contents →
Read-only**, select the correct organization/repository and an expiration date,
and complete organization approval if required. Paste the generated value only
into the organization's **Secrets** page, never into a variable or the CoChem
interface. A **403** or **404** instead needs an access/organization-policy check;
repeatedly creating tokens does not repair an incorrect repository selection.

These organization settings cover organization-owned projects only. Use the
App setup below for student-owned projects. The
[ORCA setup guide](ORCA_Actions_Setup.md) and
[CFOUR setup guide](CFOUR_Actions_Setup.md) cover archive/version checks and
expired download access. Students do not enter credentials in CoChem.

</details>

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
