import sys
import traceback
from cochem_base.core import execute_with_provenance, ProvenanceTracker
from cochem_base.core.metadata import default_provenance_tracker

try:
    print("Testing execute_with_provenance...")
    
    @execute_with_provenance
    def my_stochastic_func(x, seed=None):
        return x * 2

    # Test success
    res = my_stochastic_func(10, seed=42)
    print("Result:", res)
    
    records = default_provenance_tracker.get_records()
    print("Records length:", len(records))
    print("Record:", records[0]['function'], records[0]['seed'])

    # Test failure due to missing seed
    try:
        my_stochastic_func(5)
        print("FAIL: Should have raised ValueError")
    except ValueError as e:
        print("Caught expected ValueError:", e)

    # Test failure due to None seed
    try:
        my_stochastic_func(5, seed=None)
        print("FAIL: Should have raised RuntimeError")
    except RuntimeError as e:
        print("Caught expected RuntimeError:", e)
        
    print("SUCCESS")
except Exception as e:
    traceback.print_exc()
