import sys
from cochem_base.io.molecule_definition import Atom, Molecule

def main():
    print("Running Molecule tests...")
    
    # 1. Test valid parsing
    xyz_data = '''3
Water Molecule
O 0.000 0.000 0.117
H 0.000 0.757 -0.477
H 0.000 -0.757 -0.477
'''
    try:
        mol = Molecule.from_xyz(xyz_data)
        print(f"Successfully parsed: {mol}")
        for atom in mol.atoms:
            print(f"  {atom}")
    except Exception as e:
        print(f"Failed to parse valid XYZ: {e}")
        sys.exit(1)
        
    # 2. Test AtomicPositivity validation
    print("\nTesting strict positivity validation...")
    try:
        # X doesn't exist in our table, will default to Z=0
        invalid_xyz = '''1
Invalid
X 0.0 0.0 0.0
'''
        Molecule.from_xyz(invalid_xyz)
        print("FAIL: Did not raise ValueError for invalid atomic number.")
        sys.exit(1)
    except ValueError as e:
        print(f"SUCCESS: Caught expected ValueError: {e}")
        
    try:
        # Directly pass invalid Z
        Atom("U", -92, 0, 0, 0)
        print("FAIL: Did not raise ValueError for negative atomic number.")
        sys.exit(1)
    except ValueError as e:
        print(f"SUCCESS: Caught expected ValueError: {e}")
        
    print("\nAll tests passed successfully.")

if __name__ == "__main__":
    main()
