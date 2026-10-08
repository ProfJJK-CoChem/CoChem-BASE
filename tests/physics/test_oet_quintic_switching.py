"""Retained native ORCA derivative transport; no invented OET potential or fresh-server claim."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from cochem_base.calc.recipe_r2_execution import read_dimer_gradient
from scripts.oet_client import OETClient, MissingRequestedDerivativeError, PhysicalOETFallbackCalculator, OETDaemonUnavailableError

FIXTURE = Path(__file__).parents[1] / "data" / "orca_6_1_1_water_hf_sto3g"


def native_response():
    provenance = json.loads((FIXTURE / "provenance.json").read_text())
    assert hashlib.sha256((FIXTURE / "water.engrad").read_bytes()).hexdigest() == provenance["files"]["water.engrad"]["sha256"]
    rows = (FIXTURE / "water.xyz").read_text().splitlines()[2:]
    symbols = [row.split()[0] for row in rows]
    coordinates = [[float(v) for v in row.split()[1:4]] for row in rows]
    energy, gradient = read_dimer_gradient(FIXTURE / "water.engrad", symbols, coordinates)
    return {"status": "OK", "energy_Eh": energy, "gradient_Eh_bohr": gradient.reshape(-1).tolist()}


def test_actual_native_derivatives_preserve_units_and_unknown_uncertainty():
    response = native_response()
    result = OETClient()._normalize_server_response(response, dograd=True, n_atoms=3)
    assert result["energy_Eh"] == response["energy_Eh"]
    assert np.array_equal(result["gradient_Eh_bohr"], response["gradient_Eh_bohr"])
    assert result["uncertainty_energy_Eh"] is result["uncertainty_force_max"] is None


def test_missing_requested_derivative_cannot_be_padded_as_measured_zero():
    response = native_response()
    response.pop("gradient_Eh_bohr")
    with pytest.raises(MissingRequestedDerivativeError, match="requested gradient"):
        OETClient()._normalize_server_response(response, dograd=True, n_atoms=3)
    energy_only = OETClient()._normalize_server_response(response, dograd=False, n_atoms=3)
    assert energy_only["energy_Eh"] == response["energy_Eh"]
    assert energy_only["gradient_Eh_bohr"] == [0.0] * 9  # Explicit ORCA energy-only file padding.


def test_retired_unparameterized_oet_surrogate_cannot_calculate():
    rows = (FIXTURE / "water.xyz").read_text().splitlines()[2:]
    symbols = [row.split()[0] for row in rows]
    coordinates = [tuple(float(v) for v in row.split()[1:4]) for row in rows]
    with pytest.raises(OETDaemonUnavailableError, match="retired"):
        PhysicalOETFallbackCalculator().calculate(symbols, coordinates)
