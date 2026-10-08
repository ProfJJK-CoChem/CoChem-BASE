"""Accept real ORCA Cartesian derivatives bound to the completed calculation.

Native ORCA frequencies use the masses recorded in its Hessian. BASE separately
derives principal-isotopologue frequencies from the same Cartesian Hessian;
these two mass conventions must never be silently interchanged.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

import numpy as np


ENERGY_TOLERANCE_HARTREE = 1e-8
GEOMETRY_TOLERANCE_ANGSTROM = 1e-7
FREQUENCY_CONSISTENCY_TOLERANCE_CM1 = 0.2


def _artifact_record(path: Path, unit: str) -> dict[str, Any]:
    return {"filename": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "unit": unit}


def accept_gradient(
    path: Path, elements: list[str], coordinates_angstrom: Any,
    energy_hartree: float, *, required: bool,
) -> dict[str, Any]:
    """Reuse the geometry-bound ORCA engrad parser; never manufacture a gradient."""
    from cochem_base.calc.recipe_r2_execution import read_dimer_gradient

    if not path.is_file():
        if required:
            raise ValueError("The requested ORCA operation requires its final .engrad checkpoint")
        return {}
    energy, gradient = read_dimer_gradient(path, elements, np.asarray(coordinates_angstrom, dtype=float))
    if not math.isclose(energy, energy_hartree, abs_tol=ENERGY_TOLERANCE_HARTREE, rel_tol=0):
        raise ValueError("ORCA gradient checkpoint energy differs from the accepted electronic energy")
    return {"gradients_hartree_per_bohr": gradient.tolist(),
            "gradient_artifact": _artifact_record(path, "hartree/bohr")}


def _native_log_frequencies(log: Path, dimension: int) -> np.ndarray:
    # Only ORCA's explicitly unit-labelled vibrational rows are accepted. The
    # thermochemistry/IR summaries are not substitute frequency evidence.
    number = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][-+]?\d+)?"
    rows = re.findall(
        rf"^[ \t]*(\d+):[ \t]+({number})[ \t]+cm\*\*-1(?:[ \t].*)?$",
        log.read_text(encoding="utf-8", errors="replace"), flags=re.MULTILINE,
    )
    if len(rows) != dimension or [int(row[0]) for row in rows] != list(range(dimension)):
        raise ValueError("ORCA output must contain one complete indexed 3N frequency spectrum")
    values = np.asarray([float(row[1].replace("D", "E").replace("d", "e")) for row in rows])
    if not np.isfinite(values).all():
        raise ValueError("ORCA output frequencies must be finite")
    return values


def accept_harmonic_hessian(
    path: Path, log: Path, elements: list[str], coordinates_angstrom: Any,
    *, optimized: bool, nuclides: list[str] | None = None,
) -> dict[str, Any]:
    """Validate native derivatives and publish independent mass reweighting.

    The spectrum tolerance checks consistency between serialized derivatives,
    masses and native output; it does not establish accuracy against experiment.
    Rigid modes are projected geometrically, never discarded by a frequency
    cutoff. Their native finite numerical residuals remain explicitly recorded.
    """
    from cochem_base.chain.chain import parse_orca_hessian
    from cochem_base.spectroscopy.artifacts import load_hessian_artifact
    from cochem_base.spectroscopy.isotopologue import (
        IsotopologueSpectroscopyEngine, projected_harmonic_frequencies,
    )
    from cochem_base.physics.eckart_aligner import align_coordinates, compute_center_of_mass
    from cochem_base.geometry.nuclide_geometry import resolve_nuclear_identity

    if not path.is_file():
        raise ValueError("A harmonic frequency result requires its actual ORCA .hess checkpoint")
    artifact = load_hessian_artifact(path)
    if list(artifact.symbols) != elements:
        raise ValueError("ORCA Hessian atom identities/order differ from the accepted geometry")
    identity = resolve_nuclear_identity(nuclides if nuclides is not None else elements)
    if list(identity.elements) != elements:
        raise ValueError("Harmonic nuclide assignments differ from the accepted electronic elements")
    coordinates = np.asarray(coordinates_angstrom, dtype=float)
    if coordinates.shape != artifact.coordinates_angstrom.shape:
        raise ValueError("ORCA Hessian coordinates differ from the accepted final geometry")
    native = parse_orca_hessian(path)
    masses = np.asarray([atom["mass"] for atom in native["atoms"]], dtype=float)
    # ORCA recenters the frequency geometry even when the final optimization XYZ
    # retains its earlier origin. Validate identical ordered nuclear geometry up
    # to a proper rigid transform, and retain that transform explicitly. The raw
    # Hessian stays in its own documented coordinate frame.
    aligned, rotation, _ = align_coordinates(coordinates, artifact.coordinates_angstrom, masses=masses)
    final_com = compute_center_of_mass(coordinates, masses=masses)
    native_com = compute_center_of_mass(artifact.coordinates_angstrom, masses=masses)
    aligned += final_com
    if not np.allclose(coordinates, aligned, atol=GEOMETRY_TOLERANCE_ANGSTROM, rtol=0):
        raise ValueError("ORCA Hessian coordinates differ from the accepted final geometry")
    frequencies = native["frequencies"]
    if frequencies is None:
        raise ValueError("ORCA Hessian has no complete native frequency spectrum")
    reported = _native_log_frequencies(log, 3 * len(elements))
    # The human-readable output rounds frequencies to two decimal places.
    if not np.allclose(frequencies, reported, atol=0.011, rtol=0):
        raise ValueError("ORCA Hessian frequencies disagree with the completed output spectrum")
    recalculated, rigid_count = projected_harmonic_frequencies(
        artifact.hessian_hartree_bohr2, artifact.coordinates_angstrom, masses,
    )
    # ORCA reserves the first 3/5/6 entries for atomic/linear/nonlinear rigid
    # motion. Preserve those raw entries; only compare the vibrational subspace.
    native_vibrations = np.sort(frequencies[rigid_count:])
    recalculated = np.asarray(recalculated)
    if len(native_vibrations) != len(recalculated) or not np.allclose(
        native_vibrations, recalculated, atol=FREQUENCY_CONSISTENCY_TOLERANCE_CM1, rtol=0,
    ):
        raise ValueError("ORCA native spectrum is inconsistent with its mass-weighted Cartesian Hessian")
    principal = IsotopologueSpectroscopyEngine(
        elements, artifact.coordinates_angstrom, artifact.hessian_hartree_bohr2,
    ).compute_observables()
    selected = IsotopologueSpectroscopyEngine(
        list(identity.nuclides), artifact.coordinates_angstrom, artifact.hessian_hartree_bohr2,
    ).compute_observables()
    bundle = path.with_name(path.stem + ".harmonic-hessian.npz")
    source = {"engine": "orca", "coordinates_frame": "Native ORCA Cartesian Hessian frame",
              "raw_hessian_sha256": artifact.sha256, "nuclear_identity": identity.metadata}
    np.savez_compressed(bundle, symbols=np.asarray(identity.nuclides),
                        coordinates_angstrom=artifact.coordinates_angstrom,
                        hessian_hartree_bohr2=artifact.hessian_hartree_bohr2,
                        source=np.asarray(json.dumps(source, sort_keys=True)))
    canonical = load_hessian_artifact(bundle)
    if canonical.symbols != identity.nuclides or not np.array_equal(canonical.hessian_hartree_bohr2, artifact.hessian_hartree_bohr2):
        raise ValueError("The published ORCA harmonic bundle differs from the measured Hessian or nuclear assignments")
    maximum_difference = float(np.max(np.abs(native_vibrations - recalculated))) if len(recalculated) else 0.0
    evidence = {
        **_artifact_record(path, "hartree/bohr^2"), "shape": list(artifact.hessian_hartree_bohr2.shape),
        "source_coordinates_unit": "bohr", "accepted_coordinates_unit": "angstrom",
        "native_to_final_rotation": rotation.tolist(),
        "native_to_final_translation_angstrom": (final_com - rotation @ native_com).tolist(),
        "geometry_alignment_max_deviation_angstrom": float(np.max(np.abs(aligned - coordinates))),
        "native_masses_u": masses.tolist(), "native_frequencies_cm1": frequencies.tolist(),
        "native_rigid_frequencies_cm1": frequencies[:rigid_count].tolist(),
        "native_vibrational_frequencies_cm1": native_vibrations.tolist(),
        "rediagonalized_native_mass_frequencies_cm1": recalculated.tolist(),
        "native_spectrum_max_difference_cm1": maximum_difference,
        "native_spectrum_consistency_tolerance_cm1": FREQUENCY_CONSISTENCY_TOLERANCE_CM1,
        "rigid_mode_count": rigid_count, "geometry_optimization_validated": optimized,
        "scientific_accuracy_established": False,
    }
    return {
        "hessian_artifact": evidence,
        "hessian_bundle_artifact": {**_artifact_record(bundle, "hartree/bohr^2"), "coordinates_unit": "angstrom",
                                   "scope": "Geometry-bound measured harmonic Hessian with ordered input nuclides"},
        "harmonic_frequencies_cm1": selected.harmonic_frequencies_cm1,
        "harmonic_nuclides": list(identity.nuclides),
        "harmonic_isotope_masses_u": selected.masses,
        "principal_isotope_masses_u": principal.masses,
        "harmonic_frequency_provenance": "Rigid-motion projection and input-nuclide mass reweighting of the native Cartesian Hessian; bare element labels select their principal isotope",
    }
