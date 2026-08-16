"""
Swarm messaging module for handling MPI broadcast gatekeeping.
"""
import time

class MPIBroadcastManager:
    """
    Manages and tracks messaging limits across a computational swarm
    to prevent broadcast floods.
    """
    def __init__(self, max_broadcasts: int = 100, window_seconds: float = 60.0):
        if max_broadcasts <= 0:
            raise ValueError("max_broadcasts must be > 0.")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be > 0.")
            
        self.max_broadcasts = max_broadcasts
        self.window_seconds = window_seconds
        self.broadcast_timestamps = []
        
    def _cleanup_old_records(self, current_time: float):
        """Remove broadcast records that fall outside the time window."""
        cutoff = current_time - self.window_seconds
        self.broadcast_timestamps = [t for t in self.broadcast_timestamps if t > cutoff]

    def request_broadcast(self) -> bool:
        """
        Request permission to perform an MPI broadcast.
        Raises RuntimeError if the broadcast limit is exceeded.
        """
        current_time = time.time()
        self._cleanup_old_records(current_time)
        
        if len(self.broadcast_timestamps) >= self.max_broadcasts:
            raise RuntimeError(
                f"MPI broadcast limit exceeded: {self.max_broadcasts} "
                f"broadcasts within {self.window_seconds} seconds."
            )
            
        self.broadcast_timestamps.append(current_time)
        return True

    def get_broadcast_count(self) -> int:
        """Return the number of broadcasts in the current window."""
        self._cleanup_old_records(time.time())
        return len(self.broadcast_timestamps)

    def reset(self):
        """Reset the broadcast tracker."""
        self.broadcast_timestamps.clear()

class OutOfMemoryGateError(RuntimeError):
    """Raised when memory allocation exceeds the permitted gate limits."""

def allocate_swarm_matrix(rows: int, cols: int, max_bytes: int):
    """
    Allocates a mock matrix structure, verifying memory limits.
    Assuming 8 bytes per float64 element.
    """
    required_bytes = rows * cols * 8
    if required_bytes > max_bytes:
        raise OutOfMemoryGateError(
            f"Allocation failed: required {required_bytes} bytes, max allowed is {max_bytes} bytes."
        )
    return {
        "rows": rows,
        "cols": cols,
        "total_bytes": required_bytes,
        "dtype": "float64",
        "mock_allocated": True
    }
