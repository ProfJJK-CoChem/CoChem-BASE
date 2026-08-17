import os

from calc.cochem_calc_execution_router import ExecutionRouter
from calc.cochem_calc_input_generator import MoleculeInput, generate_orca_input


def test_execution_router_dispatch():
    """Test router safely defaults to subprocess locally."""
    router = ExecutionRouter()
    # It should route an unknown engine to subprocess safely
    path = router.resolve_execution_path("unknown_engine_99")
    assert path == "subprocess"

def test_generate_orca_input():
    """Test native disk generation of ORCA input file."""
    coords = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]
    elements = ["O", "Ti"] # Ti triggers tight grid

    mol_input = MoleculeInput(
        basin_id="test_basin_123",
        coordinates=coords,
        elements=elements,
        theory_level="B3LYP def2-SVP"
    )
    inp_path = generate_orca_input(mol_input)

    assert inp_path.exists()
    assert inp_path.is_file()

    with open(inp_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "defgrid3" in content # Ti -> tight grid
    assert "CoChem-CORE Cryptographic Provenance Stamp" in content

    # Clean up
    if inp_path.exists():
        os.remove(inp_path)
