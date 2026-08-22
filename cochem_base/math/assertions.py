"""Floating-point numerical assertion utilities and continuous variable wrappers.

Intercepts exact floating-point equality comparisons on continuous simulation variables
to avoid machine epsilon loops, while providing robust scientific tolerance checks.
"""

from __future__ import annotations

import warnings
from typing import Any, Optional

import numpy as np
import numpy.typing as npt

DEFAULT_ATOL: float = 1e-8
DEFAULT_RTOL: float = 1e-5


class MachineEpsilonWarning(UserWarning):
    """Warning raised when exact equality is used on continuous variables."""

    def __init__(
        self,
        message: str = "Exact equality comparison (==) detected on a continuous simulation variable.",
    ) -> None:
        self.message = message
        super().__init__(self.message)

    def __str__(self) -> str:
        return self.message

    def __repr__(self) -> str:
        return f"MachineEpsilonWarning({self.message!r})"


class SimulationTensor(np.ndarray):
    """A custom wrapper for float64 tensors that actively intercepts logical

    evaluations to prevent infinite loops due to machine epsilon.
    """

    DEFAULT_ATOL: float = DEFAULT_ATOL
    DEFAULT_RTOL: float = DEFAULT_RTOL

    def __new__(
        cls,
        input_array: npt.ArrayLike,
        atol: float = DEFAULT_ATOL,
        rtol: float = DEFAULT_RTOL,
    ) -> SimulationTensor:
        if atol < 0:
            raise ValueError("Absolute tolerance 'atol' must be non-negative")
        if rtol < 0:
            raise ValueError("Relative tolerance 'rtol' must be non-negative")

        obj = np.asarray(input_array, dtype=np.float64).view(cls)
        obj._atol = float(atol)
        obj._rtol = float(rtol)
        return obj

    def __array_finalize__(self, obj: Optional[Any]) -> None:
        if obj is None:
            return
        self._atol = getattr(obj, "_atol", self.DEFAULT_ATOL)
        self._rtol = getattr(obj, "_rtol", self.DEFAULT_RTOL)

    @property
    def atol(self) -> float:
        return self._atol

    @atol.setter
    def atol(self, value: float) -> None:
        if value < 0:
            raise ValueError("Absolute tolerance 'atol' must be non-negative")
        self._atol = float(value)

    @property
    def rtol(self) -> float:
        return self._rtol

    @rtol.setter
    def rtol(self, value: float) -> None:
        if value < 0:
            raise ValueError("Relative tolerance 'rtol' must be non-negative")
        self._rtol = float(value)

    def is_close_to(
        self,
        other: Any,
        rtol: Optional[float] = None,
        atol: Optional[float] = None,
        equal_nan: bool = False,
    ) -> Any:
        """Performs exact numerical tolerance check without emitting MachineEpsilonWarning."""
        r_tol = self._rtol if rtol is None else float(rtol)
        a_tol = self._atol if atol is None else float(atol)
        self_arr = np.asarray(self)
        other_arr = np.asarray(other)
        return np.isclose(self_arr, other_arr, rtol=r_tol, atol=a_tol, equal_nan=equal_nan)

    def __eq__(self, other: Any) -> Any:
        warnings.warn(
            "Exact equality comparison (==) detected on a continuous simulation variable. "
            "This can lead to infinite loops due to machine epsilon errors. "
            "Forcefully injecting np.isclose() tolerance check.",
            MachineEpsilonWarning,
            stacklevel=2,
        )
        self_arr = np.asarray(self)
        other_arr = np.asarray(other)
        return np.isclose(self_arr, other_arr, atol=self._atol, rtol=self._rtol)

    def __ne__(self, other: Any) -> Any:
        warnings.warn(
            "Exact equality comparison (!=) detected on a continuous simulation variable. "
            "This can lead to infinite loops due to machine epsilon errors. "
            "Forcefully injecting np.isclose() tolerance check.",
            MachineEpsilonWarning,
            stacklevel=2,
        )
        self_arr = np.asarray(self)
        other_arr = np.asarray(other)
        return np.logical_not(np.isclose(self_arr, other_arr, atol=self._atol, rtol=self._rtol))


def assert_allclose_eps(
    actual: npt.ArrayLike,
    desired: npt.ArrayLike,
    rtol: float = DEFAULT_RTOL,
    atol: float = DEFAULT_ATOL,
    equal_nan: bool = False,
    err_msg: str = "",
    verbose: bool = True,
) -> None:
    """Convenience assertion wrapper around numpy.testing.assert_allclose with standard tolerances."""
    np.testing.assert_allclose(
        actual,
        desired,
        rtol=rtol,
        atol=atol,
        equal_nan=equal_nan,
        err_msg=err_msg,
        verbose=verbose,
    )


__all__ = [
    "DEFAULT_ATOL",
    "DEFAULT_RTOL",
    "MachineEpsilonWarning",
    "SimulationTensor",
    "assert_allclose_eps",
]

