# CHEM 490 Directed Research — Step-by-Step Student Guide (Cumberland University)

Welcome to **CHEM 490 Directed Research in Computational Chemistry** at **Cumberland University** (Dr. Joshua J. Klaassen), partnering with **Tennessee Tech University** (external CP-FTMW microwave spectroscopy collaborator).

This is your **single end-to-end guide** for Weeks 1–16 of CHEM 490. Every repository step, browser button label, workflow name, and terminal command below matches the live `CoChem-BASE` repository and your GitHub Codespace environment verbatim.

> **Course Boundaries (Read First):**
> - **Private Template Repository:** Click **Use this template → Create a new repository** on [`ProfJJK-CoChem/CoChem-BASE`](https://github.com/ProfJJK-CoChem/CoChem-BASE), set visibility to **Private**, and name your project **`CoChem-[target]`** (for example, `CoChem-h2o-hf`).
> - **Browser-Only GitHub Codespaces:** No local Python installation, root/admin permissions, or Google Drive Desktop client is required. Everything runs in your browser via **GitHub Codespaces** (`~10–15 minutes` on a fresh Codespace, or `~30 seconds` when Prebuilds are enabled).
> - **Zero Direct Google Colab, Zero Classroom50, Zero ORCA Forum Registration:** CHEM 490 students do **not** use Google Colab directly, do **not** join Classroom50, and do **not** register on the ORCA Forum or install personal ORCA/CFOUR licenses. All open-source engines (`PySCF`, `xTB`, `CREST`, `TOPOS`, `BENCH`, `TORQ`, `GEOM`, `SpycFit`, `SCRIBE`, `spfit`/`spcat`) run locally in your Codespace; optional high-level `ORCA 6.1.1` / `CCSD(T)/CBS` / `VPT2` jobs are run by Dr. Klaassen on Cumberland University's department research computers.

---

## Plain-English CHEM 490 Student ↔ Professor Research Handoff

- **What you submit to Dr. Klaassen:** Commit your verified structures, scripts, and `FactLedger` outputs to your private `CoChem-[target]` repository and download your verified calculation bundle (`.zip`) from the Voilà dashboard (`4 · Read and save results → Download calculation files (.zip)`).
- **What Dr. Klaassen runs on Cumberland's department research computers:** Using your verified starting geometries and electronic states, Dr. Klaassen executes optional high-level licensed calculations (`ORCA 6.1.1`, `CCSD(T)/CBS` benchmarks, and anharmonic `VPT2` rotational/vibrational corrections) on Cumberland University's department research computers.
- **What Dr. Klaassen hands back to you:** Converged ORCA `.out`/`.xyz` files (for example, `professor_orca_return_h2o_ccsd.out`) for local parsing and CBS extrapolation with `cochem-bench`, plus experimental rotational spectroscopy data from our **Tennessee Tech University** CP-FTMW collaborators for Kraitchman $r_s$, weighted $r_0$, and Pickett `spfit`/`spcat` analysis.

---

## Stage 1 — Private Template Creation & Codespace Launch

### Step 1: Create Your Private `CoChem-[target]` Repository
1. Sign in to [GitHub](https://github.com/).
2. Open [`ProfJJK-CoChem/CoChem-BASE`](https://github.com/ProfJJK-CoChem/CoChem-BASE).
3. Click the green **Use this template** button → **Create a new repository**.
4. Set **Owner** to your personal GitHub username, **Repository name** to **`CoChem-[target]`**, and visibility to **Private**.
5. Click **Create repository**.

### Step 2: Optional Actions Self-Check (`student_project_setup.yml`)
If you open your repository's **Actions** tab and run **`CoChem project setup check`** (`student_project_setup.yml`):
- Leave `request_id` at its default **`self-check`** and click **Run workflow**.
- On a personal open-engine template repository without ORCA/CFOUR secrets, the workflow exits **green (`0`)** with:
  > *Open-source Codespace research setup ready (PySCF, xTB, CREST, TOPOS, BENCH, TORQ, GEOM, SpycFit, SCRIBE, spfit/spcat). Optional ORCA/CFOUR access is not configured yet — submit your verified bundle to Dr. Klaassen for department-computer ORCA/CCSD(T)/VPT2 calculations.*

### Step 3: Launch Your GitHub Codespace
1. On your private `CoChem-[target]` repository page, click **Code** → **Codespaces** → **Create codespace on main**.
2. Wait **`~10–15 minutes` on a fresh Codespace (or `~30 seconds` when Prebuilds are enabled)** while automatic setup provisions `PySCF`, `xTB`, `CREST`, `spfit`, `spcat`, `TOPOS`, `BENCH`, `TORQ`, `GEOM`, `SpycFit`, `SCRIBE`, and the 11-phase Stage 0 verification.
3. Port **8866 (`CoChem Voilà dashboard`)** displays an auto-refreshing setup progress page and switches automatically to the live CoChem dashboard as soon as setup finishes. (If needed, open VS Code's **Ports** panel and click the globe icon next to **8866**.)
4. **Always stop your Codespace when finished:** open [github.com/codespaces](https://github.com/codespaces), click **`...`** next to your Codespace, and choose **Stop codespace**.

---

## Stage 2 — Live Voilà Browser Dashboard Walkthrough (`port 8866`)

Use the four numbered buttons across the top of the dashboard:

1. **`1 · Setup`**
   - Confirm **Where will calculations run?** is set to **Local computer (Linux)** (your Codespace, where `PySCF`, `xTB`, `CREST`, `TOPOS`, and `TORQ` run locally).
   - Expand **Installation details and software versions** to verify **TOPOS**, **TORQ**, **XTB**, **CREST**, and **PySCF** in the `CoChem components` table.
   - Ignore optional ORCA/CFOUR notices when running open-source engines locally — you will use the Student ↔ Professor Handoff whenever a milestone requires ORCA.
2. **`2 · Add your molecule`**
   - Click **Upload scientific inputs** and upload your `.xyz` structure (for example, `h2o_start.xyz`).
   - Inspect the interactive **3D Structure preview** directly on **2 · Add your molecule** (drag to rotate, scroll to zoom).
   - Select your file and frame, click **Use selected starting geometry**, then click **Continue to calculation settings**.
3. **`3 · Run assigned calculation`**
   - Confirm your molecule summary, **Total charge**, and **Spin multiplicity**.
   - **To run an `xTB` geometry optimization:** Select **Engine: `xTB`** (sets `GFN2-xTB`, `Screening`), choose **Optimize the geometry**, and click **Optimize geometry**.
   - **To run a `PySCF` RHF single point:** Select **Engine: `PySCF (RHF single point)`** (automatically sets `Screening`, `Method: HF/STO-3G`, `Basis Set: STO-3G`, `Surroundings: Gas phase`), verify `Current settings` shows `program PYSCF`, and click **Run PySCF single point** (for water, `E ≈ -74.96 Ha`).
4. **`4 · Read and save results`**
   - Review the converged energy, units, and provenance details.
   - Click **Prepare calculation download**, wait for the link, and click **Download calculation files (.zip)** to save your verified bundle locally.

---

## Stage 3 — Week-by-Week CHEM 490 Codespace CLI Reference

Your Codespace terminal automatically puts `/home/vscode/CoChem_Artifacts/bin` and `/home/vscode/CoChem_Artifacts/ui-env/bin` first on `PATH`. In the default terminal:
- **Direct Python imports (`python`):** `cochem_base`, `pyscf`, `cochem_bench`, `cochem_spycfit`, `cochem_scribe`
- **Direct binaries & module CLIs on `PATH`:** `cochem-cli`, `xtb`, `crest`, `spfit`, `spcat`, `topos` (`cochem-topos`), `cochem-bench`, `cochem-torq`, `cochem-geom`, `cochem-spycfit` (or `python -m cochem_spycfit`), `cochem-scribe`

### Environment Health Check (Week 4 — `CoChem-BASE`)
```bash
cochem-cli status --json
cochem-cli audit
python -c "import cochem_base, pyscf, cochem_bench, cochem_spycfit, cochem_scribe; print('PySCF', pyscf.__version__)"
which xtb crest spfit spcat topos cochem-bench cochem-torq cochem-geom cochem-spycfit cochem-scribe
```

### Week 5 — Conformer Discovery (`CoChem-TOPOS`, `xTB`, `CREST`)
```bash
topos --help
xtb h2o_hf_dimer.xyz --opt tight --gfn 2
crest h2o_hf_dimer.xyz --gfn2 --nci -T 2
```

### Week 6 — ORCA Output Parsing & CBS Extrapolation (`CoChem-BENCH`)
Parse returned department-computer ORCA outputs (such as `professor_orca_return_h2o_ccsd.out`) and perform two-point Helgaker CBS extrapolation:
```bash
cochem-bench --help
```

### Week 7 — 1D Torsional PES & Anharmonic Analysis (`CoChem-TORQ`)
Scan torsional coordinates (such as `h2o2_start.xyz`) and inspect VPT2 outputs:
```bash
cochem-torq --help
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

### Week 10 — 8–18 GHz CP-FTMW Prediction & Pickett Fitting (`CoChem-SpycFit`, `spfit`, `spcat`, `scripts/spcat_runner.py`)
Generate Watson A-reduction Pickett `.var`/`.int` decks and execute compiled JPL `calpgm` `spcat` for 8–18 GHz CP-FTMW predictions at $T_{\text{rot}} = 2.0\text{ K}$:
```bash
python scripts/spcat_runner.py \
  --a-mhz 410000 --b-mhz 7260 --c-mhz 7140 \
  --mu-a 4.07 --temperature-k 2.0 \
  --freq-min-ghz 8.0 --freq-max-ghz 18.0 \
  --constant-type Be --allow-unvibrated-be \
  --output-json results/h2o_hf_8_18ghz.json \
  --output-csv results/h2o_hf_8_18ghz.csv
cochem-spycfit --help
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
| Codespace still starting on port `8866` | Cold setup takes `~10–15 minutes` (or `~30 seconds` with Prebuilds). Wait for the auto-refreshing progress page to switch to the Voilà dashboard. |
| ORCA/CFOUR listed as optional/unavailable | Expected in student Codespaces. Use free local engines (`PySCF`, `xTB`, `CREST`) and submit your verified `.zip` bundle to Dr. Klaassen for department-computer ORCA/CCSD(T)/VPT2 runs. |
| `scripts/spcat_runner.py` reports `"status": "PENDING"` | `spcat` binary is not on `PATH` (for example, outside Codespaces). Inside your Codespace, `/home/vscode/CoChem_Artifacts/bin/spcat` is automatically compiled and placed on `PATH`. |
| Imaginary Kraitchman coordinate (`r_s^2 < 0`) | Real physical Costain zero-point vibrational effect near a principal axis or symmetry plane (for example, $c$-axis of planar $\text{H}_2\text{O}$). Report `null` / `IMAGINARY` honestly; never replace with `0.0`. |
