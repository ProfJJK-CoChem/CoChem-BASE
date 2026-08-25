import xml.etree.ElementTree as ET
import tracemalloc
import time
import os
from typing import Any

class MemoryLimitExceeded(Exception):
    """Exception raised when memory usage exceeds the specified limit."""
    pass
class XMLParsingBenchmark:
    """
    Benchmarks XML parsing, focusing on memory constraints and execution time.
    """
    def __init__(self, memory_limit_mb: float = 2048.0) -> None:
        self.memory_limit_mb = memory_limit_mb
        self.memory_limit_bytes = memory_limit_mb * 1024 * 1024
        self.peak_memory_bytes = 0
        self.execution_time = 0.0

    def parse_file(self, filepath: str) -> None:
        """
        Iteratively parses an XML file and monitors memory usage.
        Raises MemoryLimitExceeded if peak memory > memory_limit_bytes.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"XML file not found: {filepath}")

        tracemalloc.start()
        start_time = time.time()
        
        try:
            context = ET.iterparse(filepath, events=('start', 'end'))
            context = iter(context)
            event, root = next(context)
            
            for event, elem in context:
                if event == 'end':
                    # Free memory for the element
                    elem.clear()
                    root.clear()
                    
                    # Periodically check memory limit (to fail fast on huge files)
                    current, peak = tracemalloc.get_traced_memory()
                    if peak > self.memory_limit_bytes:
                        self.peak_memory_bytes = peak
                        raise MemoryLimitExceeded(
                            f"Peak memory usage ({peak / (1024*1024):.2f} MB) "
                            f"exceeded limit of {self.memory_limit_mb} MB"
                        )
            
            # Final root clearance
            root.clear()
            
            # Capture final memory usage
            current, peak = tracemalloc.get_traced_memory()
            self.peak_memory_bytes = peak
            
            if peak > self.memory_limit_bytes:
                raise MemoryLimitExceeded(
                    f"Peak memory usage ({peak / (1024*1024):.2f} MB) "
                    f"exceeded limit of {self.memory_limit_mb} MB"
                )
                
        finally:
            self.execution_time = time.time() - start_time
            current, peak = tracemalloc.get_traced_memory()
            if peak > self.peak_memory_bytes:
                self.peak_memory_bytes = peak
            tracemalloc.stop()
            
    def get_stats(self) -> dict[str, Any]:
        return {
            "peak_memory_mb": self.peak_memory_bytes / (1024 * 1024),
            "execution_time_seconds": self.execution_time,
            "memory_limit_mb": self.memory_limit_mb
        }

def validate_xml_memory_usage(filepath: str, memory_limit_mb: float = 2048.0) -> tuple[bool, dict[str, Any]]:
    """
    Validates that parsing the given XML file does not exceed the specified memory limit.
    Returns a tuple of (is_valid, stats_dict).
    """
    benchmark = XMLParsingBenchmark(memory_limit_mb=memory_limit_mb)
    try:
        benchmark.parse_file(filepath)
        return True, benchmark.get_stats()
    except MemoryLimitExceeded as e:
        stats = benchmark.get_stats()
        stats["error"] = str(e)
        return False, stats
    except (FileNotFoundError, ET.ParseError, OSError) as e:
        return False, {"error": str(e)}
