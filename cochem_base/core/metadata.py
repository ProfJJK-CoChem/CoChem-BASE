from typing import Dict, List, Optional, Any, Callable
import functools
import time

class LAPACKCitationTracker:
    """
    Tracks and stores OpenAlex DOI citations for LAPACK routines.
    """
    def __init__(self):
        # Maps LAPACK routine names to a list of DOIs
        self._citations: Dict[str, List[str]] = {}

    def add_citation(self, routine_name: str, doi: str) -> None:
        """
        Stores an OpenAlex DOI for the specified LAPACK routine.
        """
        if not routine_name or not doi:
            raise ValueError("Routine name and DOI must be non-empty strings.")
            
        routine_name = routine_name.strip().lower()
        doi = doi.strip()
        
        if routine_name not in self._citations:
            self._citations[routine_name] = []
            
        if doi not in self._citations[routine_name]:
            self._citations[routine_name].append(doi)

    def get_citations(self, routine_name: str) -> List[str]:
        """
        Retrieves all citations for a given LAPACK routine.
        """
        routine_name = routine_name.strip().lower()
        return self._citations.get(routine_name, []).copy()

    def get_all_routines(self) -> List[str]:
        """
        Returns a list of all LAPACK routines that have citations.
        """
        return list(self._citations.keys())

    def clear(self) -> None:
        """
        Clears all stored citations.
        """
        self._citations.clear()

class ProvenanceTracker:
    """
    Tracks provenance data (seeds, function names, arguments, etc.) for stochastic/PRNG routines.
    """
    def __init__(self):
        self._records: List[Dict[str, Any]] = []

    def record_execution(self, func_name: str, seed: Any, args: tuple, kwargs: dict) -> None:
        """
        Records the execution of a stochastic function.
        """
        if seed is None:
            raise ValueError("Seed cannot be None for provenance tracking.")
            
        record = {
            "function": func_name,
            "seed": seed,
            "args": args,
            "kwargs": kwargs,
            "timestamp": time.time()
        }
        self._records.append(record)

    def get_records(self) -> List[Dict[str, Any]]:
        """
        Returns all execution records.
        """
        return self._records.copy()

    def clear(self) -> None:
        """
        Clears all execution records.
        """
        self._records.clear()

# Global tracker instance
default_provenance_tracker = ProvenanceTracker()

def execute_with_provenance(func: Callable = None, *, tracker: Optional[ProvenanceTracker] = None) -> Callable:
    """
    Decorator that records provenance data (seed, function name, args) when a stochastic/PRNG function is executed.
    Requires a 'seed' keyword argument to be present.
    """
    if func is None:
        return functools.partial(execute_with_provenance, tracker=tracker)
        
    actual_tracker = tracker if tracker is not None else default_provenance_tracker

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if "seed" not in kwargs:
            raise ValueError(f"Stochastic function '{func.__name__}' requires a 'seed' keyword argument for provenance tracking.")
            
        seed = kwargs["seed"]
        try:
            actual_tracker.record_execution(func.__name__, seed, args, kwargs)
        except Exception as e:
            raise RuntimeError(f"Provenance tracking failed for '{func.__name__}': {str(e)}") from e
            
        return func(*args, **kwargs)
        
    return wrapper
