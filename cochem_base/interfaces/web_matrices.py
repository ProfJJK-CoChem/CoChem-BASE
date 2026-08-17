"""
Web Matrices Module.

This module handles the serialization and validation of sparse matrices
for WebGL-based user interfaces, ensuring consistent binary packing
and format compliance.
"""

import base64
from typing import Dict, List, Any, Optional, Tuple

import numpy as np
from pydantic import BaseModel


class SparsityDimensions(BaseModel):
    """Dimensions of a sparse matrix."""
    rows: int
    cols: int


class MatrixElement(BaseModel):
    """A single element in a sparse matrix."""
    row: int
    col: int
    value: float


class BrowserSparsityPayload(BaseModel):
    """Payload format for BrowserSparsity-004 specification."""
    version: str
    dimensions: SparsityDimensions
    rows_b64: str
    cols_b64: str
    vals_b64: str


class WebSparsityMatrix:
    """
    Handles sparse matrices formatting for WebGL UI.
    Supports BrowserSparsity-004.
    Properly packs data into binary blobs using numpy with explicit little-endian types.
    """
    def __init__(self, rows: int, cols: int, data: Optional[List[Dict[str, Any]]] = None) -> None:
        self.rows: int = rows
        self.cols: int = cols
        self.data_dict: Dict[Tuple[int, int], float] = {}
        if data is not None:
            for d in data:
                # Enforce structural validation using Pydantic to prevent KeyError/ValueError
                element = MatrixElement(**d)
                self.add_element(element.row, element.col, element.value)

    def add_element(self, row: int, col: int, value: float) -> None:
        """Adds a single element to the sparse matrix."""
        if 0 <= row < self.rows and 0 <= col < self.cols:
            self.data_dict[(int(row), int(col))] = float(value)
        else:
            raise ValueError(f"Index out of bounds: ({row}, {col}) for dimensions ({self.rows}, {self.cols})")

    def to_browser_format(self) -> BrowserSparsityPayload:
        """
        Converts the matrix to a BrowserSparsity-004 compliant binary blob structure.
        Returns a BrowserSparsityPayload Pydantic model.
        """
        rows_list: List[int] = []
        cols_list: List[int] = []
        vals_list: List[float] = []
        for (r, c), v in self.data_dict.items():
            rows_list.append(r)
            cols_list.append(c)
            vals_list.append(v)

        # Explicitly use little-endian (<) for WebGL cross-platform consistency
        rows_arr = np.array(rows_list, dtype='<i4')
        cols_arr = np.array(cols_list, dtype='<i4')
        vals_arr = np.array(vals_list, dtype='<f4')

        return BrowserSparsityPayload(
            version="BrowserSparsity-004",
            dimensions=SparsityDimensions(rows=self.rows, cols=self.cols),
            rows_b64=base64.b64encode(rows_arr.tobytes()).decode('ascii'),
            cols_b64=base64.b64encode(cols_arr.tobytes()).decode('ascii'),
            vals_b64=base64.b64encode(vals_arr.tobytes()).decode('ascii')
        )
