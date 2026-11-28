# CHEM 490 Directed Research — Step-by-Step Student Guide (Cumberland University)

Welcome to **CHEM 490 Directed Research in Computational Chemistry** at **Cumberland University** (Dr. Joshua J. Klaassen), partnering with **Tennessee Tech University** (external CP-FTMW / GruLab SURF microwave spectroscopy collaborator).

This is your **single end-to-end guide** for Weeks 1–16 of CHEM 490. Every local WSL2 activation step, ORCA 6.1.1 / VPT2 command, CREST flag, workstation runner handoff, and analysis CLI command below matches the live `CoChem-BASE` architecture verbatim.

> **2026-11-27 Course Architecture & Boundaries (Read First):**
> - **Primary Execution Stack (Local WSL2):** CHEM 490 runs locally in **WSL2 Ubuntu** via `source ~/CoChem_Workstation_Direct/activate_cochem_wsl.sh` using `PySCF`, `xTB`, `CREST 3.0.2`, `ORCA 6.1.1` (local `revDSD-PBEP86-D4/2021` + VPT2), `TOPOS`, `BENCH`, `TORQ`, `GEOM`, `SCRIBE`, `spfit`/`spcat`, plus the optional `CoChem-SPYFY` add-on (`bash scripts/install_optional_spyfy.sh`).
> - **Deprecated / Retired Compute Surfaces & `CoChem-CURE` Authority:** `classroom50`, GitHub Codespaces, and GitHub Actions compute are **deprecated** in favor of local WSL2 workstations. **`ProfJJK-CoChem/CoChem-CURE`** is the authoritative source of truth for course profiles, milestones, and pathways (loaded dynamically when you answer **Yes** to *"Is this a course?"* in `CoChem-BASE` `1 · Setup` or `python -m cochem_base.course_loader`; this file is a local reference mirror), and `CoChem-ORACLE` is redesigned as the **zero-LLM Student Data Auditing Model**.
> - **High-End Coupled-Cluster Handoff (`cochem_workstation_job_runner`):** Higher-end canonical **`CCSD`** and **`CCSD(T)`** calculations (and `CCSD(T)/CBS` extrapolations) are submitted via **`cochem_workstation_job_runner`** using verified `cochem.student-handoff/2` bundles. **`DLPNO-CCSD(T)` is strictly BANNED under Pipeline 5.0.0** — use canonical `CCSD` / `CCSD(T)` or `revDSD-PBEP86-D4/2021` instead.

---

## Plain-English CHEM 490 Student ↔ Professor Research Handoff

- **What you run locally in WSL2:** Conformer searches (`CREST 3.0.2`), `xTB` / `PySCF` screening, local ORCA 6.1.1 **`revDSD-PBEP86-D4/2021`** equilibrium geometries and hybrid-DFT **`! VPT2`** anharmonic rotational/vibrational corrections, plus `TOPOS`, `BENCH`, `TORQ`, `GEOM`, `SCRIBE`, and `spfit`/`spcat` analysis.
- **What you hand off to `cochem_workstation_job_runner`:** Seal your verified `cochem.student-handoff/2` `.zip` + `.zip.sha256` bundle (`student/handoff.py seal` with `course_id: "CHEM490"`, `target_continuation: "workstation"`) so Dr. Klaassen can run higher-end canonical **`CCSD` / `CCSD(T)`** calculations on Cumberland University's department research computers (`DLPNO-CCSD(T)` is banned under Pipeline 5.0.0).
- **What Dr. Klaassen hands back to you:** Converged canonical ORCA `.out`/`.xyz` files (for example, `professor_orca_return_h2o_ccsd.out`) for local parsing and Helgaker CBS extrapolation with `cochem-bench`, plus experimental rotational spectroscopy data from our **Tennessee Tech University** CP-FTMW collaborators for Kraitchman $r_s$, weighted $r_0$, and Pickett `spfit`/`spcat` analysis.

---

## Stage 1 — Local WSL2 Workstation Setup & Optional Local Voilà Dashboard

### Step 1: Activate the Pre-Provisioned WSL2 Environment

```bash
source ~/CoChem_Workstation_Direct/activate_cochem_wsl.sh
cd /mnt/d/__CoChem/GitHub-Repo/CoChem-BASE
```

This puts the managed workstation binaries and scientific Python environment first on `PATH`:
- **Direct Python imports (`python`):** `cochem_base`, `pyscf`, `cochem_bench`, `cochem_scribe` (plus `cochem_spyfy` after installing the optional `CoChem-SPYFY` add-on)
- **Direct binaries & module CLIs on `PATH`:** `cochem-cli`, `xtb`, `crest`, `orca`, `spfit`, `spcat`, `topos` (`cochem-topos`), `cochem-bench`, `cochem-torq`, `cochem-geom`, `cochem-scribe` (plus `cochem-spyfy` after installing the optional `CoChem-SPYFY` add-on)

### Step 2: Optional Local Voilà Browser Dashboard (`port 8866`)

To use the four-tab Voilà GUI (`1 · Setup`, `2 · Add your molecule`, `3 · Run assigned calculation`, `4 · Read and save results`) locally on WSL2:

```bash
python /mnt/d/__CoChem/GitHub-Repo/CoChem-BASE/scripts/student_voila.py \
  /mnt/d/__CoChem/GitHub-Repo/CoChem-BASE/Start_Here.ipynb \
  --port=8866 --no-browser
```

Open `http://localhost:8866` in your browser, confirm **Local computer (Linux)** is selected, upload `.xyz` inputs, run `xTB` or `PySCF` calculations, and download verified `.zip` bundles.

*(Archival Compatibility Note: Legacy GitHub Codespaces took `~10–15 minutes` on a fresh container or `~30 seconds` with Prebuilds and are now deprecated in favor of instant local WSL2 activation above.)*

---

## Stage 2 — Local WSL2 `revDSD-PBEP86-D4/2021` + VPT2 Workflow (ORCA 6.1.1)

Local WSL2 workstations with ORCA 6.1.1 support publication-grade double-hybrid equilibrium geometries and VPT2 anharmonic rotational/vibrational corrections:

1. **Double-Hybrid Equilibrium Geometry (`revDSD-PBEP86-D4/2021`):**
   - **ORCA 6.1.1 requires the `/2021` suffix** (`revDSD-PBEP86-D4/2021`, never bare `revDSD-PBEP86-D4`).
   - Typical wall time for a 5-atom molecule (e.g., $\text{HCOOH}$) with `def2-TZVPP` / `AutoAux` is **~54 seconds** locally in WSL2:

```orca
! revDSD-PBEP86-D4/2021 def2-TZVPP AutoAux TightOpt TightSCF DefGrid3
%pal nprocs 4 end
%maxcore 2000
* xyzfile 0 1 hcooh_start.xyz
```

2. **Anharmonic VPT2 Vibrational & Rotational Corrections ($\Delta B_{\text{vib}}$):**
   - **Important ORCA 6.1.1 Limitations (Verified on Live WSL2):**
     1. ORCA 6.1.1 removed analytic MP2 Hessians, so native `! VPT2` cannot run directly on double-hybrid `revDSD-PBEP86-D4/2021`.
     2. In ORCA 6.1.1 simple input lines, dispersion must be **space-separated (`! B3LYP D4`)** — writing hyphenated `! B3LYP-D4` exits immediately with `INPUT ERROR` (exit `4`).
     3. Never combine `TightOpt` and `VPT2` on the same simple input line — ORCA 6.1.1 exits `0` after optimization and **silently skips VPT2**. Always run a **two-step workflow** (`TightOpt` first, then standalone `! ... VPT2` on the optimized `.xyz`).
   - Use **one of two verified local WSL2 VPT2 routes**:
     - **Route A (Composite Hybrid-DFT Native `! VPT2`, ~4.2 min for 5 atoms):** Combine the **`revDSD-PBEP86-D4/2021`** equilibrium geometry (`~54 s`, providing $B_e$) with a two-step **B3LYP-D4** (`! B3LYP D4 def2-TZVPP RIJCOSX def2/J`) `TightOpt` followed by standalone `! VPT2` (`~4.2 min` for 5 atoms, providing anharmonic $\Delta B_{\text{vib}}$ and VPT2 fundamentals) to form $B_0 = B_e(\text{revDSD}) + \Delta B_{\text{vib}}(\text{B3LYP-D4})$.
     - **Route B (External Displaced-`NumFreq` VPT2 at `revDSD-PBEP86-D4/2021`, ~16–22 min):** Run displaced numerical Hessians (`NumFreq`) externally around the `revDSD-PBEP86-D4/2021` minimum when pure double-hybrid anharmonic cubic/quartic force constants are required.

```orca
# Step 2a — Optimize at B3LYP D4 / def2-TZVPP first (space-separated "B3LYP D4"):
! B3LYP D4 def2-TZVPP RIJCOSX def2/J TightOpt TightSCF DefGrid3
%pal nprocs 4 end
%maxcore 2000
* xyzfile 0 1 hcooh_revdsd_opt.xyz
```

```orca
# Step 2b — Standalone native VPT2 on the Step 2a converged geometry (do NOT combine TightOpt + VPT2):
! B3LYP D4 def2-TZVPP RIJCOSX def2/J TightSCF DefGrid3 VPT2
%pal nprocs 4 end
%maxcore 2000
* xyzfile 0 1 step2a_b3lyp_opt.xyz
```

3. **Higher-End Canonical `CCSD` / `CCSD(T)` Handoff via `cochem_workstation_job_runner`:**
   - Seal your converged geometry (`student/handoff.py seal --source-dir ... --manifest ... --output ...` with `course_id: "CHEM490"`, `target_continuation: "workstation"`) and submit through **`cochem_workstation_job_runner`** for canonical **`CCSD`** / **`CCSD(T)`** (`cc-pVTZ` / `cc-pVQZ` CBS) calculations on the department research workstation.
   - **Pipeline 5.0.0 Method Rule:** **`DLPNO-CCSD(T)` is banned** under Pipeline 5.0.0. Always request canonical `CCSD` or canonical `CCSD(T)` (or use local `revDSD-PBEP86-D4/2021`).

---

## Stage 3 — Week-by-Week CHEM 490 Local WSL2 CLI Reference

### Environment Health Check (Week 4 — `CoChem-BASE`)
```bash
cochem-cli status --json
cochem-cli audit
cochem-cli addons
python -c "import cochem_base, pyscf, cochem_bench, cochem_scribe; print('PySCF', pyscf.__version__)"
which xtb crest spfit spcat topos cochem-bench cochem-torq cochem-geom cochem-scribe
```

### Week 5 — Conformer Discovery (`CoChem-TOPOS`, `xTB`, `CREST 3.0.2`)
Always pass **`--legacy --xnam "$(which xtb)" --nocross`** when running CREST 3.0.2:
```bash
topos --help
xtb h2o_hf_dimer.xyz --opt tight --gfn 2
crest h2o_hf_dimer.xyz --gfn2 --nci --legacy --xnam "$(which xtb)" --nocross -T 2
```

### Week 6 — ORCA Output Parsing & CBS Extrapolation (`CoChem-BENCH`)
Parse returned canonical workstation ORCA outputs (such as `professor_orca_return_h2o_ccsd.out`) and perform two-point Helgaker CBS extrapolation:
```bash
cochem-bench --help
```

### Week 7 — 1D Torsional PES & Anharmonic Analysis (`CoChem-TORQ`)
Run a genuine relaxed 1D torsional PES scan (`PySCF` + `geomeTRIC`, e.g., `h2o2_start.xyz`) and parse ORCA 6.1.1 VPT2 rotational outputs:
```bash
cochem-torq doctor --execution local_validation
cochem-torq torsional-scan \
  --molecule-id H2O2 \
  --xyz examples/student_inputs/h2o2_start.xyz \
  --dihedral 0 1 2 3 \
  --method b3lyp --basis def2-svp \
  --output results/h2o2_torsional_scan.json
cochem-torq parse-vpt2 results/hcooh_h2o_vpt2.out --output results/hcooh_h2o_vpt2_parsed.json
```

### Weeks 9–10 — Weighted $r_0$ & Kraitchman $r_s$ Structure Fitting (`CoChem-GEOM` & `scripts/kraitchman_rs.py`)
Use `cochem-geom` (isolated from BASE's internal constraint broker) for weighted $r_0$ fitting, and `scripts/kraitchman_rs.py --course-id CHEM490` for exact rigid-rotor Kraitchman single-substitution $|r_s|$ coordinates (honestly flagging Costain imaginary coordinates where $r_s^2 < 0$):
```bash
cochem-geom --help
python scripts/kraitchman_rs.py \
  --parent-abc 835840.3 435351.7 278139.8 \
  --iso-abc 701931.5 272912.6 192055.2 \
  --parent-mass-amu 18.010565 \
  --delta-mass-amu 1.006277 \
  --course-id CHEM490 \
  --label H2O_HDO \
  --output-json results/h2o_hdo_kraitchman.json \
  --output-md results/h2o_hdo_kraitchman.md
```

### Week 10 — 8–18 GHz CP-FTMW Prediction & Pickett Fitting (`spfit`, `spcat`, `scripts/spcat_runner.py`, & Optional `CoChem-SPYFY` Add-On)
Generate Watson A-reduction Pickett `.var`/`.int` decks and execute compiled JPL `calpgm` `spcat` for 8–18 GHz CP-FTMW predictions at $T_{\text{rot}} = 2.0\text{ K}$. If your project uses the optional **`CoChem-SPYFY`** rotational-fitting / GruLab SURF add-on (not installed by default), install it once with `bash scripts/install_optional_spyfy.sh` (or `cochem-cli install-addon spyfy`):
```bash
python scripts/spcat_runner.py \
  --a-mhz 410000 --b-mhz 7260 --c-mhz 7140 \
  --mu-a 4.07 --temperature-k 2.0 \
  --freq-min-ghz 8.0 --freq-max-ghz 18.0 \
  --constant-type Be --allow-unvibrated-be \
  --output-json results/h2o_hf_8_18ghz.json \
  --output-csv results/h2o_hf_8_18ghz.csv

# Optional CoChem-SPYFY add-on (install on demand for Pickett/GruLab SURF workflows):
bash scripts/install_optional_spyfy.sh
cochem-spyfy info
```
*(Remember Method Matrix §3.0: distinguish equilibrium $B_e$ from vibrationally corrected ground-state $B_0 = B_e + \Delta B_{\text{vib}}$ before comparing with Tennessee Tech CP-FTMW line frequencies.)*

### Week 11 — Publication Figures, Provenance & FactLedger (`CoChem-SCRIBE` & `scripts/fact_ledger.py`)
Generate publication-grade figures and SHA-256-verified provenance manifests for your *J. Phys. Chem. A* Dual-Path Capstone manuscript:
```bash
cochem-scribe --help
python scripts/fact_ledger.py --help
```

---

## Troubleshooting Quick Reference

| Symptom | Cause & Fix |
| --- | --- |
| ORCA 6.1.1 rejects `revDSD-PBEP86-D4` | ORCA 6.1.1 requires the explicit `/2021` functional keyword: `revDSD-PBEP86-D4/2021`. |
| ORCA 6.1.1 fails on `! revDSD-PBEP86-D4/2021 VPT2` | ORCA 6.1.1 removed analytic MP2 Hessians. Use composite `revDSD-PBEP86-D4/2021` geometry (~54 s) + two-step hybrid DFT **B3LYP-D4** (`! B3LYP D4 def2-TZVPP TightOpt` then standalone `! B3LYP D4 def2-TZVPP VPT2`, ~4.2 min for 5 atoms), or external displaced-`NumFreq` VPT2 (~16–22 min). |
| ORCA 6.1.1 exits `4` on `! B3LYP-D4` or silently skips `VPT2` with `TightOpt` | Write dispersion space-separated (`! B3LYP D4`, never `! B3LYP-D4`) and run `TightOpt` and `VPT2` as **two separate jobs** (combining `TightOpt` + `VPT2` on one line exits `0` and skips VPT2). |
| OpenMPI rejects `%pal nprocs 4 end` on WSL2 (`not enough slots available`) | Ensure `activate_cochem_wsl.sh` is sourced (exports `OMPI_MCA_hwloc_base_use_hwthreads_as_cpus=1` so OpenMPI maps logical threads cleanly on WSL2). |
| CREST 3.0.2 cannot locate `xtb` or hangs in GC | Pass `--legacy --xnam "$(which xtb)" --nocross` on every CREST 3.0.2 command. |
| `scripts/spcat_runner.py` reports `"status": "PENDING"` | Activate WSL2 first (`source ~/CoChem_Workstation_Direct/activate_cochem_wsl.sh`) so compiled `spcat` is on `PATH`. |
| Imaginary Kraitchman coordinate (`r_s^2 < 0`) | Real physical Costain zero-point vibrational effect near a principal axis or symmetry plane (for example, $c$-axis of planar $\text{H}_2\text{O}$). Report `null` / `IMAGINARY` honestly; never replace with `0.0`. |
