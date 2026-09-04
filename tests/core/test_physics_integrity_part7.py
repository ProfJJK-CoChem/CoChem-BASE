"""Tests for physics integrity - Part 7 (Suggestions #61, #62, #63, #64, #66)."""

import math
import os
import time
import pytest
from pydantic import ValidationError
from cochem_base.core.models import (
    MolecularTopology,
    CURRENT_CORE_SCHEMA_VERSION,
    register_migration,
    migrate_payload,
)
from cochem_base.core.exceptions import (
    CoChemError,
    CoordinateShapeError,
    SchemaMigrationError,
    AirGapBoundaryError,
)
from cochem_base.core.cochem_crypto import (
    format_rfc8785_float,
    canonicalize_json,
)
from cochem_base.core.cochem_provenance import (
    compute_boltzmann_weights,
    ThermodynamicsProvenance,
    DAGNode,
)
from cochem_base.core_engine.cochem_mass_resolver import (
    get_dynamic_atomic_mass,
    get_dynamic_isotopic_mass,
    IsotopeMassResolutionError,
)


def test_pydantic_model_schema_version_and_migration():
    """Validates Suggestion #61: schema_version injection and automated backward-compatible migration."""
    # Test current model instantiation
    top = MolecularTopology(
        symbols=["H", "H"],
        coordinates=[[0.0, 0.0, 0.0], [0.0, 0.0, 0.74]],
        molecular_charge=0,
        spin_multiplicity=1,
    )
    assert top.schema_version == CURRENT_CORE_SCHEMA_VERSION

    # Register legacy migration from v0 to v1
    @register_migration("MolecularTopology", 0)
    def migrate_v0_to_v1(data):
        d = dict(data)
        d["schema_version"] = 1
        if "spin_multiplicity" not in d:
            d["spin_multiplicity"] = 1
        return d

    legacy_payload = {
        "schema_version": 0,
        "symbols": ["O", "H", "H"],
        "coordinates": [[0.0, 0.0, 0.0], [0.0, 0.75, 0.5], [0.0, -0.75, 0.5]],
        "molecular_charge": 0,
    }
    migrated_top = MolecularTopology.from_archival_dict(legacy_payload)
    assert migrated_top.schema_version == 1
    assert migrated_top.spin_multiplicity == 1


def test_rfc8785_ieee754_canonical_float_formatting():
    """Validates Suggestion #62: ECMAScript IEEE 754 float formatting parity in canonicalize_json."""
    # Signed zero formatting
    assert format_rfc8785_float(0.0) == "0"
    assert format_rfc8785_float(-0.0) == "0"

    # Disallow NaN and Infinity
    with pytest.raises(ValueError):
        format_rfc8785_float(float("nan"))
    with pytest.raises(ValueError):
        format_rfc8785_float(float("inf"))

    # Exponential notation without leading zero in exponent
    assert format_rfc8785_float(1e-5) == "0.00001" or format_rfc8785_float(1e-5) == "1e-5"
    assert format_rfc8785_float(1e-7) == "1e-7"
    assert format_rfc8785_float(1e21) == "1e+21"

    # Canonicalize dictionary with sorted keys and floats
    payload = {"b": 1e-7, "a": -0.0, "c": [1, 2.5]}
    canonical_bytes = canonicalize_json(payload)
    # Keys must be sorted 'a', 'b', 'c', -0.0 as 0, 1e-7 without leading zero
    assert canonical_bytes == b'{"a":0,"b":1e-7,"c":[1,2.5]}'


def test_quasi_rrho_thermodynamics_provenance_logging():
    """Validates Suggestion #63: Quasi-harmonic thermodynamic parameter provenance logging."""
    node = DAGNode(node_id="act-opt-001", node_type="activity")
    energies = [0.0, 0.5, 1.2]
    weights, prov = compute_boltzmann_weights(
        energies,
        temperature_k=298.15,
        low_freq_cutoff_cm1=100.0,
        damping_model="grimme_quasi_rrho",
        dag_node=node,
    )
    assert len(weights) == 3
    assert math.isclose(sum(weights), 1.0, rel_tol=1e-6)
    assert "thermodynamics_provenance" in node.payload
    logged = node.payload["thermodynamics_provenance"]
    assert logged["damping_model"] == "grimme_quasi_rrho"
    assert logged["low_freq_cutoff_cm1"] == 100.0
    assert logged["temperature_k"] == 298.15
    assert logged["provenance_tag"] == "[D]"


def test_machine_actionable_exception_hierarchy():
    """Validates Suggestion #64: Structured exception hierarchy with machine-actionable error codes."""
    # Coordinate shape mismatch raises CoordinateShapeError
    with pytest.raises(CoordinateShapeError) as exc_info:
        MolecularTopology(
            symbols=["H"],
            coordinates=[[0.0, 0.0]],  # 2D instead of 3D
            molecular_charge=0,
            spin_multiplicity=1,
        )
    err = exc_info.value
    assert err.error_code == "COCHEM_E_INVALID_COORD_SHAPE"
    assert err.details["actual_len"] == 2
    assert err.details["expected_len"] == 3


def test_dynamic_mendeleev_mass_resolution_lru_cache():
    """Validates Suggestion #66: LRU memory caching on dynamic Mendeleev mass resolution."""
    # Warmup
    mass_c = get_dynamic_atomic_mass("C")
    assert math.isclose(mass_c, 12.011, rel_tol=1e-2)

    # Measure lookup latency for cached access
    start = time.perf_counter()
    for _ in range(1000):
        _ = get_dynamic_atomic_mass("C")
    cached_duration = time.perf_counter() - start

    # 1000 lookups should complete in less than 5 milliseconds
    assert cached_duration < 0.005

    # Nuclear isotopic masses
    mass_14c = get_dynamic_isotopic_mass("C", 14)
    assert math.isclose(mass_14c, 14.003241, rel_tol=1e-4)

    with pytest.raises(IsotopeMassResolutionError):
        get_dynamic_isotopic_mass("C", 999)
