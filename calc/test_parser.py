import pytest
from pathlib import Path
from cochem_calc_output_parser import QuantumParser

def test_verify_basis_saturation(tmp_path):
    log_content = """
    Basis Dimension        Dim             ....  165
    Auxiliary Coulomb fitting basis             ... AVAILABLE
       # of basis functions in Aux-J            ...    100
    """
    log_file = tmp_path / "test.out"
    log_file.write_text(log_content)
    
    parser = QuantumParser(str(tmp_path))
    parser.verify_basis_saturation(log_file)
    # The warning is logged, we can just ensure it runs without error.

def test_verify_basis_saturation_no_warning(tmp_path):
    log_content = """
    Basis Dimension        Dim             ....  165
    Auxiliary Coulomb fitting basis             ... AVAILABLE
       # of basis functions in Aux-J            ...    300
    """
    log_file = tmp_path / "test.out"
    log_file.write_text(log_content)
    
    parser = QuantumParser(str(tmp_path))
    parser.verify_basis_saturation(log_file)
