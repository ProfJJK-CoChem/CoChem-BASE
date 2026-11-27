# CHEM 311 (Organic Chemistry I / `CoChem-QUEST`) — Step-by-Step Student Guide (Cumberland University)

Welcome to **CHEM 311 Organic Chemistry I (`CoChem-QUEST`)** at **Cumberland University** (Dr. Joshua J. Klaassen), partnering with **Tennessee Tech University** (external CP-FTMW rotational spectroscopy collaborator).

This guide covers the complete **Modules 0–5 (`M0`–`M5`)** local WSL2 computational workflow. Every Python API attribute, engine flag, and verification check below matches the live `CoChem-BASE` repository verbatim.

> **2026-11-27 Course Architecture & Boundaries (Read First):**
> - **Primary Execution Stack (Local WSL2):** All CHEM 311 calculations run locally in WSL2 Ubuntu via `source ~/CoChem_Workstation_Direct/activate_cochem_wsl.sh` using authentic quantum chemistry engines (`RDKit`, `GFN2-xTB`, `CREST 3.0.2`, `PySCF`, `Pickett SPCAT`, `CoChem-BASE`, `CoChem-TOPOS`, `CoChem-TORQ`, `CoChem-SPYFY`).
> - **Retired / Deprecated Compute Surfaces:** `classroom50`, GitHub Codespaces, and GitHub Actions compute workflows are **retired** and must not be used for CHEM 311 calculations.
> - **Unified Repository & Auditing Model:** Legacy `CoChem-CURE` is superseded by native `CoChem-BASE` course routes (`CHEM311`, `CHEM312`, `CHEM490`). `CoChem-ORACLE` is redesigned as the **zero-LLM Student Data Auditing Model**.
> - **Integrity & Provenance:** Every numerical result must come from an authentic local calculation in your scratch directory—never hardcode or fabricate values. Package verified handoff bundles with `student/handoff.py` (`course_id: "CHEM311"`).

---

## Module 0 — Local WSL2 Workspace Setup & Verification

1. Open a WSL2 Ubuntu terminal and activate the pre-provisioned CoChem workstation environment:

```bash
source ~/CoChem_Workstation_Direct/activate_cochem_wsl.sh
mkdir -p ~/CoChem_Workstation_Direct/Scratch/chem311_run
cd ~/CoChem_Workstation_Direct/Scratch/chem311_run
```

2. Verify that all required local binaries and Python libraries resolve cleanly on `PATH`:

```bash
cochem-cli --version
cochem-topos --version
cochem-torq recipes | head -n 12
cochem-spyfy info | head -n 15
xtb --version | head -n 4
crest --version | head -n 4
which spcat spfit
python -c "import rdkit, pyscf, numpy, scipy, cochem_base; print('OK:', rdkit.__version__, pyscf.__version__)"
```

*(Optional Interactive Dashboard: To inspect the Voilà GUI locally in WSL2, run `python /mnt/d/__CoChem/GitHub-Repo/CoChem-BASE/scripts/student_voila.py /mnt/d/__CoChem/GitHub-Repo/CoChem-BASE/Start_Here.ipynb --port=8866 --no-browser` and open `http://localhost:8866`.)*

---

## Module 1 — Constitutional Isomers of $\text{C}_3\text{H}_6\text{O}$: Acetone (`CC(=O)C`) vs. Propanal (`CCC=O`)

**Learning Goal:** Confirm that constitutional isomers share the exact same monoisotopic mass (`58.0419 amu`) yet have distinct 3D mass distributions (rotational constants $A_e, B_e, C_e$ in MHz), dipole moments, and electronic energies.

```bash
mkdir -p mod1 && cd mod1
cat <<'PY' > run_mod1.py
import json, re, subprocess
from pathlib import Path
import numpy as np
from rdkit import Chem
from rdkit.Chem import AllChem
from cochem_base.spectroscopy.isotopologue import IsotopologueSpectroscopyEngine

def build_xyz(smiles: str, out_xyz: Path, seed: int = 42):
    mol = Chem.AddHs(Chem.MolFromSmiles(smiles))
    params = AllChem.ETKDGv3()
    params.randomSeed = seed
    AllChem.EmbedMolecule(mol, params)
    AllChem.MMFFOptimizeMolecule(mol)
    conf = mol.GetConformer()
    lines = [str(mol.GetNumAtoms()), f"SMILES={smiles} seed={seed}"]
    for atom in mol.GetAtoms():
        pos = conf.GetAtomPosition(atom.GetIdx())
        lines.append(f"{atom.GetSymbol():2s} {pos.x:14.8f} {pos.y:14.8f} {pos.z:14.8f}")
    out_xyz.write_text("\n".join(lines) + "\n")

def read_xyz(path: Path):
    lines = [l.strip() for l in path.read_text().splitlines() if l.strip()]
    n = int(lines[0])
    syms, coords = [], []
    for line in lines[2:2+n]:
        parts = line.split()
        syms.append(parts[0])
        coords.append([float(parts[1]), float(parts[2]), float(parts[3])])
    return syms, np.array(coords, dtype=float)

results = {}
for name, smiles in [("acetone", "CC(=O)C"), ("propanal", "CCC=O")]:
    wdir = Path(name)
    wdir.mkdir(exist_ok=True)
    start_xyz = wdir / f"{name}_start.xyz"
    build_xyz(smiles, start_xyz)
    proc = subprocess.run(
        ["xtb", str(start_xyz.name), "--opt", "--gfn", "2"],
        cwd=wdir, capture_output=True, text=True, check=True,
    )
    (wdir / "xtb_opt.out").write_text(proc.stdout + "\n" + proc.stderr)
    e_match = re.findall(r"TOTAL ENERGY\s+([-0-9.]+)\s+Eh", proc.stdout)
    d_match = re.findall(r"molecular dipole:[\s\S]*?full:\s+[-0-9.]+\s+[-0-9.]+\s+[-0-9.]+\s+([0-9.]+)", proc.stdout)
    syms, coords = read_xyz(wdir / "xtbopt.xyz")
    eng = IsotopologueSpectroscopyEngine(syms, coords)
    obs = eng.compute_observables()
    results[name] = {
        "smiles": smiles,
        "total_mass_amu": round(float(obs.total_mass_amu), 4),
        "A_e_MHz": round(float(obs.A_e_MHz), 2),
        "B_e_MHz": round(float(obs.B_e_MHz), 2),
        "C_e_MHz": round(float(obs.C_e_MHz), 2),
        "inertial_defect_amu_A2": round(float(obs.inertial_defect_amu_A2), 4),
        "gfn2_xtb_energy_eh": float(e_match[-1]) if e_match else None,
        "dipole_debye": float(d_match[-1]) if d_match else None,
    }

de_kj = (results["propanal"]["gfn2_xtb_energy_eh"] - results["acetone"]["gfn2_xtb_energy_eh"]) * 2625.50
results["delta_E_propanal_minus_acetone_kj_mol"] = round(de_kj, 2)
Path("mod1_results.json").write_text(json.dumps(results, indent=2))
print(json.dumps(results, indent=2))
PY
python run_mod1.py
cd ..
```

**Module 1 Verification Checks:**
- Both isomers report `total_mass_amu` = `58.0419` (window `58.00–58.09`).
- Acetone `A_e_MHz` ≈ `10067` MHz (window `9950–10250` MHz); propanal `A_e_MHz` ≈ `16841` MHz (window `16300–17100` MHz).
- Acetone is lower in energy than propanal by $\Delta E \approx +36.3\text{ kJ/mol}$ (`propanal - acetone > 0`).

---

## Module 2 — Stereoisomers: Enantiomers vs. Diastereomers & the Inertial Defect ($\Delta$) Flatness Test

**Learning Goal:** Verify that mirror-image enantiomers (`(1R)`- vs `(1S)-1-chloro-1-fluoroethane`) have identical rotational constants and energies in achiral space, whereas *cis* vs *trans* diastereomers (`cis-` vs `trans-1,2-dichloroethene`) are both strictly planar ($\Delta = 0.0000\text{ amu}\cdot\text{\AA}^2$) yet differ dramatically in dipole moment and $A_e$.

```bash
mkdir -p mod2 && cd mod2
cat <<'PY' > run_mod2.py
import json, re, subprocess
from pathlib import Path
import numpy as np
from rdkit import Chem
from rdkit.Chem import AllChem
from cochem_base.spectroscopy.isotopologue import IsotopologueSpectroscopyEngine

species = [
    ("1R_chlorofluoroethane", "C[C@@H](F)Cl"),
    ("1S_chlorofluoroethane", "C[C@H](F)Cl"),
    ("cis_12_dichloroethene", r"Cl/C=C\Cl"),
    ("trans_12_dichloroethene", "Cl/C=C/Cl"),
]

results = {}
for name, smiles in species:
    wdir = Path(name)
    wdir.mkdir(exist_ok=True)
    mol = Chem.AddHs(Chem.MolFromSmiles(smiles))
    params = AllChem.ETKDGv3()
    params.randomSeed = 42
    AllChem.EmbedMolecule(mol, params)
    AllChem.MMFFOptimizeMolecule(mol)
    conf = mol.GetConformer()
    lines = [str(mol.GetNumAtoms()), f"SMILES={smiles}"]
    for a in mol.GetAtoms():
        p = conf.GetAtomPosition(a.GetIdx())
        lines.append(f"{a.GetSymbol():2s} {p.x:14.8f} {p.y:14.8f} {p.z:14.8f}")
    (wdir / "start.xyz").write_text("\n".join(lines) + "\n")
    proc = subprocess.run(["xtb", "start.xyz", "--opt", "--gfn", "2"], cwd=wdir, capture_output=True, text=True, check=True)
    e_m = re.findall(r"TOTAL ENERGY\s+([-0-9.]+)\s+Eh", proc.stdout)
    d_m = re.findall(r"molecular dipole:[\s\S]*?full:\s+[-0-9.]+\s+[-0-9.]+\s+[-0-9.]+\s+([0-9.]+)", proc.stdout)
    xlines = [l.strip() for l in (wdir / "xtbopt.xyz").read_text().splitlines() if l.strip()]
    n = int(xlines[0])
    syms = [l.split()[0] for l in xlines[2:2+n]]
    coords = np.array([[float(x) for x in l.split()[1:4]] for l in xlines[2:2+n]])
    obs = IsotopologueSpectroscopyEngine(syms, coords).compute_observables()
    results[name] = {
        "smiles": smiles,
        "mass_amu": round(float(obs.total_mass_amu), 4),
        "A_e_MHz": round(float(obs.A_e_MHz), 2),
        "B_e_MHz": round(float(obs.B_e_MHz), 2),
        "C_e_MHz": round(float(obs.C_e_MHz), 2),
        "inertial_defect_amu_A2": round(float(obs.inertial_defect_amu_A2), 4),
        "energy_eh": float(e_m[-1]) if e_m else None,
        "dipole_D": float(d_m[-1]) if d_m else None,
    }

Path("mod2_results.json").write_text(json.dumps(results, indent=2))
print(json.dumps(results, indent=2))
PY
python run_mod2.py
cd ..
```

**Module 2 Verification Checks:**
- `(1R)` and `(1S)-1-chloro-1-fluoroethane`: identical mass (`81.9986 amu`), identical $A_e \approx 9001$ MHz (window `8900–9250` MHz), identical energy (`-15.6021 Eh`), and negative inertial defect (`~ -12.65 amu·Å²`).
- `cis-` and `trans-1,2-dichloroethene`: both strictly planar (`inertial_defect_amu_A2` ≈ `0.0000`); `cis` dipole ≈ `1.88 D` (window `1.70–2.05 D`) vs `trans` dipole ≈ `0.000 D`; `trans` $A_e \approx 53,509$ MHz is ~5× larger than `cis` $A_e \approx 11,471$ MHz.

---

## Module 3 — Conformational Analysis of Butane (`CCCC`) via `CREST 3.0.2` + `GFN2-xTB`

**Learning Goal:** Discover both *anti*-butane ($\phi = 180^\circ$) and *gauche*-butane ($\phi \approx 65^\circ$) using local **CREST 3.0.2** with the mandatory `--legacy --xnam $(which xtb) --nocross` compatibility flags, and compute the `298.15 K` Boltzmann population.

```bash
mkdir -p mod3 && cd mod3
python - <<'PY'
from pathlib import Path
from rdkit import Chem
from rdkit.Chem import AllChem
mol = Chem.AddHs(Chem.MolFromSmiles("CCCC"))
params = AllChem.ETKDGv3(); params.randomSeed = 42
AllChem.EmbedMolecule(mol, params); AllChem.MMFFOptimizeMolecule(mol)
conf = mol.GetConformer()
lines = [str(mol.GetNumAtoms()), "butane CCCC"]
for a in mol.GetAtoms():
    p = conf.GetAtomPosition(a.GetIdx())
    lines.append(f"{a.GetSymbol():2s} {p.x:14.8f} {p.y:14.8f} {p.z:14.8f}")
Path("butane.xyz").write_text("\n".join(lines) + "\n")
PY

# Run CREST 3.0.2 with explicit external xTB path and legacy flags:
crest butane.xyz --gfn2 --legacy --xnam "$(which xtb)" --nocross -T 2 --quick > crest_butane.out 2>&1
```

Parse `crest_conformers.xyz` to extract rotational constants, inertial defects, $\Delta E$, and Boltzmann populations (`g=1` and `g=2` degeneracy for enantiomeric *gauche*+ / *gauche*−):

```bash
python - <<'PY'
import json, math
from pathlib import Path
import numpy as np
from cochem_base.spectroscopy.isotopologue import IsotopologueSpectroscopyEngine

lines = Path("crest_conformers.xyz").read_text().splitlines()
idx, confs = 0, []
while idx < len(lines):
    if not lines[idx].strip():
        idx += 1; continue
    n = int(lines[idx].strip())
    energy = float(lines[idx+1].strip().split()[0])
    syms, coords = [], []
    for l in lines[idx+2:idx+2+n]:
        p = l.split()
        syms.append(p[0]); coords.append([float(p[1]), float(p[2]), float(p[3])])
    obs = IsotopologueSpectroscopyEngine(syms, np.array(coords)).compute_observables()
    confs.append({
        "conformer_index": len(confs) + 1,
        "energy_eh": energy,
        "A_e_MHz": round(float(obs.A_e_MHz), 2),
        "B_e_MHz": round(float(obs.B_e_MHz), 2),
        "C_e_MHz": round(float(obs.C_e_MHz), 2),
        "inertial_defect_amu_A2": round(float(obs.inertial_defect_amu_A2), 4),
    })
    idx += 2 + n

e0 = confs[0]["energy_eh"]
RT = 2.47896  # kJ/mol at 298.15 K
for c in confs:
    c["delta_E_kj_mol"] = round((c["energy_eh"] - e0) * 2625.50, 3)

summary = {"conformers": confs}
if len(confs) >= 2:
    de = confs[1]["delta_E_kj_mol"]
    w_g1 = math.exp(-de / RT)
    summary["boltzmann_298K_g1_pct"] = {"anti": round(100 / (1 + w_g1), 1), "gauche": round(100 * w_g1 / (1 + w_g1), 1)}
    summary["boltzmann_298K_g2_pct"] = {"anti": round(100 / (1 + 2*w_g1), 1), "gauche": round(100 * 2*w_g1 / (1 + 2*w_g1), 1)}

Path("mod3_results.json").write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))
PY
cd ..
```

**Module 3 Verification Checks:**
- Conformer 1 (*anti*-butane): $A_e \approx 23,370$ MHz (window `22800–23600` MHz), $\Delta \approx -12.53\text{ amu}\cdot\text{\AA}^2$.
- Conformer 2 (*gauche*-butane): $A_e \approx 13,332$ MHz, $\Delta \approx -19.95\text{ amu}\cdot\text{\AA}^2$, $\Delta E \approx +2.52\text{ kJ/mol}$.
- Room-temperature Boltzmann population: ~`73.4% anti / 26.6% gauche` (`g=1`) or ~`58.0% anti / 42.0% gauche` (`g=2`).

---

## Module 4 — Bonding, Hybridization & Charge Polarization (`PySCF`)

**Learning Goal:** Compute quantum-mechanical Löwdin orthogonalized AO Wiberg bond indices and Löwdin partial atomic charges for **ethane (`CC`)**, **ethene (`C=C`)**, **ethyne (`C#C`)**, **formaldehyde (`C=O`)**, and **acetone (`CC(=O)C`)** at `RHF/def2-svp` (avoiding minimal `sto-3g` RHF instability on $\pi$-bonds).

```bash
mkdir -p mod4 && cd mod4
cat <<'PY' > run_mod4.py
import json, subprocess
from pathlib import Path
import numpy as np
import scipy.linalg
from rdkit import Chem
from rdkit.Chem import AllChem
from pyscf import gto, scf

molecules = [
    ("ethane", "CC", (0, 1)),
    ("ethene", "C=C", (0, 1)),
    ("ethyne", "C#C", (0, 1)),
    ("formaldehyde", "C=O", (0, 1)),
    ("acetone", "CC(=O)C", (1, 2)),
]

def lowdin_wiberg_and_charges(mol, dm):
    S = mol.intor("int1e_ovlp")
    S_half = scipy.linalg.fractional_matrix_power(S, 0.5).real
    P_orth = S_half @ dm @ S_half
    aoslices = mol.aoslice_by_atom()
    natm = mol.natm
    wiberg = np.zeros((natm, natm))
    charges = []
    for i in range(natm):
        p0, p1 = aoslices[i, 2], aoslices[i, 3]
        pop_i = float(np.trace(P_orth[p0:p1, p0:p1]))
        charges.append(round(float(mol.atom_charge(i) - pop_i), 4))
        for j in range(i + 1, natm):
            q0, q1 = aoslices[j, 2], aoslices[j, 3]
            block = P_orth[p0:p1, q0:q1]
            bo = float(np.sum(block * block))
            wiberg[i, j] = wiberg[j, i] = bo
    return wiberg, charges

results = {}
for name, smiles, (a1, a2) in molecules:
    wdir = Path(name); wdir.mkdir(exist_ok=True)
    rmol = Chem.AddHs(Chem.MolFromSmiles(smiles))
    params = AllChem.ETKDGv3(); params.randomSeed = 42
    AllChem.EmbedMolecule(rmol, params); AllChem.MMFFOptimizeMolecule(rmol)
    conf = rmol.GetConformer()
    lines = [str(rmol.GetNumAtoms()), smiles]
    for a in rmol.GetAtoms():
        p = conf.GetAtomPosition(a.GetIdx())
        lines.append(f"{a.GetSymbol():2s} {p.x:14.8f} {p.y:14.8f} {p.z:14.8f}")
    (wdir / "start.xyz").write_text("\n".join(lines) + "\n")
    subprocess.run(["xtb", "start.xyz", "--opt", "--gfn", "2"], cwd=wdir, capture_output=True, text=True, check=True)
    xlines = [l.strip() for l in (wdir / "xtbopt.xyz").read_text().splitlines() if l.strip()]
    n = int(xlines[0])
    atom_str = "\n".join(xlines[2:2+n])
    pmol = gto.M(atom=atom_str, basis="def2-svp", verbose=0)
    mf = scf.RHF(pmol).run()
    assert mf.converged, f"SCF failed for {name}"
    wiberg, charges = lowdin_wiberg_and_charges(pmol, mf.make_rdm1())
    syms = [pmol.atom_symbol(i) for i in range(pmol.natm)]
    results[name] = {
        "smiles": smiles,
        "method": "RHF/def2-svp (xTB-opt geom)",
        "energy_eh": round(float(mf.e_tot), 6),
        "target_bond": f"{syms[a1]}{a1+1}-{syms[a2]}{a2+1}",
        "target_wiberg_index": round(float(wiberg[a1, a2]), 4),
        "lowdin_charges_e": {f"{syms[i]}{i+1}": charges[i] for i in range(pmol.natm)},
    }

Path("mod4_results.json").write_text(json.dumps(results, indent=2))
print(json.dumps(results, indent=2))
PY
python run_mod4.py
cd ..
```

**Module 4 Verification Checks:**
- Ethane `C1-C2` ≈ `1.07` (window `1.01–1.12`); Ethene `C1=C2` ≈ `2.07`; Ethyne `C1≡C2` ≈ `3.05` (window `2.95–3.15`).
- Formaldehyde `C1=O2` ≈ `2.37` (`q_C1 ≈ +0.20 e`, `q_O2 ≈ -0.18 e`); Acetone `C2=O3` ≈ `2.27` (`q_C2 ≈ +0.14 to +0.15 e`, `q_O3 ≈ -0.22 to -0.25 e`).

---

## Module 5 — Vibrational Frequencies, Isotope Shifts & `SPCAT` Microwave Spectrum (Formaldehyde `C=O`)

**Learning Goal:** Compute the GFN2-xTB harmonic vibrational spectrum of formaldehyde (`C=O`), re-diagonalize the Cartesian Hessian for Parent, $^{13}\text{C}$, $^{18}\text{O}$, and $^{2}\text{H}$ isotopologues via `IsotopologueSpectroscopyEngine(..., cartesian_hessian=hess)`, and predict the microwave $J = 1_{01} \leftarrow 0_{00}$ rotational transition via `Pickett SPCAT`.

1. Optimize formaldehyde and compute its Cartesian Hessian (`--ohess`):

```bash
mkdir -p mod5 && cd mod5
python - <<'PY'
from pathlib import Path
from rdkit import Chem
from rdkit.Chem import AllChem
mol = Chem.AddHs(Chem.MolFromSmiles("C=O"))
params = AllChem.ETKDGv3(); params.randomSeed = 42
AllChem.EmbedMolecule(mol, params); AllChem.MMFFOptimizeMolecule(mol)
conf = mol.GetConformer()
lines = [str(mol.GetNumAtoms()), "formaldehyde C=O"]
for a in mol.GetAtoms():
    p = conf.GetAtomPosition(a.GetIdx())
    lines.append(f"{a.GetSymbol():2s} {p.x:14.8f} {p.y:14.8f} {p.z:14.8f}")
Path("h2co.xyz").write_text("\n".join(lines) + "\n")
PY

xtb h2co.xyz --gfn 2 --ohess > xtb_ohess.out 2>&1
```

2. Diagonalize `hessian` across all four isotopologues and generate the predicted microwave catalogs:

```bash
cat <<'PY' > run_mod5.py
import json, subprocess
from pathlib import Path
import numpy as np
from cochem_base.spectroscopy.isotopologue import IsotopologueSpectroscopyEngine

xlines = [l.strip() for l in Path("xtbopt.xyz").read_text().splitlines() if l.strip()]
n = int(xlines[0])
syms = [l.split()[0] for l in xlines[2:2+n]]
coords = np.array([[float(x) for x in l.split()[1:4]] for l in xlines[2:2+n]])

# Parse xTB Cartesian Hessian (Hartree / Bohr^2)
h_vals = []
for line in Path("hessian").read_text().splitlines():
    if line.strip().startswith("$") or not line.strip():
        continue
    h_vals.extend(float(x) for x in line.split())
hess = np.array(h_vals, dtype=float).reshape((3*n, 3*n))

eng = IsotopologueSpectroscopyEngine(syms, coords, cartesian_hessian=hess)

cases = [
    ("parent_H2_12C_16O", None),
    ("13C_H2_13C_16O", {0: "13C"}),
    ("18O_H2_12C_18O", {1: "18O"}),
    ("2H_HD_12C_16O", {2: "2H"}),
]
out = {}
for label, sub in cases:
    obs = eng.compute_observables(isotopic_substitution=sub)
    A = round(float(obs.A_e_MHz), 2)
    B = round(float(obs.B_e_MHz), 2)
    C = round(float(obs.C_e_MHz), 2)
    freqs = [round(float(f), 2) for f in (obs.harmonic_frequencies_cm1 or [])]
    out[label] = {
        "mass_amu": round(float(obs.total_mass_amu), 4),
        "A_e_MHz": A,
        "B_e_MHz": B,
        "C_e_MHz": C,
        "inertial_defect_amu_A2": round(float(obs.inertial_defect_amu_A2), 4),
        "J101_000_B_plus_C_MHz": round(B + C, 2),
        "harmonic_freqs_cm1": freqs,
    }

Path("mod5_isotopologues.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=2))

# Predict microwave spectrum via CoChem-BASE Pickett SPCAT runner (Parent & 13C)
for label in ("parent_H2_12C_16O", "13C_H2_13C_16O"):
    rec = out[label]
    subprocess.run([
        "python", "/mnt/d/__CoChem/GitHub-Repo/CoChem-BASE/scripts/spcat_runner.py",
        "--a-mhz", str(rec["A_e_MHz"]), "--b-mhz", str(rec["B_e_MHz"]), "--c-mhz", str(rec["C_e_MHz"]),
        "--mu-a", "2.587", "--temperature-k", "298.15",
        "--freq-min-ghz", "60.0", "--freq-max-ghz", "90.0",
        "--constant-type", "Be", "--allow-unvibrated-be",
        "--scratch-dir", f"spcat_{label}",
        "--output-json", f"spcat_{label}.json",
    ], check=True)
PY
python run_mod5.py
cd ..
```

**Module 5 Verification Checks:**
- Parent $\text{H}_2{}^{12}\text{C}{}^{16}\text{O}$: Mode 4 (C=O stretch) ≈ `1806.51 cm⁻¹` (window `1795–1818 cm⁻¹`), $A_e \approx 291,678$ MHz, $J = 1_{01} \leftarrow 0_{00}$ at $B_e + C_e \approx 74,159.55$ MHz.
- Heavy carbon $\text{H}_2{}^{13}\text{C}{}^{16}\text{O}$: Mode 4 shifts down by `-39.69 cm⁻¹` to ≈ `1766.82 cm⁻¹`; $\Delta A_e = 0.00$ MHz (C lies on the $a$-axis); $J = 1_{01} \leftarrow 0_{00}$ shifts down to `~72,327.15 MHz`.
- Heavy oxygen $\text{H}_2{}^{12}\text{C}{}^{18}\text{O}$: $\Delta A_e = 0.00$ MHz (O also lies on the $a$-axis).
- Monodeuterated $\text{HD}{}^{12}\text{C}{}^{16}\text{O}$: $A_e$ drops by ~30% (`-87,134 MHz` to `~204,543 MHz`) because H lies off the $a$-axis.

---

## Sealing Your `CHEM311` Handoff Bundle (`student/handoff.py`)

Package and self-verify your `cochem.student-handoff/2` archive natively with `course_id: "CHEM311"` before uploading to Canvas:

```bash
python /mnt/d/__CoChem/GitHub-Repo/CoChem-BASE/student/handoff.py seal \
  --source-dir ./mod3 \
  --manifest ./chem311_manifest.json \
  --output ./handoff_out
```

Verify any sealed bundle locally with pure Python stdlib:

```bash
python /mnt/d/__CoChem/GitHub-Repo/CoChem-BASE/student/handoff.py \
  handoff_out/CoChem-chem311-*.zip \
  --sidecar handoff_out/CoChem-chem311-*.zip.sha256 \
  --stage ./received
```
