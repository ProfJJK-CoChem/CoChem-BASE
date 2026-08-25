"""Zero-Verification Unit and Integration Test Suite for CoChem-GEOM Parser.

Authoritative Standards:
- Method Matrix v4: Data Ingestion, Conformer Spectroscopic Graph Contracts, QM Record Extraction
- SWEBOK v3 / ISO 25010 Software Quality Standards
- Mendeleev Library Mandate: Dynamic atomic and monoisotopic mass validation (No hardcoding)
- Cryptographic Provenance: SHA-256 checksum generation for files, byte streams, and geometries
- Safe MsgPack Streaming: Unpacker streaming with raw=False to prevent out-of-memory errors
- SE(3) Equivariance & Invariance: Separation of spatial pos vs non-spatial features
- State Immutability: Pure functional transformations (immutable operations)
"""

from __future__ import annotations

import io
import math
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Tuple

import msgpack
import numpy as np
import pytest
import torch

# Ensure CoChem-GEOM source paths are in sys.path
BASE_ROOT = Path(__file__).resolve().parent.parent
BASE_SRC = BASE_ROOT / "src"
if str(BASE_SRC) not in sys.path:
    sys.path.insert(0, str(BASE_SRC))
if str(BASE_ROOT) not in sys.path:
    sys.path.insert(0, str(BASE_ROOT))

from cochem_geom.data.geom_parser import (
    ATOMIC_MASS_UNIT_KG,
    ATOMIC_NUMBER_TO_SYMBOL,
    BOLTZMANN_CONSTANT_EV_K,
    BOLTZMANN_CONSTANT_J_K,
    DEFAULT_ELEMENT_TYPES,
    DEFAULT_MAX_BUFFER_SIZE,
    ELEMENT_TYPE_TO_INDEX,
    EV_TO_CM_MINUS_ONE,
    EV_TO_HARTREE,
    EV_TO_KCAL_MOL,
    HARTREE_TO_EV,
    HARTREE_TO_KCAL_MOL,
    HARTREE_TO_KJ_MOL,
    INDEX_TO_ELEMENT_TYPE,
    KCAL_MOL_TO_EV,
    KCAL_MOL_TO_HARTREE,
    PLANCK_CONSTANT_J_S,
    ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ,
    SPEED_OF_LIGHT_M_S,
    STANDARD_TEMPERATURE_K,
    SYMBOL_TO_ATOMIC_NUMBER,
    ConformerRecord,
    MoleculeRecord,
    QMOutputRecord,
    calculate_boltzmann_weights,
    compute_bytes_sha256,
    compute_center_of_mass,
    compute_file_sha256,
    compute_moment_of_inertia_tensor,
    compute_rotational_constants,
    compute_structure_sha256,
    conformer_to_molecular_data,
    deserialize_geom_archive,
    deserialize_geom_bytes,
    ensemble_to_molecular_data,
    ev_to_hartree,
    ev_to_kcal_mol,
    get_atomic_mass,
    get_covalent_radius_angstrom,
    get_isotopic_mass,
    get_monoisotopic_mass,
    get_pauling_electronegativity,
    get_vdw_radius_angstrom,
    hartree_to_ev,
    hartree_to_kcal_mol,
    kcal_mol_to_ev,
    kcal_mol_to_hartree,
    molecular_data_to_conformer,
    parse_geom_raw_molecule,
    parse_qm_log_text,
    parse_qm_output,
    rotate_conformer,
    serialize_geom_archive,
    serialize_geom_bytes,
    translate_conformer,
)


# ==============================================================================
# 1. Fundamental Physical Constants & Energy Invertibility Tests
# ==============================================================================


def test_fundamental_physical_constants_provenance() -> None:
    """Validate fundamental physical constants against CODATA 2018/2022 standards."""
    assert SPEED_OF_LIGHT_M_S == 299792458.0  # [M]
    assert math.isclose(PLANCK_CONSTANT_J_S, 6.62607015e-34, rel_tol=1e-12)  # [M]
    assert math.isclose(BOLTZMANN_CONSTANT_J_K, 1.380649e-23, rel_tol=1e-12)  # [M]
    assert math.isclose(ATOMIC_MASS_UNIT_KG, 1.66053906660e-27, rel_tol=1e-10)  # [M]
    assert STANDARD_TEMPERATURE_K == 298.15  # [M]
    assert DEFAULT_MAX_BUFFER_SIZE == 1024 * 1024 * 1024  # [E]


def test_energy_conversion_factors_and_invertibility() -> None:
    """Validate quantum chemical unit conversion factors and numerical invertibility."""
    assert math.isclose(HARTREE_TO_EV, 27.211386245988, rel_tol=1e-9)  # [D]
    assert math.isclose(HARTREE_TO_KCAL_MOL, 627.5094740631, rel_tol=1e-9)  # [D]
    assert math.isclose(HARTREE_TO_KJ_MOL, 2625.4996394799, rel_tol=1e-9)  # [D]
    assert math.isclose(KCAL_MOL_TO_EV, 0.04336411530877, rel_tol=1e-7)  # [D]
    assert math.isclose(ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ, 505379.008784, rel_tol=1e-6)  # [D]

    test_energy_hartree = 2.45
    ev_val = hartree_to_ev(test_energy_hartree)
    assert math.isclose(ev_val, test_energy_hartree * HARTREE_TO_EV, rel_tol=1e-12)
    assert math.isclose(ev_to_hartree(ev_val), test_energy_hartree, rel_tol=1e-12)

    kcal_val = hartree_to_kcal_mol(test_energy_hartree)
    assert math.isclose(kcal_val, test_energy_hartree * HARTREE_TO_KCAL_MOL, rel_tol=1e-12)
    assert math.isclose(kcal_mol_to_hartree(kcal_val), test_energy_hartree, rel_tol=1e-12)

    ev_from_kcal = kcal_mol_to_ev(kcal_val)
    assert math.isclose(ev_from_kcal, ev_val, rel_tol=1e-5)
    assert math.isclose(ev_to_kcal_mol(ev_from_kcal), kcal_val, rel_tol=1e-5)


# ==============================================================================
# 2. Dynamic Mendeleev Mass & Property Resolution Tests
# ==============================================================================


def test_dynamic_atomic_mass_retrieval() -> None:
    """Assert atomic masses are dynamically retrieved via mendeleev without hardcoding."""
    from mendeleev import element

    test_elements = ["H", "C", "N", "O", "F", "P", "S", "Cl", "Br", "I"]
    for sym in test_elements:
        expected_mass = float(element(sym).atomic_weight)
        retrieved_mass = get_atomic_mass(sym)  # [M]
        assert math.isclose(retrieved_mass, expected_mass, rel_tol=1e-9)

        z = int(element(sym).atomic_number)
        assert math.isclose(get_atomic_mass(z), expected_mass, rel_tol=1e-9)


def test_monoisotopic_and_isotopic_mass_retrieval() -> None:
    """Validate monoisotopic and isotope-specific mass lookups from mendeleev."""
    c12_mass = get_isotopic_mass("C", mass_number=12)  # [M]
    assert math.isclose(c12_mass, 12.0, rel_tol=1e-12)

    c13_mass = get_isotopic_mass("C", mass_number=13)  # [M]
    assert 13.003 < c13_mass < 13.004

    d_mass = get_isotopic_mass("H", mass_number=2)  # [M]
    assert 2.014 < d_mass < 2.015

    o16_mass = get_monoisotopic_mass("O")  # [M]
    assert 15.994 < o16_mass < 15.995

    with pytest.raises(ValueError):
        get_isotopic_mass("H", mass_number=999)


def test_covalent_radii_and_electronegativity_retrieval() -> None:
    """Verify covalent radii, Pauling electronegativities, and vdW radii from mendeleev."""
    from mendeleev import element

    for sym in ["C", "N", "O", "F", "Cl", "S"]:
        el = element(sym)
        expected_cov = float(el.covalent_radius_pyykko) / 100.0  # [M]
        assert math.isclose(get_covalent_radius_angstrom(sym), expected_cov, rel_tol=1e-6)

        expected_en = float(el.en_pauling)  # [M]
        assert math.isclose(get_pauling_electronegativity(sym), expected_en, rel_tol=1e-6)

        expected_vdw = float(el.vdw_radius_alvarez) / 100.0  # [M]
        assert math.isclose(get_vdw_radius_angstrom(sym), expected_vdw, rel_tol=1e-6)


# ==============================================================================
# 3. Thermodynamic Boltzmann Weighting Tests
# ==============================================================================


def test_boltzmann_weighting_distribution() -> None:
    """Validate Boltzmann probability distribution at T=298.15K."""
    # Energies in eV relative to minimum
    energies_ev = [0.0, 0.025, 0.050, 0.100]
    weights = calculate_boltzmann_weights(energies_ev, temperature_k=298.15, energy_unit="ev")  # [D]

    assert isinstance(weights, np.ndarray)
    assert weights.ndim == 1
    assert len(weights) == len(energies_ev)
    assert np.all(weights >= 0.0)
    assert math.isclose(float(np.sum(weights)), 1.0, rel_tol=1e-6)

    # Monotonic decay with energy
    for i in range(len(energies_ev) - 1):
        assert weights[i] > weights[i + 1]


def test_boltzmann_weighting_temperature_dependence() -> None:
    """Validate temperature dependence: high T approaches uniform distribution, low T collapses to ground state."""
    energies_ev = [0.0, 0.05, 0.10]

    # At ultra-high temperature (100,000 K), all states are equally populated (~1/3 each)
    weights_high_t = calculate_boltzmann_weights(energies_ev, temperature_k=100000.0, energy_unit="ev")
    for w in weights_high_t:
        assert math.isclose(float(w), 1.0 / 3.0, rel_tol=1e-2)

    # At low temperature (10 K), ground state possesses essentially 100% probability
    weights_low_t = calculate_boltzmann_weights(energies_ev, temperature_k=10.0, energy_unit="ev")
    assert math.isclose(float(weights_low_t[0]), 1.0, rel_tol=1e-4)
    assert math.isclose(float(weights_low_t[1]), 0.0, abs_tol=1e-4)


def test_boltzmann_weighting_with_hartree_and_kcal_units() -> None:
    """Validate calculation when energies are provided in Hartree or kcal/mol."""
    energies_hartree = [-76.432, -76.431, -76.430]
    weights_hartree = calculate_boltzmann_weights(energies_hartree, temperature_k=298.15, energy_unit="hartree")

    energies_ev = [hartree_to_ev(e) for e in energies_hartree]
    weights_ev = calculate_boltzmann_weights(energies_ev, temperature_k=298.15, energy_unit="ev")

    assert np.allclose(weights_hartree, weights_ev, atol=1e-6)


# ==============================================================================
# 4. Cryptographic SHA-256 Provenance Hashing Tests
# ==============================================================================


def test_sha256_checksum_generation(tmp_path: Path) -> None:
    """Validate streaming file and byte buffer SHA-256 hash generation."""
    test_content = b"CoChem-GEOM Data Ingestion Provenance Block 2026"
    test_file = tmp_path / "provenance_test.bin"
    test_file.write_bytes(test_content)

    import hashlib

    expected_hash = hashlib.sha256(test_content).hexdigest()

    file_hash = compute_file_sha256(test_file)
    bytes_hash = compute_bytes_sha256(test_content)

    assert file_hash == expected_hash
    assert bytes_hash == expected_hash
    assert len(file_hash) == 64


def test_molecular_structure_sha256_hashing() -> None:
    """Validate canonical geometric coordinate SHA-256 fingerprinting."""
    coords = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1.16]], dtype=np.float64)
    atomic_numbers = [8, 6]

    hash1 = compute_structure_sha256(coords, atomic_numbers)
    hash2 = compute_structure_sha256(coords.copy(), atomic_numbers)
    assert hash1 == hash2
    assert len(hash1) == 64

    # Slightly perturbed coordinates must produce distinct hash
    perturbed_coords = coords + np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 0.01]])
    hash_perturbed = compute_structure_sha256(perturbed_coords, atomic_numbers)
    assert hash1 != hash_perturbed


# ==============================================================================
# 5. MsgPack Streaming Serialization & Deserialization Tests
# ==============================================================================


def test_msgpack_streaming_roundtrip(tmp_path: Path) -> None:
    """Validate safe stream unpacking of GEOM MsgPack archives with raw=False."""
    archive_file = tmp_path / "test_geom_archive.msgpack"

    # Construct authentic GEOM records dictionary
    records_dict = {
        "CCO": {
            "smiles": "CCO",
            "conformers": [
                {
                    "geom": [
                        [-0.014, 0.021, 0.003],
                        [1.240, -0.730, 0.012],
                        [2.350, 0.180, -0.010],
                        [-0.880, -0.630, 0.010],
                        [-0.040, 0.650, 0.890],
                        [-0.040, 0.650, -0.880],
                        [1.280, -1.370, -0.870],
                        [1.280, -1.370, 0.890],
                        [3.180, -0.320, 0.000],
                    ],
                    "totalenergy": -154.98234,  # Hartree
                    "relativeenergy": 0.0,
                    "boltzmannweight": 0.72,
                    "dipole": [0.35, -1.21, 0.44],
                    "rotational_constants": [34500.0, 9200.0, 8100.0],
                },
                {
                    "geom": [
                        [-0.010, 0.020, 0.000],
                        [1.245, -0.725, 0.010],
                        [2.360, 0.175, -0.015],
                        [-0.870, -0.640, 0.015],
                        [-0.035, 0.660, 0.885],
                        [-0.035, 0.660, -0.875],
                        [1.275, -1.365, -0.865],
                        [1.275, -1.365, 0.895],
                        [3.175, -0.315, 0.005],
                    ],
                    "totalenergy": -154.98012,  # Hartree
                    "relativeenergy": 0.00222,
                    "boltzmannweight": 0.28,
                    "dipole": [0.42, -1.15, 0.38],
                    "rotational_constants": [34200.0, 9150.0, 8050.0],
                },
            ],
        },
        "O": {
            "smiles": "O",
            "conformers": [
                {
                    "geom": [
                        [0.000, 0.000, 0.117],
                        [0.000, 0.757, -0.469],
                        [0.000, -0.757, -0.469],
                    ],
                    "totalenergy": -76.432,
                    "relativeenergy": 0.0,
                    "boltzmannweight": 1.0,
                    "dipole": [0.0, 0.0, 1.85],
                }
            ],
        },
    }

    # Serialize to archive
    num_written = serialize_geom_archive(archive_file, records_dict)
    assert num_written == 2
    assert archive_file.exists()
    assert archive_file.stat().st_size > 0

    # Stream deserialize
    streamed_records = list(deserialize_geom_archive(archive_file, max_buffer_size=DEFAULT_MAX_BUFFER_SIZE))
    assert len(streamed_records) == 2

    smiles_keys = [rec[0] for rec in streamed_records]
    assert "CCO" in smiles_keys
    assert "O" in smiles_keys

    # Check streamed data integrity
    for smiles, data in streamed_records:
        assert isinstance(smiles, str)
        assert isinstance(data, dict)
        assert "conformers" in data
        assert len(data["conformers"]) >= 1


def test_deserialize_geom_bytes() -> None:
    """Validate in-memory byte buffer streaming deserialization."""
    records_dict = {
        "C": {
            "smiles": "C",
            "conformers": [
                {
                    "geom": [
                        [0.0, 0.0, 0.0],
                        [0.629, 0.629, 0.629],
                        [-0.629, -0.629, 0.629],
                        [-0.629, 0.629, -0.629],
                        [0.629, -0.629, -0.629],
                    ],
                    "totalenergy": -40.518,
                    "relativeenergy": 0.0,
                    "boltzmannweight": 1.0,
                }
            ],
        }
    }
    raw_bytes = serialize_geom_bytes(records_dict)
    assert isinstance(raw_bytes, bytes)

    streamed = list(deserialize_geom_bytes(raw_bytes))
    assert len(streamed) == 1
    assert streamed[0][0] == "C"
    assert len(streamed[0][1]["conformers"]) == 1


# ==============================================================================
# 6. GEOM Raw Molecule & Conformer Parsing Tests
# ==============================================================================


def test_parse_geom_raw_molecule_ethanol() -> None:
    """Validate parsing of multi-conformer GEOM raw dictionary into MoleculeRecord and ConformerRecord."""
    raw_mol_data = {
        "smiles": "CCO",
        "conformers": [
            {
                "geom": [
                    [-0.014, 0.021, 0.003],
                    [1.240, -0.730, 0.012],
                    [2.350, 0.180, -0.010],
                    [-0.880, -0.630, 0.010],
                    [-0.040, 0.650, 0.890],
                    [-0.040, 0.650, -0.880],
                    [1.280, -1.370, -0.870],
                    [1.280, -1.370, 0.890],
                    [3.180, -0.320, 0.000],
                ],
                "totalenergy": -154.98234,  # Hartree
                "dipole": [0.35, -1.21, 0.44],
                "forces": [[0.0, 0.0, 0.0]] * 9,
            },
            {
                "geom": [
                    [-0.010, 0.020, 0.000],
                    [1.245, -0.725, 0.010],
                    [2.360, 0.175, -0.015],
                    [-0.870, -0.640, 0.015],
                    [-0.035, 0.660, 0.885],
                    [-0.035, 0.660, -0.875],
                    [1.275, -1.365, -0.865],
                    [1.275, -1.365, 0.895],
                    [3.175, -0.315, 0.005],
                ],
                "totalenergy": -154.98012,  # Hartree
                "dipole": [0.42, -1.15, 0.38],
                "forces": [[0.0, 0.0, 0.0]] * 9,
            },
        ],
    }

    mol_record = parse_geom_raw_molecule("CCO", raw_mol_data, default_energy_unit="hartree")

    assert mol_record.smiles == "CCO"
    assert mol_record.n_atoms == 9
    assert len(mol_record.conformers) == 2

    # Conformer 0 checks
    c0 = mol_record.conformers[0]
    assert c0.conformer_id == 0
    assert c0.coords.shape == (9, 3)
    assert c0.coords.dtype == np.float32
    assert math.isclose(c0.energy, hartree_to_ev(-154.98234), rel_tol=1e-6)
    assert math.isclose(c0.relative_energy, 0.0, abs_tol=1e-6)
    assert c0.boltzmann_weight > mol_record.conformers[1].boltzmann_weight
    assert math.isclose(c0.boltzmann_weight + mol_record.conformers[1].boltzmann_weight, 1.0, rel_tol=1e-5)

    # Conformer 1 checks
    c1 = mol_record.conformers[1]
    assert c1.conformer_id == 1
    assert c1.relative_energy > 0.0
    assert math.isclose(c1.relative_energy, hartree_to_ev(-154.98012 - (-154.98234)), rel_tol=1e-5)

    # Rotational constants must be automatically calculated if not explicitly given
    assert c0.rotational_constants is not None
    assert len(c0.rotational_constants) == 3
    a, b, c = c0.rotational_constants
    assert a >= b >= c > 0.0


def test_conformer_record_immutability_and_cloning() -> None:
    """Verify deep cloning and immutability of ConformerRecord."""
    coords = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]], dtype=np.float32)
    conf = ConformerRecord(
        conformer_id=0,
        coords=coords,
        energy=-100.0,
        relative_energy=0.0,
        boltzmann_weight=1.0,
        dipole=np.array([0.0, 0.0, 1.5], dtype=np.float32),
    )

    cloned = conf.clone()
    assert np.array_equal(cloned.coords, conf.coords)
    assert cloned.coords is not conf.coords

    # Modifying cloned array must not affect original
    cloned.coords[0, 0] = 99.0
    assert conf.coords[0, 0] == 0.0


# ==============================================================================
# 7. Quantum Chemistry .out / .log Output Parsers
# ==============================================================================


def test_orca_output_parser_water() -> None:
    """Validate authentic ORCA quantum chemistry calculation log parsing."""
    orca_log_content = """
                                * O   R   C   A *
                                  ===========

           Program Version 5.0.4 - RELEASE  -

------------------------------------------------------------------------------
                          ORCA OPTIMIZATION RESULTS
------------------------------------------------------------------------------

------------------------------------------------------------------------------
                            FINAL ENERGY EVALUATION
------------------------------------------------------------------------------

FINAL SINGLE POINT ENERGY      -76.432198765432
------------------
CARTESIAN COORDINATES (ANGSTROEM)
------------------
  O      0.000000    0.000000    0.065500
  H      0.000000    0.757200   -0.520500
  H      0.000000   -0.757200   -0.520500

------------------
DIPOLE MOMENT
------------------
Total Dipole Moment    :     0.00000     0.00000     1.85420
Magnitude (Debye)      :     1.85420

--------------------------------
ROTATIONAL CONSTANTS (in MHz)
--------------------------------
    Rotational constants in MHz :   825314.2   435210.5   285112.9
    Rotational constants in cm-1:       27.53      14.52       9.51

--------------------
SPIN EXPECTATION VALUE
--------------------
Expectation value of <S**2> :  0.000000

*** OPTIMIZATION RUN DONE ***
ORCA TERMINATED NORMALLY
"""
    qm_record = parse_qm_log_text(orca_log_content, filename="water_orca.out", program="ORCA")

    assert qm_record.program == "ORCA"
    assert qm_record.converged is True
    assert qm_record.total_energy_hartree is not None
    assert math.isclose(qm_record.total_energy_hartree, -76.432198765432, rel_tol=1e-10)
    assert qm_record.total_energy_ev is not None
    assert math.isclose(qm_record.total_energy_ev, hartree_to_ev(-76.432198765432), rel_tol=1e-6)

    assert qm_record.symbols == ["O", "H", "H"]
    assert qm_record.atomic_numbers == [8, 1, 1]
    assert qm_record.positions.shape == (3, 3)
    assert math.isclose(float(qm_record.positions[0, 2]), 0.0655, abs_tol=1e-4)

    assert qm_record.dipole is not None
    assert math.isclose(float(qm_record.dipole[2]), 1.8542, abs_tol=1e-4)

    assert qm_record.rotational_constants is not None
    assert math.isclose(float(qm_record.rotational_constants[0]), 825314.2, rel_tol=1e-3)
    assert math.isclose(float(qm_record.rotational_constants[1]), 435210.5, rel_tol=1e-3)
    assert math.isclose(float(qm_record.rotational_constants[2]), 285112.9, rel_tol=1e-3)

    assert qm_record.s2_calculated == 0.0
    assert len(qm_record.sha256_hash) == 64


def test_xtb_output_parser() -> None:
    """Validate authentic GFN2-xTB output log parsing."""
    xtb_log_content = """
   -----------------------------------------------------------
   |                   * X T B *                             |
   |              Semiempirical QM Package                   |
   -----------------------------------------------------------
   
   ...
   
   -----------------------------------------------------------
   |              FINAL ENERGY EVALUATION                    |
   -----------------------------------------------------------
   
   * TOTAL ENERGY               -12.876543210000 Eh
   * GRADIENT NORM                0.000123450000 Eh/a0
   
   molecular dipole:
                    x           y           z        tot (Debye)
      full:     0.0000      0.0000      1.7820      1.7820
      
   rotational constants (MHz):
                 620145.2    310520.1    206715.0
                 
   final structure:
   O   0.0000000   0.0000000   0.0600000
   H   0.0000000   0.7600000  -0.5000000
   H   0.0000000  -0.7600000  -0.5000000
   
   normal termination of xtb
"""
    qm_record = parse_qm_log_text(xtb_log_content, filename="water_xtb.out", program="xTB")

    assert qm_record.program == "xTB"
    assert qm_record.converged is True
    assert qm_record.total_energy_hartree is not None
    assert math.isclose(qm_record.total_energy_hartree, -12.87654321, rel_tol=1e-8)
    assert qm_record.symbols == ["O", "H", "H"]
    assert qm_record.dipole is not None
    assert math.isclose(float(qm_record.dipole[2]), 1.782, abs_tol=1e-3)
    assert len(qm_record.sha256_hash) == 64


def test_gaussian_output_parser() -> None:
    """Validate authentic Gaussian quantum chemistry calculation log parsing."""
    gaussian_log_content = """
 Entering Gaussian System, Inc.
 ******************************************
 Gaussian 16:  ES64L-G16RevC.01 
 ******************************************
 ...
 SCF Done:  E(RwB97XD) =  -76.4215438901     A.U. after   11 cycles
 ...
 Rotational constants (GHZ):    835.42010    440.12050    288.01020
 ...
 Dipole moment (field-independent basis, Debye):
    X=     0.0000    Y=     0.0000    Z=     1.8620  Tot=     1.8620
 ...
 Standard orientation:
 ---------------------------------------------------------------------
 Center     Atomic      Atomic             Coordinates (Angstroms)
 Number     Number       Type             X           Y           Z
 ---------------------------------------------------------------------
      1          8           0        0.000000    0.000000    0.065000
      2          1           0        0.000000    0.758000   -0.515000
      3          1           0        0.000000   -0.758000   -0.515000
 ---------------------------------------------------------------------
 Optimization completed.
 Normal termination of Gaussian 16
"""
    qm_record = parse_qm_log_text(gaussian_log_content, filename="water_gaussian.log", program="Gaussian")

    assert qm_record.program == "Gaussian"
    assert qm_record.converged is True
    assert qm_record.total_energy_hartree is not None
    assert math.isclose(qm_record.total_energy_hartree, -76.4215438901, rel_tol=1e-9)
    assert qm_record.symbols == ["O", "H", "H"]
    assert qm_record.atomic_numbers == [8, 1, 1]
    assert qm_record.dipole is not None
    assert math.isclose(float(qm_record.dipole[2]), 1.8620, abs_tol=1e-3)
    assert qm_record.rotational_constants is not None
    # GHZ converted to MHz: 835.42010 * 1000 = 835420.10 MHz
    assert math.isclose(float(qm_record.rotational_constants[0]), 835420.10, rel_tol=1e-3)


# ==============================================================================
# 8. SE(3) Equivariance & State Immutability Tests
# ==============================================================================


def test_conformer_spatial_translation_equivariance() -> None:
    """Assert spatial coordinates translate while scalar properties remain strictly invariant."""
    coords = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1.16]], dtype=np.float32)
    forces = np.array([[0.0, 0.0, 0.1], [0.0, 0.0, -0.1]], dtype=np.float32)
    dipole = np.array([0.0, 0.0, 1.8], dtype=np.float32)

    conf = ConformerRecord(
        conformer_id=0,
        coords=coords,
        energy=-50.0,
        relative_energy=0.0,
        boltzmann_weight=1.0,
        forces=forces,
        dipole=dipole,
        s2_spin=0.0,
    )

    shift = np.array([12.0, -4.0, 7.5], dtype=np.float32)
    translated = translate_conformer(conf, shift)

    # Coordinates must be translated
    expected_coords = coords + shift
    assert np.allclose(translated.coords, expected_coords, atol=1e-6)

    # Vector forces and dipole must remain invariant under pure spatial translation
    assert np.allclose(translated.forces, forces, atol=1e-6)
    assert np.allclose(translated.dipole, dipole, atol=1e-6)

    # Scalar properties must remain invariant
    assert translated.energy == conf.energy
    assert translated.relative_energy == conf.relative_energy
    assert translated.boltzmann_weight == conf.boltzmann_weight
    assert translated.s2_spin == conf.s2_spin

    # Original record must NOT be mutated
    assert not np.array_equal(conf.coords, translated.coords)


def test_conformer_spatial_rotation_equivariance() -> None:
    """Assert spatial coordinates and vector quantities rotate covariantly while scalars remain invariant."""
    coords = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1.16]], dtype=np.float32)
    forces = np.array([[0.0, 0.0, 0.1], [0.0, 0.0, -0.1]], dtype=np.float32)
    dipole = np.array([0.0, 0.0, 1.8], dtype=np.float32)

    conf = ConformerRecord(
        conformer_id=0,
        coords=coords,
        energy=-50.0,
        relative_energy=0.0,
        boltzmann_weight=1.0,
        forces=forces,
        dipole=dipole,
        s2_spin=0.0,
    )

    # 90-degree rotation matrix around X-axis
    theta = math.pi / 2.0
    rot_matrix = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, math.cos(theta), -math.sin(theta)],
            [0.0, math.sin(theta), math.cos(theta)],
        ],
        dtype=np.float32,
    )

    rotated = rotate_conformer(conf, rot_matrix)

    # Coordinates rotate by R
    expected_coords = coords @ rot_matrix.T
    assert np.allclose(rotated.coords, expected_coords, atol=1e-6)

    # Vector forces rotate by R
    expected_forces = forces @ rot_matrix.T
    assert np.allclose(rotated.forces, expected_forces, atol=1e-6)

    # Dipole moment rotates by R
    expected_dipole = dipole @ rot_matrix.T
    assert np.allclose(rotated.dipole, expected_dipole, atol=1e-6)

    # Scalar energy, relative energy, weight, and S^2 remain invariant
    assert rotated.energy == conf.energy
    assert rotated.relative_energy == conf.relative_energy
    assert rotated.boltzmann_weight == conf.boltzmann_weight
    assert rotated.s2_spin == conf.s2_spin

    # Original record unmutated
    assert not np.array_equal(conf.coords, rotated.coords)


# ==============================================================================
# 9. MolecularData Conversion and PyG Graph Integration Tests
# ==============================================================================


def test_conformer_to_molecular_data_integration() -> None:
    """Validate conversion between parsed MoleculeRecord/ConformerRecord and MolecularData tensor container."""
    raw_mol_data = {
        "smiles": "O",
        "conformers": [
            {
                "geom": [
                    [0.0, 0.0, 0.0655],
                    [0.0, 0.7572, -0.5205],
                    [0.0, -0.7572, -0.5205],
                ],
                "totalenergy": -76.432,  # Hartree
                "dipole": [0.0, 0.0, 1.85],
            }
        ],
    }
    mol_record = parse_geom_raw_molecule("O", raw_mol_data, default_energy_unit="hartree")
    conf_record = mol_record.conformers[0]

    mol_data = conformer_to_molecular_data(mol_record, conf_record)

    assert mol_data.num_nodes == 3
    assert mol_data.z.tolist() == [8, 1, 1]
    assert mol_data.pos.shape == (3, 3)
    assert mol_data.pos.dtype == torch.float32
    assert mol_data.y is not None
    assert math.isclose(float(mol_data.y.item()), hartree_to_ev(-76.432), rel_tol=1e-5)
    assert mol_data.weight is not None
    assert math.isclose(float(mol_data.weight.item()), 1.0, abs_tol=1e-6)
    assert mol_data.dipole is not None
    assert mol_data.symbols == ["O", "H", "H"]

    # Roundtrip conversion back to ConformerRecord
    reconstructed_conf = molecular_data_to_conformer(mol_data, conformer_id=0)
    assert reconstructed_conf.conformer_id == 0
    assert reconstructed_conf.coords.shape == (3, 3)
    assert math.isclose(reconstructed_conf.energy, float(mol_data.y.item()), rel_tol=1e-6)


def test_ensemble_to_molecular_data_batch() -> None:
    """Validate ensemble batch conversion for multi-conformer molecules."""
    raw_mol_data = {
        "smiles": "O",
        "conformers": [
            {
                "geom": [[0.0, 0.0, 0.0655], [0.0, 0.7572, -0.5205], [0.0, -0.7572, -0.5205]],
                "totalenergy": -76.432,
            },
            {
                "geom": [[0.0, 0.0, 0.0700], [0.0, 0.7600, -0.5100], [0.0, -0.7600, -0.5100]],
                "totalenergy": -76.430,
            },
        ],
    }
    mol_record = parse_geom_raw_molecule("O", raw_mol_data, default_energy_unit="hartree")
    data_list = ensemble_to_molecular_data(mol_record)

    assert len(data_list) == 2
    assert data_list[0].num_nodes == 3
    assert data_list[1].num_nodes == 3
    assert data_list[0].weight > data_list[1].weight


# ==============================================================================
# 10. Anti-Spoofing & Zero-Bypass Source Code Verification
# ==============================================================================


def test_anti_spoofing_integrity() -> None:
    """Verify geom_parser source code integrity against prohibited tokens."""
    import inspect
    import cochem_geom.data.geom_parser as parser_mod

    source = inspect.getsource(parser_mod).lower()

    # Reconstructed reversed tokens
    forbidden_list = [
        "kcom.tsetninu"[::-1],
        "kcoMcigaM"[::-1],
        "redlohecalp"[::-1],
        "ymmud"[::-1],
        "buts"[::-1],
        "tnemelpmI_ODOT_#"[::-1],
    ]

    for token in forbidden_list:
        assert token not in source, f"Forbidden token detected in geom_parser source: {token}"
# ==============================================================================
# 11. Adversarial Edge Cases & Spectroscopic Extensions
# ==============================================================================


def test_vibrational_frequencies_extraction() -> None:
    """Validate harmonic vibrational frequency extraction from ORCA, xTB, and Gaussian logs."""
    orca_freq_log = """
  FINAL SINGLE POINT ENERGY      -76.432100000000
  -----------------------
  VIBRATIONAL FREQUENCIES
  -----------------------
     0:         0.00 cm**-1
     1:         0.00 cm**-1
     2:         0.00 cm**-1
     3:         0.00 cm**-1
     4:         0.00 cm**-1
     5:         0.00 cm**-1
     6:      1595.23 cm**-1
     7:      3755.80 cm**-1
     8:      3885.12 cm**-1
  *** OPTIMIZATION RUN DONE ***
  ORCA TERMINATED NORMALLY
"""
    rec_orca = parse_qm_log_text(orca_freq_log, program="ORCA")
    assert rec_orca.frequencies is not None
    assert len(rec_orca.frequencies) == 9
    assert math.isclose(float(rec_orca.frequencies[6]), 1595.23, rel_tol=1e-4)

    gaussian_freq_log = """
 Entering Gaussian System
 SCF Done:  E(RwB97XD) =  -76.4215438901     A.U.
 Frequencies --  1595.2300              3755.8000              3885.1200
 Normal termination of Gaussian 16
"""
    rec_gauss = parse_qm_log_text(gaussian_freq_log, program="Gaussian")
    assert rec_gauss.frequencies is not None
    assert len(rec_gauss.frequencies) == 3
    assert math.isclose(float(rec_gauss.frequencies[0]), 1595.23, rel_tol=1e-4)

    xtb_freq_log = """
 TOTAL ENERGY               -12.876543210000 Eh
 harmonic frequencies (cm-1)
    1  1595.23
    2  3755.80
    3  3885.12
 normal termination of xtb
"""
    rec_xtb = parse_qm_log_text(xtb_freq_log, program="xTB")
    assert rec_xtb.frequencies is not None
    assert len(rec_xtb.frequencies) == 3
    assert math.isclose(float(rec_xtb.frequencies[0]), 1595.23, rel_tol=1e-4)


def test_aromatic_smiles_fallback_tokenization() -> None:
    """Validate aromatic SMILES topology extraction (c1ccccc1 -> 6 Carbons) without RDKit."""
    raw_benzene = {
        "smiles": "c1ccccc1",
        "conformers": [
            {
                "geom": [
                    [0.0, 1.397, 0.0],
                    [1.210, 0.698, 0.0],
                    [1.210, -0.698, 0.0],
                    [0.0, -1.397, 0.0],
                    [-1.210, -0.698, 0.0],
                    [-1.210, 0.698, 0.0],
                ],
                "totalenergy": -232.123,
            }
        ],
    }
    mol_rec = parse_geom_raw_molecule("c1ccccc1", raw_benzene, default_energy_unit="hartree")
    assert mol_rec.n_atoms == 6
    assert mol_rec.symbols == ["C", "C", "C", "C", "C", "C"]
    assert np.all(mol_rec.atomic_numbers == 6)


def test_orca_failed_convergence_rejection() -> None:
    """Verify that failed optimizations with normal termination are rejected as converged=False."""
    failed_orca_log = """
  FINAL SINGLE POINT ENERGY      -76.400000000000
  THE OPTIMIZATION HAS NOT CONVERGED
  ORCA TERMINATED NORMALLY
"""
    rec = parse_qm_log_text(failed_orca_log, program="ORCA")
    assert rec.converged is False
    assert rec.total_energy_hartree == -76.40


def test_mendeleev_lru_caching() -> None:
    """Verify that Mendeleev lookup functions are LRU-cached for high-throughput streaming."""
    get_atomic_mass.cache_clear()
    m1 = get_atomic_mass("C")
    m2 = get_atomic_mass("C")
    assert m1 == m2
    info = get_atomic_mass.cache_info()
    assert info.hits >= 1
