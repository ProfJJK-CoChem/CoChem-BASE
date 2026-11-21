# CoChem-BASE

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

CoChem helps you study molecular shapes, energies and interactions using
computer calculations. **CoChem-BASE is the one project you start with.** Its
browser interface prepares the CoChem tools, including TOPOS and TORQ, and
brings your files, calculations and results together.

## Start the student conformer lab

Use a public fork for all course research. A fork is your own copy of this project on GitHub.

1. Sign in to GitHub and select **Fork** at the top of this page. Choose your own account under **Owner**, then select **Create fork**. In your copy, open **Actions** and enable workflows if GitHub asks.
2. In your copy, click **Code → Codespaces → Create codespace on main**. A Codespace is a workspace that opens in your browser. Wait for the dashboard to open. If it does not appear, click **Ports** at the bottom of the workspace, find **8866**, and click its globe icon.
3. In CoChem open **1 · Setup → Run your first molecule**. Check the GitHub project name, leave **Practice with ethanol** selected, and click **Run in CoChem** once. Save the run link. For a research molecule choose **Use my XYZ file**.
4. Click **Check run and get files**. After **Results verified** appears, click **Save results ZIP** and **Save checksum**. Upload both files to the instructor’s Google Drive folder listed in your assignment. Keep the ZIP closed.
5. To run directly on GitHub, use **Actions → Student conformers (CREST, MACE, CPU PySCF) → Run workflow** in your fork. The student guide shows which two files to submit from the GitHub download.

CREST searches for shapes. MACE compares their energies. CPU PySCF adjusts the lowest-ranked shape to optimize its geometry. The public lab uses GitHub-hosted compute and requires no ORCA or CFOUR license. Select **Guidance for my course or research group** for your course. Use **Help search** or **Explain a button or field** when a word or control is unfamiliar.

[Click-by-click student guide](student/README.md) · [Ethanol lab and worked comparison](student/ETHANOL_LAB.md) · [Account and workspace setup](.docs/GET_STARTED.md#student-personal-project)

## Find the right guide

| You need… | Open… |
| --- | --- |
| Every student step, from a new account to your first saved result | [Student start guide](.docs/GET_STARTED.md#student-personal-project) |
| Help with a missing button, unavailable engine or setup message | [Troubleshooting](.docs/GET_STARTED.md#understand-a-setup-message) |
| Supported inputs, monomers/complexes, TOPOS/TORQ analyses and interpreting results | [Scientific research guide](.docs/Student_Research_No_Code.md) |
| Instructor preparation for personal student projects | [Instructor access setup](.docs/GET_STARTED.md#instructor-prepare-student-access) |
| Optional Colab GPU access, current limits and instructor secret setup | [Colab GPU setup](.docs/Google_Colab_GPU_Setup.md) |
| Classroom50 assignment submission and collection | [Classroom50 guide](.docs/Classroom50_Assignment_Deployment.md) |

Use the course assignment site for feedback, reports and the instructor’s Drive link. Files committed to your public fork and public Actions logs can be read by anyone. Keep personal information and grades in the course system. GitHub displays Actions usage and Codespaces usage separately.

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
