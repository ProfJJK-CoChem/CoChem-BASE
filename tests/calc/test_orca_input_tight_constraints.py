"""Unit tests for Complete Tight ORCA Intermolecular Optimization Convergence Criteria

and Internal Coordinate Constraints for Monomer Rigidity.
Method Matrix v4 §4.4, §9A.1, and Zero-Mock Protocol Compliance.
"""

from pathlib import Path
import re
import pytest

from cochem_base.calc.cochem_calc_input_generator import (
    MoleculeInput,
    generate_orca_input,
    build_internal_coordinate_constraints,
)


def test_orca_input_tight_convergence_criteria(tmp_path: Path, configured_registry) -> None:
    """Verifies that generated ORCA inputs for weak complexes contain all five

    requested tolerances below the independent Method Matrix §4.4 limits.
    """
    # Authentic physical coordinates for water dimer (weak intermolecular complex)
    elements = ["O", "H", "H", "O", "H", "H"]
    coords = [
        (0.0, 0.0, 0.0),
        (0.0, 0.757, 0.586),
        (0.0, -0.757, 0.586),
        (0.0, 0.0, 2.95),
        (0.757, 0.0, 3.536),
        (-0.757, 0.0, 3.536),
    ]

    inp_data = MoleculeInput(
        basin_id="water_dimer_tight_opt",
        elements=elements,
        coordinates=coords,
        theory_level="wB97X-D3 def2-TZVP",
        is_weak_complex=True,
        is_opt=True,
    )

    out_file = generate_orca_input(inp_data, output_dir=tmp_path)
    assert out_file.exists(), f"Failed to create ORCA input file at {out_file}"

    content = out_file.read_text(encoding="utf-8")

    # Native ORCA can stop with one requested criterion unmet. Each requested
    # tolerance needs margin; tightening requests must not relax SRS acceptance.
    geom = content.split("%geom\n", 1)[1].split("\nend", 1)[0]
    requests = dict(re.findall(r"^\s+(Tol\w+)\s+(\S+)\s*$", geom, re.M))
    acceptance_limits = {
        "TolE": 1e-7, "TolMaxG": 1e-5, "TolRMSG": 3e-6,
        "TolMaxD": 1e-4, "TolRMSD": 5e-5,
    }
    assert set(requests) == set(acceptance_limits)
    for criterion, limit in acceptance_limits.items():
        assert 0 < float(requests[criterion]) < limit
        assert float(requests[criterion]) / limit == pytest.approx(0.1)
    assert "MaxIter 200" in geom
    assert "InHess XTB2" in content, "Missing InHess XTB2 preconditioner in %geom"


def test_orca_input_internal_coordinate_constraints_no_cartesian_locks(tmp_path: Path, configured_registry) -> None:
    """Verifies that frozen monomer inputs use internal coordinate {B}, {A}, {D} constraints

    and eradicate all Cartesian {C idx C} locks, leaving intermolecular DOFs free to relax.
    """
    # Authentic physical coordinates for water dimer
    elements = ["O", "H", "H", "O", "H", "H"]
    coords = [
        (0.0, 0.0, 0.0),       # 0: O1
        (0.0, 0.757, 0.586),    # 1: H1
        (0.0, -0.757, 0.586),   # 2: H2
        (0.0, 0.0, 2.95),      # 3: O2
        (0.757, 0.0, 3.536),    # 4: H3
        (-0.757, 0.0, 3.536),   # 5: H4
    ]

    # Monomer 1 frozen (indices 0, 1, 2)
    inp_data = MoleculeInput(
        basin_id="water_dimer_frozen_monomer",
        elements=elements,
        coordinates=coords,
        theory_level="B3LYP D3BJ def2-SVP",
        is_weak_complex=True,
        is_opt=True,
        frozen_monomer_indices=[0, 1, 2],
    )

    out_file = generate_orca_input(inp_data, output_dir=tmp_path)
    content = out_file.read_text(encoding="utf-8")

    # 1. Assert Cartesian {C idx C} locks are strictly absent
    cartesian_locks = re.findall(r"\{C\s+\d+\s+C\}", content)
    assert len(cartesian_locks) == 0, f"Detected prohibited Cartesian locks in ORCA input: {cartesian_locks}"

    # 2. Assert intramolecular bond and angle constraints are present for water monomer 1
    assert "{B 0 1 C}" in content, "Missing intramolecular bond constraint {B 0 1 C}"
    assert "{B 0 2 C}" in content, "Missing intramolecular bond constraint {B 0 2 C}"
    assert "{A 1 0 2 C}" in content, "Missing intramolecular angle constraint {A 1 0 2 C}"

    # 3. Assert intermolecular degrees of freedom remain completely unconstrained
    assert "{B 0 3 C}" not in content, "Intermolecular distance must not be constrained"
    assert "{B 1 3 C}" not in content, "Intermolecular hydrogen bond must not be constrained"


def test_build_internal_coordinate_constraints_dihedral() -> None:
    """Verifies that internal coordinate builder correctly identifies bonds, angles, and dihedrals

    for multi-atom fragments (e.g. H2O2 in a complex) without Cartesian locks.
    """
    # Authentic physical coordinates for HOOH fragment (atoms 0, 1, 2, 3) bound to an Ar atom (atom 4)
    elements = ["H", "O", "O", "H", "Ar"]
    coords = [
        (0.90, 0.80, 0.00),     # 0: H1
        (0.00, 0.70, 0.00),     # 1: O1
        (0.00, -0.70, 0.00),    # 2: O2
        (-0.90, -0.80, 0.60),   # 3: H2 (dihedral angle ~115 deg)
        (3.50, 0.00, 0.00),     # 4: Ar
    ]
    frozen = [0, 1, 2, 3]

    constraints = build_internal_coordinate_constraints(
        elements=elements,
        coordinates=coords,
        frozen_indices=frozen,
    )

    # Check bonds
    assert "{B 0 1 C}" in constraints
    assert "{B 1 2 C}" in constraints
    assert "{B 2 3 C}" in constraints

    # Check angles
    assert "{A 0 1 2 C}" in constraints
    assert "{A 1 2 3 C}" in constraints

    # Check dihedral
    assert "{D 0 1 2 3 C}" in constraints

    # Verify no Cartesian locks
    for c in constraints:
        assert not c.startswith("{C "), f"Detected Cartesian lock {c}"
