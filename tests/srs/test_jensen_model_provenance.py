"""Analytic model contracts; these tests make no measured-trajectory claim."""

import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from cochem_base.mm.conference.ref.jensen import (
    average_inverse_inertia_ensemble,
    generate_vdw_stretch_ensemble,
    get_atomic_mass,
)


def test_gaussian_model_preserves_species_and_is_explicitly_identified():
    species1, species2 = ["Ne"], ["O", "H", "H"]
    masses1 = np.asarray([get_atomic_mass(s) for s in species1])
    masses2 = np.asarray([get_atomic_mass(s) for s in species2])
    coords1 = np.asarray([[0.0, 0.0, 0.0]])
    coords2 = np.asarray([[0.0, 0.0, 0.0], [0.9572, 0.0, 0.0], [-0.24, 0.927, 0.0]])
    state_before = np.random.get_state()
    ensemble, masses, labels = generate_vdw_stretch_ensemble(
        coords1, coords2, masses1, masses2, n_samples=128,
        monomer1_symbols=species1, monomer2_symbols=species2,
    )
    state_after = np.random.get_state()
    assert np.array_equal(state_before[1], state_after[1])
    assert state_before[2:] == state_after[2:]
    assert labels == ["Ne", "O", "H", "H"]
    assert np.array_equal(masses, np.concatenate([masses1, masses2]))
    result = average_inverse_inertia_ensemble(
        ensemble, masses, labels, provenance="gaussian_stretch_model",
    )
    assert result.symbols == labels
    assert result.provenance == "gaussian_stretch_model"
    assert result.is_valid_jensen
    assert result.B_correct >= result.B_flawed
    with pytest.raises(ValueError, match="Actual species"):
        average_inverse_inertia_ensemble(ensemble, masses)
    with pytest.raises(ValueError, match="actual species"):
        generate_vdw_stretch_ensemble(
            coords1, coords2, masses1, masses2,
            monomer1_symbols=species1, monomer2_symbols=["O"],
        )


def test_missing_isotope_does_not_substitute_atomic_weight():
    with pytest.raises(ValueError, match="[Ii]sotop"):
        get_atomic_mass("C", 999)


def test_cli_report_does_not_claim_model_is_a_measured_trajectory():
    root = Path(__file__).resolve().parents[2]
    environment = dict(os.environ, PYTHONPATH=str(root / "src"))
    result = subprocess.run(
        [sys.executable, "-m", "cochem_base.mm.conference.ref.jensen", "--json", "--vdw-3d-test"],
        cwd=root, env=environment, text=True, encoding="utf-8", capture_output=True,
        check=True, timeout=60,
    )
    payload = json.loads(result.stdout)
    assert payload["metadata"]["evidence_kind"] == "analytical_model"
    assert payload["metadata"]["measured_trajectory"] is False
    assert payload["vdw_3d_test_result"]["provenance"] == "gaussian_stretch_model"
    assert payload["vdw_3d_test_result"]["symbols"] == ["Ar", "C", "O", "O"]
