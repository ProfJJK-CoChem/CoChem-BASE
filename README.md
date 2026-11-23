# CoChem-BASE

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

CoChem helps you study molecular shapes, energies, vibrational spectra, and
rotational spectroscopy using open quantum chemistry calculations. **CoChem-BASE
is the one repository you start with.** Its browser interface and GitHub Actions
workflows prepare `PySCF`, `xTB`, `CREST 3.0.2`, `AIMNet2`, `TOPOS`, and `TORQ`
without local installation.

---

## Choose Your Course Track First

| Course Track | How to Copy `CoChem-BASE` | Visibility & Repo Name | Where to Start |
| --- | --- | --- | --- |
| **CHEM 312L Organic Chemistry II Lab (Cumberland University)** | Click **Fork** near the top right | Keep visibility **Public** · Keep name **`CoChem-BASE`** *(gives unlimited free GitHub Actions minutes; required by M1 Rubric C4)* | **[`student/CHEM312L_STEP_BY_STEP_GUIDE.md`](student/CHEM312L_STEP_BY_STEP_GUIDE.md)** |
| **CHEM 490 Directed Research (Cumberland University)** | Click **Use this template → Create a new repository** | **Private** · Name `CoChem-[target-molecule]` | **[`student/CHEM490_STEP_BY_STEP_GUIDE.md`](student/CHEM490_STEP_BY_STEP_GUIDE.md)** |

> **Course Rule (CHEM 312L & CHEM 490):** **Students do NOT use Google Colab directly, Classroom50, or personal ORCA Forum licenses, and never enter API tokens.** Open-source engines (`PySCF`, `xTB`, `CREST`, `TOPOS`, `BENCH`, `TORQ`, `GEOM`, `SpycFit`, `SCRIBE`, `spfit`/`spcat`) run in your GitHub Codespace/Actions; optional ORCA 6.1.1 / CCSD(T) / VPT2 jobs for CHEM 490 are run by Dr. Klaassen on Cumberland University's department research computers via the Student ↔ Professor Handoff.

---

## Students: start your project here (4 clicks — no secrets or enrollment needed)

- **CHEM 312L (Cumberland University, partnering with Tennessee Tech University CP-FTMW collaborators):** Follow **[`student/CHEM312L_STEP_BY_STEP_GUIDE.md`](student/CHEM312L_STEP_BY_STEP_GUIDE.md)** for the complete Day-1 through Milestone 4 (`M1`–`M4`) walkthrough.
- **CHEM 490 Directed Research (Cumberland University, partnering with Tennessee Tech University CP-FTMW collaborators):** Follow **[`student/CHEM490_STEP_BY_STEP_GUIDE.md`](student/CHEM490_STEP_BY_STEP_GUIDE.md)** for private template setup, Voilà GUI (`xTB` & `PySCF`), Weeks 4–11 CLI tools (`TOPOS`, `BENCH`, `TORQ`, `GEOM`, `SpycFit`, `SCRIBE`, `spfit`/`spcat`), and the Student ↔ Professor Handoff.
- **General browser dashboard reference:** **[Open the account and workspace guide](.docs/GET_STARTED.md#student-personal-project)**.

You use buttons and menus in your web browser. You do not need to install Python,
request organization invites, or install a GitHub App. `CoChem-BASE` automatically
provisions **`PySCF`**, **`xTB`**, **`CREST`**, **`TOPOS`**, and **`TORQ`** inside
your GitHub Codespace and runs your assigned calculations cleanly on CPU.

### 1. Create your GitHub account and copy `CoChem-BASE`

1. Sign in to your [GitHub account](https://github.com/signup) (or create one).
2. Open [ProfJJK-CoChem/CoChem-BASE](https://github.com/ProfJJK-CoChem/CoChem-BASE).
3. **For CHEM 312L (Cumberland University):** Click **Fork** near the top right,
   keep **Owner** set to your personal username, keep visibility **Public**, and
   keep the repository name **`CoChem-BASE`**, then click **Create fork**.
   *(For instructor-invited CHEM 490 private research projects only: click **Use
   this template → Create a new repository** and create a private
   `CoChem-[target-molecule]` repository.)*

### 2. Open CoChem in GitHub Codespaces

1. On **your fork's page**, click the green **Code** button.
2. Select the **Codespaces** tab, then click **Create codespace on main**.
3. Wait **~10–15 minutes on a fresh Codespace (or ~30 seconds when Prebuilds are
   enabled)** while your Codespace prepares `PySCF`, `xTB`, `CREST`, `TOPOS`,
   `BENCH`, `TORQ`, `GEOM`, `SpycFit`, `SCRIBE`, and `spfit`/`spcat`. Port **8866 (`CoChem Voilà dashboard`)** displays a live
   auto-refreshing setup progress page and automatically opens the CoChem
   dashboard as soon as setup finishes. (If the browser tab did not open
   automatically, open VS Code's **Ports** panel at the bottom and click the
   globe icon next to **8866 — CoChem Voilà dashboard**.)
4. Your Codespace terminal automatically puts `/home/vscode/CoChem_Artifacts/bin`
   and `/home/vscode/CoChem_Artifacts/ui-env/bin` first on `PATH`, so `python`,
   `python3`, `xtb`, `crest`, `spfit`, `spcat`, and all CoChem CLI commands are
   ready immediately. Starter templates (`AI_Usage_Log.md`,
   `targets/team_card.yaml`, `data/`, and `results/`) are included on Day 1.

### 3. Work through the CoChem dashboard

| In CoChem, open… | What you do |
| --- | --- |
| **Start here** | Confirm **Run calculations on** is set to **Linux** (your Codespace, where `PySCF`, `xTB`, `CREST`, `TOPOS`, and `TORQ` are ready immediately) or **GitHub Actions** for course workflows. |
| **Your files** | Upload your own scientific inputs (such as Avogadro 2 `.xyz` files) and select the starting structure. |
| **Calculations** | Inspect **Starting structure**, choose **`PySCF`** or **`xTB`**, enter your study's charge, multiplicity, method, and basis set, and run the calculation. |
| **Results** | Inspect the available values, structures, tables, and figures, and click **Download calculation bundle** to save a copy to your computer. |

**[Continue with the full instructions: upload, calculate, save and submit](.docs/GET_STARTED.md#6-upload-your-own-scientific-files)**

Open **Explain…** beside a setting, or **Scientific terms** in the sidebar,
whenever a word is unfamiliar. You can read the help without losing your draft.

**Save your work:** keep your original input files on your own computer and
use **Download calculation bundle** after retrieving a result. Follow the guide's
[save and submit steps](.docs/GET_STARTED.md#9-save-and-submit-your-work), then
[stop your Codespace](.docs/GET_STARTED.md#10-stop-and-reopen-your-workspace)
when finished.

---

## Public-Fork CURE Route (`XYZ -> CREST -> MLFF -> CPU PySCF`)

**Cumberland University** (`CHEM 312 / 312L` Organic Chemistry II Lab) partnering
with **Tennessee Tech University** (external CP-FTMW microwave spectroscopy
collaborator) supports an open-engine public-fork CURE route covering
`H, B, C, N, O, F, Si, P, S, Cl, Br`, charges `-2..+2`, multiplicities `1..3`, up
to 64 atoms, and 256 conformer/trajectory frames. (Separate private/template
research projects for CHEM 490 also support optional ORCA 6.1.1, CFOUR, SPFIT,
and SPCAT workflows when enabled by the instructor.)

### How to Submit to Your Professor (Plain-English Organic Chemistry 2 Handoff)

- **What you submit to your professor:** Upload your Milestone PDF (with your clickable public-fork GitHub Actions Run URL, Commit SHA, `FactLedger` SHA-256, and `AI_Usage_Log.md`) **and** your verified `cochem.student-handoff/2` `.zip` + `.zip.sha256` bundle to the **Canvas assignment**.
- **What your professor does with it (in Organic Chemistry 2 terms):** Verifies your SHA-256 hashes, grades your rubric, and runs high-precision quantum chemistry calculations (coupled-cluster theory) on Cumberland's department research computers using your verified 3D structures to pin down subtle hydrogen-bond strengths, exact transition-state barrier heights, and microwave rotational constants too demanding for free classroom runners.
- **What your professor hands back to you:** Graded Canvas rubric feedback, the unblinded Week 12 research-grade reference key (so you can compare your DFT energies, carbonyl shifts, and barriers against high-accuracy theory), and the Tennessee Tech University CP-FTMW spectroscopy collaborator's experimental rotational comparison for your M3/M4 report and poster.

### Course Workflows & Local CLI Tools

1. **Full CHEM 312L Walkthrough:** Read **[`student/CHEM312L_STEP_BY_STEP_GUIDE.md`](student/CHEM312L_STEP_BY_STEP_GUIDE.md)** for click-by-click `.xyz` upload instructions, exact `workflow_dispatch` inputs, and copy-pasteable Codespace CLI commands.
2. **Manual GitHub Actions Workflows (`workflow_dispatch` only — zero automatic `push:` or `schedule:` triggers):**
   - **[Day-1 Optional Setup Check](.github/workflows/student_project_setup.yml):** Private-track setup diagnostic (skipped on public forks; CHEM 312L Day-1 smoke test uses `student_conformers.yml` with `ethanol.xyz`).
   - **[Student conformers](.github/workflows/student_conformers.yml):** M1 `XYZ -> CREST 3.0.2 -> charge-aware AIMNet2 / MACE -> CPU PySCF` with `frequencies: true`.
   - **[CHEM 312 NCI Dimer & BSSE](.github/workflows/04_crest_nci_dimer_bsse.yml):** M3 `CREST --nci` ellipsoidal wall sampling + PySCF Boys–Bernardi counterpoise BSSE (`xyz`, `monomer_a_atoms`).
   - **[CHEM 312 6-Shard GVPT2](.github/workflows/05_gvpt2_6shard_anharmonic.yml):** M3 6-shard Barone GVPT2 anharmonic IR (`xyz`, `pre_optimize: true`).
   - **[CHEM 312 Reaction Profile](.github/workflows/06_aimnet2_neb_pyscf_rxn_profile.yml):** Week 10 NAS reaction profile (M3 draft → M4 synthesis) via charge-aware `AIMNet2` CI-NEB + TS + IRC + PySCF PCM (`input_dir`, `charge`, `multiplicity`, `solvent_name`, `dft_basis`, `stage`).
   - **[CHEM 312 SPCAT 8–18 GHz](.github/workflows/07_spcat_8_18ghz_prediction.yml):** M4 8–18 GHz CP-FTMW prediction at `T_rot = 2.0 K` (`xyz`, `a_mhz`, `b_mhz`, `c_mhz`, `mu_a`, `mu_b`, `mu_c`).
3. **Local Codespace Analysis Scripts (`scripts/`):** `scripts/kk_atr_correct.py` (M2 `0.5 cm^-1` diamond ATR Kramers–Kronig), `scripts/fermi_deperturb.py` (M3 Fermi dyad), `scripts/vdw_titration_diff.py` (M3 1:1 complexation & BSSE), `scripts/gvpt2_shard_runner.py` (M3 6-shard GVPT2), `scripts/kraitchman_rs.py` (M4 Kraitchman $|r_s|$ coordinates), and `scripts/fact_ledger.py` (M4 L1–L3 SHA-256 `FactLedger`).
4. **Verify your `cochem.student-handoff/2` ZIP bundle locally (pure Python stdlib):**

   ```bash
   python student/handoff.py path/to/CoChem-bundle.zip --sidecar path/to/CoChem-bundle.zip.sha256 --stage ./received
   ```

   See [`student/CHEM312L_STEP_BY_STEP_GUIDE.md`](student/CHEM312L_STEP_BY_STEP_GUIDE.md) and [`student/README.md`](student/README.md) for full details.

---

## Find the right guide

| You need… | Open… |
| --- | --- |
| Complete CHEM 312L Organic Chemistry II Lab walkthrough (M1–M4, workflows, CLI, Canvas handoff) | [CHEM 312L Step-by-Step Guide](student/CHEM312L_STEP_BY_STEP_GUIDE.md) |
| Dashboard setup, Codespaces lifecycle, and CHEM 490 personal-project steps | [Student start guide](.docs/GET_STARTED.md#student-personal-project) |
| Help with a missing button, unavailable engine, or setup message | [Troubleshooting](.docs/GET_STARTED.md#understand-a-setup-message) |
| Supported inputs, monomers/complexes, TOPOS/TORQ analyses, and interpreting results | [Scientific research guide](.docs/Student_Research_No_Code.md) |
| Instructor preparation for CHEM 490 personal private projects | [Instructor access setup](.docs/GET_STARTED.md#instructor-prepare-student-access) |

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
