"""BASE request and receipt boundary for TORQ research operations.

The downstream provider remains isolated. BASE supplies geometry ingestion,
validated user choices and integrated reports; it does not advertise absent
provider science as installed merely because a distribution can be imported.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from cochem_base.core.cochem_constants import ANGSTROM_TO_BOHR

SCAN_OPERATION = "research_scan"


def validate_scan_options(options: dict, atom_count: int) -> dict:
    """Validate a bounded rigid two-fragment scan without changing its recipe."""
    allowed = {"method", "charge", "multiplicity", "fragments", "distances_angstrom", "cores", "memory_mb"}
    if not isinstance(options, dict) or set(options) - allowed:
        raise ValueError("Unsupported TORQ scan option.")
    if type(atom_count) is not int or not 2 <= atom_count <= 50:
        raise ValueError("The classroom rigid scan supports 2 to 50 atoms.")
    method = options.get("method")
    if not isinstance(method, dict) or set(method) != {"name", "basis"}:
        raise ValueError("Choose an explicit supported method and basis.")
    if method["name"] not in {"hf", "pbe-d4", "b3lyp-d4", "mp2"}:
        raise ValueError("This scan supports HF, PBE-D4, B3LYP-D4 or canonical MP2 only.")
    if not isinstance(method["basis"], str) or re.fullmatch(r"[A-Za-z0-9+*(),_. -]{1,100}", method["basis"]) is None:
        raise ValueError("Select a nonempty bounded basis name.")
    if type(options.get("charge")) is not int or abs(options["charge"]) > 4:
        raise ValueError("The scan requires a bounded integer charge.")
    if type(options.get("multiplicity")) is not int or options["multiplicity"] != 1:
        raise ValueError("The current TORQ scan provider supports closed-shell singlets only.")
    fragments = options.get("fragments")
    if not isinstance(fragments, list) or len(fragments) != 2 or any(not isinstance(part, list) or not part for part in fragments):
        raise ValueError("Choose two nonempty fragments covering the complete complex.")
    indices = [index for part in fragments for index in part]
    if any(type(index) is not int for index in indices) or sorted(indices) != list(range(atom_count)):
        raise ValueError("Each zero-based atom index must appear in exactly one fragment.")
    distances = options.get("distances_angstrom")
    if not isinstance(distances, list) or not 1 <= len(distances) <= 20:
        raise ValueError("Select 1 to 20 actual scan distances.")
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not .2 <= value <= 100
           for value in distances) or len(set(distances)) != len(distances):
        raise ValueError("Distances must be distinct finite values between 0.2 and 100 angstrom.")
    cores, memory = options.get("cores", 1), options.get("memory_mb", 1500)
    if type(cores) is not int or not 1 <= cores <= 2 or type(memory) is not int or not 256 <= memory <= 2048:
        raise ValueError("The classroom scan permits 1–2 CPU cores and 256–2048 MiB total memory.")
    return {**options, "cores": cores, "memory_mb": memory, "distances_angstrom": [float(value) for value in distances]}


def scan_points_request(symbols: list[str], geometry_angstrom: list[list[float]], options: dict) -> list[dict]:
    """Return exact rigid translations along the original mass-COM separation."""
    import numpy as np
    from cochem_base.geometry.nuclide_geometry import resolve_nuclear_identity

    options = validate_scan_options(options, len(symbols))
    identity = resolve_nuclear_identity(symbols)
    coordinates = np.asarray(geometry_angstrom, dtype=float)
    if coordinates.shape != (len(symbols), 3) or not np.isfinite(coordinates).all():
        raise ValueError("A scan requires complete finite Cartesian coordinates.")
    masses = np.asarray(identity.masses_u, dtype=float)
    a, b = options["fragments"]
    center_a = np.average(coordinates[a], axis=0, weights=masses[a])
    center_b = np.average(coordinates[b], axis=0, weights=masses[b])
    vector = center_b - center_a
    initial = float(np.linalg.norm(vector))
    if initial < 1e-8:
        raise ValueError("Fragment centers coincide; choose an initial complex with a defined separation direction.")
    direction = vector / initial
    result = []
    for distance in options["distances_angstrom"]:
        geometry = coordinates.copy()
        geometry[b] += (distance - initial) * direction
        pair = np.linalg.norm(geometry[:, None] - geometry[None, :], axis=2)
        np.fill_diagonal(pair, np.inf)
        if np.min(pair) < .1:
            raise ValueError("The scan places nuclei less than 0.1 angstrom apart; choose a physically meaningful distance range.")
        result.append({"coordinate": distance, "geometry_angstrom": geometry.tolist(), "request": {
            "molecule": {"symbols": list(identity.nuclides), "geometry_bohr": (geometry * ANGSTROM_TO_BOHR).tolist(),
                         "charge": options["charge"], "multiplicity": options["multiplicity"]},
            "method": options["method"], "properties": ["energy"],
            "settings": {"threads": options["cores"], "memory_mb": options["memory_mb"], "check_stability": True}}})
    return result


def report_from_scan(operation_report: dict, directory: str | Path) -> dict:
    """Recheck each native scan artifact and render only actually measured values."""
    from .student_reports import build_pes_report
    from collections import Counter

    report = operation_report.get("operation_report", operation_report)
    if report.get("module_id") != "torq" or report.get("operation") != SCAN_OPERATION:
        raise ValueError("Require a TORQ research-scan operation receipt.")
    native = report.get("result", {})
    if native.get("schema_version") != "cochem.torq-rigid-scan/1":
        raise ValueError("Unsupported TORQ scan receipt.")
    root = Path(directory).resolve(strict=True)
    composition = json.dumps(dict(sorted(Counter(native["elements"]).items())), sort_keys=True)
    points = []
    for item in native["points"]:
        point = {"coordinate": item["coordinate_angstrom"], "status": item["status"]}
        if item["status"] == "computed":
            source = (root / item["result_path"]).resolve(strict=True)
            if not source.is_relative_to(root) or source.is_symlink():
                raise ValueError("Scan result path escapes its retained artifact package.")
            if hashlib.sha256(source.read_bytes()).hexdigest() != item["result_sha256"]:
                raise ValueError("The retained native scan energy receipt changed.")
            observed = json.loads(source.read_bytes())
            if (observed.get("status") != "complete" or observed.get("scf", {}).get("converged") is not True
                    or observed.get("stability", {}).get("status") != "stable"):
                raise ValueError("A measured scan point requires a complete, converged and stable real native calculation.")
            requested_method = native["method"]["name"]
            actual_method = observed.get("method", {})
            if (actual_method.get("name") != requested_method.removesuffix("-d4")
                    or actual_method.get("basis") != native["method"]["basis"]
                    or (requested_method.endswith("-d4") and actual_method.get("dispersion") != "d4")
                    or observed.get("molecule", {}).get("charge") != native["electronic_state"]["charge"]
                    or observed.get("molecule", {}).get("multiplicity") != native["electronic_state"]["multiplicity"]):
                raise ValueError("Native scan method, basis or electronic state differs from its receipt.")
            import numpy as np
            actual_geometry = np.asarray(observed.get("geometry_bohr"), dtype=float)
            planned_geometry = np.asarray(item["geometry_angstrom"], dtype=float) * ANGSTROM_TO_BOHR
            if actual_geometry.shape != planned_geometry.shape or not np.allclose(actual_geometry, planned_geometry, rtol=0, atol=1e-9):
                raise ValueError("The measured native scan geometry differs from its requested coordinate.")
            manifest_path = (root / item["native_manifest_path"]).resolve(strict=True)
            if not manifest_path.is_relative_to(root) or manifest_path.is_symlink():
                raise ValueError("Native scan manifest escapes its artifact package.")
            if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != item["native_manifest_sha256"]:
                raise ValueError("Native scan manifest checksum failed.")
            manifest = json.loads(manifest_path.read_bytes())
            for artifact in manifest["artifacts"]:
                artifact_path = (manifest_path.parent / artifact["path"]).resolve(strict=True)
                if not artifact_path.is_relative_to(manifest_path.parent) or artifact_path.is_symlink():
                    raise ValueError("Unsafe native scan artifact path.")
                if (artifact_path.stat().st_size != artifact["size_bytes"]
                        or hashlib.sha256(artifact_path.read_bytes()).hexdigest() != artifact["sha256"]):
                    raise ValueError("The authentic native scan artifact manifest no longer matches its files.")
            point.update(energy_hartree=item["energy_hartree"], source={"path": str(source),
                "sha256": item["result_sha256"], "pointer": "/energy_hartree"},
                method={"engine": "PySCF", "method": native["method"]["name"], "basis": native["method"]["basis"]},
                composition=composition, electronic_state=native["electronic_state"])
        else:
            point["reason"] = item.get("reason", "Calculation was not completed.")
        points.append(point)
    return build_pes_report(points, coordinate_label="Rigid-fragment mass-COM separation", coordinate_unit="angstrom")


def source_receipt(path: str | Path, pointer: str) -> dict:
    """Build a receipt for an already retained native JSON value."""
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "pointer": pointer}
