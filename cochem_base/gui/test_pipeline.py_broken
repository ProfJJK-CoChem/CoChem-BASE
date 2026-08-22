# Method Matrix: B3LYP-D3/D4 dispersion correction enforced
import pytest

from cochem_base.config_loader import get_artifact_dir
from cochem_base.core.models import CorrelationMatrix, GeomTorqStage, ToposStage


def test_pipeline_data_flow() -> None:
    """Verify that parameters generated in TOPOS correctly map into GEOM/TORQ without data loss."""

    conformer_path = str(get_artifact_dir() / "mol_goat_crest.xyz")

    topos_data = ToposStage(
        goat_crest_union=conformer_path,
        smiles_string="C1=CC=CC=C1",
        temperature=298.15,
        pressure_atm=1.0,
        multiplicity=1,
        charge=0,
        s_squared_threshold=0.10
    )

    matrix = CorrelationMatrix(topos=topos_data)

    geom_data = GeomTorqStage(
        frozen_monomer_opt=str(matrix.topos.goat_crest_union) + ".opt",
        dispersion_correction="D4",
        hessian_preconditioner="Lindh",
        grid_start="defgrid1",
        grid_final="defgrid3"
    )
    matrix.geom_torq = geom_data

    assert matrix.topos.smiles_string == "C1=CC=CC=C1"
    assert matrix.geom_torq.frozen_monomer_opt == conformer_path + ".opt"
    assert matrix.topos.temperature == 298.15
    assert matrix.topos.multiplicity == 1
    assert matrix.geom_torq.dispersion_correction == "D4"


def test_pydantic_physical_bounds() -> None:
    """Test Phase 5 Scientific Error Prevention for Negative Temperatures."""
    with pytest.raises(ValueError, match="Input should be greater than"):
        ToposStage(
            temperature=-10.0,  # Illegal negative Kelvin
            multiplicity=1
        )

    with pytest.raises(ValueError, match="Input should be greater than or equal to 1"):
        ToposStage(
            temperature=300.0,
            multiplicity=0  # Illegal zero multiplicity
        )
