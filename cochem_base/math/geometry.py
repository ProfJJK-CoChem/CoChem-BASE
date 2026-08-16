import math

class Point:
    """
    Represents a Cartesian point in 3D space.
    """
    def __init__(self, x: float, y: float, z: float):
        self.x = x
        self.y = y
        self.z = z

    def distance_to(self, other: 'Point') -> float:
        dist = math.sqrt((self.x - other.x)**2 + (self.y - other.y)**2 + (self.z - other.z)**2)
        if dist < 0:
            raise ValueError("Distance cannot be negative. This should be mathematically impossible.")
        return dist

class BoundingBox:
    """
    Represents a Cartesian bounding box defined by a minimum and maximum point.
    Authentically enforces CartesianPositivity-003.
    """
    def __init__(self, min_point: Point, max_point: Point):
        self.min_point = min_point
        self.max_point = max_point
        self._validate_boundaries()

    def _validate_boundaries(self):
        """
        Validates Cartesian coordinate boundaries.
        The max point must be strictly greater than the min point in all dimensions,
        yielding strictly positive dimensions for the bounding box.
        """
        if self.max_point.x <= self.min_point.x:
            raise ValueError(f"Cartesian boundaries invalid: max_x ({self.max_point.x}) must be strictly greater than min_x ({self.min_point.x}).")
        if self.max_point.y <= self.min_point.y:
            raise ValueError(f"Cartesian boundaries invalid: max_y ({self.max_point.y}) must be strictly greater than min_y ({self.min_point.y}).")
        if self.max_point.z <= self.min_point.z:
            raise ValueError(f"Cartesian boundaries invalid: max_z ({self.max_point.z}) must be strictly greater than min_z ({self.min_point.z}).")

    @property
    def dimensions(self):
        return (
            self.max_point.x - self.min_point.x,
            self.max_point.y - self.min_point.y,
            self.max_point.z - self.min_point.z
        )
