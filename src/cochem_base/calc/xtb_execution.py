"""Native xTB screening operations with explicit scientific output checks."""
from __future__ import annotations

import json
import math
from pathlib import Path
import re
from typing import Any, Sequence

from cochem_base.physics.isotopes import get_element_mass_and_abundance


def validate_xtb_config(config: Any, elements: Sequence[str]) -> list[str]:
    """Return a fixed argument list; unsupported methodology never disappears."""
    methods = {"GFN2-XTB": ("T1", ["--gfn", "2"]), "GFN-FF": ("T0", ["--gfnff"])}
    method = config.method.strip().upper()
    if method not in methods:
        raise ValueError("The xTB adapter supports GFN2-xTB and GFN-FF screening only")
    tier, arguments = methods[method]
    if config.basis_set and config.basis_set.lower() not in {"built-in", "default"}:
        raise ValueError("xTB uses a built-in basis; an external basis cannot be requested")
    if config.theory_tier and "T" + config.theory_tier.upper().removeprefix("T") != tier:
        raise ValueError(f"{config.method} requires canonical tier {tier}")
    unsupported = (
        config.product_class or config.is_freq or config.is_vpt2 or config.recipe
        or config.grid_stage is not None or config.implicit_solvation
        or config.frozen_monomer_indices is not None or config.hessian_file
        or config.cbs_cardinal_pair or config.initial_hessian != "XTB2"
        or config.ab_initio_relaxed
    )
    if unsupported:
        raise ValueError("The xTB screening adapter does not support product certification, frequencies, "
                         "VPT2, recipes, grids, solvation, constraints or Hessian reuse")
    # These methods expose unpaired-electron input but not the S² evidence
    # required by the project's open-shell acceptance gate.
    if config.multiplicity != 1:
        raise ValueError("Open-shell xTB acceptance requires spin evidence unavailable in this adapter")
    electrons = sum(get_element_mass_and_abundance(symbol)[2] for symbol in elements) - config.charge
    if electrons < 0 or electrons % 2:
        raise ValueError("Spin multiplicity is incompatible with the electron count and charge")
    arguments = [*arguments, "--chrg", str(config.charge), "--uhf", "0"]
    if config.is_opt:
        arguments.extend(["--opt", "tight"])
    return arguments


def write_xtb_input(directory: Path, elements: Sequence[str], coordinates: Sequence[Sequence[float]]) -> Path:
    path = directory / "input.xyz"
    lines = [str(len(elements)), "CoChem xTB screening input"]
    lines.extend(f"{symbol} " + " ".join(format(value, ".17g") for value in xyz)
                 for symbol, xyz in zip(elements, coordinates, strict=True))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def accept_xtb_result(result: Any, directory: Path, config: Any, elements: Sequence[str], parse_geometry: Any) -> dict:
    """Require normal termination, measured energy and requested convergence."""
    stdout, stderr = result.stdout or "", result.stderr or ""
    (directory / "xtb.out").write_text(stdout, encoding="utf-8")
    (directory / "stderr.log").write_text(stderr, encoding="utf-8")
    combined = stdout + "\n" + stderr
    if result.returncode != 0 or "normal termination of xtb" not in combined.lower():
        raise RuntimeError(f"xTB did not terminate normally (exit {result.returncode}); diagnostics in {directory}")
    if config.method.strip().upper() == "GFN2-XTB" and not re.search(r"convergence criteria satisfied after \d+ iterations", stdout, re.I):
        raise RuntimeError("xTB did not provide SCC convergence evidence")
    if config.is_opt and not re.search(r"GEOMETRY OPTIMIZATION CONVERGED AFTER \d+ ITERATIONS", stdout):
        raise RuntimeError("xTB geometry optimization did not converge")
    matches = re.findall(r"\|\s*TOTAL ENERGY\s+([^\s]+)\s+Eh\s*\|", stdout)
    if not matches:
        raise RuntimeError("xTB output has no final energy in Hartree")
    energy = float(matches[-1].replace("D", "E").replace("d", "e"))
    if not math.isfinite(energy):
        raise RuntimeError("xTB returned a nonfinite final energy")
    geometry_path = directory / ("xtbopt.xyz" if config.is_opt else "input.xyz")
    output_elements, coordinates = parse_geometry(geometry_path.read_text(encoding="utf-8"))
    if list(elements) != output_elements:
        raise RuntimeError("xTB output geometry does not match the input atoms")
    payload = {
        "engine": "xtb", "method": config.method, "scope": "screening",
        "energy_hartree": energy, "converged": True,
        "optimization_converged": True if config.is_opt else None,
        "elements": output_elements, "coordinates_angstrom": coordinates,
        "charge": config.charge, "multiplicity": config.multiplicity,
    }
    (directory / "result.json").write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")
    return payload
