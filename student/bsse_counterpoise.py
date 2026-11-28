#!/usr/bin/env python3
"""Local pure-PySCF Boys-Bernardi counterpoise BSSE CLI for 1:1 non-covalent complexes.

Computes exact 5-point Boys-Bernardi counterpoise binding energetics locally on CPU:
  - E_AB(AB): full dimer in dimer-centered basis set (DCBS)
  - E_A(A), E_B(B): monomer A and monomer B in monomer-centered basis sets (MCBS)
  - E_A(AB), E_B(AB): monomer A and monomer B with partner ghost basis functions (DCBS)
  - Delta E_raw = E_AB(AB) - E_A(A) - E_B(B)
  - Delta E_CP  = E_AB(AB) - E_A(AB) - E_B(AB)
  - BSSE        = Delta E_CP - Delta E_raw

Output JSON is 100% schema-compatible with `scripts/vdw_titration_diff.py` and
the historical `04_crest_nci_dimer_bsse.yml` `bsse_counterpoise.json` contract.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, Mapping, Sequence

try:
    from .handoff import (
        V2_ALLOWED_CHARGES,
        V2_ALLOWED_ELEMENTS,
        V2_ALLOWED_MULTIPLICITIES,
        V2_ALLOWED_SOLVATIONS,
        parse_xyz_frames,
    )
    from .starter_inputs import resolve_or_materialize_input
except ImportError:
    from handoff import (  # type: ignore[no-redef]
        V2_ALLOWED_CHARGES,
        V2_ALLOWED_ELEMENTS,
        V2_ALLOWED_MULTIPLICITIES,
        V2_ALLOWED_SOLVATIONS,
        parse_xyz_frames,
    )
    from starter_inputs import resolve_or_materialize_input  # type: ignore[no-redef]

HARTREE_TO_KCAL_MOL = 627.5094740631
HARTREE_TO_KJ_MOL = 2625.4996394799
_DLPNO_RE = re.compile(r"dlpno", re.IGNORECASE)

SUPPORTED_BSSE_METHODS: dict[str, dict[str, Any]] = {
    "rhf": {"label": "RHF", "kind": "hf", "xc": None, "dispersion": None},
    "uhf": {"label": "UHF", "kind": "hf", "xc": None, "dispersion": None},
    "b3lyp": {"label": "B3LYP", "kind": "dft", "xc": "b3lypg", "dispersion": None},
    "b3lyp-d3bj": {"label": "B3LYP-D3BJ", "kind": "dft", "xc": "b3lypg", "dispersion": "d3bj"},
    "b3lyp-d3": {"label": "B3LYP-D3BJ", "kind": "dft", "xc": "b3lypg", "dispersion": "d3bj"},
    "pbe-d3bj": {"label": "PBE-D3BJ", "kind": "dft", "xc": "pbe", "dispersion": "d3bj"},
    "wb97x-d3": {"label": "wB97X-D3", "kind": "dft", "xc": "wb97x", "dispersion": "d3zero"},
    "df-wb97x-d3": {"label": "DF-wB97X-D3", "kind": "dft", "xc": "wb97x", "dispersion": "d3zero"},
    "wb97x-v": {"label": "wB97X-V", "kind": "dft", "xc": "wb97x_v", "dispersion": None},
}

SUPPORTED_BSSE_BASIS_SETS: dict[str, str] = {
    "sto-3g": "STO-3G",
    "def2-svp": "def2-SVP",
    "def2-tzvp": "def2-TZVP",
    "def2-tzvpp": "def2-TZVPP",
    "cc-pvdz": "cc-pVDZ",
    "cc-pvtz": "cc-pVTZ",
    "aug-cc-pvdz": "aug-cc-pVDZ",
    "aug-cc-pvtz": "aug-cc-pVTZ",
}

SOLVENT_DIELECTRICS: dict[str, float] = {
    "water": 78.3553,
    "acetonitrile": 35.688,
    "dmso": 46.826,
    "methanol": 32.613,
    "ethanol": 24.852,
    "dichloromethane": 8.93,
    "chloroform": 4.7113,
    "thf": 7.4257,
    "toluene": 2.3741,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize_bsse_method_and_basis(method: str, basis: str) -> tuple[dict[str, Any], str]:
    """Validate and normalize PySCF method and basis set (strictly rejecting DLPNO)."""
    raw_method = str(method or "").strip()
    if _DLPNO_RE.search(raw_method):
        raise ValueError(
            f"Method {raw_method!r} is forbidden under Pipeline 5.0.0 DLPNOExclusionFirewall (DLPNO_EXCLUDED)."
        )
    method_key = raw_method.lower()
    if method_key not in SUPPORTED_BSSE_METHODS:
        supported = sorted({v["label"] for v in SUPPORTED_BSSE_METHODS.values()})
        raise ValueError(f"Unsupported BSSE method {method!r}; supported: {supported}")

    basis_key = str(basis or "").strip().lower()
    if basis_key not in SUPPORTED_BSSE_BASIS_SETS:
        raise ValueError(
            f"Unsupported BSSE basis set {basis!r}; supported: {list(SUPPORTED_BSSE_BASIS_SETS.values())}"
        )
    return SUPPORTED_BSSE_METHODS[method_key], SUPPORTED_BSSE_BASIS_SETS[basis_key]


def parse_atom_selection(spec: str, n_atoms: int) -> list[int]:
    """Parse 1-based atom selection like `'1-5'`, `'1,2,3'`, or `'1-3,7-8'` into sorted 0-based indices."""
    cleaned = str(spec or "").strip()
    if not cleaned:
        raise ValueError("Atom selection cannot be empty")
    indices: list[int] = []
    seen: set[int] = set()
    for token in cleaned.split(","):
        part = token.strip()
        if not part:
            continue
        if ".." in part:
            lo_s, hi_s = part.split("..", 1)
            lo, hi = int(lo_s.strip()), int(hi_s.strip())
            if lo > hi:
                raise ValueError(f"Descending atom range {part!r} is invalid")
            span = range(lo, hi + 1)
        elif "-" in part:
            lo_s, hi_s = part.split("-", 1)
            lo, hi = int(lo_s.strip()), int(hi_s.strip())
            if lo > hi:
                raise ValueError(f"Descending atom range {part!r} is invalid")
            span = range(lo, hi + 1)
        else:
            val = int(part)
            span = range(val, val + 1)
        for one_based in span:
            if not (1 <= one_based <= n_atoms):
                raise ValueError(
                    f"1-based atom index {one_based} is out of range 1..{n_atoms}"
                )
            zero_based = one_based - 1
            if zero_based in seen:
                raise ValueError(f"Duplicate 1-based atom index {one_based} in {spec!r}")
            seen.add(zero_based)
            indices.append(zero_based)
    if not indices:
        raise ValueError(f"No valid atom indices parsed from {spec!r}")
    return indices


def resolve_fragment_partition(
    n_atoms: int,
    *,
    frag_a_atoms: str | None = None,
    frag_b_atoms: str | None = None,
    monomer_a_atoms: int | None = None,
) -> tuple[list[int], list[int]]:
    """Resolve and validate a disjoint, complete partition of `0..n_atoms-1` into (frag_a, frag_b)."""
    if n_atoms < 2:
        raise ValueError(f"Dimer must contain at least 2 atoms, got {n_atoms}")

    if monomer_a_atoms is not None:
        if frag_a_atoms is not None or frag_b_atoms is not None:
            raise ValueError("Use either --monomer-a-atoms or --frag-a-atoms/--frag-b-atoms, not both")
        if not (1 <= monomer_a_atoms < n_atoms):
            raise ValueError(f"monomer_a_atoms ({monomer_a_atoms}) must be between 1 and {n_atoms - 1}")
        return list(range(monomer_a_atoms)), list(range(monomer_a_atoms, n_atoms))

    if frag_a_atoms is None:
        raise ValueError("Specify --frag-a-atoms (e.g. '1-5') or --monomer-a-atoms")

    idx_a = parse_atom_selection(frag_a_atoms, n_atoms)
    if frag_b_atoms is not None:
        idx_b = parse_atom_selection(frag_b_atoms, n_atoms)
    else:
        set_a = set(idx_a)
        idx_b = [i for i in range(n_atoms) if i not in set_a]

    if not idx_a or not idx_b:
        raise ValueError("Both fragment A and fragment B must be non-empty")
    overlap = set(idx_a) & set(idx_b)
    if overlap:
        raise ValueError(
            f"Fragments A and B overlap at 1-based atom(s): {sorted(i + 1 for i in overlap)}"
        )
    union = set(idx_a) | set(idx_b)
    if union != set(range(n_atoms)):
        missing = sorted(i + 1 for i in (set(range(n_atoms)) - union))
        raise ValueError(
            f"Fragments A and B must cover all {n_atoms} atoms; missing 1-based atom(s): {missing}"
        )
    return idx_a, idx_b


def _check_fragment_parity(symbols: Sequence[str], charge: int, multiplicity: int, label: str) -> None:
    if charge not in V2_ALLOWED_CHARGES:
        raise ValueError(f"Unsupported {label} charge {charge}; expected one of {V2_ALLOWED_CHARGES}")
    if multiplicity not in V2_ALLOWED_MULTIPLICITIES:
        raise ValueError(
            f"Unsupported {label} multiplicity {multiplicity}; expected one of {V2_ALLOWED_MULTIPLICITIES}"
        )
    n_electrons = sum(V2_ALLOWED_ELEMENTS[s] for s in symbols) - charge
    unpaired = multiplicity - 1
    if n_electrons < 1 or n_electrons < unpaired or (n_electrons % 2) != (unpaired % 2):
        raise ValueError(
            f"Electron count {n_electrons} for {label} is incompatible with "
            f"charge={charge}, multiplicity={multiplicity}"
        )


def _apply_solvation(mf: Any, solvation: str, solvent_name: str | None) -> Any:
    if solvation == "gas":
        return mf
    eps_key = (solvent_name or "water").strip().lower()
    if eps_key not in SOLVENT_DIELECTRICS:
        raise ValueError(
            f"Unsupported solvent_name {solvent_name!r}; supported: {sorted(SOLVENT_DIELECTRICS)}"
        )
    eps = SOLVENT_DIELECTRICS[eps_key]
    if solvation == "pcm":
        mf = mf.PCM()
        mf.with_solvent.method = "IEF-PCM"
        mf.with_solvent.eps = eps
        return mf
    if solvation == "ddcosmo":
        mf = mf.DDCOSMO()
        mf.with_solvent.eps = eps
        return mf
    raise ValueError(f"Unsupported solvation {solvation!r}")


def _build_pyscf_mf(
    mol: Any,
    method_spec: Mapping[str, Any],
    *,
    solvation: str,
    solvent_name: str | None,
) -> Any:
    from pyscf import dft, scf

    unrestricted = mol.spin != 0 or method_spec["label"] == "UHF"
    if method_spec["kind"] == "hf":
        mf = scf.UHF(mol) if unrestricted else scf.RHF(mol)
    else:
        mf = (dft.UKS(mol) if unrestricted else dft.RKS(mol)).density_fit()
        mf.xc = method_spec["xc"]
        if method_spec["dispersion"]:
            mf.disp = method_spec["dispersion"]
    mf = _apply_solvation(mf, solvation, solvent_name)
    mf.conv_tol = 1e-9
    return mf


def run_counterpoise_bsse(
    dimer_xyz: str | Path,
    *,
    frag_a_atoms: str | None = None,
    frag_b_atoms: str | None = None,
    monomer_a_atoms: int | None = None,
    method: str = "B3LYP-D3BJ",
    basis: str = "def2-SVP",
    charge: int = 0,
    multiplicity: int = 1,
    frag_a_charge: int = 0,
    frag_b_charge: int | None = None,
    frag_a_multiplicity: int = 1,
    frag_b_multiplicity: int = 1,
    solvation: str = "gas",
    solvent_name: str | None = None,
    cores: int = 2,
) -> dict[str, Any]:
    """Run authentic PySCF 5-point Boys-Bernardi counterpoise BSSE calculation on CPU."""
    method_spec, basis_label = normalize_bsse_method_and_basis(method, basis)
    if solvation not in V2_ALLOWED_SOLVATIONS:
        raise ValueError(f"Unsupported solvation {solvation!r}; expected one of {V2_ALLOWED_SOLVATIONS}")

    qb = (charge - frag_a_charge) if frag_b_charge is None else frag_b_charge
    if frag_a_charge + qb != charge:
        raise ValueError(
            f"frag_a_charge ({frag_a_charge}) + frag_b_charge ({qb}) must equal total charge ({charge})"
        )

    with tempfile.TemporaryDirectory(prefix="cochem_bsse_input_") as tmp_dir:
        xyz_path = resolve_or_materialize_input(dimer_xyz, materialize_dir=tmp_dir)
        xyz_sha = _sha256_file(xyz_path)
        xyz_text = xyz_path.read_text(encoding="utf-8")
        dimer_name = xyz_path.name

    parsed = parse_xyz_frames(
        xyz_text,
        allowed_elements=V2_ALLOWED_ELEMENTS,
        charge=charge,
        multiplicity=multiplicity,
        require_energy=False,
    )
    if len(parsed) != 1:
        raise ValueError(f"Expected a single-frame dimer XYZ in {dimer_xyz!r}, got {len(parsed)} frames")
    frame = parsed[0]

    idx_a, idx_b = resolve_fragment_partition(
        frame.n_atoms,
        frag_a_atoms=frag_a_atoms,
        frag_b_atoms=frag_b_atoms,
        monomer_a_atoms=monomer_a_atoms,
    )

    symbols_a = [frame.symbols[i] for i in idx_a]
    symbols_b = [frame.symbols[i] for i in idx_b]
    _check_fragment_parity(symbols_a, frag_a_charge, frag_a_multiplicity, "fragment A")
    _check_fragment_parity(symbols_b, qb, frag_b_multiplicity, "fragment B")

    import pyscf
    from pyscf import gto, lib

    lib.num_threads(max(1, int(cores)))
    atoms_all = list(zip(frame.symbols, frame.coords))
    atoms_a = [(frame.symbols[i], frame.coords[i]) for i in idx_a]
    atoms_b = [(frame.symbols[i], frame.coords[i]) for i in idx_b]
    ghost_a = [(f"X-{s}", c) for s, c in atoms_a]
    ghost_b = [(f"X-{s}", c) for s, c in atoms_b]

    eff_solvent = solvent_name if solvation != "gas" else None

    def _sp_energy(atom_list: list[tuple[str, list[float]]], q: int, mult: int, label: str) -> float:
        mol = gto.M(
            atom=atom_list,
            unit="Angstrom",
            basis=basis_label,
            charge=int(q),
            spin=int(mult) - 1,
            verbose=0,
        )
        mf = _build_pyscf_mf(mol, method_spec, solvation=solvation, solvent_name=eff_solvent)
        energy = float(mf.kernel())
        if not mf.converged or not math.isfinite(energy):
            raise RuntimeError(
                f"PySCF SCF failed to converge for {label} ({method_spec['label']}/{basis_label})"
            )
        return energy

    e_ab = _sp_energy(atoms_all, charge, multiplicity, "dimer AB(AB)")
    e_a_mon = _sp_energy(atoms_a, frag_a_charge, frag_a_multiplicity, "monomer A(A)")
    e_b_mon = _sp_energy(atoms_b, qb, frag_b_multiplicity, "monomer B(B)")
    e_a_dcbs = _sp_energy(atoms_a + ghost_b, frag_a_charge, frag_a_multiplicity, "monomer A(AB) DCBS")
    e_b_dcbs = _sp_energy(ghost_a + atoms_b, qb, frag_b_multiplicity, "monomer B(AB) DCBS")

    delta_e_raw_eh = e_ab - (e_a_mon + e_b_mon)
    delta_e_cp_eh = e_ab - (e_a_dcbs + e_b_dcbs)
    bsse_eh = delta_e_cp_eh - delta_e_raw_eh

    return {
        "schema": "cochem.bsse-counterpoise/1",
        "status": "COMPUTED",
        "created_at_utc": _utc_now(),
        "engine": "PySCF",
        "pyscf_version": getattr(pyscf, "__version__", "unknown"),
        "dimer_xyz": dimer_name,
        "dimer_xyz_sha256": xyz_sha,
        "formula": frame.formula,
        "n_atoms": frame.n_atoms,
        "frag_a_indices_1based": [i + 1 for i in idx_a],
        "frag_b_indices_1based": [i + 1 for i in idx_b],
        "charge": int(charge),
        "multiplicity": int(multiplicity),
        "frag_a_charge": int(frag_a_charge),
        "frag_b_charge": int(qb),
        "frag_a_multiplicity": int(frag_a_multiplicity),
        "frag_b_multiplicity": int(frag_b_multiplicity),
        "method": method_spec["label"],
        "basis": basis_label,
        "solvation": solvation,
        "solvent_name": eff_solvent,
        "e_dimer_hartree": e_ab,
        "e_monomer_a_hartree": e_a_mon,
        "e_monomer_b_hartree": e_b_mon,
        "e_monomer_a_dcbs_hartree": e_a_dcbs,
        "e_monomer_b_dcbs_hartree": e_b_dcbs,
        "delta_e_raw_hartree": delta_e_raw_eh,
        "delta_e_cp_hartree": delta_e_cp_eh,
        "bsse_hartree": bsse_eh,
        "e_int_raw_kcal_mol": delta_e_raw_eh * HARTREE_TO_KCAL_MOL,
        "e_int_counterpoise_kcal_mol": delta_e_cp_eh * HARTREE_TO_KCAL_MOL,
        "bsse_correction_kcal_mol": bsse_eh * HARTREE_TO_KCAL_MOL,
        "delta_e_raw_kcal_mol": delta_e_raw_eh * HARTREE_TO_KCAL_MOL,
        "delta_e_cp_kcal_mol": delta_e_cp_eh * HARTREE_TO_KCAL_MOL,
        "bsse_kcal_mol": bsse_eh * HARTREE_TO_KCAL_MOL,
        "delta_e_raw_kj_mol": delta_e_raw_eh * HARTREE_TO_KJ_MOL,
        "delta_e_cp_kj_mol": delta_e_cp_eh * HARTREE_TO_KJ_MOL,
        "bsse_kj_mol": bsse_eh * HARTREE_TO_KJ_MOL,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bsse_counterpoise.py",
        description=(
            "Compute local CPU PySCF Boys-Bernardi counterpoise BSSE (Delta E_raw, BSSE, Delta E_CP) "
            "and emit bsse_counterpoise.json compatible with scripts/vdw_titration_diff.py."
        ),
    )
    parser.add_argument(
        "--dimer-xyz",
        required=True,
        help="Path to dimer .xyz file (or starter name such as hcooh_water_dimer.xyz / water_dimer.xyz).",
    )
    parser.add_argument(
        "--frag-a-atoms",
        default=None,
        help="1-based atom indices/ranges for fragment A (e.g. '1-5' or '1,2,3').",
    )
    parser.add_argument(
        "--frag-b-atoms",
        default=None,
        help="1-based atom indices/ranges for fragment B (e.g. '6-8'; defaults to complement of fragment A).",
    )
    parser.add_argument(
        "--monomer-a-atoms",
        type=int,
        default=None,
        help="Alternative shorthand: leading N atoms form fragment A and remaining atoms form fragment B.",
    )
    parser.add_argument(
        "--method",
        default="B3LYP-D3BJ",
        help="PySCF method (default: B3LYP-D3BJ; supports RHF, UHF, B3LYP, B3LYP-D3BJ, PBE-D3BJ, wB97X-D3, DF-wB97X-D3).",
    )
    parser.add_argument(
        "--basis",
        default="def2-SVP",
        help="PySCF basis set (default: def2-SVP; supports STO-3G, def2-SVP, def2-TZVP, def2-TZVPP, cc-pVDZ, cc-pVTZ).",
    )
    parser.add_argument("--charge", type=int, default=0, choices=list(V2_ALLOWED_CHARGES))
    parser.add_argument("--multiplicity", type=int, default=1, choices=list(V2_ALLOWED_MULTIPLICITIES))
    parser.add_argument("--frag-a-charge", type=int, default=0, choices=list(V2_ALLOWED_CHARGES))
    parser.add_argument("--frag-b-charge", type=int, default=None, choices=list(V2_ALLOWED_CHARGES))
    parser.add_argument("--frag-a-multiplicity", type=int, default=1, choices=list(V2_ALLOWED_MULTIPLICITIES))
    parser.add_argument("--frag-b-multiplicity", type=int, default=1, choices=list(V2_ALLOWED_MULTIPLICITIES))
    parser.add_argument("--solvation", default="gas", choices=list(V2_ALLOWED_SOLVATIONS))
    parser.add_argument("--solvent-name", default=None)
    parser.add_argument("--cores", type=int, default=2)
    parser.add_argument(
        "--out",
        "--output-json",
        dest="out",
        type=Path,
        default=None,
        help="Output path for bsse_counterpoise.json.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        result = run_counterpoise_bsse(
            args.dimer_xyz,
            frag_a_atoms=args.frag_a_atoms,
            frag_b_atoms=args.frag_b_atoms,
            monomer_a_atoms=args.monomer_a_atoms,
            method=args.method,
            basis=args.basis,
            charge=args.charge,
            multiplicity=args.multiplicity,
            frag_a_charge=args.frag_a_charge,
            frag_b_charge=args.frag_b_charge,
            frag_a_multiplicity=args.frag_a_multiplicity,
            frag_b_multiplicity=args.frag_b_multiplicity,
            solvation=args.solvation,
            solvent_name=args.solvent_name,
            cores=args.cores,
        )
        encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
        if args.out is not None:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(encoded, encoding="utf-8", newline="\n")
        print(encoded, end="")
        return 0
    except (ValueError, RuntimeError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
