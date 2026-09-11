"""Domain Integrity Preflight Guard & Mutual Exclusivity Validator.

Authoritative Preflight Ontological Gatekeeper for CoChem-BASE (Task L3.2.1).
Enforces strict ontological disambiguation between:
- Product B: Gas-phase parent-anchored microwave rotational spectroscopy
- Product M: Solid-state materials and extended periodic systems

Complies with Method Matrix v4 Sections 1.2, 2.2, 3.0, and 4.4.
Zero-mock physical enforcement: Fails closed on boundary collisions.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import numpy as np

from cochem_base.exceptions import OntologicalCollisionError


# Prohibited periodic / solid-state parameter keywords for Product B
_PERIODIC_SOLID_STATE_KEYS: Set[str] = {
    "lattice_vectors",
    "unit_cell",
    "cell",
    "lattice",
    "kpoints",
    "kmesh",
    "k_points",
    "monkhorst_pack",
    "cutoff_energy",
    "ecut",
    "encut",
    "pseudo_potentials",
    "pseudopotentials",
    "pseudos",
    "pseudo_potential",
    "pseudopotential",
}

# Prohibited gas-phase microwave spectroscopic parameter keywords for Product M
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
}


def _extract_dict_payload(job_spec: Union[Dict[str, Any], Any]) -> Dict[str, Any]:
    """Coerces various input structures (dict, Pydantic model, object) into a dictionary."""
    if isinstance(job_spec, dict):
        return job_spec
    if hasattr(job_spec, "model_dump") and callable(job_spec.model_dump):
        return job_spec.model_dump()
    if hasattr(job_spec, "dict") and callable(job_spec.dict):
        return job_spec.dict()
    if hasattr(job_spec, "__dict__"):
        return vars(job_spec)
    return {}


def _scan_keys_and_values(
    data: Any,
    max_depth: int = 5,
) -> Tuple[List[str], List[str], bool]:
    """Recursively scans payload keys and values for periodic and spectroscopic indicators.

    Returns
    -------
    Tuple[List[str], List[str], bool]
        - found_periodic: list of matched periodic parameter keys
        - found_spectroscopic: list of matched spectroscopic parameter keys
        - has_active_pbc: True if pbc is explicitly enabled (True or non-all-False tuple)
    """
    found_periodic: List[str] = []
    found_spectroscopic: List[str] = []
    has_active_pbc = False

    def _recurse(obj: Any, depth: int) -> None:
        nonlocal has_active_pbc
        if depth > max_depth or obj is None:
            return

        if isinstance(obj, dict):
            for k, v in obj.items():
                k_str = str(k).strip()
                k_lower = k_str.lower()

                # Check PBC condition
                if k_lower == "pbc":
                    if v is True:
                        has_active_pbc = True
                        found_periodic.append(f"pbc={v}")
                    elif isinstance(v, (list, tuple)) and any(bool(x) for x in v):
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

        elif isinstance(obj, (list, tuple)):
            for item in obj:
                _recurse(item, depth + 1)

    _recurse(data, 0)
    return found_periodic, found_spectroscopic, has_active_pbc


def _find_declared_product(data: Any, max_depth: int = 4) -> str:
    """Searches for declared product identifier across payload dictionaries."""
    if not isinstance(data, dict) or max_depth <= 0:
        return ""
    for k in ("product", "product_category", "product_class", "domain", "product_type"):
        val = data.get(k)
        if val is not None and isinstance(val, (str, bytes)):
            s = str(val).strip().upper()
            if s:
                return s
    for sub_k in ("keywords", "parameters", "settings", "options", "model", "provenance"):
        sub = data.get(sub_k)
        if isinstance(sub, dict):
            res = _find_declared_product(sub, max_depth - 1)
            if res:
                return res
    return ""


def validate_product_ontology_preflight(
    job_spec: Union[Dict[str, Any], Any],
) -> Dict[str, Any]:
    """Inspects job specifications to enforce mutual exclusivity between Product B and Product M.

    Fails closed immediately with OntologicalCollisionError if:
    1. A declared Product B job contains periodic boundary conditions, lattice vectors,
       k-points, energy cutoffs, or pseudopotentials.
    2. A declared Product M job contains rotational constants (A, B, C), centrifugal distortion,
       Eckart frame orientation, or vibrational rotational coupling (Delta B_vib).
    3. An undeclared job contains both sets of domain-specific invariants simultaneously.

    Parameters
    ----------
    job_spec : Union[Dict[str, Any], Any]
        Raw dictionary or structured job configuration object (e.g. CalculationJobPayload).

    Returns
    -------
    Dict[str, Any]
        Structured validation telemetry dictionary compliant with CoChem provenance logging.

    Raises
    ------
    OntologicalCollisionError
        If spectroscopic and periodic parameters collide within the same job payload.
    """
    payload = _extract_dict_payload(job_spec)

    # Determine declared product category
    product_str = _find_declared_product(payload)

    is_product_b = product_str in {
        "PRODUCT_B",
        "PRODUCT_B_SEMI_EXPERIMENTAL",
        "PRODUCT B",
        "B",
    }
    is_product_m = product_str in {
        "PRODUCT_M",
        "PRODUCT_M_SOLID_STATE",
        "PRODUCT_M_MATERIALS",
        "PRODUCT M",
        "M",
    }

    # Scan payload recursively
    found_periodic, found_spectroscopic, has_active_pbc = _scan_keys_and_values(payload)

    # Rule 1: Product B mutual exclusivity guard
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

    # Rule 2: Product M mutual exclusivity guard
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

    # Rule 3: Undeclared payload simultaneous collision guard
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
