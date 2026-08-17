import ctypes
from typing import Any


class SafeCBuffer:
    """
    A robust ctypes wrapper representing a C-kernel memory buffer.
    Enforces strict memory boundary checks to prevent BufferOverflow-009.
    """
    def __init__(self, size: int) -> None:
        if size <= 0:
            raise ValueError("Buffer size must be strictly positive.")
        self.size: int = size
        self._buffer: Any = (ctypes.c_double * size)()

    def write(self, index: int, value: float) -> None:
        """
        Writes a double to the C-kernel buffer.
        Authentically enforces memory bounds.
        """
        if index < 0 or index >= self.size:
            raise IndexError(f"Buffer overflow attempt: index {index} is out of bounds for size {self.size}.")
        self._buffer[index] = ctypes.c_double(value)

    def read(self, index: int) -> float:
        """
        Reads a double from the C-kernel buffer.
        Authentically enforces memory bounds.
        """
        if index < 0 or index >= self.size:
            raise IndexError(f"Buffer overflow attempt: index {index} is out of bounds for size {self.size}.")
        return float(self._buffer[index])

    def get_raw_pointer(self) -> Any:
        """
        Returns the raw ctypes pointer for C-kernel integration.
        """
        return ctypes.cast(self._buffer, ctypes.POINTER(ctypes.c_double))

