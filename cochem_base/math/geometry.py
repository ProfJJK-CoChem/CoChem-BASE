"""Cartesian geometry, 3D Point algebra, and BoundingBox spatial structures.

Implements CartesianPositivity-003 boundary enforcement, distance metrics,
valence bond angles, dihedral angles, centroid, and radius of gyration.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple, Union

import numpy as np
from pydantic import BaseModel, model_validator


class Point:
    """Represents an immutable/mutable Cartesian point or vector in 3D Euclidean space."""

    __slots__ = ("_x", "_y", "_z")

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        if kwargs:
            if "x" in kwargs and "y" in kwargs and "z" in kwargs:
                self._x = float(kwargs["x"])
                self._y = float(kwargs["y"])
                self._z = float(kwargs["z"])
                return
            raise ValueError("Point requires 'x', 'y', and 'z' keyword arguments")

        if len(args) == 1:
            val = args[0]
            if isinstance(val, Point):
                self._x = val.x
                self._y = val.y
                self._z = val.z
                return
            if isinstance(val, (list, tuple, np.ndarray)):
                if len(val) != 3:
                    raise ValueError(f"Expected 3 coordinates, got {len(val)}")
                self._x = float(val[0])
                self._y = float(val[1])
                self._z = float(val[2])
                return
            raise ValueError(f"Cannot initialize Point from single argument of type {type(val)}")

        if len(args) == 3:
            self._x = float(args[0])
            self._y = float(args[1])
            self._z = float(args[2])
            return

        raise ValueError(f"Invalid arguments for Point: args={args}, kwargs={kwargs}")

    @property
    def x(self) -> float:
        return self._x

    @property
    def y(self) -> float:
        return self._y

    @property
    def z(self) -> float:
        return self._z

    @classmethod
    def origin(cls) -> Point:
        return cls(0.0, 0.0, 0.0)

    @classmethod
    def from_tuple(cls, tup: Tuple[float, float, float] | Sequence[float]) -> Point:
        if len(tup) != 3:
            raise ValueError(f"Expected 3 coordinates, got {len(tup)}")
        return cls(tup[0], tup[1], tup[2])

    @classmethod
    def from_numpy(cls, arr: np.ndarray) -> Point:
        if arr.size != 3:
            raise ValueError(f"NumPy array must contain exactly 3 elements, got {arr.size}")
        flat = arr.flatten()
        return cls(flat[0], flat[1], flat[2])

    @classmethod
    def from_dict(cls, d: Dict[str, float]) -> Point:
        if not ("x" in d and "y" in d and "z" in d):
            raise KeyError("Dictionary must contain 'x', 'y', and 'z' keys")
        return cls(d["x"], d["y"], d["z"])

    def to_tuple(self) -> Tuple[float, float, float]:
        return (self._x, self._y, self._z)

    def to_list(self) -> List[float]:
        return [self._x, self._y, self._z]

    def to_dict(self) -> Dict[str, float]:
        return {"x": self._x, "y": self._y, "z": self._z}

    def to_numpy(self) -> np.ndarray:
        return np.array([self._x, self._y, self._z], dtype=np.float64)

    def distance_to(self, other: Any) -> float:
        p = other if isinstance(other, Point) else Point(other)
        return math.sqrt((self._x - p.x)**2 + (self._y - p.y)**2 + (self._z - p.z)**2)

    def norm(self) -> float:
        return math.sqrt(self._x**2 + self._y**2 + self._z**2)

    def normalized(self) -> Point:
        n = self.norm()
        if n == 0.0:
            raise ValueError("Cannot normalize zero-length vector")
        return Point(self._x / n, self._y / n, self._z / n)

    def dot(self, other: Any) -> float:
        p = other if isinstance(other, Point) else Point(other)
        return self._x * p.x + self._y * p.y + self._z * p.z

    def cross(self, other: Any) -> Point:
        p = other if isinstance(other, Point) else Point(other)
        return Point(
            self._y * p.z - self._z * p.y,
            self._z * p.x - self._x * p.z,
            self._x * p.y - self._y * p.x,
        )

    def __repr__(self) -> str:
        return f"Point(x={self._x}, y={self._y}, z={self._z})"

    def __str__(self) -> str:
        return f"({self._x}, {self._y}, {self._z})"

    def __hash__(self) -> int:
        return hash((self._x, self._y, self._z))

    def __len__(self) -> int:
        return 3

    def __getitem__(self, index: int) -> float:
        if index in (0, -3):
            return self._x
        if index in (1, -2):
            return self._y
        if index in (2, -1):
            return self._z
        raise IndexError("Point index out of range (expected -3 to 2)")

    def __iter__(self) -> Iterator[float]:
        yield self._x
        yield self._y
        yield self._z

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Point):
            return self._x == other.x and self._y == other.y and self._z == other.z
        if isinstance(other, (tuple, list)) and len(other) == 3:
            return self._x == other[0] and self._y == other[1] and self._z == other[2]
        return False

    def __add__(self, other: Any) -> Point:
        if isinstance(other, Point):
            return Point(self._x + other.x, self._y + other.y, self._z + other.z)
        if isinstance(other, (int, float)):
            f = float(other)
            return Point(self._x + f, self._y + f, self._z + f)
        if isinstance(other, (tuple, list)) and len(other) == 3:
            return Point(self._x + other[0], self._y + other[1], self._z + other[2])
        raise TypeError(f"Unsupported operand type for +: 'Point' and '{type(other)}'")

    def __radd__(self, other: Any) -> Point:
        return self.__add__(other)

    def __sub__(self, other: Any) -> Point:
        if isinstance(other, Point):
            return Point(self._x - other.x, self._y - other.y, self._z - other.z)
        if isinstance(other, (int, float)):
            f = float(other)
            return Point(self._x - f, self._y - f, self._z - f)
        if isinstance(other, (tuple, list)) and len(other) == 3:
            return Point(self._x - other[0], self._y - other[1], self._z - other[2])
        raise TypeError(f"Unsupported operand type for -: 'Point' and '{type(other)}'")

    def __rsub__(self, other: Any) -> Point:
        if isinstance(other, (int, float)):
            f = float(other)
            return Point(f - self._x, f - self._y, f - self._z)
        if isinstance(other, (tuple, list)) and len(other) == 3:
            return Point(other[0] - self._x, other[1] - self._y, other[2] - self._z)
        raise TypeError(f"Unsupported operand type for -: '{type(other)}' and 'Point'")

    def __mul__(self, other: Union[int, float]) -> Point:
        if isinstance(other, (int, float)):
            f = float(other)
            return Point(self._x * f, self._y * f, self._z * f)
        raise TypeError(f"Unsupported operand type for *: 'Point' and '{type(other)}'")

    def __rmul__(self, other: Union[int, float]) -> Point:
        return self.__mul__(other)

    def __truediv__(self, other: Union[int, float]) -> Point:
        if isinstance(other, (int, float)):
            f = float(other)
            if f == 0.0:
                raise ZeroDivisionError("Division by zero in Point.")
            return Point(self._x / f, self._y / f, self._z / f)
        raise TypeError(f"Unsupported operand type for /: 'Point' and '{type(other)}'")

    def __neg__(self) -> Point:
        return Point(-self._x, -self._y, -self._z)

    def __pos__(self) -> Point:
        return Point(self._x, self._y, self._z)

    def __abs__(self) -> float:
        return self.norm()


class BoundingBox(BaseModel):
    """Represents a Cartesian bounding box defined by a minimum and maximum point.

    Authentically enforces CartesianPositivity-003.
    """

    min_point: Point
    max_point: Point

    model_config = {"arbitrary_types_allowed": True}

    @model_validator(mode="after")
    def _validate_boundaries(self) -> BoundingBox:
        """Validates Cartesian coordinate boundaries.

        The max point must be strictly greater than the min point in all dimensions.
        """
        if self.max_point.x <= self.min_point.x:
            raise ValueError(
                f"Cartesian boundaries invalid: max_x ({self.max_point.x}) must be strictly greater than min_x ({self.min_point.x})."
            )
        if self.max_point.y <= self.min_point.y:
            raise ValueError(
                f"Cartesian boundaries invalid: max_y ({self.max_point.y}) must be strictly greater than min_y ({self.min_point.y})."
            )
        if self.max_point.z <= self.min_point.z:
            raise ValueError(
                f"Cartesian boundaries invalid: max_z ({self.max_point.z}) must be strictly greater than min_z ({self.min_point.z})."
            )
        return self

    @property
    def dimensions(self) -> Tuple[float, float, float]:
        return (
            self.max_point.x - self.min_point.x,
            self.max_point.y - self.min_point.y,
            self.max_point.z - self.min_point.z,
        )

    @property
    def center(self) -> Point:
        return Point(
            (self.min_point.x + self.max_point.x) / 2.0,
            (self.min_point.y + self.max_point.y) / 2.0,
            (self.min_point.z + self.max_point.z) / 2.0,
        )

    @property
    def volume(self) -> float:
        dx, dy, dz = self.dimensions
        return dx * dy * dz

    @classmethod
    def from_points(cls, points: Sequence[Any], padding: float = 0.0) -> BoundingBox:
        if not points:
            raise ValueError("Cannot construct BoundingBox from an empty point sequence")
        if padding < 0.0:
            raise ValueError("Padding must be non-negative")

        pts = [p if isinstance(p, Point) else Point(p) for p in points]
        min_x = min(p.x for p in pts) - padding
        min_y = min(p.y for p in pts) - padding
        min_z = min(p.z for p in pts) - padding

        max_x = max(p.x for p in pts) + padding
        max_y = max(p.y for p in pts) + padding
        max_z = max(p.z for p in pts) + padding

        return cls(min_point=Point(min_x, min_y, min_z), max_point=Point(max_x, max_y, max_z))

    @classmethod
    def from_center_and_dimensions(
        cls, center: Any, dimensions: Sequence[float] | Tuple[float, float, float]
    ) -> BoundingBox:
        if len(dimensions) != 3 or any(d <= 0 for d in dimensions):
            raise ValueError("All dimensions must be strictly positive")
        c = center if isinstance(center, Point) else Point(center)
        hx = dimensions[0] / 2.0
        hy = dimensions[1] / 2.0
        hz = dimensions[2] / 2.0
        return cls(
            min_point=Point(c.x - hx, c.y - hy, c.z - hz),
            max_point=Point(c.x + hx, c.y + hy, c.z + hz),
        )

    @classmethod
    def from_min_max_coords(
        cls, min_coords: Sequence[float], max_coords: Sequence[float]
    ) -> BoundingBox:
        return cls(
            min_point=Point.from_tuple(min_coords),
            max_point=Point.from_tuple(max_coords),
        )

    def contains_point(self, point: Any, inclusive: bool = True) -> bool:
        p = point if isinstance(point, Point) else Point(point)
        if inclusive:
            return (
                self.min_point.x <= p.x <= self.max_point.x
                and self.min_point.y <= p.y <= self.max_point.y
                and self.min_point.z <= p.z <= self.max_point.z
            )
        return (
            self.min_point.x < p.x < self.max_point.x
            and self.min_point.y < p.y < self.max_point.y
            and self.min_point.z < p.z < self.max_point.z
        )

    def __contains__(self, point: Any) -> bool:
        return self.contains_point(point, inclusive=True)

    def clamp_point(self, point: Any) -> Point:
        p = point if isinstance(point, Point) else Point(point)
        cx = max(self.min_point.x, min(self.max_point.x, p.x))
        cy = max(self.min_point.y, min(self.max_point.y, p.y))
        cz = max(self.min_point.z, min(self.max_point.z, p.z))
        return Point(cx, cy, cz)

    def distance_to_point(self, point: Any) -> float:
        p = point if isinstance(point, Point) else Point(point)
        clamped = self.clamp_point(p)
        return p.distance_to(clamped)

    def intersects(self, other: BoundingBox) -> bool:
        return not (
            self.max_point.x < other.min_point.x
            or self.min_point.x > other.max_point.x
            or self.max_point.y < other.min_point.y
            or self.min_point.y > other.max_point.y
            or self.max_point.z < other.min_point.z
            or self.min_point.z > other.max_point.z
        )

    def intersection(self, other: BoundingBox) -> Optional[BoundingBox]:
        min_x = max(self.min_point.x, other.min_point.x)
        min_y = max(self.min_point.y, other.min_point.y)
        min_z = max(self.min_point.z, other.min_point.z)

        max_x = min(self.max_point.x, other.max_point.x)
        max_y = min(self.max_point.y, other.max_point.y)
        max_z = min(self.max_point.z, other.max_point.z)

        if max_x <= min_x or max_y <= min_y or max_z <= min_z:
            return None

        return BoundingBox(min_point=Point(min_x, min_y, min_z), max_point=Point(max_x, max_y, max_z))

    def union(self, other: BoundingBox) -> BoundingBox:
        min_x = min(self.min_point.x, other.min_point.x)
        min_y = min(self.min_point.y, other.min_point.y)
        min_z = min(self.min_point.z, other.min_point.z)

        max_x = max(self.max_point.x, other.max_point.x)
        max_y = max(self.max_point.y, other.max_point.y)
        max_z = max(self.max_point.z, other.max_point.z)

        return BoundingBox(min_point=Point(min_x, min_y, min_z), max_point=Point(max_x, max_y, max_z))

    def expand(self, delta: float) -> BoundingBox:
        return BoundingBox(
            min_point=Point(self.min_point.x - delta, self.min_point.y - delta, self.min_point.z - delta),
            max_point=Point(self.max_point.x + delta, self.max_point.y + delta, self.max_point.z + delta),
        )

    def scale(self, factor: float) -> BoundingBox:
        if factor <= 0:
            raise ValueError("Scale factor must be strictly positive")
        c = self.center
        dims = self.dimensions
        new_dims = (dims[0] * factor, dims[1] * factor, dims[2] * factor)
        return BoundingBox.from_center_and_dimensions(c, new_dims)

    def translate(self, dx: float, dy: float, dz: float) -> BoundingBox:
        return BoundingBox(
            min_point=Point(self.min_point.x + dx, self.min_point.y + dy, self.min_point.z + dz),
            max_point=Point(self.max_point.x + dx, self.max_point.y + dy, self.max_point.z + dz),
        )

    def __str__(self) -> str:
        dx, dy, dz = self.dimensions
        return f"BoundingBox(min={self.min_point}, max={self.max_point}, dims=({dx:.2f}, {dy:.2f}, {dz:.2f}))"


def euclidean_distance(p1: Any, p2: Any) -> float:
    pt1 = p1 if isinstance(p1, Point) else Point(p1)
    pt2 = p2 if isinstance(p2, Point) else Point(p2)
    return pt1.distance_to(pt2)


def manhattan_distance(p1: Any, p2: Any) -> float:
    pt1 = p1 if isinstance(p1, Point) else Point(p1)
    pt2 = p2 if isinstance(p2, Point) else Point(p2)
    return abs(pt1.x - pt2.x) + abs(pt1.y - pt2.y) + abs(pt1.z - pt2.z)


def angle_between(p1: Any, p2: Any, p3: Any, degrees: bool = False) -> float:
    """Calculates valence bond angle p1 - p2 - p3 (p2 is apex)."""
    pt1 = p1 if isinstance(p1, Point) else Point(p1)
    apex = p2 if isinstance(p2, Point) else Point(p2)
    pt3 = p3 if isinstance(p3, Point) else Point(p3)

    v1 = pt1 - apex
    v2 = pt3 - apex

    n1 = v1.norm()
    n2 = v2.norm()
    if n1 == 0.0 or n2 == 0.0:
        raise ValueError("Cannot calculate angle with degenerate zero-length bond vectors")

    cos_val = max(-1.0, min(1.0, v1.dot(v2) / (n1 * n2)))
    rad = math.acos(cos_val)
    return math.degrees(rad) if degrees else rad


def dihedral_angle(p1: Any, p2: Any, p3: Any, p4: Any, degrees: bool = False) -> float:
    """Calculates dihedral torsion angle p1 - p2 - p3 - p4."""
    pt1 = p1 if isinstance(p1, Point) else Point(p1)
    pt2 = p2 if isinstance(p2, Point) else Point(p2)
    pt3 = p3 if isinstance(p3, Point) else Point(p3)
    pt4 = p4 if isinstance(p4, Point) else Point(p4)

    b1 = pt2 - pt1
    b2 = pt3 - pt2
    b3 = pt4 - pt3

    b2_norm = b2.norm()
    if b2_norm == 0.0:
        raise ValueError("Cannot calculate dihedral angle with degenerate central bond")

    n1 = b1.cross(b2)
    n2 = b2.cross(b3)

    if n1.norm() == 0.0 or n2.norm() == 0.0:
        raise ValueError("Cannot calculate dihedral angle with collinear bond vectors")

    n1_norm = n1.normalized()
    n2_norm = n2.normalized()
    b2_dir = b2.normalized()

    m1 = n1_norm.cross(b2_dir)

    x = n1_norm.dot(n2_norm)
    y = m1.dot(n2_norm)

    rad = math.atan2(y, x)
    return math.degrees(rad) if degrees else rad


def centroid(points: Sequence[Any]) -> Point:
    if not points:
        raise ValueError("Cannot calculate centroid of an empty sequence of points")
    pts = [p if isinstance(p, Point) else Point(p) for p in points]
    n = len(pts)
    return Point(
        sum(p.x for p in pts) / n,
        sum(p.y for p in pts) / n,
        sum(p.z for p in pts) / n,
    )


def radius_of_gyration(
    points: Sequence[Any], masses: Optional[Sequence[float]] = None
) -> float:
    if not points:
        raise ValueError("Cannot calculate radius of gyration of an empty sequence of points")

    pts = [p if isinstance(p, Point) else Point(p) for p in points]
    n = len(pts)

    if masses is not None:
        if len(masses) != n:
            raise ValueError(f"Length of masses ({len(masses)}) does not match points ({n})")
        total_m = sum(masses)
        if total_m <= 0:
            raise ValueError("Total mass must be strictly positive")

        c = Point(
            sum(p.x * m for p, m in zip(pts, masses)) / total_m,
            sum(p.y * m for p, m in zip(pts, masses)) / total_m,
            sum(p.z * m for p, m in zip(pts, masses)) / total_m,
        )
        rg_sq = sum(m * (p.distance_to(c)**2) for p, m in zip(pts, masses)) / total_m
        return math.sqrt(rg_sq)

    c = centroid(pts)
    rg_sq = sum(p.distance_to(c)**2 for p in pts) / n
    return math.sqrt(rg_sq)


__all__ = [
    "BoundingBox",
    "Point",
    "angle_between",
    "centroid",
    "dihedral_angle",
    "euclidean_distance",
    "manhattan_distance",
    "radius_of_gyration",
]

