"""Isolated MACE-OFF24 medium CPU evaluation worker (no base-process ML imports)."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path


def evaluate(request: dict) -> dict:
    import numpy as np
    import torch
    from ase import Atoms
    from mace.calculators import MACECalculator
    from scipy.constants import physical_constants

    torch.set_num_threads(request["cores"])
    model = Path(request["checkpoint"])
    with model.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != request["checkpoint_sha256"]:
        raise ValueError("Checkpoint changed after authorization")
    calculator = MACECalculator(model_paths=str(model), device="cpu", default_dtype="float64")
    atoms = Atoms(request["elements"], positions=request["coordinates_angstrom"])
    allowed = set(int(number) for number in calculator.models[0].atomic_numbers.tolist())
    if not set(atoms.numbers).issubset(allowed):
        return {"status": "UNSUPPORTED_DOMAIN", "error": "Elements outside this checkpoint's training domain"}
    atoms.calc = calculator
    energy_ev = float(atoms.get_potential_energy())
    forces = np.asarray(atoms.get_forces(), dtype=float)
    if not np.isfinite(energy_ev) or forces.shape != (len(atoms), 3) or not np.isfinite(forces).all():
        return {"status": "ENGINE_FAILURE", "error": "MACE returned incomplete or nonfinite energy/forces"}
    eh_ev = physical_constants["Hartree energy in eV"][0]
    bohr_angstrom = physical_constants["Bohr radius"][0] * 1e10
    return {
        "status": "SUCCESS", "energy_hartree": energy_ev / eh_ev,
        "gradient_hartree_per_bohr": (-forces * bohr_angstrom / eh_ev).tolist(),
        "checkpoint_sha256": digest,
        "versions": {name: importlib.metadata.version(name) for name in ("mace-torch", "torch", "ase")},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path)
    parser.add_argument("result", type=Path)
    args = parser.parse_args()
    try:
        result = evaluate(json.loads(args.request.read_text(encoding="utf-8")))
    except (ImportError, FileNotFoundError) as exc:
        result = {"status": "UNAVAILABLE", "error": str(exc), "exception_type": type(exc).__name__}
    except RuntimeError as exc:
        result = {"status": "ENGINE_FAILURE", "error": str(exc), "exception_type": type(exc).__name__}
    # Unanticipated programming/serialization errors retain a nonzero process
    # traceback and cannot masquerade as a supported scientific fallback trigger.
    args.result.write_text(json.dumps(result, allow_nan=False, indent=2), encoding="utf-8")
    return 0 if result["status"] == "SUCCESS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
