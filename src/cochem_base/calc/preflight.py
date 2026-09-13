"""Domain Integrity Preflight Guard & Mutual Exclusivity Validator.

Authoritative Preflight Ontological Gatekeeper for CoChem-BASE (Task L3.2.1).
Enforces strict ontological disambiguation between:
- Product B: Gas-phase parent-anchored microwave rotational spectroscopy [M]
- Product M: Solid-state materials and extended periodic systems [M]

Complies with Method Matrix v4 Sections 1.2, 2.2, 3.0, and 4.4 [M].
Physical enforcement: Fails closed on boundary collisions [M].
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

import numpy as np

from cochem_base.exceptions import OntologicalCollisionError
from cochem_base.formatters.cochem_inertial_defect_validator import (
    DEFAULT_PRODUCT_B_MAX_ERROR_REL,
    validate_product_b_invariants,
)


# Prohibited periodic / solid-state parameter keywords for Product B [M]
_PERIODIC_SOLID_STATE_KEYS: Set[str] = {
    "lattice_vectors",
    "unit_cell",
    "cell",
    "lattice",
    "kpoints",
    "kmesh",
    "k_points",
    "kgrid",
    "k_grid",
    "kpoints_grid",
    "monkhorst_pack",
    "gamma_point",
    "cutoff_energy",
    "ecut",
    "encut",
    "pseudo_potentials",
    "pseudopotentials",
    "pseudos",
    "pseudo_potential",
    "pseudopotential",
    "paw",
    "paw_potentials",
    "reciprocal_lattice",
    "reciprocal_vectors",
    "reciprocal_lattice_vectors",
    "supercell",
    "spacegroup",
    "space_group",
    "brillouin_zone",
    "bloch",
}

# Prohibited gas-phase microwave spectroscopic parameter keywords for Product M [M]
_SPECTROSCOPIC_GAS_PHASE_KEYS: Set[str] = {
    "rotational_constants",
    "rotational_constants_mhz",
    "rotational_constants_cm1",
    "rot_constants",
    "rot_a",
    "rot_b",
    "rot_c",
    "a_mhz",
    "b_mhz",
    "c_mhz",
    "a0",
    "b0",
    "c0",
    "a_0",
    "b_0",
    "c_0",
    "be",
    "centrifugal_distortion",
    "quartic_distortion",
    "sextic_distortion",
    "centrifugal_distortion_constants",
    "watson",
    "watson_parameters",
    "eckart",
    "eckart_frame",
    "eckart_orientation",
    "eckart_frame_orientation",
    "eckart_align",
    "eckart_alignment",
    "vibrational_rotational_coupling",
    "delta_b_vib",
    "delta_vib",
    "alpha_constants",
    "alpha_matrix",
    "inertial_defect",
    "planar_moments",
    "spcat",
    "spfit",
    "pickett",
    "ray_asymmetry",
    "ray_asymmetry_parameter",
    "ray_kappa",
    "kappa",
    "asymmetry_parameter",
    "dipole_moment_debye",
    "microwave_transitions",
    "rotational_spectrum",
    "quadrupole_coupling",
    "nuclear_quadrupole",
    "spin_rotation",
}


def _extract_dict_payload(job_spec: Union[Dict[str, Any], Any]) -> Dict[str, Any]:
    """Coerces various input structures (dict, Pydantic model, object) into a dictionary [M]."""
    if isinstance(job_spec, dict):
        return job_spec
    if hasattr(job_spec, "model_dump") and callable(job_spec.model_dump):
        return job_spec.model_dump()
    if hasattr(job_spec, "dict") and callable(job_spec.dict):
        return job_spec.dict()
    if hasattr(job_spec, "__dict__"):
        return vars(job_spec)
    return {}


def _is_active_pbc(v: Any) -> bool:
    """Robustly evaluates whether a PBC specification activates periodic boundary conditions [M]."""
    if v is None:
        return False
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (int, np.integer)):
        return int(v) != 0
    if isinstance(v, (float, np.floating)):
        return float(v) != 0.0
    if isinstance(v, str):
        cleaned = v.strip().lower()
        if cleaned in {"true", "1", "yes", "t", "active", "periodic"}:
            return True
        if cleaned in {"false", "0", "no", "f", "none", "inactive"}:
            return False
        try:
            import ast
            parsed = ast.literal_eval(cleaned)
            return _is_active_pbc(parsed)
        except Exception:
            return False
    if isinstance(v, np.ndarray):
        if v.size == 0:
            return False
        try:
            return bool(np.any(v))
        except Exception:
            return any(_is_active_pbc(x) for x in v.flat)
    if isinstance(v, (list, tuple, Sequence)) and not isinstance(v, (str, bytes)):
        return any(_is_active_pbc(x) for x in v)
    return False


def _scan_keys_and_values(
    data: Any,
    max_depth: int = 5,
) -> Tuple[List[str], List[str], bool]:
    """Recursively scans payload keys and values for periodic and spectroscopic indicators [M].

    Returns
    -------
    Tuple[List[str], List[str], bool]
        - found_periodic: list of matched periodic parameter keys
        - found_spectroscopic: list of matched spectroscopic parameter keys
        - has_active_pbc: True if pbc is explicitly enabled (True or non-all-False sequence)
    """
    found_periodic: List[str] = []
    found_spectroscopic: List[str] = []
    has_active_pbc = False

    def _recurse(obj: Any, depth: int) -> None:
        nonlocal has_active_pbc
        if depth > max_depth or obj is None:
            return

        # Coerce structured objects / dataclasses to dict if applicable
        if not isinstance(obj, (dict, list, tuple, np.ndarray, str, bytes, int, float, bool, np.number, np.bool_)):
            if hasattr(obj, "model_dump") and callable(obj.model_dump):
                obj = obj.model_dump()
            elif hasattr(obj, "dict") and callable(obj.dict):
                obj = obj.dict()
            elif hasattr(obj, "__dict__"):
                obj = vars(obj)

        if isinstance(obj, dict):
            for k, v in obj.items():
                k_str = str(k).strip()
                k_lower = k_str.lower()

                # Check PBC condition (supports bool, np.bool_, int, str, list, tuple, np.ndarray) [M]
                if k_lower == "pbc":
                    if _is_active_pbc(v):
                        has_active_pbc = True
                        found_periodic.append(f"pbc={v}")

                # Check periodic keys
                if k_lower in _PERIODIC_SOLID_STATE_KEYS and v is not None:
                    found_periodic.append(str(k))

                # Check exact uppercase rotational constants A, B, C or named spectroscopic keys
                if k_str in {"A", "B", "C"} and v is not None and isinstance(v, (int, float, np.number)):
                    found_spectroscopic.append(str(k))
                elif k_lower in _SPECTROSCOPIC_GAS_PHASE_KEYS and v is not None:
                    found_spectroscopic.append(str(k))

                _recurse(v, depth + 1)

        elif isinstance(obj, np.ndarray):
            if obj.ndim > 0 and obj.dtype == object:
                for item in obj.flat:
                    _recurse(item, depth + 1)

        elif isinstance(obj, (list, tuple, Sequence)) and not isinstance(obj, (str, bytes)):
            for item in obj:
                _recurse(item, depth + 1)

    _recurse(data, 0)
    return found_periodic, found_spectroscopic, has_active_pbc


def _normalize_product_token(val: Any) -> str:
    """Extracts and normalizes product string representation from strings, bytes, or enums [M]."""
    if val is None:
        return ""
    import re
    candidates = []
    if hasattr(val, "name") and isinstance(val.name, (str, bytes)):
        candidates.append(str(val.name))
    if hasattr(val, "value"):
        candidates.append(str(val.value))
    candidates.append(str(val))

    for candidate in candidates:
        cand_clean = candidate.strip()
        if "." in cand_clean:
            cand_clean = cand_clean.split(".")[-1].strip()
        normalized = re.sub(r"[^A-Za-z0-9]+", "_", cand_clean).strip("_").upper()
        if normalized:
            return normalized
    return ""


def _find_declared_product(data: Any, max_depth: int = 4) -> str:
    """Searches for declared product identifier across payload dictionaries and objects [M]."""
    if max_depth <= 0 or data is None:
        return ""
    if not isinstance(data, dict):
        if hasattr(data, "model_dump") and callable(data.model_dump):
            data = data.model_dump()
        elif hasattr(data, "dict") and callable(data.dict):
            data = data.dict()
        elif hasattr(data, "__dict__"):
            data = vars(data)
        else:
            return ""

    for k in ("product", "product_category", "product_class", "domain", "product_type"):
        val = data.get(k)
        if val is not None:
            norm = _normalize_product_token(val)
            if norm:
                return norm

    for sub_k in ("keywords", "parameters", "settings", "options", "model", "provenance", "config", "calc_config"):
        sub = data.get(sub_k)
        if sub is not None:
            res = _find_declared_product(sub, max_depth - 1)
            if res:
                return res
    return ""


def validate_product_ontology_preflight(
    job_spec: Union[Dict[str, Any], Any],
) -> Dict[str, Any]:
    """Inspects job specifications to enforce mutual exclusivity between Product B and Product M [M].

    Fails closed immediately with OntologicalCollisionError if:
    1. A declared Product B job contains periodic boundary conditions, lattice vectors,
       k-points, energy cutoffs, or pseudopotentials [M].
    2. A declared Product M job contains rotational constants (A, B, C), centrifugal distortion,
       Eckart frame orientation, or vibrational rotational coupling (Delta B_vib) [M].
    3. An undeclared job contains both sets of domain-specific invariants simultaneously [M].

    Parameters
    ----------
    job_spec : Union[Dict[str, Any], Any]
        Raw dictionary or structured job configuration object (e.g. CalculationJobPayload).

    Returns
    -------
    Dict[str, Any]
        Structured validation telemetry dictionary compliant with CoChem provenance logging [M].

    Raises
    ------
    OntologicalCollisionError
        If spectroscopic and periodic parameters collide within the same job payload [M].
    """
    payload = _extract_dict_payload(job_spec)

    # Determine declared product category
    product_str = _find_declared_product(payload)

    _PRODUCT_B_ALIASES = {
        "B",
        "PRODUCT_B",
        "PRODUCTB",
        "PRODUCT_B_SEMI_EXPERIMENTAL",
        "PRODUCT_B_GAS_PHASE",
        "PRODUCT_B_ROTATIONAL",
        "GAS_PHASE",
        "MICROWAVE",
        "ROTATIONAL_SPECTROSCOPY",
    }
    _PRODUCT_M_ALIASES = {
        "M",
        "PRODUCT_M",
        "PRODUCTM",
        "PRODUCT_M_SOLID_STATE",
        "PRODUCT_M_MATERIALS",
        "PRODUCT_M_CRYSTAL",
        "SOLID_STATE",
        "MATERIALS",
        "CRYSTAL",
        "PERIODIC",
    }

    is_product_b = (
        product_str in _PRODUCT_B_ALIASES
        or product_str.startswith("PRODUCT_B_")
        or product_str.startswith("PRODUCTB_")
    )
    is_product_m = (
        product_str in _PRODUCT_M_ALIASES
        or product_str.startswith("PRODUCT_M_")
        or product_str.startswith("PRODUCTM_")
    )

    # Scan payload recursively
    found_periodic, found_spectroscopic, has_active_pbc = _scan_keys_and_values(payload)

    # Rule 1: Product B mutual exclusivity guard [M]
    if is_product_b:
        if found_periodic or has_active_pbc:
            violating_items = sorted(set(found_periodic))
            raise OntologicalCollisionError(
                f"Ontological collision: Job declared as Product B (gas-phase microwave spectroscopy) "
                f"contains prohibited solid-state periodic parameters: {violating_items} [M].",
                details={
                    "declared_product": product_str,
                    "prohibited_periodic_parameters": violating_items,
                    "has_active_pbc": has_active_pbc,
                },
            )

    # Rule 2: Product M mutual exclusivity guard [M]
    elif is_product_m:
        if found_spectroscopic:
            violating_items = sorted(set(found_spectroscopic))
            raise OntologicalCollisionError(
                f"Ontological collision: Job declared as Product M (solid-state materials) "
                f"contains prohibited gas-phase microwave spectroscopic parameters: {violating_items} [M].",
                details={
                    "declared_product": product_str,
                    "prohibited_spectroscopic_parameters": violating_items,
                },
            )

    # Rule 3: Undeclared payload simultaneous collision guard [M]
    else:
        if (found_periodic or has_active_pbc) and found_spectroscopic:
            raise OntologicalCollisionError(
                f"Ontological collision: Job payload mixes gas-phase microwave spectroscopic parameters "
                f"{sorted(set(found_spectroscopic))} with solid-state periodic parameters "
                f"{sorted(set(found_periodic))} simultaneously [M].",
                details={
                    "periodic_parameters": sorted(set(found_periodic)),
                    "spectroscopic_parameters": sorted(set(found_spectroscopic)),
                    "has_active_pbc": has_active_pbc,
                },
            )

    # Resolve detected or declared category
    if is_product_b:
        resolved_category = "PRODUCT_B"
    elif is_product_m:
        resolved_category = "PRODUCT_M"
    elif found_spectroscopic and not found_periodic:
        resolved_category = "PRODUCT_B_INFERRED"
    elif (found_periodic or has_active_pbc) and not found_spectroscopic:
        resolved_category = "PRODUCT_M_INFERRED"
    else:
        resolved_category = "GENERIC_QUANTUM_CHEMICAL"

    telemetry: Dict[str, Any] = {
        "status": "VALID",
        "product_category": resolved_category,
        "checked_invariants": [
            "domain_integrity_guard",
            "mutual_exclusivity_preflight",
            "gas_phase_boundary_invariant",
            "solid_state_periodic_invariant",
        ],
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "detected_parameters": {
            "has_periodic_parameters": bool(found_periodic or has_active_pbc),
            "has_spectroscopic_parameters": bool(found_spectroscopic),
            "periodic_keys_found": sorted(set(found_periodic)),
            "spectroscopic_keys_found": sorted(set(found_spectroscopic)),
            "has_active_pbc": has_active_pbc,
        },
    }

    return telemetry
    

__all__ = [
    "validate_product_ontology_preflight",
    "validate_product_b_invariants",
    "DEFAULT_PRODUCT_B_MAX_ERROR_REL",
]
