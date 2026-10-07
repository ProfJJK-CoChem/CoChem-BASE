"""Acceptance of measured restricted-HF results from the isolated PySCF worker."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np


def accept_pyscf_result(result: Any, directory: Path, deck: Path, config: Any, elements: list, coordinates: list) -> dict:
    (directory / "pyscf.out").write_text(result.stdout or "", encoding="utf-8")
    (directory / "stderr.log").write_text(result.stderr or "", encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"PySCF failed with exit code {result.returncode}; diagnostics retained in {directory}")
    payload = json.loads(deck.with_suffix(".result.json").read_text(encoding="utf-8"))
    if payload.get("scf_converged") is not True or payload.get("method") != "RHF":
        raise RuntimeError("PySCF lacks explicit restricted-HF convergence evidence")
    if payload.get("basis") != config.basis_set or payload.get("version") != config.pyscf_version:
        raise RuntimeError("PySCF output basis or version contradicts the requested calculation")
    if payload.get("input_sha256") != hashlib.sha256(deck.read_bytes()).hexdigest():
        raise RuntimeError("PySCF result does not belong to the submitted input")
    energy = payload.get("energy_hartree")
    gradients = np.asarray(payload.get("gradients_hartree_per_bohr"), dtype=float)
    if isinstance(energy, bool) or not isinstance(energy, (int, float)) or not math.isfinite(energy):
        raise RuntimeError("PySCF returned no finite electronic energy")
    if gradients.shape != (len(elements), 3) or not np.isfinite(gradients).all():
        raise RuntimeError("PySCF returned no finite complete nuclear gradient")
    payload.update(engine="pyscf", method="RHF", elements=elements, coordinates_angstrom=coordinates,
                   charge=config.charge, multiplicity=config.multiplicity, converged=True)
    return payload
