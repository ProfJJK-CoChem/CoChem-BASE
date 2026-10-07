"""Real HDF/Parquet and table boundaries preserve absent Scribe observations."""

import json

import h5py
import numpy as np
import pandas as pd
import pytest

from cochem_base.harvesters.scribe_aggregator import (
    HARTREE_TO_KCAL_MOL,
    DataAggregator,
    compress_tensors_for_llm,
    flatten_conformers_to_df,
    flatten_spectroscopy_to_df,
    flatten_telemetry_to_df,
    flatten_thermodynamics_to_df,
)


@pytest.mark.parametrize("values", [[], [np.nan], [np.nan, np.inf, -np.inf]])
def test_unobserved_tensor_statistics_are_null(values):
    result = compress_tensors_for_llm(values)
    assert result == dict.fromkeys(("Min", "Max", "Mean", "StdDev"))
    json.dumps(result, allow_nan=False)


def test_tensor_statistics_use_only_finite_observations_and_keep_zero():
    assert compress_tensors_for_llm([np.nan, 0.0, 2.0, np.inf]) == {
        "Min": 0.0, "Max": 2.0, "Mean": 1.0, "StdDev": 1.0,
    }
    assert compress_tensors_for_llm([0.0]) == {
        "Min": 0.0, "Max": 0.0, "Mean": 0.0, "StdDev": 0.0,
    }


def test_tables_keep_missing_cells_distinct_from_measured_zero():
    conformers = flatten_conformers_to_df([
        {"conformer_id": "unobserved"},
        {"conformer_id": "invalid", "relative_energy_kcal_mol": np.inf},
        {"conformer_id": "ground", "relative_energy_kcal_mol": 0.0},
    ])
    assert conformers["relative_energy_kcal_mol"].isna().tolist() == [True, True, False]
    assert conformers.iloc[2]["relative_energy_kcal_mol"] == 0.0
    assert flatten_conformers_to_df([{}])["relative_energy_kcal_mol"].isna().all()
    assert flatten_spectroscopy_to_df({})["Value"].isna().all()
    spectrum = flatten_spectroscopy_to_df({
        "rotational_constants": {"A": 0.0, "B": None, "C": np.inf},
        "dipole_moments": {"mu_a": pd.NA},
    }).set_index("Parameter")
    assert spectrum.loc["A", "Value"] == 0.0
    assert spectrum.drop(index="A")["Value"].isna().all()
    thermal = flatten_thermodynamics_to_df({"zpe_kcal_mol": 0.0})
    assert thermal.iloc[0]["Value"] == 0.0
    assert thermal.iloc[1:]["Value"].isna().all()
    assert flatten_telemetry_to_df({})["Value"].isna().all()


def test_existing_dataframes_are_normalized_without_mutation():
    original = pd.DataFrame({"conformer_id": ["a", "b"], "relative_energy_kcal_mol": [pd.NA, 0.0]})
    result = flatten_conformers_to_df(original)
    assert result["relative_energy_kcal_mol"].dtype.kind == "f"
    assert pd.isna(result.iloc[0]["relative_energy_kcal_mol"])
    assert result.iloc[1]["relative_energy_kcal_mol"] == 0.0
    assert original["relative_energy_kcal_mol"].dtype == object
    for flatten in (flatten_spectroscopy_to_df, flatten_thermodynamics_to_df):
        result = flatten(pd.DataFrame({"Value": [pd.NA, np.inf, 0.0]}))
        assert result["Value"].isna().tolist() == [True, True, False]


def test_hdf_conformer_reference_excludes_missing_and_nonfinite_energies(tmp_path):
    archive = tmp_path / "landscape.h5"
    with h5py.File(archive, "w", libver="latest") as handle:
        conformers = handle.create_group("conformers")
        conformers.create_group("a_missing")
        for name, energy in (("b_nan", np.nan), ("c_inf", np.inf), ("d_neginf", -np.inf),
                             ("ground", -2.0), ("excited", -1.0)):
            conformers.create_group(name).attrs["energy"] = energy
    aggregator = DataAggregator(archive, artifact_dir=tmp_path)
    records = aggregator.harvest_conformers()
    assert [record["conformer_id"] for record in records[:2]] == ["ground", "excited"]
    assert records[0]["relative_energy_kcal_mol"] == 0.0
    assert records[1]["relative_energy_kcal_mol"] == pytest.approx(HARTREE_TO_KCAL_MOL)
    assert all(record["relative_energy_kcal_mol"] is None for record in records[2:])
    assert aggregator.harvest_conformers(top_n=1)[0]["conformer_id"] == "ground"
    json.dumps(records, allow_nan=False)


@pytest.mark.parametrize("storage", ["group", "dataset", "attributes"])
@pytest.mark.parametrize("components,total", [([3.0, 4.0], None), ([3.0, 4.0, 0.0], 5.0),
                                               ([0.0, 0.0, 0.0], 0.0), ([0.0, np.inf, 0.0], None)])
def test_real_hdf_dipole_requires_three_finite_components(tmp_path, storage, components, total):
    archive = tmp_path / "landscape.h5"
    with h5py.File(archive, "w", libver="latest") as handle:
        spec = handle.create_group("spectroscopy")
        spec.attrs["A"] = 0.0
        if storage == "dataset":
            spec.create_dataset("dipole_moments", data=components)
        else:
            target = spec.create_group("dipole_moments") if storage == "group" else spec
            for key, value in zip(("mu_a", "mu_b", "mu_c"), components):
                target.attrs[key] = value
    observed = DataAggregator(archive, artifact_dir=tmp_path).harvest_spectroscopy()
    assert observed["dipole_moments"]["total"] == total
    assert observed["rotational_constants"] == {"A": 0.0, "B": None, "C": None}
    assert all(value is None for value in observed["centrifugal_distortion"].values())
    json.dumps(observed, allow_nan=False)


def test_hdf_explicit_zero_dipole_total_does_not_need_components(tmp_path):
    archive = tmp_path / "landscape.h5"
    with h5py.File(archive, "w", libver="latest") as handle:
        handle.create_group("spectroscopy/dipole_moments").create_dataset("total", data=0.0)
    observed = DataAggregator(archive, artifact_dir=tmp_path).harvest_spectroscopy()["dipole_moments"]
    assert observed == {"mu_a": None, "mu_b": None, "mu_c": None, "total": 0.0}


@pytest.mark.parametrize("units,expected", [("kcal/mol", 0.02), ("Hartree", 0.02 * HARTREE_TO_KCAL_MOL),
                                            (None, None), ("unknown", None)])
@pytest.mark.parametrize("metadata_location", ["dataset", "group"])
def test_hdf_legacy_energy_needs_declared_units(tmp_path, units, expected, metadata_location):
    archive = tmp_path / "landscape.h5"
    with h5py.File(archive, "w", libver="latest") as handle:
        group = handle.create_group("thermodynamics")
        dataset = group.create_dataset("zero_point_energy", data=0.02)
        if units is not None:
            target = dataset if metadata_location == "dataset" else group
            target.attrs["units"] = units
    observed = DataAggregator(archive, artifact_dir=tmp_path).harvest_thermodynamics()
    assert observed["zpe_kcal_mol"] == expected
    assert observed["enthalpy_kcal_mol"] is None
    assert observed["gibbs_free_energy_kcal_mol"] is None


def test_hdf_named_energy_units_and_conflicting_metadata(tmp_path):
    archive = tmp_path / "landscape.h5"
    with h5py.File(archive, "w", libver="latest") as handle:
        group = handle.create_group("thermodynamics")
        group.attrs["zpe_kcal_mol"] = 0.02
        group.attrs["enthalpy_hartree"] = 0.02
        dataset = group.create_dataset("gibbs_free_energy_kcal_mol", data=0.02)
        dataset.attrs["units"] = "Hartree"
        group.create_dataset("vpt2_frequencies", data=[0.0, np.nan, np.inf, 123.0])
    observed = DataAggregator(archive, artifact_dir=tmp_path).harvest_thermodynamics()
    assert observed["zpe_kcal_mol"] == 0.02
    assert observed["enthalpy_kcal_mol"] == pytest.approx(0.02 * HARTREE_TO_KCAL_MOL)
    assert observed["gibbs_free_energy_kcal_mol"] is None
    assert observed["vpt2_frequencies"] == [0.0, None, None, 123.0]
    json.dumps(observed, allow_nan=False)


def test_real_parquet_fallback_preserves_missing_fields_and_zero(tmp_path):
    pd.DataFrame({"conformer_id": ["missing", "zero", "positive"],
                  "relative_energy_kcal_mol": [np.nan, 0.0, 1.0]}).to_parquet(tmp_path / "conformers.parquet")
    pd.DataFrame({"A": [0.0], "B": [np.inf], "mu_a": [3.0], "mu_b": [4.0]}).to_parquet(tmp_path / "spectroscopy.parquet")
    pd.DataFrame({"zpe": [0.02], "enthalpy_kcal_mol": [0.0]}).to_parquet(tmp_path / "thermodynamics.parquet")
    aggregator = DataAggregator(tmp_path / "absent.h5", parquet_dir=tmp_path, artifact_dir=tmp_path)
    records = aggregator.harvest_conformers()
    assert [row["conformer_id"] for row in records] == ["zero", "positive", "missing"]
    assert records[-1]["relative_energy_kcal_mol"] is None
    assert aggregator.harvest_conformers(top_n=1)[0]["relative_energy_kcal_mol"] == 0.0
    spectrum = aggregator.harvest_spectroscopy()
    assert spectrum["rotational_constants"] == {"A": 0.0, "B": None, "C": None}
    assert spectrum["dipole_moments"]["total"] is None
    thermal = aggregator.harvest_thermodynamics()
    assert thermal["zpe_kcal_mol"] is None
    assert thermal["enthalpy_kcal_mol"] == 0.0
    assert thermal["gibbs_free_energy_kcal_mol"] is None
    pd.DataFrame({"total": [0.0]}).to_parquet(tmp_path / "spectroscopy.parquet")
    assert aggregator.harvest_spectroscopy()["dipole_moments"]["total"] == 0.0
    json.dumps([records, spectrum, thermal], allow_nan=False)


def test_aggregate_unavailable_observations_remain_missing_in_tables(tmp_path):
    archive = tmp_path / "landscape.h5"
    with h5py.File(archive, "w", libver="latest"):
        pass
    # A real, unreadable-as-telemetry record exercises aggregate_all's fallback.
    (tmp_path / "cochem_audit_log.json").write_text("", encoding="utf-8")
    aggregator = DataAggregator(archive, parquet_dir=tmp_path, artifact_dir=tmp_path)
    observed = aggregator.aggregate_all()
    assert observed["telemetry"]["wall_clock_time_seconds"] is None
    assert observed["telemetry"]["peak_gpu_vram_mb"] is None
    for table in ("spectroscopy", "thermodynamics", "telemetry"):
        assert aggregator.flatten_to_dataframe(observed[table], table)["Value"].isna().all()


def test_real_telemetry_zero_does_not_evaluate_missing_gb_fallback(tmp_path):
    log = {"wall_clock_seconds": 0.0, "gpu_vram_peak_mb": 0.0, "peak_vram_gb": None}
    (tmp_path / "cochem_audit_log.json").write_text(json.dumps(log), encoding="utf-8")
    observed = DataAggregator(artifact_dir=tmp_path).harvest_telemetry()
    assert observed["wall_clock_time_seconds"] == 0.0
    assert observed["peak_gpu_vram_mb"] == 0.0
