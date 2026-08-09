import pytest
from cochem_base.core.models import CorrelationMatrix, ToposStage, GeomTorqStage

def test_pipeline_data_flow():
    """Verify that parameters generated in TOPOS correctly map into GEOM/TORQ without data loss."""
    
    # Simulate TOPOS completion
    topos_data = ToposStage(
        mmff94_conformer="/tmp/mol_mmff94.xyz",
        smiles_string="C1=CC=CC=C1",
        torsional_scan=[5.0, 10.0, 15.0],
        point_group_id="D6h",
        z_matrix="C 0.0 0.0 0.0\n...",
        temperature=298.15,
        multiplicity=1
    )
    
    # Pass to correlation matrix
    matrix = CorrelationMatrix(topos=topos_data)
    
    # Simulate routing to GEOM/TORQ
    # GEOM requires the z_matrix or conformer from TOPOS
    # We simulate GEOM initializing using TOPOS outputs
    geom_data = GeomTorqStage(
        b3lyp_opt=matrix.topos.mmff94_conformer + ".opt",
        internal_coords={"length": 1.4}
    )
    matrix.geom_torq = geom_data
    
    # Validate
    assert matrix.topos.smiles_string == "C1=CC=CC=C1"
    assert matrix.geom_torq.b3lyp_opt == "/tmp/mol_mmff94.xyz.opt"
    assert matrix.topos.temperature == 298.15
    assert matrix.topos.multiplicity == 1

def test_pydantic_physical_bounds():
    """Test Phase 5 Scientific Error Prevention for Negative Temperatures."""
    with pytest.raises(ValueError, match="Input should be greater than"):
        ToposStage(
            temperature=-10.0, # Illegal negative Kelvin
            multiplicity=1
        )
        
    with pytest.raises(ValueError, match="Input should be greater than or equal to 1"):
        ToposStage(
            temperature=300.0,
            multiplicity=0 # Illegal zero multiplicity
        )
