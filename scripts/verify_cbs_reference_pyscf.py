#!/usr/bin/env python3
"""Independently recompute a generated H2 reference with isolated real PySCF.

Run using the audited PySCF silo interpreter. Agreement checks cross-engine
canonical CCSD(T) energies at the generated geometry, not experimental accuracy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run(reference_path: Path, output: Path) -> dict:
    import pyscf
    from pyscf import cc, gto, lib, scf

    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    if reference.get("schema_version") != "cochem.bounded-cbs-reference/1" or reference.get("status") != "passed":
        raise ValueError("A completed physical H2 reference generation report is required")
    output = output.expanduser().resolve()
    checkout = Path(__file__).resolve().parents[1]
    if output.is_relative_to(checkout):
        raise ValueError("Acceptance artifacts must remain outside the source checkout")
    if output.exists():
        raise FileExistsError("Prior independent reference evidence cannot be overwritten")
    output.parent.mkdir(parents=True, exist_ok=True)
    work = output.parent / (output.stem + "-work")
    work.mkdir(exist_ok=False)
    distance = reference["distance_angstrom"]
    if not math.isfinite(distance) or not 0.65 < distance < 0.85:
        raise ValueError("Reference is outside the bounded H2 geometry domain")
    lib.num_threads(1)
    report = {"status": "failed", "engine": "PySCF", "version": pyscf.__version__,
              "reference_path": str(reference_path.resolve()), "reference_sha256": digest(reference_path),
              "script_sha256": digest(Path(__file__)), "interpreter": sys.executable,
              "work_directory": str(work),
              "distance_angstrom": distance, "threads": 1, "basis_checks": {},
              "energy_agreement_tolerance_hartree": 1e-7,
              "experimental_accuracy_established": False}
    started = time.monotonic()
    try:
        for basis in ("cc-pVTZ", "cc-pVQZ"):
            physical = reference["minimum"]["basis_results"][basis]
            if digest(Path(physical["output_path"])) != physical["output_sha256"]:
                raise ValueError("Source ORCA reference changed before independent verification")
            log = work / f"pyscf-{basis}.log"
            molecule = gto.M(atom=[("H", (0., 0., -distance / 2)), ("H", (0., 0., distance / 2))],
                             basis=basis, unit="Angstrom", charge=0, spin=0, verbose=4,
                             output=str(log))
            mean_field = scf.RHF(molecule)
            mean_field.conv_tol = 1e-12
            mean_field.max_cycle = 100
            mean_field.kernel()
            if not mean_field.converged:
                raise RuntimeError("Independent PySCF RHF reference did not converge")
            correlated = cc.CCSD(mean_field)
            correlated.conv_tol = 1e-12
            correlated.conv_tol_normt = 1e-10
            correlated.max_cycle = 100
            correlated.kernel()
            if not correlated.converged:
                raise RuntimeError("Independent PySCF CCSD reference did not converge")
            triples = float(correlated.ccsd_t())
            energy = float(correlated.e_tot) + triples
            difference = abs(energy - physical["ccsdt_energy_hartree"])
            molecule.stdout.flush()
            report["basis_checks"][basis] = {
                "scf_converged": True, "ccsd_converged": True,
                "scf_energy_hartree": float(mean_field.e_tot),
                "triples_correction_hartree": triples, "ccsdt_energy_hartree": energy,
                "orca_ccsdt_energy_hartree": physical["ccsdt_energy_hartree"],
                "difference_hartree": difference,
                "output_path": str(log), "output_sha256": digest(log),
            }
            if not math.isfinite(energy) or difference > report["energy_agreement_tolerance_hartree"]:
                raise RuntimeError("Independent PySCF and ORCA reference energies disagree")
        report["status"] = "passed"
        return report
    except Exception as error:
        report.update(error=str(error), error_type=type(error).__name__)
        raise
    finally:
        report["elapsed_seconds"] = time.monotonic() - started
        output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.reference, args.output)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
