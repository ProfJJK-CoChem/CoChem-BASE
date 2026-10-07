"""Parser format/absence checks; these fragments are not quantum reference data."""
import pytest

from cochem_base.core_engine.cochem_core_cfour_bridge import (
    CFOURInputConfig, CFOUROutputParser, export_cfour_to_spcat_var,
)
from cochem_base.exceptions import ConvergenceError


def test_empty_cfour_output_cannot_produce_zero_energy() -> None:
    with pytest.raises(ValueError, match="no measured finite electronic energy"):
        CFOUROutputParser.parse_cfour_stdout("No electronic results in this diagnostic stream")


def test_cfour_fortran_exponent_is_preserved_and_nan_is_rejected() -> None:
    result = CFOUROutputParser.parse_cfour_stdout("SCF energy: -1.25D+02")
    assert result.final_energy_hartree == -125
    with pytest.raises(ValueError):
        CFOUROutputParser.parse_cfour_stdout("SCF energy: -1.25D+02\nFINAL ENERGY: NaN")


def test_an_energy_token_does_not_fabricate_spectroscopy() -> None:
    # A deliberately incomplete parser fragment establishes only one numeric token.
    result = CFOUROutputParser.parse_cfour_stdout("SCF energy: -1.0")
    assert result.final_energy_hartree == -1
    assert result.Ae_MHz is None and result.Be_MHz is None and result.Ce_MHz is None
    assert result.B0_MHz is None and result.delta_B_vib_MHz is None
    assert result.dipole_total_debye is None
    assert result.harmonic_force_field.zpe_cm_inv is None
    with pytest.raises(ValueError, match="ground-state rotational constants"):
        export_cfour_to_spcat_var(result)


@pytest.mark.parametrize("fragment", [
    "SCF energy: -1.0",
    "SCF converged\nCCSD NOT CONVERGED",
    "SCF converged\nCCSD energy: -1.0",
])
def test_energy_or_zero_exit_cannot_replace_cfour_convergence(fragment: str) -> None:
    with pytest.raises(ConvergenceError):
        CFOUROutputParser.verify_execution_evidence(fragment, CFOURInputConfig())
