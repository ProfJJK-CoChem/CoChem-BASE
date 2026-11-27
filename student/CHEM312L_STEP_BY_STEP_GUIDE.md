# CHEM 312L Step-by-Step Student Guide (Cumberland University)

Welcome to **CHEM 312 / 312L Organic Chemistry II Laboratory** at **Cumberland University** (Dr. Joshua J. Klaassen), partnering with **Tennessee Tech University** (external CP-FTMW microwave spectroscopy collaborator).

This is your **single end-to-end guide** from Day 1 through Milestone 4 (`M1`–`M4`). Every local WSL2 activation command, script path, CREST flag, and handoff step below matches the live `CoChem-BASE` repository verbatim.

> **2026-11-27 Course Architecture & Boundaries (Read First):**
> - **Primary Execution Stack (Local WSL2):** CHEM 312L runs locally in **WSL2 Ubuntu** (`source ~/CoChem_Workstation_Direct/activate_cochem_wsl.sh`) using authentic open-source engines (`PySCF`, `xTB`, `CREST 3.0.2`, `AIMNet2`, `SPCAT`, `TOPOS`, `TORQ`, `CoChem-KINETIC`).
> - **Deprecated / Retired Compute Surfaces:** Legacy `classroom50`, GitHub Codespaces, and GitHub Actions compute workflows are **deprecated** in favor of local WSL2 execution (historical workflow references are kept at the bottom strictly for archival compatibility). Legacy `CoChem-CURE` is superseded by native `CoChem-BASE` course routes (`CHEM 311`, `CHEM 312L`, `CHEM 490`), and `CoChem-ORACLE` is redesigned as the **zero-LLM Student Data Auditing Model**.
> - **All Submissions Go to Canvas:** Every Milestone PDF (`M1`–`M4`) and verified `cochem.student-handoff/2` `.zip` + `.zip.sha256` bundle is submitted through your **Canvas** assignment.
> - **Standardized Lab Conventions:** Nicolet iS50 diamond ATR-FTIR spectra are recorded at **`0.5 cm^-1` resolution** (`n_1 = 2.417`, `45.0 deg`). Your AI disclosure log is **`AI_Usage_Log.md`** (starter template committed at the root of `CoChem-BASE`).

---

## Plain-English Organic Chemistry 2 Professor Handoff Box

- **What you submit to your professor:** Upload your Milestone PDF (with your local Commit SHA, `FactLedger` SHA-256, and `AI_Usage_Log.md`) **and** your verified `cochem.student-handoff/2` `.zip` + `.zip.sha256` bundle to the **Canvas assignment**.
- **What your professor does with it (in Organic Chemistry 2 terms):** Verifies your SHA-256 hashes, grades your rubric (with `CoChem-ORACLE` zero-LLM Student Data Auditing Model checks), and runs high-precision quantum chemistry calculations (canonical coupled-cluster theory via `cochem_workstation_job_runner`) on Cumberland's department research computers using your verified 3D structures to pin down subtle hydrogen-bond strengths, exact transition-state barrier heights, and microwave rotational constants.
- **What your professor hands back to you:** Graded Canvas rubric feedback, the unblinded Week 12 research-grade reference key (so you can compare your DFT energies, carbonyl shifts, and barriers against high-accuracy theory), and the Tennessee Tech University CP-FTMW spectroscopy collaborator's experimental rotational comparison for your M3/M4 report and poster.

---

## Stage 0 — Day-1 Local WSL2 Setup (5 Minutes)

### Step 1: Activate the Pre-Provisioned WSL2 Environment

1. Open your **WSL2 Ubuntu** terminal and activate the CoChem workstation stack:

```bash
source ~/CoChem_Workstation_Direct/activate_cochem_wsl.sh
cd /mnt/d/__CoChem/GitHub-Repo/CoChem-BASE
```

2. Verify local binaries and Python engines are live on `PATH`:

```bash
cochem-cli --version
xtb --version | head -n 4
crest --version | head -n 4
which spcat spfit
python -c "import pyscf, numpy, scipy, cochem_base; print('OK PySCF:', pyscf.__version__)"
```

3. Starter folders and templates are already committed in `CoChem-BASE`:
   - `AI_Usage_Log.md` — Fill in as you complete `M1`–`M4`.
   - `targets/team_card.yaml` — Record your team's assigned molecule, dimer, and reaction inputs.
   - `data/` — Place your wet-lab Nicolet iS50 ATR-FTIR `.csv` files here.
   - `results/` — Save all local script outputs (`.csv`, `.json`, `.md`, `FactLedger.*`) here.

### Step 2: Run Your Day-1 Local Smoke Test (`ethanol.xyz`)

Run a quick local conformer + PySCF check using **CREST 3.0.2** with the mandatory `--legacy --xnam "$(which xtb)" --nocross` flags:

```bash
mkdir -p ~/CoChem_Workstation_Direct/Scratch/chem312_day1
cd ~/CoChem_Workstation_Direct/Scratch/chem312_day1
cp /mnt/d/__CoChem/GitHub-Repo/CoChem-BASE/examples/student_inputs/ethanol.xyz .
crest ethanol.xyz --gfn2 --legacy --xnam "$(which xtb)" --nocross -T 2 --quick > crest_ethanol.out 2>&1
```

*(Optional Voilà GUI: launch `python /mnt/d/__CoChem/GitHub-Repo/CoChem-BASE/scripts/student_voila.py /mnt/d/__CoChem/GitHub-Repo/CoChem-BASE/Start_Here.ipynb --port=8866 --no-browser` and open `http://localhost:8866`.)*

---

## Preparing Your `.xyz` Molecule Inputs

Place your starting geometries inside your working scratch directory (or `examples/student_inputs/` in your local clone):

```bash
# Single monomer or dimer .xyz file:
cp <file>.xyz examples/student_inputs/

# Week 10 NAS reaction folder (reactant.xyz + product.xyz):
mkdir -p examples/student_inputs/<rxn_folder>
cp reactant.xyz product.xyz examples/student_inputs/<rxn_folder>/
```

---

## Local WSL2 Course Calculation Commands (`M1`–`M4`)

### M1 (Weeks 1–4) — Conformers, MLFF Screening & CPU PySCF (`student/conformers.py` + `CREST 3.0.2`)

Always pass **`--legacy --xnam "$(which xtb)" --nocross`** whenever invoking `crest` 3.0.2 directly:

```bash
# Direct CREST 3.0.2 conformer search (monomer):
crest examples/student_inputs/hcooh_start.xyz \
  --gfn2 --legacy --xnam "$(which xtb)" --nocross -T 2

# Direct CREST 3.0.2 NCI dimer search (M3 Weeks 10–11):
crest examples/student_inputs/hcooh_water_dimer.xyz \
  --gfn2 --nci --legacy --xnam "$(which xtb)" --nocross -T 2

# Integrated conformer + charge-aware AIMNet2/MACE + CPU PySCF pipeline:
python student/conformers.py \
  --xyz examples/student_inputs/hcooh_start.xyz \
  --charge 0 --multiplicity 1 \
  --mlff auto --method B3LYP-D3BJ --basis def2-SVP \
  --solvation gas --frequencies \
  --course-id CHEM312 \
  --output-dir results/m1_hcooh
```

*(Note: CHEM 312L uses PySCF Boys–Bernardi counterpoise BSSE for M3 1:1 dimers—there is no PSI4 SAPT0 step. For Week 10 NAS reaction profiles, run `cochem-kinetic rxn-profile` locally with `$COCHEM_AIMNET_PYTHON` exported by `activate_cochem_wsl.sh`.)*

---

## Local WSL2 Analysis CLI Cheat-Sheet (All 6 Real Scripts)

Run these commands directly inside your activated WSL2 terminal. Every command below is copy-pasteable and uses real script names and verified flags.

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

Combines monomer harmonic IR JSON, `bsse_counterpoise.json`, and optional dimer harmonic IR JSON or experimental ATR CSVs (unmeasured or omitted slots are honestly marked `PENDING`):

```bash
python scripts/vdw_titration_diff.py \
  --complex-label "HCOOH...H2O" \
  --monomer-json results/monomer_ir.json \
  --bsse-json results/bsse_counterpoise.json \
  --output-csv results/vdw_diff.csv \
  --output-md results/vdw_diff.md \
  --output-json results/vdw_diff.json
```

*(Note: `--dimer-json results/dimer_ir.json` is optional if you also run a separate dimer frequency calculation—counterpoise BSSE produces `bsse_counterpoise.json` without a dimer Hessian. Add `--exp-monomer-csv data/monomer_atr.csv --exp-complex-csv data/complex_atr.csv --kk-correct` once experimental titration spectra are collected.)*

### 4. M3 — 6-Shard Barone GVPT2 Planner, Shard Runner & Aggregator (`scripts/gvpt2_shard_runner.py`)

Run all 6 deterministic displaced-geometry shards locally in WSL2 and aggregate into `gvpt2_shard_manifest.json`:

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

Hashes every primary (`L1`) and derived (`L2`) artifact into a tamper-evident `FactLedger.json` and `FactLedger.md`, then seals and verifies your `cochem.student-handoff/2` archive fail-closed before uploading to Canvas:

```bash
# Build FactLedger.json and FactLedger.md:
python scripts/fact_ledger.py \
  --artifacts results/hcooh_kk.json results/fermi_dyad.json results/kraitchman_rs.json \
  --output-json results/FactLedger.json \
  --output-md results/FactLedger.md

# Verify fail-closed (must print "verified": true):
python scripts/fact_ledger.py --verify results/FactLedger.json

# Verify your sealed cochem.student-handoff/2 ZIP + .sha256 sidecar:
python student/handoff.py path/to/CoChem-bundle.zip \
  --sidecar path/to/CoChem-bundle.zip.sha256 \
  --stage ./received
```

---

## Deprecated / Legacy GitHub Actions Workflows (Historical Archive Reference Only)

> **Deprecated Notice:** GitHub Actions compute runners, GitHub Codespaces, and `classroom50` are **deprecated** for CHEM 312L. Execute all calculations locally in WSL2 above. The historical `workflow_dispatch` filenames below are retained strictly for reading archived artifacts:
> - `student_conformers.yml` (legacy M1 conformer workflow)
> - `04_crest_nci_dimer_bsse.yml` (legacy M3 dimer NCI & counterpoise BSSE workflow)
> - `05_gvpt2_6shard_anharmonic.yml` (legacy M3 6-shard GVPT2 workflow)
> - `06_aimnet2_neb_pyscf_rxn_profile.yml` (legacy Week 10 NAS reaction-profile workflow)
> - `07_spcat_8_18ghz_prediction.yml` (legacy M4 8–18 GHz SPCAT prediction workflow)

---

## Pre-Submission Checklist (Every Milestone `M1`–`M4`)

1. All calculations ran authentically in local WSL2 (`source ~/CoChem_Workstation_Direct/activate_cochem_wsl.sh`).
2. Local Commit SHA and `FactLedger` SHA-256 are pasted into your Milestone PDF.
3. `python scripts/fact_ledger.py --verify results/FactLedger.json` prints `"verified": true`.
4. `python student/handoff.py <bundle.zip> --sidecar <bundle.zip.sha256> --stage ./received` exits `0`.
5. `AI_Usage_Log.md` is updated and included with your Canvas submission.
6. Milestone PDF + verified `.zip` + `.zip.sha256` are uploaded to your **Canvas** assignment.
