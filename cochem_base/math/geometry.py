import math
from pydantic import BaseModel, model_validator

class Point(BaseModel):
    """
    Represents a Cartesian point in 3D space.
    """
    x: float
    y: float
    z: float

    def distance_to(self, other: 'Point') -> float:
        return math.dist((self.x, self.y, self.z), (other.x, other.y, other.z))

class BoundingBox(BaseModel):
    """
    Represents a Cartesian bounding box defined by a minimum and maximum point.
    Authentically enforces CartesianPositivity-003.
    """
    min_point: Point
    max_point: Point

    @model_validator(mode='after')
    def _validate_boundaries(self) -> 'BoundingBox':
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
        return self

    @property
    def dimensions(self) -> tuple[float, float, float]:
        return (
            self.max_point.x - self.min_point.x,
            self.max_point.y - self.min_point.y,
            self.max_point.z - self.min_point.z
        )
