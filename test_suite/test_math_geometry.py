"""Comprehensive Zero-Mock Physical Test Suite for cochem_base.math.geometry.

Tests 3D Cartesian Point primitives, vector algebra, distance metrics, BoundingBox
CartesianPositivity-003 boundary enforcement, spatial queries (intersection, union,
containment, clamping), and molecular conformation metrics (bond angles, dihedral
angles, centroid, radius of gyration).
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from cochem_base.math.geometry import (
    BoundingBox,
    Point,
    angle_between,
    centroid,
    dihedral_angle,
    euclidean_distance,
    manhattan_distance,
    radius_of_gyration,
)
from cochem_base.path_sanitization import leak_patterns


@pytest.fixture
def geometry_source_path() -> Path:
    """Return the absolute path to cochem_base/math/geometry.py."""
    path = Path(__file__).resolve().parent.parent / "cochem_base" / "math" / "geometry.py"
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


def test_geometry_file_encoding_and_lf_endings(geometry_source_path: Path) -> None:
    """Verify strictly Unix LF line endings, UTF-8 encoding, and no UTF-8 BOM."""
    raw = geometry_source_path.read_bytes()
    assert b"\r\n" not in raw, "Found Windows CRLF (\\r\\n) line endings in math/geometry.py"
    assert b"\n" in raw, "Missing newline characters in math/geometry.py"
    assert not raw.startswith(b"\xef\xbb\xbf"), "Found UTF-8 BOM marker in math/geometry.py"


def test_zero_personal_path_leaks_in_geometry(geometry_source_path: Path) -> None:
    """Verify zero personal machine or local username path leakage in geometry.py."""
    lines = geometry_source_path.read_text(encoding="utf-8").splitlines()
    patterns = leak_patterns()
    leaks = []
    for lineno, line in enumerate(lines, 1):
        for pattern, placeholder in patterns:
            if pattern.search(line):
                leaks.append((lineno, placeholder, line.strip()))

    assert len(leaks) == 0, f"Detected personal path leaks in geometry.py: {leaks}"


# ---------------------------------------------------------------------------
# Point Instantiation & Conversion Tests
# ---------------------------------------------------------------------------


def test_point_instantiation_variants() -> None:
    """Verify Point instantiation via keywords, positional args, sequences, and copies."""
    # Keyword arguments
    p1 = Point(x=1.0, y=2.0, z=3.0)
    assert p1.x == 1.0 and p1.y == 2.0 and p1.z == 3.0

    # Positional arguments
    p2 = Point(1.0, 2.0, 3.0)
    assert p2.x == 1.0 and p2.y == 2.0 and p2.z == 3.0

    # Sequence / List / Tuple
    p3 = Point([1.0, 2.0, 3.0])
    assert p3.x == 1.0 and p3.y == 2.0 and p3.z == 3.0

    p4 = Point((1.0, 2.0, 3.0))
    assert p4.x == 1.0 and p4.y == 2.0 and p4.z == 3.0

    # From another Point instance
    p5 = Point(p1)
    assert p5.x == 1.0 and p5.y == 2.0 and p5.z == 3.0

    # Origin factory
    p_orig = Point.origin()
    assert p_orig.x == 0.0 and p_orig.y == 0.0 and p_orig.z == 0.0


def test_point_factory_methods() -> None:
    """Verify Point.from_tuple, from_numpy, and from_dict factory classmethods."""
    # from_tuple
    p_tup = Point.from_tuple((4.5, 5.5, 6.5))
    assert p_tup.to_tuple() == (4.5, 5.5, 6.5)

    with pytest.raises(ValueError, match="Expected 3 coordinates"):
        Point.from_tuple((1.0, 2.0))

    # from_numpy
    arr = np.array([10.0, 20.0, 30.0])
    p_np = Point.from_numpy(arr)
    assert np.array_equal(p_np.to_numpy(), arr)

    with pytest.raises(ValueError, match="NumPy array must contain exactly 3 elements"):
        Point.from_numpy(np.array([1.0, 2.0]))

    # from_dict
    p_dict = Point.from_dict({"x": 7.0, "y": 8.0, "z": 9.0})
    assert p_dict == Point(7.0, 8.0, 9.0)

    with pytest.raises(KeyError, match="must contain 'x', 'y', and 'z' keys"):
        Point.from_dict({"x": 1.0, "y": 2.0})


def test_point_conversions_and_representations() -> None:
    """Verify to_tuple, to_list, to_dict, to_numpy, __repr__, __str__, and __hash__."""
    p = Point(1.5, 2.5, 3.5)
    assert p.to_tuple() == (1.5, 2.5, 3.5)
    assert p.to_list() == [1.5, 2.5, 3.5]
    assert p.to_dict() == {"x": 1.5, "y": 2.5, "z": 3.5}
    assert np.array_equal(p.to_numpy(), np.array([1.5, 2.5, 3.5]))

    assert "Point(x=1.5, y=2.5, z=3.5)" in repr(p)
    assert "(1.5, 2.5, 3.5)" in str(p)
    assert hash(p) == hash((1.5, 2.5, 3.5))

    # Indexing and Iteration
    assert p[0] == 1.5 and p[1] == 2.5 and p[2] == 3.5
    assert p[-1] == 3.5 and p[-2] == 2.5 and p[-3] == 1.5
    assert len(p) == 3
    assert list(p) == [1.5, 2.5, 3.5]

    with pytest.raises(IndexError, match="out of range"):
        _ = p[3]
    with pytest.raises(IndexError, match="out of range"):
        _ = p[-4]


# ---------------------------------------------------------------------------
# Point Vector Algebra & Distance Metrics
# ---------------------------------------------------------------------------


def test_point_vector_arithmetic() -> None:
    """Verify addition, subtraction, scalar multiplication, division, and negation."""
    p1 = Point(1.0, 2.0, 3.0)
    p2 = Point(4.0, 5.0, 6.0)

    # Point + Point
    p_add = p1 + p2
    assert p_add == Point(5.0, 7.0, 9.0)

    # Point + scalar
    assert (p1 + 10.0) == Point(11.0, 12.0, 13.0)
    assert (10.0 + p1) == Point(11.0, 12.0, 13.0)

    # Point - Point
    p_sub = p2 - p1
    assert p_sub == Point(3.0, 3.0, 3.0)

    # Point - scalar and scalar - Point
    assert (p2 - 1.0) == Point(3.0, 4.0, 5.0)
    assert (10.0 - p1) == Point(9.0, 8.0, 7.0)

    # Point * scalar
    assert (p1 * 2.0) == Point(2.0, 4.0, 6.0)
    assert (2.0 * p1) == Point(2.0, 4.0, 6.0)

    # Point / scalar
    assert (p1 / 2.0) == Point(0.5, 1.0, 1.5)

    with pytest.raises(ZeroDivisionError):
        _ = p1 / 0.0

    # Unary operators
    assert (-p1) == Point(-1.0, -2.0, -3.0)
    assert (+p1) == p1
    assert math.isclose(abs(Point(3.0, 4.0, 0.0)), 5.0)


def test_point_equality_and_closeness() -> None:
    """Verify Point equality against Point, tuples, lists, NumPy arrays, and tolerances."""
    p = Point(1.0, 2.0, 3.0)
    assert p == Point(1.0, 2.0, 3.0)
    assert p == (1.0, 2.0, 3.0)
    assert p == [1.0, 2.0, 3.0]
    assert p == np.array([1.0, 2.0, 3.0])
    assert p != Point(1.0, 2.0, 3.1)
    assert p != (1.0, 2.0)
    assert p != "non_point"

    p_near = Point(1.0 + 1e-9, 2.0 - 1e-9, 3.0)
    assert p.is_close_to(p_near, atol=1e-8)
    assert not p.is_close_to(p_near, atol=1e-10, rtol=0.0)


def test_point_geometric_metrics() -> None:
    """Verify distance_to, squared_distance_to, manhattan_distance_to, chebyshev_distance_to."""
    p1 = Point(0.0, 0.0, 0.0)
    p2 = Point(1.0, 2.0, 2.0)

    # Euclidean: sqrt(1^2 + 2^2 + 2^2) = sqrt(9) = 3
    assert math.isclose(p1.distance_to(p2), 3.0)
    assert math.isclose(p1.squared_distance_to(p2), 9.0)

    # Manhattan: |1| + |2| + |2| = 5
    assert math.isclose(p1.manhattan_distance_to(p2), 5.0)

    # Chebyshev: max(|1|, |2|, |2|) = 2
    assert math.isclose(p1.chebyshev_distance_to(p2), 2.0)

    # Norm and Normalization
    assert math.isclose(p2.norm(), 3.0)
    assert math.isclose(p2.squared_norm(), 9.0)
    unit_p2 = p2.normalized()
    assert math.isclose(unit_p2.norm(), 1.0)
    assert unit_p2 == Point(1.0 / 3.0, 2.0 / 3.0, 2.0 / 3.0)

    with pytest.raises(ValueError, match="Cannot normalize zero-length vector"):
        Point(0.0, 0.0, 0.0).normalized()


def test_point_dot_cross_midpoint_angle() -> None:
    """Verify dot product, cross product, midpoint, and vector angle computations."""
    vx = Point(1.0, 0.0, 0.0)
    vy = Point(0.0, 1.0, 0.0)
    vz = Point(0.0, 0.0, 1.0)

    # Dot product: orthogonal = 0
    assert vx.dot(vy) == 0.0
    assert vx.dot(vx) == 1.0

    # Cross product: X × Y = Z
    assert vx.cross(vy) == vz
    assert vy.cross(vz) == vx
    assert vz.cross(vx) == vy

    # Midpoint
    mid = vx.midpoint(vy)
    assert mid == Point(0.5, 0.5, 0.0)

    # Angle between orthogonal vectors
    ang_rad = vx.angle_to(vy, degrees=False)
    assert math.isclose(ang_rad, math.pi / 2.0)

    ang_deg = vx.angle_to(vy, degrees=True)
    assert math.isclose(ang_deg, 90.0)

    # Angle with zero vector error
    with pytest.raises(ValueError, match="Cannot calculate angle with zero-length vector"):
        vx.angle_to(Point.origin())


def test_point_transformations() -> None:
    """Verify Point translate and scale methods."""
    p = Point(1.0, 2.0, 3.0)
    assert p.translate(10.0, -5.0, 2.0) == Point(11.0, -3.0, 5.0)
    assert p.scale(3.0) == Point(3.0, 6.0, 9.0)


# ---------------------------------------------------------------------------
# BoundingBox Validation & Properties (CartesianPositivity-003)
# ---------------------------------------------------------------------------


def test_bounding_box_valid_instantiation_and_properties() -> None:
    """Verify valid BoundingBox dimensions, center, volume, surface area, and corners."""
    bbox = BoundingBox(
        min_point=Point(0.0, 0.0, 0.0),
        max_point=Point(2.0, 4.0, 6.0),
    )
    assert bbox.dimensions == (2.0, 4.0, 6.0)
    assert bbox.dx == 2.0
    assert bbox.dy == 4.0
    assert bbox.dz == 6.0
    assert bbox.volume == 48.0
    # surface area: 2 * (2*4 + 4*6 + 6*2) = 2 * (8 + 24 + 12) = 2 * 44 = 88
    assert bbox.surface_area == 88.0
    assert bbox.center == Point(1.0, 2.0, 3.0)
    # diagonal length: sqrt(4 + 16 + 36) = sqrt(56)
    assert math.isclose(bbox.diagonal_length, math.sqrt(56.0))
    assert math.isclose(bbox.radius, math.sqrt(56.0) / 2.0)

    corners = bbox.corners
    assert len(corners) == 8
    assert corners[0] == Point(0.0, 0.0, 0.0)
    assert corners[6] == Point(2.0, 4.0, 6.0)


@pytest.mark.parametrize(
    ("min_pt", "max_pt", "failing_dim"),
    [
        (Point(1.0, 0.0, 0.0), Point(1.0, 2.0, 3.0), "max_x"),
        (Point(1.0, 0.0, 0.0), Point(0.5, 2.0, 3.0), "max_x"),
        (Point(0.0, 2.0, 0.0), Point(1.0, 2.0, 3.0), "max_y"),
        (Point(0.0, 2.0, 0.0), Point(1.0, 1.5, 3.0), "max_y"),
        (Point(0.0, 0.0, 3.0), Point(1.0, 2.0, 3.0), "max_z"),
        (Point(0.0, 0.0, 3.0), Point(1.0, 2.0, 2.5), "max_z"),
    ],
)
def test_bounding_box_positivity_validation(min_pt: Point, max_pt: Point, failing_dim: str) -> None:
    """Verify CartesianPositivity-003 raises ValueError when max <= min in any dimension."""
    with pytest.raises(ValueError, match=r"Cartesian boundaries invalid") as exc_info:
        BoundingBox(min_point=min_pt, max_point=max_pt)
    assert failing_dim in str(exc_info.value)


def test_bounding_box_factories() -> None:
    """Verify BoundingBox.from_points, from_center_and_dimensions, and from_min_max_coords."""
    # from_points
    pts = [
        Point(1.0, -2.0, 3.0),
        Point(5.0, 4.0, -1.0),
        Point(2.0, 0.0, 1.0),
    ]
    bbox = BoundingBox.from_points(pts)
    assert bbox.min_point == Point(1.0, -2.0, -1.0)
    assert bbox.max_point == Point(5.0, 4.0, 3.0)

    # from_points with padding
    bbox_pad = BoundingBox.from_points(pts, padding=1.0)
    assert bbox_pad.min_point == Point(0.0, -3.0, -2.0)
    assert bbox_pad.max_point == Point(6.0, 5.0, 4.0)

    # Empty points error
    with pytest.raises(ValueError, match="Cannot construct BoundingBox from an empty point sequence"):
        BoundingBox.from_points([])

    # Negative padding error
    with pytest.raises(ValueError, match="Padding must be non-negative"):
        BoundingBox.from_points(pts, padding=-0.5)

    # from_center_and_dimensions
    center = Point(0.0, 0.0, 0.0)
    dims = (4.0, 6.0, 8.0)
    bbox_cd = BoundingBox.from_center_and_dimensions(center, dims)
    assert bbox_cd.min_point == Point(-2.0, -3.0, -4.0)
    assert bbox_cd.max_point == Point(2.0, 3.0, 4.0)

    with pytest.raises(ValueError, match="All dimensions must be strictly positive"):
        BoundingBox.from_center_and_dimensions(center, (4.0, -1.0, 2.0))

    # from_min_max_coords
    bbox_coords = BoundingBox.from_min_max_coords([0.0, 1.0, 2.0], [5.0, 6.0, 7.0])
    assert bbox_coords.dimensions == (5.0, 5.0, 5.0)


# ---------------------------------------------------------------------------
# BoundingBox Spatial Queries & Transformations
# ---------------------------------------------------------------------------


def test_bounding_box_containment_and_queries() -> None:
    """Verify contains_point, 'in' operator, clamp_point, and distance_to_point."""
    bbox = BoundingBox(min_point=Point(0.0, 0.0, 0.0), max_point=Point(10.0, 10.0, 10.0))

    # Interior point
    assert bbox.contains_point(Point(5.0, 5.0, 5.0), inclusive=True)
    assert bbox.contains_point(Point(5.0, 5.0, 5.0), inclusive=False)
    assert Point(5.0, 5.0, 5.0) in bbox

    # Boundary point
    assert bbox.contains_point(Point(0.0, 5.0, 5.0), inclusive=True)
    assert not bbox.contains_point(Point(0.0, 5.0, 5.0), inclusive=False)
    assert Point(0.0, 5.0, 5.0) in bbox

    # Exterior point
    assert not bbox.contains_point(Point(12.0, 5.0, 5.0))
    assert Point(12.0, 5.0, 5.0) not in bbox

    # Clamping
    p_out = Point(15.0, -5.0, 5.0)
    p_clamped = bbox.clamp_point(p_out)
    assert p_clamped == Point(10.0, 0.0, 5.0)
    assert bbox.distance_to_point(p_out) == math.sqrt(5.0**2 + 5.0**2)

    # Point inside has distance 0
    assert bbox.distance_to_point(Point(5.0, 5.0, 5.0)) == 0.0


def test_bounding_box_intersections_and_unions() -> None:
    """Verify intersects, intersection, union, expand, scale, and translate."""
    b1 = BoundingBox(min_point=Point(0.0, 0.0, 0.0), max_point=Point(10.0, 10.0, 10.0))
    b2 = BoundingBox(min_point=Point(5.0, 5.0, 5.0), max_point=Point(15.0, 15.0, 15.0))
    b_disjoint = BoundingBox(min_point=Point(20.0, 20.0, 20.0), max_point=Point(30.0, 30.0, 30.0))

    # Intersection
    assert b1.intersects(b2)
    inter = b1.intersection(b2)
    assert inter is not None
    assert inter.min_point == Point(5.0, 5.0, 5.0)
    assert inter.max_point == Point(10.0, 10.0, 10.0)

    # Disjoint
    assert not b1.intersects(b_disjoint)
    assert b1.intersection(b_disjoint) is None

    # Union
    u = b1.union(b2)
    assert u.min_point == Point(0.0, 0.0, 0.0)
    assert u.max_point == Point(15.0, 15.0, 15.0)

    # Expand
    b_exp = b1.expand(2.0)
    assert b_exp.min_point == Point(-2.0, -2.0, -2.0)
    assert b_exp.max_point == Point(12.0, 12.0, 12.0)

    # Scale
    b_scaled = b1.scale(2.0)
    assert b_scaled.center == b1.center
    assert b_scaled.dimensions == (20.0, 20.0, 20.0)

    with pytest.raises(ValueError, match="Scale factor must be strictly positive"):
        b1.scale(-1.0)

    # Translate
    b_trans = b1.translate(5.0, -5.0, 2.0)
    assert b_trans.min_point == Point(5.0, -5.0, 2.0)
    assert b_trans.max_point == Point(15.0, 5.0, 12.0)

    # Repr and Str
    assert "BoundingBox" in repr(b1)
    assert "dims=" in str(b1)
    assert b1 == BoundingBox(min_point=Point(0.0, 0.0, 0.0), max_point=Point(10.0, 10.0, 10.0))
    assert b1 != "other"


# ---------------------------------------------------------------------------
# Functional Molecular & Geometric Utilities
# ---------------------------------------------------------------------------


def test_functional_distances() -> None:
    """Verify euclidean_distance and manhattan_distance functional helpers."""
    p1 = (1.0, 2.0, 3.0)
    p2 = (4.0, 6.0, 3.0)
    # dx=3, dy=4, dz=0 -> dist = 5
    assert math.isclose(euclidean_distance(p1, p2), 5.0)
    assert math.isclose(manhattan_distance(p1, p2), 7.0)


def test_angle_between() -> None:
    """Verify angle_between valence bond angle computations."""
    p1 = (1.0, 0.0, 0.0)
    p2 = (0.0, 0.0, 0.0)  # Apex
    p3 = (0.0, 1.0, 0.0)

    # 90 degrees / pi/2 radians
    assert math.isclose(angle_between(p1, p2, p3, degrees=False), math.pi / 2.0)
    assert math.isclose(angle_between(p1, p2, p3, degrees=True), 90.0)

    # 180 degrees linear
    p4 = (-1.0, 0.0, 0.0)
    assert math.isclose(angle_between(p1, p2, p4, degrees=True), 180.0)

    # Degenerate bond error
    with pytest.raises(ValueError, match="Cannot calculate angle with degenerate"):
        angle_between(p2, p2, p3)


def test_dihedral_angle() -> None:
    """Verify dihedral_angle calculation for planar, cis, trans, and gauche conformations."""
    # Trans conformation (180 degrees)
    # Atoms in X-Y plane: C1 - C2 - C3 - C4 in trans zigzag
    a1 = Point(0.0, 1.0, 0.0)
    a2 = Point(1.0, 0.0, 0.0)
    a3 = Point(2.0, 0.0, 0.0)
    a4 = Point(3.0, -1.0, 0.0)
    deg_trans = dihedral_angle(a1, a2, a3, a4, degrees=True)
    assert math.isclose(abs(deg_trans), 180.0, abs_tol=1e-6)

    # Cis conformation (0 degrees)
    a4_cis = Point(3.0, 1.0, 0.0)
    deg_cis = dihedral_angle(a1, a2, a3, a4_cis, degrees=True)
    assert math.isclose(deg_cis, 0.0, abs_tol=1e-6)

    # +90 degrees perpendicular conformation
    a4_perp_pos = Point(2.0, 0.0, -1.0)
    deg_perp_pos = dihedral_angle(a1, a2, a3, a4_perp_pos, degrees=True)
    assert math.isclose(deg_perp_pos, 90.0, abs_tol=1e-6)

    # -90 degrees perpendicular conformation
    a4_perp_neg = Point(2.0, 0.0, 1.0)
    deg_perp_neg = dihedral_angle(a1, a2, a3, a4_perp_neg, degrees=True)
    assert math.isclose(deg_perp_neg, -90.0, abs_tol=1e-6)

    # Degenerate central bond
    with pytest.raises(ValueError, match="degenerate central bond"):
        dihedral_angle(a1, a2, a2, a4)

    # Collinear bond error
    with pytest.raises(ValueError, match="collinear bond vectors"):
        dihedral_angle((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0), (3.0, 0.0, 0.0))


def test_centroid_and_radius_of_gyration() -> None:
    """Verify centroid and unweighted / mass-weighted radius of gyration."""
    points = [
        Point(1.0, 0.0, 0.0),
        Point(-1.0, 0.0, 0.0),
        Point(0.0, 1.0, 0.0),
        Point(0.0, -1.0, 0.0),
    ]

    # Centroid at (0, 0, 0)
    c = centroid(points)
    assert c == Point(0.0, 0.0, 0.0)

    # Unweighted Rg: all 4 points at dist 1 from center -> Rg = sqrt(4 * 1^2 / 4) = 1.0
    rg_unweighted = radius_of_gyration(points)
    assert math.isclose(rg_unweighted, 1.0)

    # Mass-weighted Rg with heavy mass on one atom
    masses = [10.0, 1.0, 1.0, 1.0]  # total = 13
    rg_weighted = radius_of_gyration(points, masses=masses)
    assert rg_weighted > 0.0

    # Error handling
    with pytest.raises(ValueError, match="Cannot calculate centroid of an empty"):
        centroid([])

    with pytest.raises(ValueError, match="Cannot calculate radius of gyration"):
        radius_of_gyration([])

    with pytest.raises(ValueError, match="Length of masses"):
        radius_of_gyration(points, masses=[1.0, 2.0])

    with pytest.raises(ValueError, match="Total mass must be strictly positive"):
        radius_of_gyration(points, masses=[0.0, 0.0, 0.0, 0.0])
