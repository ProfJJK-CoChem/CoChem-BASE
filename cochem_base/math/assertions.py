import warnings
import numpy as np

class MachineEpsilonWarning(Warning):
    """Warning raised when exact equality is used on continuous variables."""
    def __init__(self, message="Exact equality comparison (==) detected on a continuous simulation variable."):
        self.message = message
        super().__init__(self.message)
        
    def __str__(self):
        return repr(self.message)
class SimulationTensor(np.ndarray):
    """
    A custom wrapper for float64 tensors that actively intercepts logical 
    evaluations to prevent infinite loops due to machine epsilon.
    """
    def __new__(cls, input_array):
        obj = np.asarray(input_array, dtype=np.float64).view(cls)
        return obj

    def __eq__(self, other):
        # We throw the warning
        warnings.warn(
            "Exact equality comparison (==) detected on a continuous simulation variable. "
            "This can lead to infinite loops due to machine epsilon errors. "
            "Forcefully injecting np.isclose() tolerance check.",
            MachineEpsilonWarning,
            stacklevel=2
        )
        
        # Forcefully inject np.isclose tolerance check, bypassing self to avoid infinite recursion
        self_arr = np.asarray(self)
        other_arr = np.asarray(other)
        return np.isclose(self_arr, other_arr, atol=1e-8, rtol=1e-5)

    def __ne__(self, other):
        return not self.__eq__(other)
