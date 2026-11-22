# CoChem Student CURE Workflows & Handoff Guide (`student/`)

**Start here if you are in CHEM 312L (Cumberland University):**
**[Open the Complete CHEM 312L Step-by-Step Student Guide (`CHEM312L_STEP_BY_STEP_GUIDE.md`)](CHEM312L_STEP_BY_STEP_GUIDE.md)**

CoChem supports **public-fork CURE workflows** (`XYZ -> CREST 3.0.2 -> MLFF -> CPU PySCF -> cochem.student-handoff/2`)
for **Cumberland University** (`CHEM 312 / 312L` Organic Chemistry II Lab) in
spectroscopy partnership with **Tennessee Tech University** (external CP-FTMW
microwave spectroscopy collaborator), as well as separate instructor-invited
private research repositories (`CHEM 490`).

> **CHEM 312L Boundaries:** Click **Fork** on `ProfJJK-CoChem/CoChem-BASE`, keep
> visibility **Public**, and keep the repository name **`CoChem-BASE`** (required
> by M1 Rubric C4 for unlimited free GitHub Actions minutes). CHEM 312L runs
> exclusively on GitHub Codespaces + free public-fork GitHub Actions (`PySCF`,
> `xTB`, `CREST 3.0.2`, `AIMNet2`, `SPCAT`), submits exclusively via **Canvas**,
> and never uses external cloud GPU notebooks, licensed cluster programs
> (ORCA/CFOUR), or API tokens.

---

## 1. Dashboard & Codespace Start

1. Fork `ProfJJK-CoChem/CoChem-BASE` into your personal GitHub account as a **Public** fork named `CoChem-BASE`.
2. Open a GitHub Codespace on `main` and wait **5–10 minutes on a fresh Codespace (or ~30 seconds when Prebuilds are enabled)** for port **8866 (`CoChem Voilà dashboard`)** to launch automatically with `PySCF`, `xTB`, `CREST`, `TOPOS`, and `TORQ`.
3. Your Codespace terminal automatically places `/home/vscode/CoChem_Artifacts/ui-env/bin` first on `PATH`, so `python` and `python3` run all local scripts directly without manual environment activation.
4. Starter files (`AI_Usage_Log.md`, `targets/team_card.yaml`, `data/`, `results/`) are already present on Day 1. Standardized ATR-FTIR resolution is **`0.5 cm^-1`**.

---

## 2. Exact Canonical Course Workflows (`workflow_dispatch` Only)

Upload your `.xyz` structures into **`examples/student_inputs/`** (via GitHub Web UI **Add file → Upload files** or via `git add examples/student_inputs/<file>.xyz && git commit && git push`), then dispatch the exact workflow from your fork's **Actions** tab (all course workflows are strictly `workflow_dispatch`-only — zero automatic `push:` triggers and zero `schedule:` crons):

| Workflow | Purpose & Key Inputs | Course Track |
| --- | --- | --- |
| `.github/workflows/student_project_setup.yml` | Optional private-track setup check (`request_id`); skipped on public forks. CHEM 312L Day-1 smoke test uses `student_conformers.yml` on `ethanol.xyz`. | `CHEM490` private check |
| `.github/workflows/student_conformers.yml` | Generalized `XYZ -> CREST 3.0.2 -> AIMNet2/MACE -> CPU PySCF` conformer search and optimization (`xyz`, `charge`, `multiplicity`, `frequencies: true`, `course_id: CHEM312`) | `CHEM312` M1, `CHEM490` |
| `.github/workflows/04_crest_nci_dimer_bsse.yml` | `CREST --nci` ellipsoidal wall sampling + PySCF Boys–Bernardi counterpoise BSSE (`xyz`, `monomer_a_atoms`) | `CHEM312` M3 (Weeks 10–11) |
| `.github/workflows/05_gvpt2_6shard_anharmonic.yml` | Deterministic 6-shard (`shard: 0..5`) Barone GVPT2 displaced-Hessian anharmonic workflow (`xyz`, `pre_optimize: true`) | `CHEM312` M3 |
| `.github/workflows/06_aimnet2_neb_pyscf_rxn_profile.yml` | Charge-aware `AIMNet2` 11-image CI-NEB + TS polish + IRC + PySCF `DF-wB97X-D3/def2-TZVPP + PCM` (`input_dir`, `charge`, `multiplicity`, `solvent_name`, `dft_basis`, `stage`) | `CHEM312` Week 10 NAS (M3 draft → M4 synthesis) |
| `.github/workflows/07_spcat_8_18ghz_prediction.yml` | Watson A-reduction SPCAT 8–18 GHz CP-FTMW prediction (`T_rot = 2.0 K`, `xyz`, `a_mhz`, `b_mhz`, `c_mhz`, `mu_a`, `mu_b`, `mu_c`) + L1–L3 `FactLedger` | `CHEM312` M4, `CHEM490` |

### Local Codespace Analysis CLI Tools (`scripts/`)

| Script | Module | Purpose |
| --- | --- | --- |
| `scripts/kk_atr_correct.py` | M2 | Single-bounce diamond ATR-FTIR (`0.5 cm^-1`, `n_1 = 2.417`, `45 deg`) Kramers–Kronig phase retrieval and Fresnel inversion (`--input`/`--csv`, `--n-inf`, `--angle-deg`/`--angle`, `--n-crystal`/`--crystal`, `--output-csv`/`--out`, `--output-json`) |
| `scripts/fermi_deperturb.py` | M3 | Exact 2×2 secular matrix Martin Fermi resonance deperturbation (`nu_1^0`, `2*nu_2^0`, `|W|`, mixing angle `theta`) |
| `scripts/vdw_titration_diff.py` | M3 | 1:1 `monomer...H2O` / `monomer...CO2` C=O vibrational shift + Boys–Bernardi counterpoise BSSE report (`PENDING` for unmeasured ATR spectra) |
| `scripts/gvpt2_shard_runner.py` | M3 | Deterministic 6-shard (`0..5`) GVPT2 displacement planner (`plan`), shard runner (`run-shard`), and fail-closed aggregator (`aggregate`) |
| `scripts/kraitchman_rs.py` | M4 | Planar & 3D rigid-rotor Kraitchman single-substitution `|r_s|` coordinates with honest Costain imaginary-axis (`r_s^2 < 0` → `null`) reporting |
| `scripts/fact_ledger.py` | M4 | Cryptographic L1–L3 SHA-256 `FactLedger.json` / `FactLedger.md` builder and fail-closed `--verify` tamper checker |

---

## 3. Generalized Scientific Domain (`cochem.student-handoff/2`)

- **Elements (11):** `H`, `B`, `C`, `N`, `O`, `F`, `Si`, `P`, `S`, `Cl`, `Br`
- **Electronic state:** `charge` in `{-2, -1, 0, +1, +2}`, `multiplicity` in `{1, 2, 3}` (checked for electron-spin parity)
- **Size budgets:** `1..64` atoms per frame, `1..256` frames per trajectory
- **MLFF routing rule:** Charge-aware **`AIMNet2`** is mandatory whenever `charge != 0`, `multiplicity != 1`, or any heteroatom (`F`, `S`, `Cl`, `Br`, `P`, `Si`, `B`) is present. Neutral-only `MACE-OFF24` is permitted only for neutral singlet `H/C/N/O` molecules.
- **CPU PySCF refinement:** `RHF`/`UHF`, `B3LYP-D3BJ`, or `(DF-)wB97X-D3` with `STO-3G`, `def2-SVP`, `def2-TZVP`, or `def2-TZVPP`, optional `gas` / `pcm` / `ddcosmo` solvation, and optional harmonic frequency check (`frequencies: true` → `hessian_calculated`, `n_imaginary_modes`).
- **Home course & collaborator metadata:** Cumberland University (`CHEM 312 / 312L`) with `"collaborator_institution": "Tennessee Tech University"`.

---

## 4. Plain-English Organic Chemistry 2 Professor Handoff & Bundle Verification

Every workflow seals a portable `cochem.student-handoff/2` ZIP archive together
with a `.zip.sha256` sidecar. Verify any `v1` (`cochem.student-conformer-handoff/1`)
or `v2` (`cochem.student-handoff/2`) bundle locally using only the Python standard library:

```bash
python student/handoff.py path/to/CoChem-bundle.zip --sidecar path/to/CoChem-bundle.zip.sha256 --stage ./received
```

- **What you submit to your professor:** Upload your Milestone PDF (with your clickable public-fork GitHub Actions Run URL, Commit SHA, `FactLedger` SHA-256, and `AI_Usage_Log.md`) **and** your verified `cochem.student-handoff/2` `.zip` + `.zip.sha256` bundle to the **Canvas assignment**.
- **What your professor does with it (in Organic Chemistry 2 terms):** Verifies your SHA-256 hashes, grades your rubric, and runs high-precision quantum chemistry calculations (coupled-cluster theory) on Cumberland's department research computers using your verified 3D structures to pin down subtle hydrogen-bond strengths, exact transition-state barrier heights, and microwave rotational constants too demanding for free classroom runners.
- **What your professor hands back to you:** Graded Canvas rubric feedback, the unblinded Week 12 research-grade reference key (so you can compare your DFT energies, carbonyl shifts, and barriers against high-accuracy theory), and the Tennessee Tech University CP-FTMW spectroscopy collaborator's experimental rotational comparison for your M3/M4 report and poster.
