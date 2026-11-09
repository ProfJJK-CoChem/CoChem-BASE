# CoChem-BASE

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

CoChem helps you study molecular shapes, energies and interactions using
computer calculations. **CoChem-BASE is the one project you start with.** Its
browser interface prepares the CoChem tools, including TOPOS and TORQ, and
brings your files, calculations and results together.

## Students: start your project here (4 clicks — no secrets or enrollment needed)

**[Open the step-by-step student guide](.docs/GET_STARTED.md#student-personal-project)**

You use buttons and menus in your web browser. You do not need to install Python,
type computer commands, request organization invites, or install a GitHub App.
`CoChem-BASE` automatically provisions **`PySCF`**, **`xTB`**, **`CREST`**,
**`TOPOS`**, and **`TORQ`** inside your GitHub Codespace, and connects to
**`GPU4PySCF`** on Google Colab GPU.

### 1. Create your GitHub account and copy `CoChem-BASE`

1. Sign in to your [GitHub account](https://github.com/signup) (or create one).
2. Open [ProfJJK-CoChem/CoChem-BASE](https://github.com/ProfJJK-CoChem/CoChem-BASE).
3. Click **Use this template → Create a new repository** (or **Fork**) near the top right.
4. Under **Owner**, select **your own GitHub username** and name your repository
   **`CoChem-[target-molecule]`** (for example `CoChem-benzene-water`), then click
   **Create repository**.

### 2. Open CoChem in GitHub Codespaces

1. On **your new repository's page**, click the green **Code** button.
2. Select the **Codespaces** tab, then click **Create codespace on main**.
3. Wait 2–4 minutes while your Codespace prepares `PySCF`, `xTB`, `CREST`,
   `TOPOS`, and `TORQ`. Port **8866 (`CoChem Voilà dashboard`)** displays a live
   auto-refreshing setup progress page and automatically opens the CoChem
   dashboard as soon as setup finishes. (If the browser tab did not open
   automatically, open VS Code's **Ports** panel at the bottom and click the
   globe icon next to **8866 — CoChem Voilà dashboard**.)

### 3. Work through the CoChem dashboard

| In CoChem, open… | What you do |
| --- | --- |
| **Start here** | Confirm **Run calculations on** is set to **Linux** (your Codespace, where `PySCF`, `xTB`, `CREST`, `TOPOS`, and `TORQ` are ready immediately) or use the Google Colab GPU notebook for **`GPU4PySCF`**. |
| **Your files** | Upload your own scientific inputs (such as Avogadro 2 `.xyz` files) and select the starting structure. |
| **Calculations** | Inspect **Starting structure**, choose **`PySCF`** or **`xTB`**, enter your study's charge, multiplicity, method, and basis set, and run the calculation. |
| **Results** | Inspect the available values, structures, tables, and figures, and click **Download calculation bundle** to save a copy to your computer. |

**[Continue with the full instructions: upload, calculate, save and submit](.docs/GET_STARTED.md#6-upload-your-own-scientific-files)**

Open **Explain…** beside a setting, or **Scientific terms** in the sidebar,
whenever a word is unfamiliar. You can read the help without losing your draft.
ORCA and CFOUR are **optional and strongly recommended** calculation programs.
If one is unavailable, its dependent choices stay unavailable; other available
features remain usable. Your instructor fixes lab access—students do not enter
tokens or download licensed engine archives.

**Save your work:** keep your original input files on your own computer and
use **Download calculation bundle** after retrieving a result. Uploaded research
files and results are stored separately from the code; saving or synchronizing
the repository does not back them all up. Follow the guide's
[save and submit steps](.docs/GET_STARTED.md#9-save-and-submit-your-work), then
[stop your Codespace](.docs/GET_STARTED.md#10-stop-and-reopen-your-workspace)
when finished.

## Find the right guide

| You need… | Open… |
| --- | --- |
| Every student step, from a new account to your first saved result | [Student start guide](.docs/GET_STARTED.md#student-personal-project) |
| Help with a missing button, unavailable engine or setup message | [Troubleshooting](.docs/GET_STARTED.md#understand-a-setup-message) |
| Supported inputs, monomers/complexes, TOPOS/TORQ analyses and interpreting results | [Scientific research guide](.docs/Student_Research_No_Code.md) |
| Instructor preparation for personal student projects | [Instructor access setup](.docs/GET_STARTED.md#instructor-prepare-student-access) |
| Optional Colab GPU access, current limits and instructor secret setup | [Colab GPU setup](.docs/Google_Colab_GPU_Setup.md) |
| Classroom50 assignment submission and collection | [Classroom50 guide](.docs/Classroom50_Assignment_Deployment.md) |

Classroom50 provides your course instructions and submission route. Your private
`CoChem-` project is where you work. Follow your instructor's instructions to
share the finished report; a private project is not automatically visible to
an instructor. Student-owned projects use that account's Actions allowance;
Codespaces has a separate allowance. Check the payer and usage shown by GitHub
before agreeing to paid use.

<details>
<summary><strong>Other calculation environments: local computer or HPC</strong></summary>

The interface and calculation location are separate choices. BASE also supports
local Linux, Windows/WSL2, macOS and configured HPC schedulers. Use the correct
engine build and complete setup on the computer that will run the calculation.
A Linux ORCA archive does not run natively on Windows or macOS.

[ORCA setup](.docs/ORCA_Actions_Setup.md) ·
[CFOUR setup](.docs/CFOUR_Actions_Setup.md) ·
[Ecosystem module setup](.docs/Ecosystem_Modules_Setup.md)

</details>

<details>
<summary><strong>Instructor deployment and release records</strong></summary>

The [instructor-managed App guide](.docs/Personal_Project_App_Deployment.md)
contains the one-time configuration for students' personal private projects.
An App is GitHub's way to grant the lab's setup service permission to configure
selected projects. Team membership alone does not copy an organization's
credentials into a personal repository.

Run the [single-student pilot](.docs/Student_Deployment_Pilot.md) before a class
rollout. The current **1.1 release candidate** is not a blanket certification
of every scientific method or student deployment. See the
[SRS conformance record](.docs/SRS_Student_1_1_Conformance_Trace.md) for evidence
and open qualifications. The [1.0.1](.docs/Release_1_0_1.md) and
[1.0.0](.docs/Release_1_0_0.md) records describe earlier releases.

</details>

<details>
<summary><strong>Workstation and developer installation</strong></summary>

## Expert local and developer setup

The commands below prepare local workstations and development checkouts. Use
Python 3.12 for the pinned Stage 0 environments. Students using Classroom50
and Codespaces follow the graphical guide above; automatic BASE setup prepares
their workspace and hidden ecosystem components.

The [private-project expert alternatives](.docs/Private_Student_Projects.md#expert-alternatives-for-authorized-repository-owners)
retain manual GitHub CLI and licensed local-provisioning procedures for experienced
maintainers. Those commands are not part of the student deployment route.

From an upstream development checkout:

```bash
git clone https://github.com/ProfJJK-CoChem/CoChem-BASE.git
cd CoChem-BASE
./Launch_CoChem_Mac_Linux.sh
```

An unpacked source distribution provides the same launcher. In Windows
PowerShell, use `.\Launch_CoChem_Windows.bat --native`. The launchers prepare the UI environment and open
`Start_Here.ipynb` with Voilà. To prepare without launching:

```bash
python3 scripts/bootstrap_environment.py
```

Interaction and calculation environments are separate choices. BASE submits
Actions requests and retrieves their verified results through the interface.
Native execution requires
the selected host's audited setup. For a remote interface, use an authenticated
host connection and SSH port forwarding according to the site's access policy.

## Python installation and CLI

The wheel supplies Python packages and `cochem-cli`. The complete notebook and
launcher pathway uses a source checkout or source distribution. Installing the
package does not install licensed engines or authorize their use.

For development in a separate virtual environment:

```bash
python3.12 -m venv /path/outside/checkout/cochem-env
source /path/outside/checkout/cochem-env/bin/activate
python -m pip install -e '.[dev,ui,catalog,symmetry,scribe]'
cochem-cli --version
cochem-cli --help
```

The installed module form is `python -m cochem_base.cli`; source users can run
`python cli.py`. For a prepared host:

```bash
cochem-cli setup --all --artifact-dir /path/outside/checkout/artifacts
cochem-cli status --json
cochem-cli run --help
```

The default setup storage profile requires 50 GB free. Small hosted examples
use an explicit bounded profile after provisioner disk checks; that does not
reduce the requirements of larger calculations.


</details>

<details>
<summary><strong>Architecture, development checks and completion handoff</strong></summary>

Replacement agents should start with the [current takeover brief](.docs/AGENT_TAKEOVER.md),
then read the [complete implementation backlog](.docs/WORKSTATION_COMPLETION_HANDOFF.md).
The governing requirements are [SRS Chunk 17](.docs/SRS_Chunk_17_CoChem_BASE_Architecture.md)
plus [proposal additions](.docs/SRS_Chunk_Proposal_CoChem_BASE_Architectural_Review.md).
The [ingestion specification](.docs/task1_subsystems_architectural_specification.md)
and [Method Matrix](Method_Matrix.md) define input and scientific requirements.

In a prepared development environment, the canonical check is:

```bash
python ci_tools/base_ci.py all --output /path/outside/checkout/acceptance
```

[Scientific acceptance](.docs/ORCA_Scientific_Acceptance.md) distinguishes actual
calculations from setup, browser and software checks. Code, managed runtimes,
original inputs and results are stored separately.

</details>
