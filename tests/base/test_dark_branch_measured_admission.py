"""Missing native observations cannot become zero or equilibrium populations."""
from pathlib import Path
import json
from cochem_base.spectroscopy.parser import SpectroscopyTelemetryParser
from cochem_base.formatters.cochem_dark_branch_filter import DarkBranchFilter

FIXTURE = Path(__file__).parents[1] / "data/orca_6_1_1_water_hf_sto3g/water.out.txt"


def test_real_native_dipole_with_unknown_relative_energy_never_gets_population():
    native = SpectroscopyTelemetryParser().parse_file(FIXTURE)
    source = {"conformer_id": "native-water", "source_sha256": native.source_sha256,
              "dipole_total_debye": native.total_dipole}
    retained, summary = DarkBranchFilter().filter_conformer_ensemble([source])
    assert len(retained) == 1 and retained[0]["is_bright"] is None
    assert retained[0]["relative_energy_kcal_mol"] is None
    assert retained[0]["boltzmann_weight"] is None
    assert retained[0]["dipole_total_debye"] == native.total_dipole
    assert "relative_energy_kcal_mol" not in source
    assert summary["conformer_evaluation_temperature_k"] is None
    assert summary["configured_rotational_temperature_k"] == 2.0
    json.dumps(summary, allow_nan=False)


def test_missing_one_native_dipole_component_stays_unknown_and_retained():
    native = SpectroscopyTelemetryParser().parse_file(FIXTURE)
    source = {"conformer_id": "native-water", "source_sha256": native.source_sha256,
              "mu_a": native.dipole_components[0], "mu_b": native.dipole_components[1]}
    retained, summary = DarkBranchFilter().filter_conformer_ensemble([source])
    assert retained[0]["dipole_total_debye"] is None
    assert retained[0]["is_bright"] is None
    assert summary["dark_conformers_count"] == 0
    assert "dipole_unavailable_reason" in retained[0]


def test_complete_native_vector_can_be_inspected_but_cannot_create_gibbs_population():
    native = SpectroscopyTelemetryParser().parse_file(FIXTURE)
    source = dict(zip(("mu_a", "mu_b", "mu_c"), native.dipole_components, strict=True))
    source["source_sha256"] = native.source_sha256
    retained, _ = DarkBranchFilter().filter_conformer_ensemble([source])
    assert retained[0]["dipole_total_debye"] > 1.7
    assert retained[0]["population_kind"] == "unavailable_unqualified_legacy_ensemble"
    assert retained[0]["boltzmann_weight"] is None
