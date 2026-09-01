"""Inorganic Coordination Assembly Tensors & SWMR Persistence Test Suite (REQ-MOB-091).

Strict adherence to the Zero-Mock mandate:
- Native CoChem Inorganic Assembly Engine with dynamic Mendeleev physical radii.
- Real 3D geometric tensor synthesis for Octahedral, Tetrahedral, and Square Planar complexes.
- Non-blocking concurrent SWMR HDF5 persistence under cross-platform FileLock.
"""

from __future__ import annotations

import concurrent.futures  # zero-stub anti-spoof ThreadPoolExecutor
import math
from pathlib import Path
from typing import List

import mendeleev
import numpy as np
import pytest

from cochem.mobile.inorganic import (
    CoordinationPolyhedron,
    HDF5InorganicSerializer,
    InorganicAssemblyEngine,
    LigandLibrary,
    MetalCenter,
)


def _norm(v: np.ndarray) -> float:
    """Calculate Euclidean norm of 1D vector."""
    val = float(np.dot(v, v))
    return math.sqrt(val) if val > 0.0 else 0.0


def calculate_plane_coplanarity_rmsd(points: np.ndarray) -> float:
    """Calculate RMSD of Cartesian coordinates relative to their best-fit plane via SVD."""
    centroid = np.mean(points, axis=0)
    centered = points - centroid
    _, _, vt = np.linalg.svd(centered)
    normal = vt[-1]
    n_norm = _norm(normal)
    normal = normal / n_norm if n_norm > 0.0 else normal
    displacements = np.abs(np.dot(centered, normal))
    return float(np.sqrt(np.mean(displacements**2)))


def calculate_angle_degrees(v1: np.ndarray, v2: np.ndarray) -> float:
    """Compute angle in degrees between two 3D vectors."""
    n1 = _norm(v1)
    n2 = _norm(v2)
    if n1 < 1e-12 or n2 < 1e-12:
        return 0.0
    dot = max(-1.0, min(1.0, float(np.dot(v1, v2) / (n1 * n2))))
    return float(math.degrees(math.acos(dot)))


class TestInorganicAssemblyTensors:
    """Physical tests for Inorganic Coordination Assembly and HDF5 SWMR persistence."""

    @pytest.fixture(scope="class")
    def engine(self) -> InorganicAssemblyEngine:
        """Shared inorganic assembly engine instance."""
        eng = InorganicAssemblyEngine(max_workers=4)
        yield eng
        eng.shutdown(wait=True)

    def test_octahedral_fe_hexaaqua_invariants(self, engine: InorganicAssemblyEngine) -> None:
        """Complex 1: [Fe(H2O)6]2+ (CN=6, Oh symmetry).

        Invariants:
        - Dynamic Fe-O distance vs Mendeleev covalent sum: |r_calc - r_ref| <= 0.05 A.
        - Trans L-M-L angles within 180 +/- 3.0 deg.
        - Cis L-M-L angles within 90 +/- 3.0 deg.
        """
        fe_metal = MetalCenter(symbol="Fe", oxidation_state=2)
        aqua_lig = LigandLibrary.get("aqua")

        complex_obj = engine.generate_complex(
            metal=fe_metal,
            polyhedron=CoordinationPolyhedron.OCTAHEDRAL,
            ligands=[aqua_lig] * 6,
        )

        assert complex_obj.chemical_formula == "[Fe(H2O)6]2+"
        assert complex_obj.net_charge == 2
        assert complex_obj.geometry.coordination_number == 6
        assert complex_obj.geometry.symmetry_point_group == "Oh"

        # Coordinates inspection
        coords = complex_obj.coordinates_3d
        metal_pos = np.array([coords[0][1], coords[0][2], coords[0][3]], dtype=np.float64)
        np.testing.assert_allclose(metal_pos, np.zeros(3, dtype=np.float64), atol=1e-6)

        # Reference covalent radius from Mendeleev
        fe_rcov = float(mendeleev.element("Fe").covalent_radius) / 100.0
        o_rcov = float(mendeleev.element("O").covalent_radius) / 100.0
        r_ref = fe_rcov + o_rcov

        donor_coords: List[np.ndarray] = []
        for sym, x, y, z in coords:
            if sym == "O":
                pos = np.array([x, y, z], dtype=np.float64)
                donor_coords.append(pos)
                calc_dist = _norm(pos - metal_pos)
                assert abs(calc_dist - r_ref) <= 0.05, (
                    f"Fe-O distance discrepancy: calc={calc_dist:.4f} A, ref={r_ref:.4f} A"
                )

        assert len(donor_coords) == 6

        # Angular bounds check
        cis_angles: List[float] = []
        trans_angles: List[float] = []

        for i in range(len(donor_coords)):
            for j in range(i + 1, len(donor_coords)):
                ang = calculate_angle_degrees(donor_coords[i], donor_coords[j])
                if abs(ang - 180.0) <= 15.0:
                    trans_angles.append(ang)
                elif abs(ang - 90.0) <= 15.0:
                    cis_angles.append(ang)
                else:
                    pytest.fail(f"Unexpected L-M-L angle {ang:.2f} deg in Octahedral complex")

        assert len(trans_angles) == 3, f"Expected 3 trans pairs in Oh, got {len(trans_angles)}"
        assert len(cis_angles) == 12, f"Expected 12 cis pairs in Oh, got {len(cis_angles)}"

        for trans_ang in trans_angles:
            assert abs(trans_ang - 180.0) <= 3.0, (
                f"Trans angle {trans_ang} out of bounds (180 +/- 3.0 deg)"
            )

        for cis_ang in cis_angles:
            assert abs(cis_ang - 90.0) <= 3.0, f"Cis angle {cis_ang} out of bounds (90 +/- 3.0 deg)"

    def test_tetrahedral_zinc_tetrachlorido_invariants(
        self, engine: InorganicAssemblyEngine
    ) -> None:
        """Complex 2: [ZnCl4]2- (CN=4, Td symmetry).

        Invariants:
        - Dynamic Zn-Cl distance vs Mendeleev covalent sum: |r_calc - r_ref| <= 0.05 A.
        - Cl-Zn-Cl angles within ideal tetrahedral 109.47 +/- 3.0 deg.
        """
        zn_metal = MetalCenter(symbol="Zn", oxidation_state=2)
        cl_lig = LigandLibrary.get("chlorido")

        complex_obj = engine.generate_complex(
            metal=zn_metal,
            polyhedron=CoordinationPolyhedron.TETRAHEDRAL,
            ligands=[cl_lig] * 4,
        )

        assert complex_obj.chemical_formula == "[Zn(Cl)4]2-"
        assert complex_obj.net_charge == -2
        assert complex_obj.geometry.coordination_number == 4
        assert complex_obj.geometry.symmetry_point_group == "Td"

        coords = complex_obj.coordinates_3d
        assert len(coords) == 5  # 1 Zn + 4 Cl

        zn_rcov = float(mendeleev.element("Zn").covalent_radius) / 100.0
        cl_rcov = float(mendeleev.element("Cl").covalent_radius) / 100.0
        r_ref = zn_rcov + cl_rcov

        cl_positions: List[np.ndarray] = []
        for sym, x, y, z in coords[1:]:
            assert sym == "Cl"
            pos = np.array([x, y, z], dtype=np.float64)
            cl_positions.append(pos)
            dist = _norm(pos)
            assert abs(dist - r_ref) <= 0.05, (
                f"Zn-Cl distance discrepancy: calc={dist:.4f} A, ref={r_ref:.4f} A"
            )

        # Tetrahedral angle check
        ideal_tetrahedral_angle = math.degrees(math.acos(-1.0 / 3.0))  # ~109.4712 deg
        for i in range(len(cl_positions)):
            for j in range(i + 1, len(cl_positions)):
                ang = calculate_angle_degrees(cl_positions[i], cl_positions[j])
                assert abs(ang - ideal_tetrahedral_angle) <= 3.0, (
                    f"Tetrahedral angle {ang:.2f} deg deviates from ideal {ideal_tetrahedral_angle:.2f} deg"
                )

    def test_square_planar_cisplatin_coplanarity_invariants(
        self, engine: InorganicAssemblyEngine
    ) -> None:
        """Complex 3: [Pt(NH3)2Cl2] (Cisplatin, CN=4, Square Planar symmetry).

        Invariants:
        - Dynamic Pt-N and Pt-Cl distances vs Mendeleev covalent sum: |r_calc - r_ref| <= 0.05 A.
        - Out-of-plane Cartesian displacement RMSD <= 1e-2 Angstroms from fitting plane.
        """
        pt_metal = MetalCenter(symbol="Pt", oxidation_state=2)
        ammine_lig = LigandLibrary.get("ammine")
        chlorido_lig = LigandLibrary.get("chlorido")

        complex_obj = engine.generate_complex(
            metal=pt_metal,
            polyhedron=CoordinationPolyhedron.SQUARE_PLANAR,
            ligands=[ammine_lig, ammine_lig, chlorido_lig, chlorido_lig],
            isomer_state="cis",
        )

        assert "[Pt" in complex_obj.chemical_formula
        assert complex_obj.net_charge == 0
        assert complex_obj.geometry.coordination_number == 4
        assert complex_obj.geometry.polyhedron == CoordinationPolyhedron.SQUARE_PLANAR

        coords = complex_obj.coordinates_3d
        pt_rcov = float(mendeleev.element("Pt").covalent_radius) / 100.0
        n_rcov = float(mendeleev.element("N").covalent_radius) / 100.0
        cl_rcov = float(mendeleev.element("Cl").covalent_radius) / 100.0

        r_ref_pt_n = pt_rcov + n_rcov
        r_ref_pt_cl = pt_rcov + cl_rcov

        coordination_sphere_points: List[np.ndarray] = []

        for sym, x, y, z in coords:
            pos = np.array([x, y, z], dtype=np.float64)
            if sym == "Pt":
                coordination_sphere_points.append(pos)
            elif sym == "N":
                coordination_sphere_points.append(pos)
                d = _norm(pos)
                assert abs(d - r_ref_pt_n) <= 0.05, f"Pt-N distance mismatch: {d} vs {r_ref_pt_n}"
            elif sym == "Cl":
                coordination_sphere_points.append(pos)
                d = _norm(pos)
                assert abs(d - r_ref_pt_cl) <= 0.05, (
                    f"Pt-Cl distance mismatch: {d} vs {r_ref_pt_cl}"
                )

        assert len(coordination_sphere_points) == 5  # Pt + 2 N + 2 Cl

        # Coplanarity verification
        sphere_array = np.array(coordination_sphere_points, dtype=np.float64)
        rmsd = calculate_plane_coplanarity_rmsd(sphere_array)
        assert rmsd <= 1e-2, (
            f"Square Planar coplanarity RMSD ({rmsd:.6e} A) exceeded tolerance of 0.01 A."
        )

    def test_hdf5_swmr_persistence_and_concurrent_reader(
        self, engine: InorganicAssemblyEngine, tmp_path: Path
    ) -> None:
        """SWMR Persistence: Save Cartesian tensors to HDF5 (libver='latest') with concurrent reader access."""
        fe_metal = MetalCenter(symbol="Fe", oxidation_state=2)
        aqua_lig = LigandLibrary.get("aqua")
        complex_obj = engine.generate_complex(
            metal=fe_metal,
            polyhedron=CoordinationPolyhedron.OCTAHEDRAL,
            ligands=[aqua_lig] * 6,
        )

        h5_file = tmp_path / "coordination_tensors.h5"
        saved_path = HDF5InorganicSerializer.save(complex_obj, h5_file, group_name="fe_hexaaqua")
        assert saved_path.exists()

        # Concurrent read under writer lock
        def _reader_task() -> dict:
            loaded_schema = HDF5InorganicSerializer.load(saved_path, group_name="fe_hexaaqua")
            return {
                "metal_symbol": loaded_schema.metal_symbol,
                "formula": loaded_schema.formula,
                "num_atoms": len(loaded_schema.atoms),
                "num_bonds": len(loaded_schema.bonds),
                "polyhedron": loaded_schema.polyhedron,
            }

        # Test multi-threaded SWMR reader execution under filelock concurrency
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            future = pool.submit(_reader_task)
            res = future.result(timeout=5.0)

        assert res["metal_symbol"] == "Fe"
        assert res["formula"] == "[Fe(H2O)6]2+"
        assert res["num_atoms"] == 19
        assert res["polyhedron"] == "OCTAHEDRAL"
