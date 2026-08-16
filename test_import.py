import sys

try:
    import cochem_base.math.assertions
    print("Import successful", file=sys.stdout)
except Exception as e:
    print(f"Import failed: {e}", file=sys.stderr)
