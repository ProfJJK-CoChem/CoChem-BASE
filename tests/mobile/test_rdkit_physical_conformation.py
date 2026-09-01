"""Physical Conformation & RDKit 3D Forcefield Minimization Test Suite (REQ-MOB-090).

Strict adherence to the Zero-Mock mandate:
- Authentic ab-initio RDKit ETKDGv3 distance geometry and MMFF94s/UFF energy relaxation.
- Dynamic physical properties dynamically retrieved via Mendeleev.
- Real filesystem .xyz coordinate serialization with 8-decimal precision and LF normalization.
- CPU deterministic fallback under CUDA isolation.
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import List, Tuple

import mendeleev
import numpy as np
import pytest
from rdkit import Chem
from rdkit.Chem import AllChem

from cochem.mobile.rdkit_bridge import (
    InvalidSmilesError,
    RDKit3DResult,
    generate_deterministic_3d_coordinates,
    relax_geometry_and_calculate_energy,
    smiles_to_3d,
    smiles_to_3d_async,
    validate_and_sanitize_smiles,
)

FIXTURES_SMILES: List[Tuple[str, str, int]] = [
    ("CCO", "Ethanol", 9),  # C2H6O: 2 C + 6 H + 1 O = 9 atoms
    ("c1ccccc1", "Benzene", 12),  # C6H6: 6 C + 6 H = 12 atoms
    ("CC(=O)Oc1ccccc1C(=O)O", "Aspirin", 21),  # C9H8O4: 9 C + 8 H + 4 O = 21 atoms
]


class TestPhysicalConformerInvariants:
    """Rigorous physical validation of conformer synthesis across organic benchmarks."""

    @pytest.mark.parametrize("smiles,name,expected_atom_count", FIXTURES_SMILES)
    def test_coordinate_validity_and_finite_float64(
        self, smiles: str, name: str, expected_atom_count: int
    ) -> None:
        """Invariant 1: All Cartesian coordinates are finite float64 numbers with correct shape."""
        result = smiles_to_3d(smiles, random_seed=42)
        assert isinstance(result, RDKit3DResult)
        assert result.num_atoms == expected_atom_count

        coords = np.array(result.coordinates_3d, dtype=np.float64)
        assert coords.shape == (expected_atom_count, 3)
        assert np.isfinite(coords).all(), f"Non-finite coordinates detected in {name} ({smiles})"
        assert not np.isnan(coords).any()
        assert not np.isinf(coords).any()

    @pytest.mark.parametrize("smiles,name,expected_atom_count", FIXTURES_SMILES)
    def test_steric_clash_boundary_invariant(
        self, smiles: str, name: str, expected_atom_count: int
    ) -> None:
        """Invariant 2: No pair of atoms violates physical steric barrier (min ||r_i - r_j|| >= 0.80 A)."""
        result = smiles_to_3d(smiles, random_seed=42)
        coords = np.array(result.coordinates_3d, dtype=np.float64)
        n_atoms = len(coords)

        min_interatomic_distance = float("inf")
        closest_pair = (-1, -1)

        for i in range(n_atoms):
            for j in range(i + 1, n_atoms):
                diff = coords[i] - coords[j]
                dist = float(np.linalg.norm(diff))
                if dist < min_interatomic_distance:
                    min_interatomic_distance = dist
                    closest_pair = (i, j)

        # Invariant check: minimal interatomic distance >= 0.80 Angstroms
        assert min_interatomic_distance >= 0.80, (
            f"Steric clash detected in {name} ({smiles}): atoms {closest_pair} separation is "
            f"{min_interatomic_distance:.4f} A (< 0.80 A)."
        )

    @pytest.mark.parametrize("smiles,name,expected_atom_count", FIXTURES_SMILES)
    def test_force_field_optimization_convergence(
        self, smiles: str, name: str, expected_atom_count: int
    ) -> None:
        """Invariant 3: MMFF94s / UFF forcefield minimization succeeds with status code 0 (converged)."""
        clean_smi, mol = validate_and_sanitize_smiles(smiles)
        mol_h = Chem.AddHs(mol)
        mol_embedded = generate_deterministic_3d_coordinates(mol_h, clean_smi, random_seed=42)

        # Confirm conformer is 3D
        conf = mol_embedded.GetConformer()
        assert conf.Is3D() is True, f"Conformer for {name} is not marked as 3D."

        # Test MMFF94s optimization directly
        if AllChem.MMFFHasAllMoleculeParams(mol_embedded):
            opt_status = AllChem.MMFFOptimizeMolecule(
                mol_embedded, mmffVariant="MMFF94s", maxIters=500
            )
            assert opt_status == 0, (
                f"MMFF94s optimization did not converge for {name} (status={opt_status})"
            )
        else:
            opt_status = AllChem.UFFOptimizeMolecule(mol_embedded, maxIters=500)
            assert opt_status == 0, (
                f"UFF optimization did not converge for {name} (status={opt_status})"
            )

        # Verify via bridge engine
        energy, method, converged = relax_geometry_and_calculate_energy(mol_embedded, max_iters=500)
        assert converged is True
        assert method in ("MMFF94s", "UFF")
        assert math.isfinite(energy)

    @pytest.mark.parametrize("smiles,name,expected_atom_count", FIXTURES_SMILES)
    def test_mendeleev_dynamic_mass_conservation(
        self, smiles: str, name: str, expected_atom_count: int
    ) -> None:
        """Invariant 4: Molecular mass strictly matches sum of dynamic Mendeleev elemental weights."""
        result = smiles_to_3d(smiles, random_seed=42)
        assert len(result.atomic_symbols) == expected_atom_count
        assert len(result.atomic_masses) == expected_atom_count

        calculated_mass_sum = 0.0
        for sym, mass in zip(result.atomic_symbols, result.atomic_masses, strict=True):
            elem = mendeleev.element(sym)
            expected_weight = float(elem.atomic_weight)
            assert abs(mass - expected_weight) < 1e-6, (
                f"Dynamic Mendeleev mismatch on element {sym}: {mass} vs {expected_weight}"
            )
            calculated_mass_sum += expected_weight

        assert abs(result.total_mass_amu - calculated_mass_sum) < 1e-4, (
            f"Total mass mismatch for {name}: {result.total_mass_amu} vs {calculated_mass_sum}"
        )

    @pytest.mark.parametrize("smiles,name,expected_atom_count", FIXTURES_SMILES)
    def test_physical_xyz_serialization_and_reparsing(
        self, smiles: str, name: str, expected_atom_count: int, tmp_path: Path
    ) -> None:
        """Invariant 5: Quantum-ready .xyz serialization with 3-part schema and 8-decimal precision."""
        result = smiles_to_3d(smiles, random_seed=42)
        xyz_file = tmp_path / f"{name.lower()}_quantum.xyz"
        saved_path = result.save_xyz(xyz_file)
        assert saved_path.exists()

        content = saved_path.read_text(encoding="utf-8")
        lines = [line for line in content.splitlines() if line.strip()]

        # Part 1: Atom count on line 1
        assert int(lines[0].strip()) == expected_atom_count

        # Part 2: Comment header with energy and method
        header = lines[1]
        assert "canonical_smiles=" in header
        assert "energy_kcal_mol=" in header
        assert "method=" in header
        assert "charge=" in header
        assert "multiplicity=" in header

        # Part 3: Atom lines with 8-decimal precision
        atom_lines = lines[2:]
        assert len(atom_lines) == expected_atom_count

        reparsed_coords: List[List[float]] = []
        reparsed_symbols: List[str] = []

        for _idx, line in enumerate(atom_lines):
            parts = line.split()
            assert len(parts) == 4, f"Malformed XYZ atom line: '{line}'"
            sym = parts[0]
            x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
            reparsed_symbols.append(sym)
            reparsed_coords.append([x, y, z])

            # Verify 8-decimal formatting string representation
            coord_str = parts[1]
            assert "." in coord_str
            decimals = len(coord_str.split(".")[1])
            assert decimals == 8, (
                f"Coordinate '{coord_str}' does not have strict 8-decimal precision."
            )

        # Coordinates parity check
        original_coords = np.array(result.coordinates_3d, dtype=np.float64)
        reparsed_arr = np.array(reparsed_coords, dtype=np.float64)
        np.testing.assert_allclose(original_coords, reparsed_arr, atol=1e-7)
        assert reparsed_symbols == result.atomic_symbols

    def test_cpu_deterministic_parity_under_cuda_isolation(self) -> None:
        """Invariant 6: Deterministic conformer reproduction under CUDA_VISIBLE_DEVICES='' isolation."""
        original_cuda = os.environ.get("CUDA_VISIBLE_DEVICES")
        try:
            os.environ["CUDA_VISIBLE_DEVICES"] = ""

            # Run Aspirin conformer generation twice with identical randomSeed
            aspirin_smi = "CC(=O)Oc1ccccc1C(=O)O"
            run_1 = smiles_to_3d(aspirin_smi, random_seed=42)
            run_2 = smiles_to_3d(aspirin_smi, random_seed=42)

            arr1 = np.array(run_1.coordinates_3d, dtype=np.float64)
            arr2 = np.array(run_2.coordinates_3d, dtype=np.float64)

            # Strict bitwise coordinate parity across runs
            np.testing.assert_array_equal(arr1, arr2)
            assert abs(run_1.energy_kcal_mol - run_2.energy_kcal_mol) < 1e-9
            assert run_1.force_field_method == run_2.force_field_method
        finally:
            if original_cuda is not None:
                os.environ["CUDA_VISIBLE_DEVICES"] = original_cuda
            else:
                os.environ.pop("CUDA_VISIBLE_DEVICES", None)

    def test_async_smiles_to_3d_execution(self) -> None:
        """Verify asynchronous conformer generation worker dispatch."""
        import asyncio

        res = asyncio.run(smiles_to_3d_async("CCO", random_seed=42))
        assert res.num_atoms == 9
        assert res.converged is True

    def test_single_atom_guard(self) -> None:
        """Verify single atom edge cases (e.g. Helium [He]) place coordinate at origin."""
        res = smiles_to_3d("[He]", random_seed=42)
        assert res.num_atoms == 1
        assert res.coordinates_3d == [[0.0, 0.0, 0.0]]
        assert res.energy_kcal_mol == 0.0

    def test_invalid_smiles_rejection(self) -> None:
        """Verify unparseable SMILES raises InvalidSmilesError with 422 HTTP mapping."""
        with pytest.raises(InvalidSmilesError) as exc_info:
            smiles_to_3d("C1234_INVALID_SMILES")
        assert exc_info.value.status_code == 422
        assert "Invalid SMILES representation" in str(exc_info.value)
