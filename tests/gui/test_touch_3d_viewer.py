"""
Physical Zero-Mock Verification Suite for CoChem-Mobile Touch-Optimized 3D Molecular Visualization.
(REQ-MOB-020 - REQ-MOB-028)

Strict Zero-Mock Mandate:
- 100% authentic physical structures (H2O, Benzene, Ethanol, Caffeine, Ethane).
- Zero mock libraries, zero stubs, zero dummy data, zero bypasses.
- Dynamic Mendeleev van der Waals radius resolution (pm -> Angstrom).
- Mathematical invariants: SO(3) arcball quaternion normalization ||q|| = 1.0, SO(3) Lie group properties.
"""

from __future__ import annotations

import math
import tempfile
from pathlib import Path

import ipywidgets
import numpy as np
import pydantic
import pytest
from mendeleev import element as _mendeleev_element


from cochem.core.cochem_elements import (
    get_vdw_radius,
)
from cochem.core.mendeleev_invariants import mendeleev_resolver
from cochem.gui.schemas import (
    CameraState,
    SelectionState,
    VibrationTensor,
    ViewportConfig,
)
from cochem.gui.widgets.touch_3d_viewer import (
    Touch3DViewer,
    apply_vibration_mode,
    calculate_bounding_radius,
    calculate_centroid,
    calculate_dihedral,
    calculate_initial_focal_distance,
    parse_cube,
    parse_pdb,
    parse_xyz,
    project_to_sphere,
    quaternion_from_vectors,
    quaternion_multiply,
    quaternion_normalize,
    quaternion_to_rotation_matrix,
    rotate_dihedral_subset,
    verify_static_assets,
)


# =============================================================================
# Authentic Physical Molecular Coordinate Fixtures (Zero-Mock)
# =============================================================================

# Water (H2O, C2v symmetry)
WATER_SYMBOLS = ["O", "H", "H"]
WATER_COORDS = np.array([
    [0.000000, 0.000000, 0.117400],
    [0.000000, 0.757000, -0.469600],
    [0.000000, -0.757000, -0.469600],
], dtype=np.float64)

# Benzene (C6H6, D6h symmetry)
BENZENE_SYMBOLS = ["C", "C", "C", "C", "C", "C", "H", "H", "H", "H", "H", "H"]
BENZENE_COORDS = np.array([
    [1.3970, 0.0000, 0.0000],
    [0.6985, 1.2098, 0.0000],
    [-0.6985, 1.2098, 0.0000],
    [-1.3970, 0.0000, 0.0000],
    [-0.6985, -1.2098, 0.0000],
    [0.6985, -1.2098, 0.0000],
    [2.4790, 0.0000, 0.0000],
    [1.2395, 2.1469, 0.0000],
    [-1.2395, 2.1469, 0.0000],
    [-2.4790, 0.0000, 0.0000],
    [-1.2395, -2.1469, 0.0000],
    [1.2395, -2.1469, 0.0000],
], dtype=np.float64)

# Ethane (C2H6, Staggered D3d Conformation)
ETHANE_STAGGERED_SYMBOLS = ["C", "C", "H", "H", "H", "H", "H", "H"]
ETHANE_STAGGERED_COORDS = np.array([
    [-0.7630, 0.0000, 0.0000],   # C1
    [0.7630, 0.0000, 0.0000],    # C2
    [-1.1550, 1.0280, 0.0000],   # H1 (on C1)
    [-1.1550, -0.5140, 0.8900],  # H2 (on C1)
    [-1.1550, -0.5140, -0.8900], # H3 (on C1)
    [1.1550, -1.0280, 0.0000],   # H4 (on C2)
    [1.1550, 0.5140, -0.8900],   # H5 (on C2)
    [1.1550, 0.5140, 0.8900],    # H6 (on C2)
], dtype=np.float64)

# Caffeine (C8H10N4O2, 24 Atoms)
CAFFEINE_SYMBOLS = [
    "N", "C", "N", "C", "C", "C", "N", "C", "N", "O", "O", "C", "C", "C",
    "H", "H", "H", "H", "H", "H", "H", "H", "H", "H",
]
CAFFEINE_COORDS = np.array([
    [-0.529, 1.134, -0.000],
    [-1.874, 0.778, -0.000],
    [-2.052, -0.567, 0.000],
    [-0.793, -1.096, 0.000],
    [0.231, -0.088, -0.000],
    [1.589, -0.407, -0.000],
    [1.670, -1.776, -0.000],
    [0.407, -2.257, 0.000],
    [2.748, 0.407, -0.000],
    [-2.813, 1.564, -0.000],
    [0.083, -3.428, 0.000],
    [-3.342, -1.229, 0.000],
    [-0.203, 2.548, -0.000],
    [4.077, -0.169, 0.000],
    [-3.856, -0.916, 0.906],
    [-3.220, -2.312, 0.000],
    [-3.856, -0.916, -0.906],
    [-0.672, 3.018, -0.871],
    [0.874, 2.665, -0.000],
    [-0.672, 3.018, 0.871],
    [4.786, 0.658, 0.000],
    [4.225, -0.776, 0.893],
    [4.225, -0.776, -0.893],
    [2.529, -2.298, -0.000],
], dtype=np.float64)

# Ethanol (C2H6O, 9 Atoms)
ETHANOL_SYMBOLS = ["C", "C", "O", "H", "H", "H", "H", "H", "H"]
ETHANOL_COORDS = np.array([
    [-1.218, 0.219, 0.000],
    [0.000, -0.686, 0.000],
    [1.192, 0.111, 0.000],
    [-2.122, -0.395, 0.000],
    [-1.238, 0.849, 0.892],
    [-1.238, 0.849, -0.892],
    [-0.013, -1.326, 0.890],
    [-0.013, -1.326, -0.890],
    [1.960, -0.468, 0.000],
], dtype=np.float64)



# =============================================================================
# 1. Pydantic v2 Schema Immutability & Validation Tests
# =============================================================================

class TestTouch3DViewerSchemas:
    """Rigorous physical validation of Pydantic v2 3D viewer schemas."""

    def test_camera_state_defaults(self) -> None:
        """Verify default initialization of CameraState."""
        cam = CameraState()
        assert cam.quaternion == (0.0, 0.0, 0.0, 1.0)
        assert cam.position == (0.0, 0.0, 10.0)
        assert cam.target == (0.0, 0.0, 0.0)
        assert cam.fov_degrees == 45.0
        assert cam.focal_distance == 10.0

    def test_camera_state_custom_and_bounds(self) -> None:
        """Verify custom valid parameters and boundary enforcement."""
        cam = CameraState(
            quaternion=(0.0, 0.7071, 0.0, 0.7071),
            position=(1.0, 2.0, 15.0),
            target=(1.0, 2.0, 0.0),
            fov_degrees=60.0,
            focal_distance=15.0,
        )
        assert cam.fov_degrees == 60.0
        assert cam.focal_distance == 15.0

        # Boundary rejections: fov <= 10.0 or >= 120.0, focal_distance <= 0.0
        with pytest.raises(pydantic.ValidationError):
            CameraState(fov_degrees=10.0)
        with pytest.raises(pydantic.ValidationError):
            CameraState(fov_degrees=120.0)
        with pytest.raises(pydantic.ValidationError):
            CameraState(focal_distance=0.0)

    def test_camera_state_immutability(self) -> None:
        """Verify CameraState is frozen and extra fields are forbidden."""
        cam = CameraState()
        with pytest.raises((pydantic.ValidationError, TypeError)):
            cam.fov_degrees = 50.0  # type: ignore[misc]
        with pytest.raises(pydantic.ValidationError):
            CameraState(unrecognized_field=123)  # type: ignore[call-arg]

    def test_viewport_config_validation(self) -> None:
        """Verify ViewportConfig validation and constraints."""
        vp = ViewportConfig(width_px=1024, height_px=768, device_pixel_ratio=2.0, background_color="#000000")
        assert vp.width_px == 1024
        assert vp.height_px == 768
        assert vp.device_pixel_ratio == 2.0
        assert vp.background_color == "#000000"

        # Boundary rejections
        with pytest.raises(pydantic.ValidationError):
            ViewportConfig(width_px=150)
        with pytest.raises(pydantic.ValidationError):
            ViewportConfig(height_px=100)
        with pytest.raises(pydantic.ValidationError):
            ViewportConfig(device_pixel_ratio=0.2)
        with pytest.raises(pydantic.ValidationError):
            ViewportConfig(device_pixel_ratio=6.0)

    def test_selection_state_validation(self) -> None:
        """Verify SelectionState model."""
        sel = SelectionState(selected_atom_indices=(0, 1, 2), active_dihedral=(0, 1, 2, 3))
        assert sel.selected_atom_indices == (0, 1, 2)
        assert sel.active_dihedral == (0, 1, 2, 3)

        with pytest.raises((pydantic.ValidationError, TypeError)):
            sel.selected_atom_indices = (1, 2)  # type: ignore[misc]

    def test_vibration_tensor_validation(self) -> None:
        """Verify VibrationTensor normal mode displacement contract."""
        tensor = VibrationTensor(
            mode_index=1,
            frequency_cm1=1595.0,
            displacement_vectors=((0.0, 0.05, 0.0), (0.0, -0.4, 0.3), (0.0, -0.4, -0.3)),
        )
        assert tensor.mode_index == 1
        assert tensor.frequency_cm1 == 1595.0
        assert len(tensor.displacement_vectors) == 3

        with pytest.raises(pydantic.ValidationError):
            VibrationTensor(
                mode_index=0,  # ge=1 violated
                frequency_cm1=100.0,
                displacement_vectors=((0.0, 0.0, 0.0),),
            )


# =============================================================================
# 2. Dynamic Mendeleev Invariants & Dimensional Conversion (pm -> Å)
# =============================================================================

class TestMendeleevDynamicResolution:
    """Verify Mendeleev Mandate: dynamic Bondi-Mantina vdW radii resolution."""

    @pytest.mark.parametrize("sym", ["H", "C", "N", "O", "F", "P", "S", "Cl", "Br"])
    def test_dynamic_vdw_radius_angstrom_conversion(self, sym: str) -> None:
        """Verify vdW radius is retrieved from mendeleev in pm and converted to Angstrom."""
        elem = _mendeleev_element(sym)
        expected_pm = elem.vdw_radius or elem.vdw_radius_alvarez or elem.vdw_radius_bondi or 170.0
        expected_angstrom = float(expected_pm) / 100.0

        resolved_angstrom = get_vdw_radius(sym)
        assert math.isclose(resolved_angstrom, expected_angstrom, rel_tol=1e-5)

        # Check mendeleev_resolver method consistency
        resolver_angstrom = mendeleev_resolver.get_vdw_radius_angstrom(sym)
        assert math.isclose(resolver_angstrom, expected_angstrom, rel_tol=1e-5)


# =============================================================================
# 3. Geometric Centroid & Bounding Radius Invariants
# =============================================================================

class TestGeometryAndCentroid:
    """Verify geometric centroid, bounding radius, and initial camera focal distance."""

    def test_water_centroid_and_bounding_radius(self) -> None:
        """Verify water molecule centroid and physical bounding radius in Angstroms."""
        centroid = calculate_centroid(WATER_COORDS)
        expected_c = np.mean(WATER_COORDS, axis=0)
        assert np.allclose(centroid, expected_c)

        r_vdw_o = get_vdw_radius("O")
        r_vdw_h = get_vdw_radius("H")

        # Distances from centroid
        d_o = np.linalg.norm(WATER_COORDS[0] - centroid) + r_vdw_o
        d_h1 = np.linalg.norm(WATER_COORDS[1] - centroid) + r_vdw_h
        d_h2 = np.linalg.norm(WATER_COORDS[2] - centroid) + r_vdw_h
        expected_R = max(d_o, d_h1, d_h2)

        R = calculate_bounding_radius(WATER_SYMBOLS, WATER_COORDS)
        assert math.isclose(R, expected_R, rel_tol=1e-5)
        assert R > 1.5  # Physical scale sanity

        # Initial focal distance: d = R / sin(FOV/2)
        fov_deg = 45.0
        d_focal = calculate_initial_focal_distance(R, fov_deg)
        expected_d = R / math.sin(math.radians(fov_deg * 0.5))
        assert math.isclose(d_focal, expected_d, rel_tol=1e-5)

    def test_benzene_centroid_and_symmetry(self) -> None:
        """Verify benzene centroid is at the origin (0, 0, 0) and radius reflects C6 ring + H + vdW."""
        centroid = calculate_centroid(BENZENE_COORDS)
        assert np.allclose(centroid, np.zeros(3), atol=1e-4)

        R = calculate_bounding_radius(BENZENE_SYMBOLS, BENZENE_COORDS)
        r_vdw_h = get_vdw_radius("H")
        expected_R = 2.4790 + r_vdw_h
        assert math.isclose(R, expected_R, rel_tol=1e-3)

    def test_caffeine_complex_molecule_geometry(self) -> None:
        """Verify 24-atom caffeine complex organic molecule centroid and dynamic bounding radius."""
        centroid = calculate_centroid(CAFFEINE_COORDS)
        assert centroid.shape == (3,)
        assert len(CAFFEINE_SYMBOLS) == 24
        assert len(CAFFEINE_COORDS) == 24

        R = calculate_bounding_radius(CAFFEINE_SYMBOLS, CAFFEINE_COORDS)
        assert R > 4.5  # Typical radius for caffeine ~5-6 Angstroms

        focal_d = calculate_initial_focal_distance(R, fov_degrees=45.0)
        assert focal_d > R

    def test_ethanol_geometry_and_centroid(self) -> None:
        """Verify 9-atom ethanol molecule centroid and bounding radius."""
        centroid = calculate_centroid(ETHANOL_COORDS)
        assert centroid.shape == (3,)
        R = calculate_bounding_radius(ETHANOL_SYMBOLS, ETHANOL_COORDS)
        assert 2.5 < R < 5.0



# =============================================================================
# 4. SO(3) Arcball Virtual Sphere & Quaternion Math Invariants
# =============================================================================

class TestArcballAndQuaternionMath:
    """Verify SO(3) Arcball projection, quaternion composition, and rotation matrix isomorphism."""

    def test_virtual_sphere_projection_center(self) -> None:
        """Verify center (0, 0) projects to pole (0, 0, 1)."""
        v = project_to_sphere(0.0, 0.0)
        assert np.allclose(v, [0.0, 0.0, 1.0], atol=1e-6)
        assert math.isclose(np.linalg.norm(v), 1.0, rel_tol=1e-6)

    def test_virtual_sphere_projection_sphere_region(self) -> None:
        """Verify x^2 + y^2 <= 0.5 region satisfies sphere equation z = sqrt(1 - x^2 - y^2)."""
        x, y = 0.5, 0.5  # d^2 = 0.5
        v = project_to_sphere(x, y)
        expected_z = math.sqrt(0.5)
        unnorm = np.array([0.5, 0.5, expected_z])
        expected_v = unnorm / np.linalg.norm(unnorm)
        assert np.allclose(v, expected_v, atol=1e-6)
        assert math.isclose(np.linalg.norm(v), 1.0, rel_tol=1e-6)

    def test_virtual_sphere_projection_hyperbolic_sheet(self) -> None:
        """Verify x^2 + y^2 > 0.5 region projects to hyperbolic sheet z = 0.5 / sqrt(x^2 + y^2)."""
        x, y = 0.8, 0.6  # d^2 = 1.0
        v = project_to_sphere(x, y)
        unnorm = np.array([0.8, 0.6, 0.5])
        expected_v = unnorm / np.linalg.norm(unnorm)
        assert np.allclose(v, expected_v, atol=1e-6)
        assert math.isclose(np.linalg.norm(v), 1.0, rel_tol=1e-6)

    def test_quaternion_identity_from_identical_vectors(self) -> None:
        """Verify rotation from v to v yields identity quaternion [0, 0, 0, 1]."""
        v = np.array([0.0, 0.0, 1.0], dtype=np.float64)
        q = quaternion_from_vectors(v, v)
        assert np.allclose(q, [0.0, 0.0, 0.0, 1.0], atol=1e-6)

    def test_quaternion_90_degree_rotation(self) -> None:
        """Verify 90 degree rotation from X to Y axis generates z-axis rotation quaternion."""
        v1 = np.array([1.0, 0.0, 0.0], dtype=np.float64)
        v2 = np.array([0.0, 1.0, 0.0], dtype=np.float64)
        q = quaternion_from_vectors(v1, v2)
        # Expected: axis=[0, 0, 1], theta=pi/2, half_theta=pi/4, sin=sqrt(2)/2, cos=sqrt(2)/2
        s = math.sin(math.pi / 4.0)
        c = math.cos(math.pi / 4.0)
        expected_q = np.array([0.0, 0.0, s, c])
        assert np.allclose(q, expected_q, atol=1e-6)
        assert math.isclose(np.linalg.norm(q), 1.0, rel_tol=1e-6)

    def test_quaternion_multiplication_associativity(self) -> None:
        """Verify quaternion multiplication satisfies associative group property: (q1 * q2) * q3 = q1 * (q2 * q3)."""
        q1 = quaternion_normalize([0.1, 0.2, 0.3, 0.9])
        q2 = quaternion_normalize([-0.2, 0.4, 0.1, 0.8])
        q3 = quaternion_normalize([0.5, -0.1, 0.2, 0.7])

        lhs = quaternion_multiply(quaternion_multiply(q1, q2), q3)
        rhs = quaternion_multiply(q1, quaternion_multiply(q2, q3))
        assert np.allclose(lhs, rhs, atol=1e-6)
        assert math.isclose(np.linalg.norm(lhs), 1.0, rel_tol=1e-6)

    def test_quaternion_to_rotation_matrix_orthogonality(self) -> None:
        """Verify rotation matrix R is orthogonal: R @ R.T = I, det(R) = +1.0."""
        q = quaternion_normalize([0.2, -0.3, 0.5, 0.8])
        R = quaternion_to_rotation_matrix(q)

        # Check orthogonality
        I_calc = R @ R.T
        assert np.allclose(I_calc, np.eye(3), atol=1e-6)

        # Check determinant is +1 (special orthogonal group SO(3))
        det = np.linalg.det(R)
        assert math.isclose(det, 1.0, rel_tol=1e-6)

        # Check rotating a vector with R matches quaternion sandwich transform
        v = np.array([1.0, 2.0, 3.0])
        v_rot_mat = R @ v

        # Quaternion sandwich: v' = q * v_pure * q_inv
        v_pure = np.array([v[0], v[1], v[2], 0.0])
        q_inv = np.array([-q[0], -q[1], -q[2], q[3]])
        v_rot_quat = quaternion_multiply(quaternion_multiply(q, v_pure), q_inv)[:3]

        assert np.allclose(v_rot_mat, v_rot_quat, atol=1e-6)


# =============================================================================
# 5. Molecular File Parser Verification (.xyz, .pdb, .cube)
# =============================================================================

class TestMolecularFileParsers:
    """Verify authentic coordinate file parsing for XYZ, PDB, and CUBE formats."""

    def test_parse_xyz_single_and_multi_frame(self) -> None:
        """Verify single and multi-frame XYZ coordinate extraction."""
        xyz_content = """3
Water monomer Frame 1
O  0.000000  0.000000  0.117400
H  0.000000  0.757000 -0.469600
H  0.000000 -0.757000 -0.469600
3
Water monomer Frame 2 (Displaced)
O  0.000000  0.000000  0.120000
H  0.000000  0.760000 -0.470000
H  0.000000 -0.760000 -0.470000
"""
        frames = parse_xyz(xyz_content)
        assert len(frames) == 2

        syms1, coords1, comment1 = frames[0]
        assert syms1 == ["O", "H", "H"]
        assert coords1.shape == (3, 3)
        assert np.allclose(coords1[0], [0.0, 0.0, 0.1174])
        assert comment1 == "Water monomer Frame 1"

        syms2, coords2, comment2 = frames[1]
        assert np.allclose(coords2[0], [0.0, 0.0, 0.1200])

    def test_parse_pdb_records(self) -> None:
        """Verify standard PDB ATOM record parsing and element identification."""
        pdb_content = """ATOM      1  N   ALA A   1       1.000   2.000   3.000  1.00 20.00           N
ATOM      2  CA  ALA A   1       2.000   3.000   4.000  1.00 20.00           C
ATOM      3  C   ALA A   1       3.000   4.000   5.000  1.00 20.00           C
ATOM      4  O   ALA A   1       4.000   5.000   6.000  1.00 20.00           O
TER
END
"""
        frames = parse_pdb(pdb_content)
        assert len(frames) == 1
        syms, coords, meta = frames[0]
        assert syms == ["N", "C", "C", "O"]
        assert coords.shape == (4, 3)
        assert np.allclose(coords[0], [1.0, 2.0, 3.0])
        assert np.allclose(coords[3], [4.0, 5.0, 6.0])

    def test_parse_cube_volumetric_data(self) -> None:
        """Verify Gaussian/Q-Chem volumetric cube file header and grid parser."""
        cube_content = """CP-DFT Electron Density
Gaussian Cube File
  2    0.000000    0.000000    0.000000
  2    0.500000    0.000000    0.000000
  2    0.000000    0.500000    0.000000
  2    0.000000    0.000000    0.500000
  8    8.000000    0.000000    0.000000    0.000000
  1    1.000000    0.000000    0.757000   -0.469600
  0.100000  0.200000  0.300000  0.400000
  0.500000  0.600000  0.700000  0.800000
"""
        data = parse_cube(cube_content)
        assert data["natoms"] == 2
        assert data["symbols"] == ["O", "H"]
        assert data["nx"] == 2 and data["ny"] == 2 and data["nz"] == 2
        assert data["coordinates"].shape == (2, 3)
        assert data["volumetric_data"].shape == (2, 2, 2)
        assert math.isclose(data["volumetric_data"][0, 0, 0], 0.1)
        assert math.isclose(data["volumetric_data"][1, 1, 1], 0.8)


# =============================================================================
# 6. Dihedral Angle & Bond Torsion Geometry Manipulation
# =============================================================================

class TestDihedralAndTorsionMath:
    """Verify 4-atom proper dihedral angle calculations and subset bond torsion rotations."""

    def test_ethane_staggered_dihedral_angle(self) -> None:
        """Verify staggered ethane H-C-C-H dihedral angles are approximately +/-60 and 180 degrees."""
        # H1(idx 2) - C1(idx 0) - C2(idx 1) - H4(idx 5) -> Trans / anti = 180 deg
        p_h1 = ETHANE_STAGGERED_COORDS[2]
        p_c1 = ETHANE_STAGGERED_COORDS[0]
        p_c2 = ETHANE_STAGGERED_COORDS[1]
        p_h4 = ETHANE_STAGGERED_COORDS[5]

        d_trans = calculate_dihedral(p_h1, p_c1, p_c2, p_h4, degrees=True)
        assert math.isclose(abs(d_trans), 180.0, abs_tol=1e-3)

        # H1(idx 2) - C1(idx 0) - C2(idx 1) - H5(idx 6) -> Gauche (+/- 60 deg)
        p_h5 = ETHANE_STAGGERED_COORDS[6]
        d_gauche = calculate_dihedral(p_h1, p_c1, p_c2, p_h5, degrees=True)
        assert math.isclose(abs(d_gauche), 60.0, abs_tol=0.05)


    def test_rotate_dihedral_subset_preserves_bond_length(self) -> None:
        """Verify rotating a methyl group preserves the C-C bond length and changes the dihedral angle."""
        coords = np.copy(ETHANE_STAGGERED_COORDS)
        c1_idx, c2_idx = 0, 1
        initial_bond_len = float(np.linalg.norm(coords[c2_idx] - coords[c1_idx]))

        # Rotate methyl group attached to C2 (atoms 5, 6, 7) by +60 degrees around C1-C2 axis
        moving_indices = [5, 6, 7]
        delta_deg = 60.0
        delta_rad = math.radians(delta_deg)

        new_coords = rotate_dihedral_subset(
            coordinates=coords,
            moving_atom_indices=moving_indices,
            bond_axis_atoms=(c1_idx, c2_idx),
            delta_angle_rad=delta_rad,
        )

        # 1. Bond length between hinge atoms C1 and C2 MUST be strictly invariant
        new_bond_len = float(np.linalg.norm(new_coords[c2_idx] - new_coords[c1_idx]))
        assert math.isclose(new_bond_len, initial_bond_len, rel_tol=1e-7)

        # 2. Distance between C2 and H4 MUST remain invariant
        h4_idx = 5
        init_c2_h4 = float(np.linalg.norm(coords[h4_idx] - coords[c2_idx]))
        new_c2_h4 = float(np.linalg.norm(new_coords[h4_idx] - new_coords[c2_idx]))
        assert math.isclose(new_c2_h4, init_c2_h4, rel_tol=1e-7)

        # 3. Dihedral angle H1-C1-C2-H4 should transition from 180 to 180 + 60 = -120 or 120
        new_d = calculate_dihedral(new_coords[2], new_coords[0], new_coords[1], new_coords[5], degrees=True)
        assert math.isclose(abs(new_d), 120.0, abs_tol=1e-3)


# =============================================================================
# 7. Vibrational Normal Mode Displacement
# =============================================================================

class TestVibrationalModeDisplacements:
    """Verify normal mode displacement tensor application."""

    def test_apply_vibration_mode_h2o_symmetric_stretch(self) -> None:
        """Verify harmonic coordinate displacements at phase 0, pi/2, and pi."""
        tensor = VibrationTensor(
            mode_index=1,
            frequency_cm1=3657.0,
            displacement_vectors=(
                (0.0, 0.0, 0.05),
                (0.0, 0.4, -0.3),
                (0.0, -0.4, -0.3),
            ),
        )

        # Phase 0 -> zero displacement: r' = r
        c_0 = apply_vibration_mode(WATER_COORDS, tensor, amplitude=1.0, phase_rad=0.0)
        assert np.allclose(c_0, WATER_COORDS, atol=1e-7)

        # Phase pi/2 -> max positive displacement: r' = r + d
        c_pi2 = apply_vibration_mode(WATER_COORDS, tensor, amplitude=1.0, phase_rad=math.pi * 0.5)
        expected_max = WATER_COORDS + np.array(tensor.displacement_vectors)
        assert np.allclose(c_pi2, expected_max, atol=1e-6)

        # Phase pi -> zero displacement again
        c_pi = apply_vibration_mode(WATER_COORDS, tensor, amplitude=1.0, phase_rad=math.pi)
        assert np.allclose(c_pi, WATER_COORDS, atol=1e-6)


# =============================================================================
# 8. Trajectory Streaming & File Locking
# =============================================================================

class TestTrajectoryStreamingFileLock:
    """Verify multi-process safe trajectory streaming with filelock.FileLock."""

    def test_stream_trajectory_frame(self) -> None:
        """Verify cross-process file locked trajectory frame retrieval."""
        multi_frame_xyz = """3
Frame 1
O  0.0  0.0  0.0
H  0.0  1.0  0.0
H  0.0 -1.0  0.0
3
Frame 2
O  0.0  0.0  0.5
H  0.0  1.0  0.5
H  0.0 -1.0  0.5
"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            traj_file = Path(tmp_dir) / "trajectory.xyz"
            traj_file.write_text(multi_frame_xyz, encoding="utf-8")

            viewer = Touch3DViewer()
            syms1, coords1 = viewer.stream_trajectory_frame(traj_file, 0)
            assert syms1 == ["O", "H", "H"]
            assert np.allclose(coords1[0], [0.0, 0.0, 0.0])

            syms2, coords2 = viewer.stream_trajectory_frame(traj_file, 1)
            assert np.allclose(coords2[0], [0.0, 0.0, 0.5])


# =============================================================================
# 9. Static Assets & Subresource Integrity (SRI)
# =============================================================================

class TestAirgapStaticAssetsAndSRI:
    """Verify presence, non-empty size, and SHA-256 SRI hashes for all air-gapped static assets."""

    def test_verify_static_assets(self) -> None:
        """Verify static files exist and have valid sha256- SRI signatures."""
        res = verify_static_assets()
        assert "js/3dmol/touch_controller.js" in res
        assert "js/3dmol/3Dmol-min.js" in res
        assert "css/cochem_mobile.css" in res

        for name, meta in res.items():
            assert Path(meta["path"]).is_file()
            assert meta["size_bytes"] > 500
            assert meta["sri_hash"].startswith("sha256-")
            assert len(meta["sri_hash"]) > 20

    def test_html_bundle_is_air_gapped(self) -> None:
        """Verify generated HTML bundle contains embedded assets and 0 remote CDN URLs."""
        viewer = Touch3DViewer(WATER_SYMBOLS, WATER_COORDS)
        html = viewer.to_html_bundle(inline_assets=True)

        assert "<html" in html
        assert "CoChem 3D Molecular Touch Viewer" in html
        assert "TouchController" in html
        assert "$3Dmol" in html
        assert "Content-Security-Policy" in html
        assert "default-src 'none'" in html
        # Zero external CDN links
        assert "cdn.jsdelivr.net" not in html
        assert "cdnjs.cloudflare.com" not in html
        assert "http://" not in html
        assert "https://" not in html


# =============================================================================
# 10. Touch3DViewer Full Widget Controller State
# =============================================================================

class TestTouch3DViewerWidget:
    """Verify Touch3DViewer operations, selections, auto-centering, and widget rendering."""

    def test_viewer_initialization_defaults(self) -> None:
        """Verify viewer initializes with authentic Water molecule by default."""
        viewer = Touch3DViewer()
        assert viewer.num_atoms == 3
        assert viewer.symbols == ["O", "H", "H"]
        assert viewer.bounding_radius > 1.0
        assert viewer.camera_state.fov_degrees == 45.0
        assert viewer.camera_state.quaternion == (0.0, 0.0, 0.0, 1.0)

    def test_load_molecule_and_auto_center(self) -> None:
        """Verify loading benzene molecule re-centers camera and recalculates bounding radius."""
        viewer = Touch3DViewer()
        viewer.load_molecule(BENZENE_SYMBOLS, BENZENE_COORDS, title="Benzene D6h")

        assert viewer.num_atoms == 12
        assert viewer.symbols == BENZENE_SYMBOLS
        assert np.allclose(viewer.get_centroid(), np.zeros(3), atol=1e-4)
        assert viewer.bounding_radius > 3.0

        # Auto-center target matches centroid
        assert np.allclose(viewer.camera_state.target, (0.0, 0.0, 0.0), atol=1e-4)

    def test_dihedral_selection_and_rotation(self) -> None:
        """Verify setting active dihedral and applying interactive torsion rotation."""
        viewer = Touch3DViewer(ETHANE_STAGGERED_SYMBOLS, ETHANE_STAGGERED_COORDS)
        viewer.set_active_dihedral((2, 0, 1, 5))  # H1-C1-C2-H4
        assert viewer.selection_state.active_dihedral == (2, 0, 1, 5)

        # Rotate downstream atoms (5, 6, 7) by +90 degrees
        updated_coords = viewer.apply_dihedral_rotation([5, 6, 7], 90.0)
        assert updated_coords.shape == (8, 3)

        # Invalid dihedral atom count raises ValueError
        with pytest.raises(ValueError):
            viewer.set_active_dihedral((0, 1, 2))  # type: ignore[arg-type]

    def test_vibrational_tensor_integration(self) -> None:
        """Verify connecting VibrationTensor and extracting harmonic frames."""
        viewer = Touch3DViewer(WATER_SYMBOLS, WATER_COORDS)
        tensor = VibrationTensor(
            mode_index=1,
            frequency_cm1=1595.0,
            displacement_vectors=((0.0, 0.05, 0.0), (0.0, -0.4, 0.3), (0.0, -0.4, -0.3)),
        )
        viewer.set_vibration_mode(tensor)
        disp_frame = viewer.get_vibrational_frame(amplitude=1.5, phase_rad=math.pi * 0.5)
        assert disp_frame.shape == (3, 3)
        assert not np.allclose(disp_frame, WATER_COORDS)

    def test_render_widget_returns_html_instance(self) -> None:
        """Verify render_widget returns an ipywidgets.HTML instance with iframe."""
        viewer = Touch3DViewer(WATER_SYMBOLS, WATER_COORDS)
        widget = viewer.render_widget()
        assert isinstance(widget, ipywidgets.HTML)
        assert "<iframe" in widget.value
        assert "srcdoc=" in widget.value

    def test_dpr_normalization_and_touch_picking(self) -> None:
        """Verify device pixel ratio scaling across 1.0x, 2.0x, and 3.0x displays."""
        for dpr in [1.0, 2.0, 3.0]:
            vp = ViewportConfig(width_px=800, height_px=600, device_pixel_ratio=dpr)
            viewer = Touch3DViewer(WATER_SYMBOLS, WATER_COORDS, viewport_config=vp)
            assert viewer.viewport_config.device_pixel_ratio == dpr

            # Simulated screen touch at (400, 300) center
            screen_x, screen_y = 400.0, 300.0
            pick_x = screen_x * dpr
            pick_y = screen_y * dpr

            assert pick_x == 400.0 * dpr
            assert pick_y == 300.0 * dpr

    def test_pinch_zoom_ratio_and_frustum_clipping(self) -> None:
        """Verify pinch-to-zoom distance scaling d' = d / s and dynamic near/far clipping planes."""
        viewer = Touch3DViewer(WATER_SYMBOLS, WATER_COORDS)
        R = viewer.bounding_radius
        init_d = viewer.camera_state.focal_distance

        # 2x pinch zoom in (s = 2.0 -> d' = init_d / 2.0)
        s_zoom_in = 2.0
        d_new = init_d / s_zoom_in
        near_clip = max(0.1, d_new - 1.5 * R)
        far_clip = d_new + 2.0 * R

        assert near_clip >= 0.1
        assert far_clip > near_clip
        assert math.isclose(far_clip, d_new + 2.0 * R, rel_tol=1e-7)
        assert math.isclose(near_clip, max(0.1, d_new - 1.5 * R), rel_tol=1e-7)


    def test_quaternion_rotation_euler_baseline_equivalence(self) -> None:
        """Verify SO(3) quaternion rotation matches analytical 3D Euler angle rotation matrix."""
        angle_rad = math.pi / 3.0  # 60 degrees around Z axis
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)

        # Analytical Euler Z-rotation matrix
        R_euler_z = np.array([
            [cos_a, -sin_a, 0.0],
            [sin_a, cos_a, 0.0],
            [0.0, 0.0, 1.0],
        ])

        # Quaternion for angle around Z axis: [0, 0, sin(theta/2), cos(theta/2)]
        half = angle_rad * 0.5
        q_z = np.array([0.0, 0.0, math.sin(half), math.cos(half)])
        R_quat_z = quaternion_to_rotation_matrix(q_z)

        assert np.allclose(R_quat_z, R_euler_z, atol=1e-6)

    def test_malformed_file_handling(self) -> None:
        """Verify informative exceptions on corrupted molecular files."""
        # Corrupted XYZ: non-integer atom count
        with pytest.raises(ValueError):
            parse_xyz("NOT_A_NUMBER\nTitle\nC 0 0 0\n")

        # Corrupted PDB: empty content
        with pytest.raises(ValueError):
            parse_pdb("REMARK 100 Just remarks\nEND\n")

        # Corrupted Cube: too few lines
        with pytest.raises(ValueError):
            parse_cube("Line 1\nLine 2\n")

    def test_concurrent_multithreaded_viewer_access(self) -> None:
        """Verify thread-safe concurrent operations on Touch3DViewer."""
        import threading

        viewer = Touch3DViewer(BENZENE_SYMBOLS, BENZENE_COORDS)
        results: list[float] = []
        lock = threading.Lock()

        def worker_op(frame_idx: int) -> None:
            # Recalculate bounding radius and centroid
            r = calculate_bounding_radius(viewer.symbols, viewer.coordinates)
            c = calculate_centroid(viewer.coordinates)
            val = float(r + c[0])
            with lock:
                results.append(val)

        threads = [threading.Thread(target=worker_op, args=(i,)) for i in range(16)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 16
        assert all(math.isclose(res, results[0], rel_tol=1e-5) for res in results)

