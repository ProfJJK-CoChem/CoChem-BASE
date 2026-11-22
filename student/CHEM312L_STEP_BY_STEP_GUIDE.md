# CHEM 312L Step-by-Step Student Guide (Cumberland University)

Welcome to **CHEM 312 / 312L Organic Chemistry II Laboratory** at **Cumberland University** (Dr. Joshua J. Klaassen), partnering with **Tennessee Tech University** (external CP-FTMW microwave spectroscopy collaborator).

This is your **single end-to-end guide** from Day 1 through Milestone 4 (`M1`–`M4`). Every workflow name, folder path, input field, and terminal command below matches the live `CoChem-BASE` repository verbatim.

> **Course Boundaries (Read First):**
> - **Public Fork Required:** Every CHEM 312L student clicks **Fork** on [`ProfJJK-CoChem/CoChem-BASE`](https://github.com/ProfJJK-CoChem/CoChem-BASE), keeps visibility **Public**, and keeps the repository name **`CoChem-BASE`**. Public forks get unlimited free GitHub Actions minutes and are required by **M1 Rubric C4**. Do **not** create a private repo for CHEM 312L.
> - **Zero External Cloud Accounts or Licenses:** CHEM 312L runs 100% on your free public-fork **GitHub Actions** and **GitHub Codespaces** using open-source engines (`PySCF`, `xTB`, `CREST 3.0.2`, `AIMNet2`, `SPCAT`). Students never touch external cloud GPU notebooks, licensed cluster programs (ORCA/CFOUR), or API tokens.
> - **All Submissions Go to Canvas:** Every Milestone PDF (`M1`–`M4`) and verified `.zip` + `.zip.sha256` bundle is submitted through your **Canvas** assignment.
> - **Standardized Lab Conventions:** Nicolet iS50 diamond ATR-FTIR spectra are recorded at **`0.5 cm^-1` resolution** (`n_1 = 2.417`, `45.0 deg`). Your AI disclosure log is **`AI_Usage_Log.md`** (starter template already committed at the root of your fork).

---

## Plain-English Organic Chemistry 2 Professor Handoff Box

- **What you submit to your professor:** Upload your Milestone PDF (with your clickable public-fork GitHub Actions Run URL, Commit SHA, `FactLedger` SHA-256, and `AI_Usage_Log.md`) **and** your verified `cochem.student-handoff/2` `.zip` + `.zip.sha256` bundle to the **Canvas assignment**.
- **What your professor does with it (in Organic Chemistry 2 terms):** Verifies your SHA-256 hashes, grades your rubric, and runs high-precision quantum chemistry calculations (coupled-cluster theory) on Cumberland's department research computers using your verified 3D structures to pin down subtle hydrogen-bond strengths, exact transition-state barrier heights, and microwave rotational constants too demanding for free classroom runners.
- **What your professor hands back to you:** Graded Canvas rubric feedback, the unblinded Week 12 research-grade reference key (so you can compare your DFT energies, carbonyl shifts, and barriers against high-accuracy theory), and the Tennessee Tech University CP-FTMW spectroscopy collaborator's experimental rotational comparison for your M3/M4 report and poster.

---

## Stage 0 — Day-1 Setup (10 Minutes)

### Step 1: Fork `CoChem-BASE` as a Public Repository

1. Sign in to your personal [GitHub](https://github.com/) account.
2. Open [`ProfJJK-CoChem/CoChem-BASE`](https://github.com/ProfJJK-CoChem/CoChem-BASE).
3. Click **Fork** near the top right.
4. Keep **Owner** set to your personal username, keep **Repository name** as **`CoChem-BASE`**, and keep visibility **Public**. Click **Create fork**.
5. Open your fork's **Actions** tab and click **I understand my workflows, go ahead and enable them** (GitHub asks once on new forks).

### Step 2: Run Your Day-1 Smoke Test on GitHub Actions

1. On your public fork, click **Actions** → select **`Student conformers (CREST 3.0.2, AIMNet2/MACE, CPU PySCF)`** (`student_conformers.yml`) in the left sidebar.
2. Click **Run workflow** → leave the default **`xyz: ethanol.xyz`** (and `course_id: CHEM312`) → click the green **Run workflow** button.
3. Wait for the green checkmark, open the completed run, and download the `cochem-student-handoff-v2` artifact ZIP (contains your inner `.zip` and `.zip.sha256` sidecar).

*(Note: `student_project_setup.yml` in the Actions sidebar is an optional private-track setup diagnostic for CHEM 490 instructor-invited repositories and is skipped on public forks—use `student_conformers.yml` on `ethanol.xyz` for your CHEM 312L Day-1 smoke test.)*

### Step 3: Open Your Personal GitHub Codespace (for Local Analysis & Dashboard)

1. On your public fork's home page, click the green **Code** button → **Codespaces** tab → **Create codespace on main**.
2. Wait **5–10 minutes on a fresh Codespace (or ~30 seconds when Prebuilds are enabled)** while `PySCF`, `xTB`, `CREST`, `TOPOS`, and `TORQ` finish preparing. Port **8866 (`CoChem Voilà dashboard`)** shows a live auto-refreshing progress page and opens the dashboard automatically when ready.
3. Starter folders and templates are already committed in your fork on Day 1:
   - `AI_Usage_Log.md` — Fill in as you complete `M1`–`M4`.
   - `targets/team_card.yaml` — Record your team's assigned molecule, dimer, and reaction inputs.
   - `data/` — Place your wet-lab Nicolet iS50 ATR-FTIR `.csv` files here.
   - `results/` — Save all local script outputs (`.csv`, `.json`, `.md`, `FactLedger.*`) here.
4. Your Codespace terminal automatically puts the managed scientific Python environment (`/home/vscode/CoChem_Artifacts/ui-env/bin`) first on `PATH`, so `python` and `python3` have `numpy`, `scipy`, `pandas`, and `cochem-cli` ready immediately with zero manual `venv` activation.
5. **Always stop your Codespace when finished:** open [github.com/codespaces](https://github.com/codespaces), click **`...`** next to your Codespace, and choose **Stop codespace**. (Stopping a Codespace does not cancel a running GitHub Actions job.)

---

## How to Upload `.xyz` Molecules to Your Fork (Required Before Running Workflows)

All GitHub Actions course workflows read your starting structures from **`examples/student_inputs/`** in your public fork. Use **either** Option A (zero terminal) or Option B (Codespace terminal):

### Option A — GitHub Web UI (Click-by-Click, Zero Terminal)

1. Open your public fork (`https://github.com/<your-username>/CoChem-BASE`) in your browser.
2. Click the **`examples`** folder, then click **`student_inputs`**.
3. Click **Add file** → **Upload files** near the top right.
4. Drag and drop your `.xyz` file (for example, `hcooh_start.xyz` or `hcooh_water_dimer.xyz`) into the upload box.
   - For a Week 10 NAS reaction folder (e.g., `hcof_fluoride_rxn/` containing `reactant.xyz` and `product.xyz`), drag the entire folder into the upload box so it appears at `examples/student_inputs/hcof_fluoride_rxn/reactant.xyz` and `product.xyz`.
5. Scroll down, enter a short commit message (e.g., `Add HCOOH starting geometry`), leave **Commit directly to the `main` branch** selected, and click **Commit changes**.

### Option B — Codespace Terminal

```bash
# Single monomer or dimer .xyz file:
cp <file>.xyz examples/student_inputs/
git add examples/student_inputs/<file>.xyz
git commit -m "Add molecule"
git push

# Week 10 NAS reaction folder (reactant.xyz + product.xyz):
mkdir -p examples/student_inputs/<rxn_folder>
cp reactant.xyz product.xyz examples/student_inputs/<rxn_folder>/
git add examples/student_inputs/<rxn_folder>/
git commit -m "Add NAS reaction inputs"
git push
```

---

## Exact Canonical Course Workflows (GitHub Actions Tab)

All course workflows are strictly manual **`workflow_dispatch`** (zero automatic `push` triggers, zero scheduled crons). Open your fork's **Actions** tab, pick the exact workflow filename below, click **Run workflow**, and fill in these exact inputs:

| # | Milestone / Timing | Exact Workflow Filename | Exact `workflow_dispatch` Inputs to Fill In |
| --- | --- | --- | --- |
| 1 | Day-1 Optional Diagnostic | `student_project_setup.yml` | Private-track / instructor setup check (`request_id`); **skipped on public forks**. CHEM 312L Day-1 smoke test uses `student_conformers.yml` with `xyz: ethanol.xyz`. |
| 2 | **M1** (Weeks 1–4) | `student_conformers.yml` | `xyz`: filename in `examples/student_inputs/` (e.g., `hcooh_start.xyz`), `charge`: `'0'` (or `'-1'`, etc.), `multiplicity`: `'1'`, `mlff`: `auto`, `method`: `B3LYP-D3BJ` (or `wB97X-D3`), `basis`: `def2-SVP` (or `def2-TZVP`), `solvation`: `gas`, **`frequencies`: `true`** (checkbox in UI to compute harmonic frequencies and verify 0 imaginary modes), `course_id`: `CHEM312`, `target_continuation`: `workstation`. |
| 3 | **M3** (Weeks 10–11 Dimer NCI & BSSE) | `04_crest_nci_dimer_bsse.yml` | `xyz`: dimer filename in `examples/student_inputs/` (e.g., `hcooh_water_dimer.xyz`), **`monomer_a_atoms`**: leading atom count for monomer A (e.g., `'5'` for atoms 1–5 HCOOH, leaving atoms 6–8 as H2O), `charge`: `'0'`, `multiplicity`: `'1'`, `monomer_a_charge`: `'0'`, `monomer_b_charge`: `'0'`, `method`: `wB97X-D3`, `basis`: `def2-TZVP`, `solvation`: `gas`, `course_id`: `CHEM312`. |
| 4 | **M3** (Weeks 7–9 Anharmonic IR) | `05_gvpt2_6shard_anharmonic.yml` | `xyz`: monomer filename in `examples/student_inputs/` (e.g., `hcooh_start.xyz`), `charge`: `'0'`, `multiplicity`: `'1'`, `method`: `B3LYP-D3BJ`, `basis`: `def2-SVP`, `solvation`: `gas`, **`pre_optimize`: `true`**, `step_size`: `'0.01'`, `course_id`: `CHEM312`. Runs 6 parallel shards (`0..5`) and aggregates anharmonic Barone GVPT2 frequencies. |
| 5 | **Week 10 NAS** (M3 draft → **M4** synthesis) | `06_aimnet2_neb_pyscf_rxn_profile.yml` | `input_dir`: `examples/student_inputs/<rxn_folder>` containing `reactant.xyz` + `product.xyz` (or `R.xyz`, `Int_tet.xyz`, `P.xyz`), `input_name`: `<rxn_folder>.xyz`, **`charge`**: `'-1'` (for anionic NAS such as `HCOF + F-`) or `'0'`, **`multiplicity`**: `'1'`, `solvent_name`: `acetonitrile` (or `water`), `temp_k`: `'298.15'`, `dft_basis`: `def2-TZVPP` (or `def2-SVP` for fast checks), `stage`: `all` (`mlff` or `validate`), `course_id`: `CHEM312`. |
| 6 | **M4** (Weeks 12–15 Rotational Prediction) | `07_spcat_8_18ghz_prediction.yml` | `xyz`: monomer filename in `examples/student_inputs/`, `charge`: `'0'`, `multiplicity`: `'1'`, **`a_mhz`**, **`b_mhz`**, **`c_mhz`**, **`mu_a`**, **`mu_b`**, **`mu_c`** (plus optional quartic distortion `dj_khz`..`d2_khz`), `t_rot_k`: `'2.0'`, `freq_min_ghz`: `'8.0'`, `freq_max_ghz`: `'18.0'`, `constant_type`: `B0`, `course_id`: `CHEM312`. |

*(Note on M3/M4 placement of Week 10 NAS: `06_aimnet2_neb_pyscf_rxn_profile.yml` is dispatched during Week 10 for your initial M3 reaction-profile draft and synthesized into your final M4 dossier and poster. CHEM 312L uses PySCF Boys–Bernardi counterpoise BSSE in `04_crest_nci_dimer_bsse.yml`—there is no PSI4 SAPT0 step.)*

---

## Local Codespace CLI Cheat-Sheet (All 6 Real Scripts)

Run these commands directly inside your Codespace terminal (`python` already points to the scientific `ui-env`). Every command below is copy-pasteable and uses real script names and verified flags.

### 1. M2 — Kramers–Kronig ATR-FTIR Correction (`scripts/kk_atr_correct.py`)

Corrects optical red-shifts in single-bounce diamond ATR-FTIR spectra (`0.5 cm^-1` resolution, `n_1 = 2.417`, `45.0 deg`):

```bash
python scripts/kk_atr_correct.py \
  --input data/nicolet_is50_hcooh_atr.csv \
  --n-inf 1.3714 \
  --angle-deg 45.0 \
  --n-crystal 2.417 \
  --output-csv results/hcooh_kk.csv \
  --output-json results/hcooh_kk.json
```

*(Backward-compatible shorthand aliases `--csv`, `--angle`, `--crystal diamond` (`diamond`/`znse`/`ge`), and `--out` are also accepted and produce identical output.)*

### 2. M3 — 2×2 Martin Fermi Resonance Deperturbation (`scripts/fermi_deperturb.py`)

Recovers unperturbed $\nu_1^0$, dark overtone $2\nu_2^0$, coupling $|W|$, and mixing angle $\theta$ from an observed Fermi doublet:

```bash
python scripts/fermi_deperturb.py \
  --nu-plus 1742.0 \
  --nu-minus 1712.0 \
  --intensity-ratio 0.65 \
  --label HCOOH_CO_dyad \
  --output-json results/fermi_dyad.json \
  --output-md results/fermi_dyad.md
```

### 3. M3 — 1:1 Complexation Shift & Counterpoise BSSE Analyzer (`scripts/vdw_titration_diff.py`)

Combines monomer/dimer harmonic IR JSONs, `bsse_counterpoise.json` from `04_crest_nci_dimer_bsse.yml`, and optional experimental ATR CSVs (unmeasured experimental slots are honestly marked `PENDING`):

```bash
python scripts/vdw_titration_diff.py \
  --complex-label "HCOOH...H2O" \
  --monomer-json results/monomer_ir.json \
  --dimer-json results/dimer_ir.json \
  --bsse-json results/bsse_counterpoise.json \
  --output-csv results/vdw_diff.csv \
  --output-md results/vdw_diff.md \
  --output-json results/vdw_diff.json
```

*(Add `--exp-monomer-csv data/monomer_atr.csv --exp-complex-csv data/complex_atr.csv --kk-correct` once experimental titration spectra are collected.)*

### 4. M3 — 6-Shard Barone GVPT2 Planner, Shard Runner & Aggregator (`scripts/gvpt2_shard_runner.py`)

Used automatically inside `05_gvpt2_6shard_anharmonic.yml`, or locally in Codespace to inspect/aggregate downloaded shard JSONs:

```bash
# Plan K=6 displaced-geometry shards:
python scripts/gvpt2_shard_runner.py plan \
  --xyz examples/student_inputs/hcooh_start.xyz \
  --output-dir results/gvpt2_plan \
  --n-shards 6 \
  --step-size 0.01

# Run a single shard (shard_id in 0..5):
python scripts/gvpt2_shard_runner.py run-shard \
  --plan results/gvpt2_plan/gvpt2_plan.json \
  --shard-id 0 \
  --output-dir results/gvpt2_shards \
  --method B3LYP-D3BJ \
  --basis def2-SVP

# Aggregate all 6 shards into gvpt2_shard_manifest.json (fail-closed if any shard is missing):
python scripts/gvpt2_shard_runner.py aggregate \
  --plan results/gvpt2_plan/gvpt2_plan.json \
  --shards-dir results/gvpt2_shards \
  --output-dir results/gvpt2_out
```

### 5. M4 — Kraitchman Single-Substitution $|r_s|$ Coordinates (`scripts/kraitchman_rs.py`)

Computes planar or 3D rigid-rotor substitution coordinates $|a|, |b|, |c|$ from parent vs. singly-substituted isotopologue rotational constants ($A, B, C$ in MHz). Costain imaginary coordinates ($r_s^2 < 0$) are flagged honestly (`imaginary: true`, `abs_rs_angstrom: null`):

```bash
# From JSON files (containing a_mhz/b_mhz/c_mhz and optional molecular_mass_amu):
python scripts/kraitchman_rs.py \
  --parent results/parent_rot.json \
  --iso results/iso_rot.json \
  --parent-mass-amu 46.005479 \
  --delta-mass-amu 1.006277 \
  --mode nonplanar \
  --output-json results/kraitchman_rs.json \
  --output-md results/kraitchman_rs.md

# Or directly from CLI rotational constants (A B C in MHz):
python scripts/kraitchman_rs.py \
  --parent-abc 77512.23 12055.11 10416.12 \
  --iso-abc 75900.10 11680.45 10112.88 \
  --parent-mass-amu 46.005479 \
  --delta-mass-amu 1.006277 \
  --mode planar \
  --output-json results/kraitchman_rs.json \
  --output-md results/kraitchman_rs.md
```

### 6. M4 — Cryptographic L1–L3 Provenance Ledger (`scripts/fact_ledger.py`) & Handoff Verification (`student/handoff.py`)

Hashes every primary (`L1`) and derived (`L2`) artifact into a tamper-evident `FactLedger.json` and `FactLedger.md`, then verifies all digests fail-closed before uploading to Canvas:

```bash
# Build FactLedger.json and FactLedger.md:
python scripts/fact_ledger.py \
  --artifacts results/hcooh_kk.json results/fermi_dyad.json results/kraitchman_rs.json \
  --output-json results/FactLedger.json \
  --output-md results/FactLedger.md

# Verify fail-closed (must print "verified": true):
python scripts/fact_ledger.py --verify results/FactLedger.json

# Verify your downloaded GitHub Actions cochem.student-handoff/2 ZIP + .sha256 sidecar:
python student/handoff.py path/to/CoChem-bundle.zip \
  --sidecar path/to/CoChem-bundle.zip.sha256 \
  --stage ./received
```

---

## Pre-Submission Checklist (Every Milestone `M1`–`M4`)

1. Public fork URL (`https://github.com/<your-username>/CoChem-BASE`) is **Public** and clickable.
2. GitHub Actions Run URL and Commit SHA are pasted into your Milestone PDF.
3. `python scripts/fact_ledger.py --verify results/FactLedger.json` prints `"verified": true`.
4. `python student/handoff.py <bundle.zip> --sidecar <bundle.zip.sha256> --stage ./received` exits `0`.
5. `AI_Usage_Log.md` is updated, committed, and attached/included.
6. Milestone PDF + verified `.zip` + `.zip.sha256` are uploaded to your **Canvas** assignment.
7. Your GitHub Codespace is **stopped** at [github.com/codespaces](https://github.com/codespaces).
