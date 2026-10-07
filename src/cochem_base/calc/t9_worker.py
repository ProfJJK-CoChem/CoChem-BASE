"""Standalone PySCF worker; executed with -I in the configured micro-silo."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys


def main(input_path: Path) -> None:
    import pyscf
    from pyscf import gto, lib, mcscf, mrpt, scf

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    config = payload["configuration"]
    if sys.prefix == sys.base_prefix:
        raise RuntimeError("PySCF recovery requires an isolated micro-silo interpreter")
    if pyscf.__version__ != config["pyscf_version"]:
        raise RuntimeError(f"PySCF version drift: expected {config['pyscf_version']}, got {pyscf.__version__}")
    lib.num_threads(config["threads"])
    mol = gto.M(
        atom=list(zip(payload["elements"], payload["coordinates_angstrom"], strict=True)),
        unit="Angstrom", basis=config["basis"], charge=payload["charge"],
        spin=payload["multiplicity"] - 1, max_memory=config["memory_mb"], verbose=4,
    )
    reference = scf.ROHF(mol) if mol.spin else scf.RHF(mol)
    reference.conv_tol = 1e-10
    reference.max_cycle = config["max_cycle"]
    reference.kernel()
    if not reference.converged or not math.isfinite(float(reference.e_tot)):
        raise RuntimeError("T9 reference SCF did not converge")
    selected = config["active_orbitals"]
    if max(selected) >= reference.mo_coeff.shape[1]:
        raise ValueError("An active orbital index lies outside the computed MO space")
    nalpha = (config["active_electrons"] + mol.spin) // 2
    nbeta = config["active_electrons"] - nalpha
    calculation = mcscf.CASSCF(reference, len(selected), (nalpha, nbeta))
    calculation.conv_tol = 1e-9
    calculation.conv_tol_grad = 1e-6
    calculation.max_cycle_macro = config["max_cycle"]
    calculation.fcisolver.spin = mol.spin
    # The penalty selects the explicitly requested S state when equal M_S
    # admits multiple total spins. Acceptance still checks measured <S^2>.
    target_s2 = (mol.spin / 2) * (mol.spin / 2 + 1)
    calculation.fix_spin_(ss=target_s2)
    calculation.kernel(calculation.sort_mo(selected, base=0))
    if not calculation.converged or not math.isfinite(float(calculation.e_tot)):
        raise RuntimeError("T9 CASSCF did not converge")
    spin_square, observed_multiplicity = calculation.fcisolver.spin_square(
        calculation.ci, calculation.ncas, calculation.nelecas,
    )
    correction = float(mrpt.NEVPT(calculation).kernel()) if config["method"] == "NEVPT2" else None
    energy = float(calculation.e_tot) + (correction if correction is not None else 0)
    if any(not math.isfinite(float(value)) for value in (energy, spin_square, observed_multiplicity)):
        raise RuntimeError("T9 returned nonfinite electronic evidence")
    result = {
        "engine": "PySCF", "pyscf_version": pyscf.__version__, "method": config["method"],
        "basis": config["basis"], "scf_converged": bool(reference.converged),
        "casscf_converged": bool(calculation.converged),
        "energy_hartree": energy, "casscf_energy_hartree": float(calculation.e_tot),
        "nevpt2_correction_hartree": correction, "spin_square": float(spin_square),
        "observed_multiplicity": float(observed_multiplicity),
        "active_electrons": config["active_electrons"], "active_orbitals": selected,
        "orbital_index_reference": "zero-based converged ROHF/RHF molecular orbitals",
        "charge": mol.charge, "multiplicity": payload["multiplicity"],
        "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "micro_silo": sys.prefix,
    }
    input_path.with_name("t9_result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
