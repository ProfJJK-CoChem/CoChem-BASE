# CoChem-BASE

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

CoChem helps you study molecular shapes, energies, vibrational spectra, and
rotational spectroscopy using authentic quantum chemistry calculations.
**CoChem-BASE is the unified starting repository** across **CHEM 311**,
**CHEM 312L**, and **CHEM 490**, running primarily on **local WSL2 Ubuntu**
(`source ~/CoChem_Workstation_Direct/activate_cochem_wsl.sh`) with `PySCF`,
`xTB`, `CREST 3.0.2`, `AIMNet2`, `ORCA 6.1.1`, `TOPOS`, `BENCH`, `TORQ`,
`GEOM`, `SCRIBE`, and `SPCAT`/`SPFIT`.

---

## Is This a Course? (`CoChem-BASE` ↔ `CoChem-CURE`)

`CoChem-BASE` is the core scientific workbench and runs standalone by default.
When you start setup—either in **`1 · Setup`** of the Voilà dashboard or via the CLI
(`python -m cochem_base.course_loader`)—`CoChem-BASE` asks **"Is this a course?"**:

- **No (default — standalone research / general calculations):** `CoChem-BASE` runs
  independently with zero `CoChem-CURE` dependency and makes no network or package install
  calls on startup.
- **Yes (course mode — dynamic `CoChem-CURE` loading):** `CoChem-BASE` obtains
  **[`ProfJJK-CoChem/CoChem-CURE`](https://github.com/ProfJJK-CoChem/CoChem-CURE)** and
  dynamically loads course selection, course profiles, milestones, and execution pathways
  from `cochem_cure.provider` (`cochem.course-provider/1`).

```bash
# Interactive "Is this a course? [y/N]:" prompt
python -m cochem_base.course_loader

# Non-interactive standalone research mode (never requires CoChem-CURE)
python -m cochem_base.course_loader --is-course no

# Non-interactive course mode (obtain CoChem-CURE, list courses, and inspect a pathway)
python -m cochem_base.course_loader --is-course yes --obtain --list-courses
python -m cochem_base.course_loader --is-course yes --course CHEM311 --show-pathway
```

### Choose Your Course Track

| Course Track | Primary Execution Stack | Local Guide Mirror (Authoritative Profiles in `CoChem-CURE`) |
| --- | --- | --- |
| **CHEM 311 Organic Chemistry I (`CoChem-QUEST`, Cumberland University)** | Local WSL2 (`source ~/CoChem_Workstation_Direct/activate_cochem_wsl.sh`) — `RDKit`, `GFN2-xTB`, `CREST 3.0.2`, `PySCF`, `IsotopologueSpectroscopyEngine`, `SPCAT` | **[`student/CHEM311_STEP_BY_STEP_GUIDE.md`](student/CHEM311_STEP_BY_STEP_GUIDE.md)** |
| **CHEM 312L Organic Chemistry II Lab (Cumberland University)** | Local WSL2 (`source ~/CoChem_Workstation_Direct/activate_cochem_wsl.sh`) — `CREST 3.0.2`, `AIMNet2`, `PySCF`, `CoChem-KINETIC`, KK-ATR, GVPT2, Kraitchman, `FactLedger` | **[`student/CHEM312L_STEP_BY_STEP_GUIDE.md`](student/CHEM312L_STEP_BY_STEP_GUIDE.md)** |
| **CHEM 490 Directed Research (Cumberland University)** | Local WSL2 (`source ~/CoChem_Workstation_Direct/activate_cochem_wsl.sh`) — `ORCA 6.1.1` (`revDSD-PBEP86-D4/2021` + VPT2), `TOPOS`, `BENCH`, `TORQ`, `GEOM`, `SCRIBE`, `SPYFY`, + `cochem_workstation_job_runner` canonical `CCSD`/`CCSD(T)` handoff | **[`student/CHEM490_STEP_BY_STEP_GUIDE.md`](student/CHEM490_STEP_BY_STEP_GUIDE.md)** |

> **2026-11-27 Architecture & Course Rules (`CHEM 311`, `CHEM 312L`, `CHEM 490`):**
> - **Local WSL2 Primary Stack:** Activate `source ~/CoChem_Workstation_Direct/activate_cochem_wsl.sh`. Legacy **`classroom50`**, **GitHub Codespaces**, and **GitHub Actions compute** are **deprecated / retired**.
> - **`CoChem-BASE` ↔ `CoChem-CURE` Split:** `CoChem-BASE` provides the standalone scientific engines, UI, and handoff verifier; **`ProfJJK-CoChem/CoChem-CURE`** is the authoritative repository for course profiles, milestones, and pathways, obtained dynamically when you answer **Yes** to *"Is this a course?"*. **`CoChem-ORACLE`** is redesigned as the **zero-LLM Student Data Auditing Model**.
> - **CREST 3.0.2 Flags:** Always pass `--legacy --xnam "$(which xtb)" --nocross` when invoking CREST 3.0.2 locally.
> - **Coupled-Cluster & Handoff Policy:** Higher-end canonical `CCSD` / `CCSD(T)` calculations for CHEM 490 are routed via **`cochem_workstation_job_runner`** (`cochem.student-handoff/2`). **`DLPNO-CCSD(T)` is strictly banned under Pipeline 5.0.0.**

---

## Students: Start Locally in WSL2

- **CHEM 311 (`CoChem-QUEST`, Cumberland University, partnering with Tennessee Tech University):** Follow **[`student/CHEM311_STEP_BY_STEP_GUIDE.md`](student/CHEM311_STEP_BY_STEP_GUIDE.md)** for Modules 0–5 (`mod1`–`mod5`).
- **CHEM 312L (Cumberland University, partnering with Tennessee Tech University CP-FTMW collaborators):** Follow **[`student/CHEM312L_STEP_BY_STEP_GUIDE.md`](student/CHEM312L_STEP_BY_STEP_GUIDE.md)** for Milestones 1–4 (`M1`–`M4`).
- **CHEM 490 Directed Research (Cumberland University, partnering with Tennessee Tech University CP-FTMW / GruLab SURF collaborators):** Follow **[`student/CHEM490_STEP_BY_STEP_GUIDE.md`](student/CHEM490_STEP_BY_STEP_GUIDE.md)** for local WSL2 ORCA 6.1.1 `revDSD-PBEP86-D4/2021` + VPT2, ecosystem CLIs (`TOPOS`, `BENCH`, `TORQ`, `GEOM`, `SCRIBE`, `spfit`/`spcat`, optional `CoChem-SPYFY`), and `cochem_workstation_job_runner` canonical `CCSD` / `CCSD(T)` handoffs.
- **All Student Guides Index:** **[`student/README.md`](student/README.md)** · **[General Dashboard Reference](.docs/GET_STARTED.md#student-personal-project)**.

### 1. Activate Your Local WSL2 Environment

```bash
source ~/CoChem_Workstation_Direct/activate_cochem_wsl.sh
cd /mnt/d/__CoChem/GitHub-Repo/CoChem-BASE
cochem-cli --version
```

### 2. Optional Local Voilà Dashboard (`port 8866`)

```bash
python scripts/student_voila.py Start_Here.ipynb --port=8866 --no-browser
```

Open `http://localhost:8866` to upload `.xyz` files, run local `xTB` / `PySCF` jobs, and download verified calculation bundles.

### 3. Work through the CoChem dashboard

| In CoChem, open… | What you do |
| --- | --- |
| **Start here** | Confirm **Run calculations on** is set to **Local computer (Linux)** (your WSL2 workstation, where `PySCF`, `xTB`, `CREST 3.0.2`, `TOPOS`, and `TORQ` are ready immediately). |
| **Your files** | Upload your own scientific inputs (such as Avogadro 2 `.xyz` files) and select the starting structure. |
| **Calculations** | Inspect **Starting structure**, choose **`PySCF`** or **`xTB`**, enter your study's charge, multiplicity, method, and basis set, and run the calculation. |
| **Results** | Inspect the available values, structures, tables, and figures, and click **Download calculation bundle** to save a copy to your computer. |

**[Continue with the full instructions: upload, calculate, save and submit](.docs/GET_STARTED.md#6-upload-your-own-scientific-files)**

---

## Unified Course Routes (`CHEM311`, `CHEM312`, `CHEM490`) & `cochem.student-handoff/2`

**Cumberland University** (`CHEM 311`, `CHEM 312 / 312L`, `CHEM 490`) partnering
with **Tennessee Tech University** (external CP-FTMW microwave spectroscopy
collaborator) pairs **`CoChem-BASE`** with dynamically loaded course profiles
from **`ProfJJK-CoChem/CoChem-CURE`** (obtained when you answer **Yes** to
*"Is this a course?"*), covering `H, B, C, N, O, F, Si, P, S, Cl, Br`, charges
`-2..+2`, multiplicities `1..3`, up to 64 atoms, and 256 conformer/trajectory
frames.

### How to Submit to Your Professor (Plain-English Handoff)

- **What you submit to your professor:** Upload your Milestone PDF (with your Commit SHA, `FactLedger` SHA-256, and `AI_Usage_Log.md`) **and** your verified `cochem.student-handoff/2` `.zip` + `.zip.sha256` bundle to the **Canvas assignment**.
- **What your professor does with it:** Verifies your SHA-256 hashes (with `CoChem-ORACLE` zero-LLM Student Data Auditing Model checks) and runs higher-end canonical `CCSD` / `CCSD(T)` calculations via `cochem_workstation_job_runner` on Cumberland's department research computers (`DLPNO-CCSD(T)` is banned under Pipeline 5.0.0).
- **What your professor hands back to you:** Graded Canvas rubric feedback, canonical reference outputs, and the Tennessee Tech University CP-FTMW spectroscopy collaborator's experimental rotational comparison for your report and poster.

### Course Guides, Local Scripts & Bundle Verification

1. **Course Guides:** [`student/CHEM311_STEP_BY_STEP_GUIDE.md`](student/CHEM311_STEP_BY_STEP_GUIDE.md) · [`student/CHEM312L_STEP_BY_STEP_GUIDE.md`](student/CHEM312L_STEP_BY_STEP_GUIDE.md) · [`student/CHEM490_STEP_BY_STEP_GUIDE.md`](student/CHEM490_STEP_BY_STEP_GUIDE.md) · [`student/README.md`](student/README.md).
2. **Local WSL2 Analysis Scripts (`scripts/`):** `scripts/kk_atr_correct.py` (M2 `0.5 cm^-1` diamond ATR Kramers–Kronig), `scripts/fermi_deperturb.py` (M3 Fermi dyad), `scripts/vdw_titration_diff.py` (M3 1:1 complexation & BSSE), `scripts/gvpt2_shard_runner.py` (M3 6-shard GVPT2), `scripts/kraitchman_rs.py` (M4 Kraitchman $|r_s|$ coordinates), and `scripts/fact_ledger.py` (M4 L1–L3 SHA-256 `FactLedger`).
3. **Verify your `cochem.student-handoff/2` ZIP bundle locally (pure Python stdlib):**

   ```bash
   python student/handoff.py path/to/CoChem-bundle.zip --sidecar path/to/CoChem-bundle.zip.sha256 --stage ./received
   ```

   *(Legacy Archive: the retired "4 clicks" GitHub Codespaces / Public-Fork CURE Route and `.github/workflows/student_conformers.yml` compute definitions are deprecated in favor of local WSL2 execution and retained solely for archived bundle provenance.)*

---

## Find the right guide

| You need… | Open… |
| --- | --- |
| Complete CHEM 311 Organic Chemistry I (`CoChem-QUEST`) local WSL2 walkthrough (M0–M5) | [CHEM 311 Step-by-Step Guide](student/CHEM311_STEP_BY_STEP_GUIDE.md) |
| Complete CHEM 312L Organic Chemistry II Lab walkthrough (M1–M4, local WSL2 CLI, Canvas handoff) | [CHEM 312L Step-by-Step Guide](student/CHEM312L_STEP_BY_STEP_GUIDE.md) |
| Complete CHEM 490 Directed Research walkthrough (local WSL2 ORCA 6.1.1 `revDSD-PBEP86-D4/2021` + VPT2, workstation runner handoff) | [CHEM 490 Step-by-Step Guide](student/CHEM490_STEP_BY_STEP_GUIDE.md) |
| General dashboard reference and troubleshooting | [Student start guide](.docs/GET_STARTED.md#student-personal-project) · [Troubleshooting](.docs/GET_STARTED.md#understand-a-setup-message) |
| Supported inputs, monomers/complexes, TOPOS/TORQ analyses, and interpreting results | [Scientific research guide](.docs/Student_Research_No_Code.md) |

<details>
<summary><strong>Advanced / CHEM 490 Instructor-Invited Track Only (ORCA, CFOUR, Optional Cloud/Local Engines)</strong></summary>

*Not used in CHEM 312L.* For instructor-invited CHEM 490 private research projects
or workstation/HPC deployments:

- ORCA and CFOUR are optional licensed engines managed strictly by the instructor;
  students never enter tokens or download licensed engine archives.
- [ORCA setup](.docs/ORCA_Actions_Setup.md) ·
  [CFOUR setup](.docs/CFOUR_Actions_Setup.md) ·
  [Ecosystem module setup](.docs/Ecosystem_Modules_Setup.md) ·
  [Optional cloud GPU notes (Instructor backend only — never used directly by students)](.docs/Google_Colab_GPU_Setup.md) ·
  [Legacy private-project assignment deployment](.docs/Classroom50_Assignment_Deployment.md)

The interface and calculation location are separate choices. BASE also supports
local Linux, Windows/WSL2, macOS, and configured HPC schedulers.

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
Python 3.12 for the pinned Stage 0 environments. Students follow the guides
above; automatic BASE setup prepares their workspace and hidden ecosystem
components.

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
Native execution requires the selected host's audited setup.

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
