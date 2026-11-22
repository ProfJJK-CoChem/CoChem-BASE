# CoChem Student CURE Workflows & Pipeline 5.0.0 Handoff (`student/`)

CoChem supports **both** private/template research repositories (such as CHEM 490
ORCA 6.1.1 / CFOUR / SPFIT / SPCAT projects) and **public-fork CURE workflows**
(`XYZ -> CREST 3.0.2 -> MLFF -> CPU PySCF -> cochem.student-handoff/2`) developed
for **Tennessee Tech University** courses (`CHEM312`, `CHEM490`, `CHEM410`, `CHEM411`).

## 1. Dashboard-First Start (Recommended)

1. Copy or fork `ProfJJK-CoChem/CoChem-BASE` into your own GitHub account.
2. Open a GitHub Codespace on `main` and wait for port **8866 (`CoChem Voilà dashboard`)**
   to launch automatically with `PySCF`, `xTB`, `CREST`, `TOPOS`, and `TORQ`.
3. Upload your `.xyz` structure, verify total **charge** and **spin multiplicity**,
   run your assigned calculation, and download your verified ZIP bundle.

## 2. Manual GitHub Actions Fallback (`workflow_dispatch` Only)

When working from a public fork without a live Codespace, run one of the manual
course workflows from the **Actions** tab (all course workflows are strictly
`workflow_dispatch`-only — zero automatic `push:` triggers and zero `schedule:` crons):

| Workflow | Purpose | Course Track |
| --- | --- | --- |
| `.github/workflows/student_conformers.yml` | Generalized `XYZ -> CREST 3.0.2 -> AIMNet2/MACE -> CPU PySCF` conformer search and optimization | `CHEM312` M1, `CHEM490`, `CHEM410`, `CHEM411` |
| `.github/workflows/04_crest_nci_dimer_bsse.yml` | `CREST --nci` ellipsoidal wall sampling + PySCF Boys-Bernardi counterpoise BSSE | `CHEM312` M3 (Week 10/11) |
| `.github/workflows/05_gvpt2_6shard_anharmonic.yml` | Deterministic 6-shard (`shard: 0..5`) Barone GVPT2 displaced-Hessian anharmonic workflow (`vpt2_anharmonic`) | `CHEM312` M3 |
| `.github/workflows/06_aimnet2_neb_pyscf_rxn_profile.yml` | Charge-aware `AIMNet2` 11-image CI-NEB + TS polish + IRC + PySCF `DF-wB97X-D3/def2-TZVPP + PCM` via `cochem-kinetic rxn-profile` | `CHEM312` M3 (Week 10) |
| `.github/workflows/07_spcat_8_18ghz_prediction.yml` | Watson A-reduction SPCAT 8–18 GHz CP-FTMW prediction (`T_rot = 2.0 K`) + L1–L3 `FactLedger` dossier | `CHEM312` M4, `CHEM490` |

### CHEM 312 M2–M4 Analysis CLI Tools (`scripts/`)

| Script | Module | Purpose |
| --- | --- | --- |
| `scripts/kk_atr_correct.py` | M2 | Single-bounce diamond ATR-FTIR (`n_1 = 2.417`, `45 deg`) Kramers-Kronig phase retrieval and Fresnel inversion (`n(nu)`, `kappa(nu)`, `Delta_nu` blue-shift) |
| `scripts/vdw_titration_diff.py` | M3 | 1:1 `monomer...H2O` / `monomer...CO2` C=O vibrational shift + counterpoise BSSE report (`PENDING` for unmeasured ATR spectra) |
| `scripts/fermi_deperturb.py` | M3 | Exact 2x2 secular matrix Martin Fermi resonance deperturbation (`nu_1^0`, `2*nu_2^0`, `|W|`, mixing angle `theta`) |
| `scripts/gvpt2_shard_runner.py` | M3 | Deterministic 6-shard (`0..5`) GVPT2 displacement planner, shard runner, and incomplete-shard-safe aggregator |
| `scripts/fact_ledger.py` | M4 | Cryptographic L1–L3 SHA-256 `FactLedger.json` / `FactLedger.md` builder and fail-closed tamper verifier |

## 3. Generalized Scientific Domain (`cochem.student-handoff/2`)

- **Elements (11):** `H`, `B`, `C`, `N`, `O`, `F`, `Si`, `P`, `S`, `Cl`, `Br`
- **Electronic state:** `charge` in `{-2, -1, 0, +1, +2}`, `multiplicity` in `{1, 2, 3}` (checked for electron-spin parity)
- **Size budgets:** `1..64` atoms per frame, `1..256` frames per trajectory
- **MLFF routing rule:** Charge-aware **`AIMNet2`** is mandatory whenever `charge != 0`, `multiplicity != 1`, or any heteroatom (`F`, `S`, `Cl`, `Br`, `P`, `Si`, `B`) is present. Neutral-only `MACE-OFF24` is permitted only for neutral singlet `H/C/N/O` molecules.
- **CPU PySCF refinement:** `RHF`/`UHF`, `B3LYP-D3BJ`, or `(DF-)wB97X-D3` with `STO-3G`, `def2-SVP`, `def2-TZVP`, or `def2-TZVPP`, optional `gas` / `pcm` / `ddcosmo` solvation, and optional harmonic frequency check (`hessian_calculated`, `n_imaginary_modes`).
- **Collaborator institution:** `"Tennessee Tech University"`.

## 4. Portable Verification & Pipeline 5.0.0 Handoff

Every workflow seals a `cochem.student-handoff/2` ZIP archive together with a
`.zip.sha256` sidecar. Verify any `v1` (`cochem.student-conformer-handoff/1`) or
`v2` (`cochem.student-handoff/2`) bundle using only the Python standard library:

```bash
python student/handoff.py path/to/CoChem-bundle.zip --sidecar path/to/CoChem-bundle.zip.sha256 --stage ./received
```

Upload both the inner `.zip` and `.zip.sha256` file to your course's Pipeline 5.0.0
handoff folder for automated workstation, Colab GPU, or GCP Spot continuation.
