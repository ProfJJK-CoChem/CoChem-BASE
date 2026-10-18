# CoChem-BASE

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)

CoChem-BASE is the place to upload your scientific files, choose a calculation
and inspect its results. It prepares the other CoChem components, including
TOPOS and TORQ, for you.

**[Start here: open CoChem and run your first calculation](.docs/GET_STARTED.md)**

Already viewing the CoChem dashboard in your browser?

1. Open **Start here**, select **GitHub Actions** under **Run calculations on**,
   and choose **Check ORCA & CFOUR**.
2. Open **Your files** and upload your own structures or other scientific inputs.
   For a molecular calculation, select the intended frame, choose **Use selected
   starting geometry**, then **Continue to calculation settings**.
3. In **Calculations → Method and settings**, check charge and spin, then choose
   the assigned engine, method, basis and surroundings. Choose the task under
   **Calculate** and select **Run on GitHub Actions**.

Open **Explain…** beside a setting for examples and scientific guidance. Use
**Scientific terms** in the sidebar to search definitions; your calculation draft
stays in place. The TOPOS and TORQ tabs have their own named start buttons.

If an engine is unavailable, follow the explanation beside it in **Start here**.
ORCA and CFOUR are **optional and strongly recommended**. Missing access to one
leaves only its dependent choices unavailable. You can still upload files and
use the installed free methods.

## Open the interface

In your project on GitHub, choose **Code → Codespaces → Create codespace**.
A Codespace is your browser-based VS Code workspace. Approve the project
permissions GitHub requests, then wait for automatic setup.
Open **8866 — CoChem Voilà dashboard** from VS Code's **Ports** panel; keep
that port **Private**.

The Codespace displays the interface. **GitHub Actions** runs a calculation on a
separate computer and returns its results. No student terminal commands, Python
editing, access-token entry or separate TOPOS/TORQ checkout are required.

**Using the instructor's existing repository?** Start with its configured
access; you do not need a student App invitation. **Creating your own private
project?** Follow the [student setup steps](.docs/GET_STARTED.md#student-personal-project).
Your instructor must prepare that access before you can use private engines.

## Find what you need

| I want to… | Open… |
| --- | --- |
| Get started, enable an engine, or understand a setup message | [Quick start and troubleshooting](.docs/GET_STARTED.md) |
| Upload XYZ, MOL/SDF, MOL2, PDB, QCSchema, conformer pools or measured data | [Scientific input and research guide](.docs/Student_Research_No_Code.md#use-the-scientific-input-library) |
| Set up student-owned projects as an instructor | [Instructor access setup](.docs/GET_STARTED.md#instructor-prepare-student-access) |
| Collect student work through Classroom50 | [Classroom50 assignment guide](.docs/Classroom50_Assignment_Deployment.md) |
| Read the software's tested scope and remaining work | [Implementation status](.docs/SRS_Implementation_Status.md) |

Students supply their own starting structures and scientific files. XYZ is one
supported format, not the only input route. BASE keeps uploaded originals and
calculation records so results can be checked later.

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

Maintainers should read the [workstation completion handoff](.docs/WORKSTATION_COMPLETION_HANDOFF.md).
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
