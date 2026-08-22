"""Physical Electrostatics and Dual-Number Forward-Mode Automatic Differentiation Engine.

Implements Coulomb potential, electric fields, electrostatic force vectors, singularity
traps, and DualNumber arithmetic for computing exact analytical derivatives.
"""

from __future__ import annotations

import math
from typing import Any, Callable, List, Optional, Sequence, Tuple, Union

COULOMB_CONSTANT: float = 8.9875517923e9
DEFAULT_SINGULARITY_THRESHOLD: float = 1e-12
ELEMENTARY_CHARGE: float = 1.602176634e-19


class SingularityError(ValueError):
    """Exception raised when a distance singularity or division by zero is encountered."""

    def __init__(
        self,
        message: Optional[str] = None,
        distance: Optional[float] = None,
        threshold: Optional[float] = None,
    ) -> None:
        self.distance = distance
        self.threshold = threshold
        if message is None:
            if distance is not None and threshold is not None:
                message = f"Distance {distance} is dangerously close to zero (threshold={threshold}), causing a singularity."
            elif distance is not None:
                message = f"Distance {distance} is dangerously close to zero, causing a singularity."
            else:
                message = "A distance singularity was encountered."
        super().__init__(message)


def coulomb_potential(
    q1: float,
    q2: float,
    distance: float,
    k: float = COULOMB_CONSTANT,
    singularity_threshold: float = DEFAULT_SINGULARITY_THRESHOLD,
) -> float:
    """Calculates the Coulomb electrostatic potential between two point charges in Joules."""
    if singularity_threshold <= 0:
        raise ValueError("singularity_threshold must be strictly positive")
    if distance < singularity_threshold:
        raise SingularityError(
            f"Distance {distance} is dangerously close to zero, causing a singularity.",
            distance=distance,
            threshold=singularity_threshold,
        )
    return float(k * q1 * q2 / distance)


def coulomb_gradient(
    q1: float,
    q2: float,
    dx: float,
    dy: float,
    dz: float,
    k: float = COULOMB_CONSTANT,
    singularity_threshold: float = DEFAULT_SINGULARITY_THRESHOLD,
) -> Tuple[float, float, float]:
    """Calculates the gradient of the Coulomb potential (force vector components)."""
    if singularity_threshold <= 0:
        raise ValueError("singularity_threshold must be strictly positive")
    distance_sq = dx**2 + dy**2 + dz**2
    distance = math.sqrt(distance_sq)

    if distance < singularity_threshold:
        raise SingularityError(
            f"Distance {distance} is dangerously close to zero, causing a singularity.",
            distance=distance,
            threshold=singularity_threshold,
        )

    magnitude = k * q1 * q2 / (distance_sq * distance)
    return (float(magnitude * dx), float(magnitude * dy), float(magnitude * dz))


def coulomb_field(
    q: float,
    dx: float,
    dy: float,
    dz: float,
    k: float = COULOMB_CONSTANT,
    singularity_threshold: float = DEFAULT_SINGULARITY_THRESHOLD,
) -> Tuple[float, float, float]:
    """Calculates the electric field vector created by point charge q at displacement (dx, dy, dz)."""
    return coulomb_gradient(q, 1.0, dx, dy, dz, k=k, singularity_threshold=singularity_threshold)


def coulomb_force(
    q1: float,
    q2: float,
    pos1: Sequence[float],
    pos2: Sequence[float],
    k: float = COULOMB_CONSTANT,
    singularity_threshold: float = DEFAULT_SINGULARITY_THRESHOLD,
) -> Tuple[float, float, float]:
    """Calculates the electrostatic force vector acting on charge 1 due to charge 2."""
    if len(pos1) != 3 or len(pos2) != 3:
        raise ValueError("Cartesian position vectors must have length 3")
    dx = float(pos1[0] - pos2[0])
    dy = float(pos1[1] - pos2[1])
    dz = float(pos1[2] - pos2[2])
    return coulomb_gradient(q1, q2, dx, dy, dz, k=k, singularity_threshold=singularity_threshold)


class DualNumber:
    """A dual number (a + bε where ε² = 0) for exact forward-mode automatic differentiation."""

    __slots__ = ("real", "dual")

    def __init__(self, real: float, dual: float = 0.0) -> None:
        self.real = float(real)
        self.dual = float(dual)

    def __repr__(self) -> str:
        return f"DualNumber(real={self.real}, dual={self.dual})"

    def __str__(self) -> str:
        return f"{self.real} + {self.dual}ε"

    def __float__(self) -> float:
        return self.real

    def __pos__(self) -> DualNumber:
        return DualNumber(self.real, self.dual)

    def __neg__(self) -> DualNumber:
        return DualNumber(-self.real, -self.dual)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, DualNumber):
            return self.real == other.real and self.dual == other.dual
        if isinstance(other, (int, float)):
            return self.real == float(other) and self.dual == 0.0
        return False

    def __add__(self, other: Union[DualNumber, float, int]) -> DualNumber:
        if isinstance(other, DualNumber):
            return DualNumber(self.real + other.real, self.dual + other.dual)
        return DualNumber(self.real + float(other), self.dual)

    def __radd__(self, other: Union[float, int]) -> DualNumber:
        return DualNumber(self.real + float(other), self.dual)

    def __sub__(self, other: Union[DualNumber, float, int]) -> DualNumber:
        if isinstance(other, DualNumber):
            return DualNumber(self.real - other.real, self.dual - other.dual)
        return DualNumber(self.real - float(other), self.dual)

    def __rsub__(self, other: Union[float, int]) -> DualNumber:
        return DualNumber(float(other) - self.real, -self.dual)

    def __mul__(self, other: Union[DualNumber, float, int]) -> DualNumber:
        if isinstance(other, DualNumber):
            return DualNumber(
                self.real * other.real,
                self.real * other.dual + self.dual * other.real,
            )
        f_other = float(other)
        return DualNumber(self.real * f_other, self.dual * f_other)

    def __rmul__(self, other: Union[float, int]) -> DualNumber:
        f_other = float(other)
        return DualNumber(self.real * f_other, self.dual * f_other)

    def __truediv__(self, other: Union[DualNumber, float, int]) -> DualNumber:
        if isinstance(other, DualNumber):
            if other.real == 0.0:
                raise ZeroDivisionError("Division by zero in DualNumber.")
            real = self.real / other.real
            dual = (self.dual * other.real - self.real * other.dual) / (other.real**2)
            return DualNumber(real, dual)
        f_other = float(other)
        if f_other == 0.0:
            raise ZeroDivisionError("Division by zero in DualNumber.")
        return DualNumber(self.real / f_other, self.dual / f_other)

    def __rtruediv__(self, other: Union[float, int]) -> DualNumber:
        if self.real == 0.0:
            raise ZeroDivisionError("Division by zero in DualNumber.")
        f_other = float(other)
        real = f_other / self.real
        dual = -f_other * self.dual / (self.real**2)
        return DualNumber(real, dual)

    def __pow__(self, power: Union[float, int]) -> DualNumber:
        p = float(power)
        if self.real == 0.0:
            if p <= 0:
                raise ValueError("Derivative undefined for non-positive power at zero")
            if p == 1.0:
                return DualNumber(0.0, self.dual)
            return DualNumber(0.0, 0.0)
        real = self.real**p
        dual = p * (self.real ** (p - 1.0)) * self.dual
        return DualNumber(real, dual)

    def sqrt(self) -> DualNumber:
        if self.real <= 0.0:
            raise ValueError("Square root undefined for non-positive dual number base.")
        s = math.sqrt(self.real)
        return DualNumber(s, self.dual / (2.0 * s))

    def exp(self) -> DualNumber:
        e = math.exp(self.real)
        return DualNumber(e, self.dual * e)

    def log(self) -> DualNumber:
        if self.real <= 0.0:
            raise ValueError("Logarithm undefined for non-positive dual number base.")
        return DualNumber(math.log(self.real), self.dual / self.real)

    def sin(self) -> DualNumber:
        return DualNumber(math.sin(self.real), self.dual * math.cos(self.real))

    def cos(self) -> DualNumber:
        return DualNumber(math.cos(self.real), -self.dual * math.sin(self.real))


def dual_gradient(
    f: Callable[[Sequence[DualNumber]], DualNumber],
    point: Sequence[float],
) -> Tuple[float, List[float]]:
    """Calculates the exact function value and gradient at point using forward-mode automatic differentiation."""
    n = len(point)
    # Evaluate function value
    dual_point_base = [DualNumber(float(x), 0.0) for x in point]
    base_val = f(dual_point_base).real

    gradient: List[float] = []
    for i in range(n):
        coords = [
            DualNumber(float(x), 1.0 if j == i else 0.0)
            for j, x in enumerate(point)
        ]
        res = f(coords)
        gradient.append(res.dual)

    return float(base_val), gradient


def numerical_gradient(
    f: Callable[[Sequence[float]], float],
    point: Sequence[float],
    h: float = 1e-6,
) -> List[float]:
    """Calculates numerical gradient using central finite differences."""
    if h <= 0:
        raise ValueError("Step size 'h' must be strictly positive")

    coords = [float(x) for x in point]
    grad: List[float] = []

    for i in range(len(coords)):
        coords_plus = list(coords)
        coords_minus = list(coords)
        coords_plus[i] += h
        coords_minus[i] -= h
        f_plus = f(coords_plus)
        f_minus = f(coords_minus)
        grad.append((f_plus - f_minus) / (2.0 * h))

    return grad


__all__ = [
    "COULOMB_CONSTANT",
    "DEFAULT_SINGULARITY_THRESHOLD",
    "DualNumber",
    "ELEMENTARY_CHARGE",
    "SingularityError",
    "coulomb_field",
    "coulomb_force",
    "coulomb_gradient",
    "coulomb_potential",
    "dual_gradient",
    "numerical_gradient",
]

