import numpy as np
import base64
import json

class WebSparsityMatrix:
    """
    Handles sparse matrices formatting for WebGL UI.
    Supports BrowserSparsity-004.
    Properly packs data into binary blobs using numpy.
    """
    def __init__(self, rows, cols, data=None):
        self.rows = rows
        self.cols = cols
        self.data_dict = {}
        if data is not None:
            for d in data:
                self.add_element(d['row'], d['col'], d['value'])
        
    def add_element(self, row, col, value):
        if 0 <= row < self.rows and 0 <= col < self.cols:
            self.data_dict[(int(row), int(col))] = float(value)
        else:
            raise ValueError("Index out of bounds")
            
    def to_browser_format(self):
        """
        Converts the matrix to a BrowserSparsity-004 compliant binary blob structure.
        Returns a dictionary with base64 encoded flat typed arrays (Float32Array for values, Int32Array for indices).
        """
        rows_list = []
        cols_list = []
        vals_list = []
        for (r, c), v in self.data_dict.items():
            rows_list.append(r)
            cols_list.append(c)
            vals_list.append(v)
            
        rows_arr = np.array(rows_list, dtype=np.int32)
        cols_arr = np.array(cols_list, dtype=np.int32)
        vals_arr = np.array(vals_list, dtype=np.float32)
        
        return {
            "version": "BrowserSparsity-004",
            "dimensions": {"rows": self.rows, "cols": self.cols},
            "rows_b64": base64.b64encode(rows_arr.tobytes()).decode('ascii'),
            "cols_b64": base64.b64encode(cols_arr.tobytes()).decode('ascii'),
            "vals_b64": base64.b64encode(vals_arr.tobytes()).decode('ascii')
        }
