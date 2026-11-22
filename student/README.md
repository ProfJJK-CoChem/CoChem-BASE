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
| `.github/workflows/student_conformers.yml` | Generalized `XYZ -> CREST 3.0.2 -> AIMNet2/MACE -> CPU PySCF` conformer search and optimization | `CHEM312`, `CHEM490`, `CHEM410`, `CHEM411` |
| `.github/workflows/06_aimnet2_neb_pyscf_rxn_profile.yml` | Charge-aware `AIMNet2` 11-image CI-NEB + TS polish + IRC + PySCF `DF-wB97X-D3/def2-TZVPP + PCM` via `cochem-kinetic rxn-profile` | `CHEM312` Week 10 |
| `.github/workflows/04_crest_nci_dimer_bsse.yml` | `CREST --nci` ellipsoidal wall sampling + PySCF counterpoise BSSE | `CHEM312` Week 10/11 |

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
