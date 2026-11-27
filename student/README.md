# CoChem Student Course Workflows & Handoff Guide (`student/`)

Choose your course at **Cumberland University** (partnering with **Tennessee Tech University** external CP-FTMW microwave spectroscopy collaborators):

- **[CHEM 311 Organic Chemistry I (`CoChem-QUEST`) Step-by-Step Guide (`CHEM311_STEP_BY_STEP_GUIDE.md`)](CHEM311_STEP_BY_STEP_GUIDE.md)** — Local WSL2 Modules 0–5 (`RDKit`, `GFN2-xTB`, `CREST 3.0.2`, `PySCF`, `IsotopologueSpectroscopyEngine`, `Pickett SPCAT`).
- **[CHEM 312L Organic Chemistry II Lab Step-by-Step Guide (`CHEM312L_STEP_BY_STEP_GUIDE.md`)](CHEM312L_STEP_BY_STEP_GUIDE.md)** — Local WSL2 Milestones 1–4 (`CREST 3.0.2`, `AIMNet2`, `PySCF`, KK-ATR, Fermi deperturbation, 6-shard GVPT2, Kraitchman $|r_s|$, `FactLedger`).
- **[CHEM 490 Directed Research Step-by-Step Guide (`CHEM490_STEP_BY_STEP_GUIDE.md`)](CHEM490_STEP_BY_STEP_GUIDE.md)** — Local WSL2 ORCA 6.1.1 (`revDSD-PBEP86-D4/2021` + VPT2), `TOPOS`/`BENCH`/`TORQ`/`GEOM`/`SCRIBE`/`SPYFY`, and `cochem_workstation_job_runner` canonical `CCSD`/`CCSD(T)` handoffs.

> **2026-11-27 Architecture Notice (`CoChem-BASE` ↔ `CoChem-CURE`):**
> - **Primary Execution Stack:** Local **WSL2 Ubuntu** (`source ~/CoChem_Workstation_Direct/activate_cochem_wsl.sh`) is the primary execution stack across `CHEM 311`, `CHEM 312L`, and `CHEM 490`.
> - **"Is This a Course?" Dynamic `CoChem-CURE` Split:** `CoChem-BASE` asks *"Is this a course?"* in **`1 · Setup`** and via `python -m cochem_base.course_loader`. Answer **No** (default) to run `CoChem-BASE` standalone for independent research; answer **Yes** to obtain **`ProfJJK-CoChem/CoChem-CURE`** and dynamically load authoritative course profiles, milestones, and pathways (the `CHEM*_STEP_BY_STEP_GUIDE.md` files below are local mirrors). Legacy `classroom50`, GitHub Codespaces, and GitHub Actions compute are **deprecated**. `CoChem-ORACLE` is redesigned as the **zero-LLM Student Data Auditing Model**.
> - **CREST 3.0.2 Mandate:** Always pass `--legacy --xnam "$(which xtb)" --nocross` when invoking CREST 3.0.2 locally.

---

## 1. Local WSL2 Start (All Courses)

1. Open WSL2 Ubuntu and activate the managed environment:
   ```bash
   source ~/CoChem_Workstation_Direct/activate_cochem_wsl.sh
   ```
2. Starter files (`AI_Usage_Log.md`, `targets/team_card.yaml`, `data/`, `results/`) are committed at the repository root. Standardized CHEM 312L ATR-FTIR resolution is **`0.5 cm^-1`**.
3. For optional local GUI inspection, run `python scripts/student_voila.py Start_Here.ipynb --port=8866 --no-browser` and open `http://localhost:8866`.

---

## 2. Local Analysis CLI Tools (`scripts/`)

| Script | Module | Purpose |
| --- | --- | --- |
| `scripts/kk_atr_correct.py` | M2 | Single-bounce diamond ATR-FTIR (`0.5 cm^-1`, `n_1 = 2.417`, `45 deg`) Kramers–Kronig phase retrieval and Fresnel inversion (`--input`/`--csv`, `--n-inf`, `--angle-deg`/`--angle`, `--n-crystal`/`--crystal`, `--output-csv`/`--out`, `--output-json`) |
| `scripts/fermi_deperturb.py` | M3 | Exact 2×2 secular matrix Martin Fermi resonance deperturbation (`nu_1^0`, `2*nu_2^0`, `|W|`, mixing angle `theta`) |
| `scripts/vdw_titration_diff.py` | M3 | 1:1 `monomer...H2O` / `monomer...CO2` C=O vibrational shift + Boys–Bernardi counterpoise BSSE report (`PENDING` for unmeasured ATR spectra) |
| `scripts/gvpt2_shard_runner.py` | M3 | Deterministic 6-shard (`0..5`) GVPT2 displacement planner (`plan`), shard runner (`run-shard`), and fail-closed aggregator (`aggregate`) |
| `scripts/kraitchman_rs.py` | M4 | Planar, 3D asymmetric, & symmetric-top Kraitchman single-substitution `|r_s|` coordinates with honest Costain imaginary-axis (`r_s^2 < 0` → `null`) reporting |
| `scripts/fact_ledger.py` | M4 | Cryptographic L1–L3 SHA-256 `FactLedger.json` / `FactLedger.md` builder and fail-closed `--verify` tamper checker |

### Deprecated / Legacy GitHub Actions Workflows (Historical Archive Reference Only)

GitHub Actions compute workflows are **deprecated** in favor of local WSL2 execution. Historical `workflow_dispatch` definitions are retained strictly for archived bundle provenance:

| Legacy Workflow | Historical Purpose | Course Track |
| --- | --- | --- |
| `.github/workflows/student_project_setup.yml` | Legacy setup diagnostic | `CHEM490` archive |
| `.github/workflows/student_conformers.yml` | Legacy M1 `XYZ -> CREST 3.0.2 -> AIMNet2/MACE -> CPU PySCF` | `CHEM312` M1, `CHEM490` |
| `.github/workflows/04_crest_nci_dimer_bsse.yml` | Legacy M3 `CREST --nci` + PySCF counterpoise BSSE | `CHEM312` M3 |
| `.github/workflows/05_gvpt2_6shard_anharmonic.yml` | Legacy M3 6-shard Barone GVPT2 | `CHEM312` M3 |
| `.github/workflows/06_aimnet2_neb_pyscf_rxn_profile.yml` | Legacy Week 10 NAS `AIMNet2` CI-NEB + PySCF PCM | `CHEM312` M3/M4 |
| `.github/workflows/07_spcat_8_18ghz_prediction.yml` | Legacy M4 SPCAT 8–18 GHz prediction | `CHEM312` M4, `CHEM490` |

---

## 3. Generalized Scientific Domain (`cochem.student-handoff/2`)

- **Course IDs:** `CHEM311`, `CHEM312`, `CHEM490`, `CHEM410`, `CHEM411`
- **Elements (11):** `H`, `B`, `C`, `N`, `O`, `F`, `Si`, `P`, `S`, `Cl`, `Br`
- **Electronic state:** `charge` in `{-2, -1, 0, +1, +2}`, `multiplicity` in `{1, 2, 3}` (checked for electron-spin parity)
- **Size budgets:** `1..64` atoms per frame, `1..256` frames per trajectory
- **MLFF routing rule:** Charge-aware **`AIMNet2`** is mandatory whenever `charge != 0`, `multiplicity != 1`, or any heteroatom (`F`, `S`, `Cl`, `Br`, `P`, `Si`, `B`) is present. Neutral-only `MACE-OFF24` is permitted only for neutral singlet `H/C/N/O` molecules.
- **CPU PySCF refinement:** `RHF`/`UHF`, `B3LYP-D3BJ`, or `(DF-)wB97X-D3` with `STO-3G`, `def2-SVP`, `def2-TZVP`, or `def2-TZVPP`, optional `gas` / `pcm` / `ddcosmo` solvation, and optional harmonic frequency check (`frequencies: true` → `hessian_calculated`, `n_imaginary_modes`).
- **Home course & collaborator metadata:** Cumberland University (`CHEM 311`, `CHEM 312 / 312L`, `CHEM 490`) with `"collaborator_institution": "Tennessee Tech University"`.

---

## 4. Plain-English Professor Handoff & Atomic Bundle Verification

Every sealed handoff produces a portable `cochem.student-handoff/2` ZIP archive together with a `.zip.sha256` sidecar (if self-verification fails during `seal`, any partial `.zip` / `.sha256` artifacts are atomically removed). Verify any `v1` or `v2` bundle locally using only the Python standard library:

```bash
python student/handoff.py path/to/CoChem-bundle.zip --sidecar path/to/CoChem-bundle.zip.sha256 --stage ./received
```

- **What you submit to your professor:** Upload your Milestone PDF (with your Commit SHA, `FactLedger` SHA-256, and `AI_Usage_Log.md`) **and** your verified `cochem.student-handoff/2` `.zip` + `.zip.sha256` bundle to the **Canvas assignment**.
- **What your professor does with it:** Verifies your SHA-256 hashes (via `CoChem-ORACLE` zero-LLM Student Data Auditing Model checks) and runs higher-end canonical `CCSD` / `CCSD(T)` calculations via `cochem_workstation_job_runner` (`DLPNO-CCSD(T)` is banned under Pipeline 5.0.0) on Cumberland University's department research computers.
- **What your professor hands back to you:** Graded Canvas rubric feedback, high-accuracy canonical reference outputs, and the Tennessee Tech University CP-FTMW spectroscopy collaborator's experimental rotational comparison for your report and poster.
