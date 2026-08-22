"""Comprehensive physical Zero-Mock test suite for cochem_base.io.thermo_constants.

Validates:
- CODATA & IUPAC reference constants (R, k_B, N_A, h, F, c, a_0, T_std, P_std).
- Pydantic v2 data models (ThermodynamicState, ReactionThermodynamics) with strict validation & immutability.
- Bidirectional physical unit converters (temperature, pressure, energy).
- Ideal gas equation of state solvers (PV = nRT).
- Gibbs free energy, equilibrium constant, and Arrhenius rate kinetics calculations.
- Backward compatibility with legacy ThermoConstantsValidator and global standard constants.
- Unix LF line endings, standard UTF-8 encoding, and zero personal path leaks.
"""

from __future__ import annotations

import math
from pathlib import Path
import pytest
from pydantic import ValidationError

import cochem_base.io as io_pkg
from cochem_base.io.thermo_constants import (
    ATMOSPHERE_TO_PASCAL,
    AVOGADRO_CONSTANT_N_A,
    BAR_TO_PASCAL,
    BOHR_RADIUS_ANGSTROM,
    BOLTZMANN_CONSTANT_K_B,
    CALORIE_TO_JOULE,
    ELEMENTARY_CHARGE_E,
    EV_TO_HARTREE,
    EV_TO_JOULE,
    EV_TO_KCAL_MOL,
    EV_TO_KJ_MOL,
    FARADAY_CONSTANT_F,
    GAS_CONSTANT_R,
    HARTREE_TO_EV,
    HARTREE_TO_JOULE,
    HARTREE_TO_KCAL_MOL,
    HARTREE_TO_KJ_MOL,
    JOULE_TO_CALORIE,
    JOULE_TO_EV,
    JOULE_TO_HARTREE,
    KCAL_MOL_TO_EV,
    KCAL_MOL_TO_HARTREE,
    KCAL_MOL_TO_KJ_MOL,
    KJ_MOL_TO_EV,
    KJ_MOL_TO_HARTREE,
    KJ_MOL_TO_KCAL_MOL,
    MOLAR_GAS_CONSTANT_R,
    NIST_PRESSURE,
    NIST_TEMPERATURE,
    PASCAL_TO_ATMOSPHERE,
    PASCAL_TO_BAR,
    PASCAL_TO_PSI,
    PASCAL_TO_TORR,
    PLANCK_CONSTANT_H,
    PSI_TO_PASCAL,
    REDUCED_PLANCK_CONSTANT_HBAR,
    ReactionThermodynamics,
    SPEED_OF_LIGHT_C,
    STANDARD_PRESSURE,
    STANDARD_STATE_PRESSURE_IUPAC,
    STANDARD_TEMPERATURE,
    STP_PRESSURE,
    STP_PRESSURE_ATM,
    STP_TEMPERATURE,
    ThermoConstantsValidator,
    ThermodynamicState,
    TORR_TO_PASCAL,
    ZERO_CELSIUS_IN_KELVIN,
    atm_to_pascal,
    bar_to_pascal,
    calculate_arrhenius_rate_constant,
    calculate_delta_g_from_k,
    calculate_equilibrium_constant,
    calculate_gibbs_free_energy,
    calculate_ideal_gas_moles,
    calculate_ideal_gas_pressure,
    calculate_ideal_gas_temperature,
    calculate_ideal_gas_volume,
    calculate_molar_volume,
    calculate_thermal_energy_rt,
    calories_to_joules,
    celsius_to_fahrenheit,
    celsius_to_kelvin,
    ev_to_hartree,
    ev_to_joules,
    ev_to_kcal_mol,
    ev_to_kj_mol,
    fahrenheit_to_celsius,
    fahrenheit_to_kelvin,
    hartree_to_ev,
    hartree_to_joules,
    hartree_to_kcal_mol,
    hartree_to_kj_mol,
    joules_to_calories,
    joules_to_ev,
    joules_to_hartree,
    kcal_mol_to_ev,
    kcal_mol_to_hartree,
    kcal_mol_to_kj_mol,
    kelvin_to_celsius,
    kelvin_to_fahrenheit,
    kj_mol_to_ev,
    kj_mol_to_hartree,
    kj_mol_to_kcal_mol,
    pascal_to_atm,
    pascal_to_bar,
    pascal_to_psi,
    pascal_to_torr,
    psi_to_pascal,
    torr_to_pascal,
)
from cochem_base.path_sanitization import leak_patterns


@pytest.fixture
def thermo_constants_file_path() -> Path:
    """Return absolute path to cochem_base/io/thermo_constants.py."""
    path = Path(__file__).resolve().parent.parent / "cochem_base" / "io" / "thermo_constants.py"
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


def test_file_encoding_and_lf_line_endings(thermo_constants_file_path: Path) -> None:
    """Verify strictly Unix LF line endings (\\n), standard UTF-8 encoding, and no BOM."""
    raw = thermo_constants_file_path.read_bytes()
    assert b"\r\n" not in raw, "Found Windows CRLF (\\r\\n) line endings in thermo_constants.py"
    assert b"\n" in raw, "Missing newline characters in thermo_constants.py"
    assert not raw.startswith(b"\xef\xbb\xbf"), "Found UTF-8 BOM marker in thermo_constants.py"


def test_zero_personal_path_leaks(thermo_constants_file_path: Path) -> None:
    """Verify zero personal machine or local user path leakage in thermo_constants.py."""
    lines = thermo_constants_file_path.read_text(encoding="utf-8").splitlines()
    patterns = leak_patterns()
    leaks = []
    for lineno, line in enumerate(lines, 1):
        for pattern, placeholder in patterns:
            if pattern.search(line):
                leaks.append((lineno, placeholder, line.strip()))

    assert len(leaks) == 0, f"Detected personal path leaks in thermo_constants.py: {leaks}"


def test_io_package_lazy_resolution() -> None:
    """Verify that cochem_base.io lazily exports thermodynamic constants and models."""
    assert getattr(io_pkg, "STANDARD_TEMPERATURE") == 298.15
    assert getattr(io_pkg, "STANDARD_PRESSURE") == 101325.0
    assert getattr(io_pkg, "MOLAR_GAS_CONSTANT_R") == MOLAR_GAS_CONSTANT_R
    assert getattr(io_pkg, "ThermoConstantsValidator") is ThermoConstantsValidator
    assert getattr(io_pkg, "ThermodynamicState") is ThermodynamicState
    assert getattr(io_pkg, "ReactionThermodynamics") is ReactionThermodynamics


def test_fundamental_physical_constants_values() -> None:
    """Verify authoritative CODATA 2018/2022 recommended fundamental physical constants."""
    assert math.isclose(MOLAR_GAS_CONSTANT_R, 8.31446261815324, rel_tol=1e-12)
    assert GAS_CONSTANT_R == MOLAR_GAS_CONSTANT_R
    assert math.isclose(BOLTZMANN_CONSTANT_K_B, 1.380649e-23, rel_tol=1e-12)
    assert math.isclose(AVOGADRO_CONSTANT_N_A, 6.02214076e23, rel_tol=1e-12)
    assert math.isclose(PLANCK_CONSTANT_H, 6.62607015e-34, rel_tol=1e-12)
    assert math.isclose(ELEMENTARY_CHARGE_E, 1.602176634e-19, rel_tol=1e-12)
    assert math.isclose(SPEED_OF_LIGHT_C, 299792458.0, rel_tol=1e-12)
    assert math.isclose(FARADAY_CONSTANT_F, AVOGADRO_CONSTANT_N_A * ELEMENTARY_CHARGE_E, rel_tol=1e-9)
    assert math.isclose(REDUCED_PLANCK_CONSTANT_HBAR, PLANCK_CONSTANT_H / (2.0 * math.pi), rel_tol=1e-12)
    assert math.isclose(BOHR_RADIUS_ANGSTROM, 0.529177210903, rel_tol=1e-9)


def test_standard_states_and_temperatures() -> None:
    """Verify IUPAC, NIST, and STP temperature/pressure standard definitions."""
    assert STANDARD_TEMPERATURE == 298.15
    assert STANDARD_PRESSURE == 101325.0
    assert STANDARD_STATE_PRESSURE_IUPAC == 100000.0
    assert STP_TEMPERATURE == 273.15
    assert STP_PRESSURE == 100000.0
    assert STP_PRESSURE_ATM == 101325.0
    assert NIST_TEMPERATURE == 293.15
    assert NIST_PRESSURE == 101325.0
    assert ZERO_CELSIUS_IN_KELVIN == 273.15


def test_temperature_conversions() -> None:
    """Verify temperature conversions between Kelvin, Celsius, and Fahrenheit."""
    # Absolute zero
    assert kelvin_to_celsius(0.0) == -273.15
    assert math.isclose(kelvin_to_fahrenheit(0.0), -459.67, abs_tol=1e-4)

    # Freezing point of water
    assert celsius_to_kelvin(0.0) == 273.15
    assert kelvin_to_celsius(273.15) == 0.0
    assert celsius_to_fahrenheit(0.0) == 32.0
    assert fahrenheit_to_celsius(32.0) == 0.0

    # Boiling point of water
    assert celsius_to_kelvin(100.0) == 373.15
    assert kelvin_to_celsius(373.15) == 100.0
    assert celsius_to_fahrenheit(100.0) == 212.0
    assert fahrenheit_to_celsius(212.0) == 100.0

    # Standard ambient temperature (25 °C = 298.15 K = 77 °F)
    assert celsius_to_kelvin(25.0) == 298.15
    assert kelvin_to_celsius(298.15) == 25.0
    assert celsius_to_fahrenheit(25.0) == 77.0
    assert fahrenheit_to_kelvin(77.0) == 298.15

    # Boundary checks: below absolute zero raises ValidationError
    with pytest.raises(ValidationError):
        kelvin_to_celsius(-1.0)
    with pytest.raises(ValidationError):
        celsius_to_kelvin(-300.0)
    with pytest.raises(ValidationError):
        fahrenheit_to_kelvin(-500.0)


def test_pressure_conversions() -> None:
    """Verify pressure conversions between Pa, atm, bar, Torr, and psi."""
    # 1 atm
    pa_1atm = 101325.0
    assert math.isclose(pascal_to_atm(pa_1atm), 1.0, rel_tol=1e-9)
    assert math.isclose(atm_to_pascal(1.0), pa_1atm, rel_tol=1e-9)
    assert math.isclose(pascal_to_torr(pa_1atm), 760.0, rel_tol=1e-9)
    assert math.isclose(torr_to_pascal(760.0), pa_1atm, rel_tol=1e-9)
    assert math.isclose(pascal_to_bar(pa_1atm), 1.01325, rel_tol=1e-9)
    assert math.isclose(bar_to_pascal(1.0), 100000.0, rel_tol=1e-9)
    assert math.isclose(pascal_to_psi(pa_1atm), 14.695948775, rel_tol=1e-5)
    assert math.isclose(psi_to_pascal(14.695948775), pa_1atm, rel_tol=1e-5)

    # Negative pressure boundary
    with pytest.raises(ValidationError):
        pascal_to_atm(-10.0)
    with pytest.raises(ValidationError):
        atm_to_pascal(-1.0)


def test_energy_conversions() -> None:
    """Verify energy conversions between Hartree, eV, kJ/mol, kcal/mol, Joules, and calories."""
    # 1 Hartree
    assert math.isclose(hartree_to_ev(1.0), 27.211386245988, rel_tol=1e-9)
    assert math.isclose(ev_to_hartree(27.211386245988), 1.0, rel_tol=1e-9)
    assert math.isclose(hartree_to_kcal_mol(1.0), 627.5094740631, rel_tol=1e-9)
    assert math.isclose(kcal_mol_to_hartree(627.5094740631), 1.0, rel_tol=1e-9)
    assert math.isclose(hartree_to_kj_mol(1.0), 2625.4996394799, rel_tol=1e-9)
    assert math.isclose(kj_mol_to_hartree(2625.4996394799), 1.0, rel_tol=1e-9)
    assert math.isclose(hartree_to_joules(1.0), 4.3597447222071e-18, rel_tol=1e-9)
    assert math.isclose(joules_to_hartree(4.3597447222071e-18), 1.0, rel_tol=1e-9)

    # Joules and Calories
    assert math.isclose(calories_to_joules(1.0), 4.184, rel_tol=1e-9)
    assert math.isclose(joules_to_calories(4.184), 1.0, rel_tol=1e-9)

    # eV and Joules
    assert math.isclose(ev_to_joules(1.0), 1.602176634e-19, rel_tol=1e-9)
    assert math.isclose(joules_to_ev(1.602176634e-19), 1.0, rel_tol=1e-9)

    # eV to molar energies
    assert math.isclose(ev_to_kj_mol(1.0), 96.48533212331, rel_tol=1e-9)
    assert math.isclose(kj_mol_to_ev(96.48533212331), 1.0, rel_tol=1e-9)
    assert math.isclose(ev_to_kcal_mol(1.0), 23.06054801, rel_tol=1e-5)
    assert math.isclose(kcal_mol_to_ev(23.06054801), 1.0, rel_tol=1e-5)

    # kJ/mol and kcal/mol
    assert math.isclose(kcal_mol_to_kj_mol(1.0), 4.184, rel_tol=1e-9)
    assert math.isclose(kj_mol_to_kcal_mol(4.184), 1.0, rel_tol=1e-9)


def test_ideal_gas_law_solvers() -> None:
    """Verify ideal gas equation solvers (PV = nRT) and molar volume."""
    n = 2.0  # moles
    T = 298.15  # K
    P = 101325.0  # Pa

    # Calculate V = nRT / P
    V = calculate_ideal_gas_volume(moles=n, temperature_k=T, pressure_pa=P)
    expected_v = (n * MOLAR_GAS_CONSTANT_R * T) / P
    assert math.isclose(V, expected_v, rel_tol=1e-12)

    # Round-trip P = nRT / V
    P_calc = calculate_ideal_gas_pressure(moles=n, temperature_k=T, volume_m3=V)
    assert math.isclose(P_calc, P, rel_tol=1e-12)

    # Round-trip n = PV / RT
    n_calc = calculate_ideal_gas_moles(pressure_pa=P, volume_m3=V, temperature_k=T)
    assert math.isclose(n_calc, n, rel_tol=1e-12)

    # Round-trip T = PV / nR
    T_calc = calculate_ideal_gas_temperature(pressure_pa=P, volume_m3=V, moles=n)
    assert math.isclose(T_calc, T, rel_tol=1e-12)

    # Molar volume at standard temperature and pressure
    Vm_std = calculate_molar_volume(temperature_k=298.15, pressure_pa=101325.0)
    assert math.isclose(Vm_std * 1000.0, 24.4654, rel_tol=1e-4)  # ~24.465 L/mol

    Vm_stp_iupac = calculate_molar_volume(temperature_k=273.15, pressure_pa=100000.0)
    assert math.isclose(Vm_stp_iupac * 1000.0, 22.7109, rel_tol=1e-4)  # ~22.711 L/mol

    Vm_stp_atm = calculate_molar_volume(temperature_k=273.15, pressure_pa=101325.0)
    assert math.isclose(Vm_stp_atm * 1000.0, 22.414, rel_tol=1e-4)  # ~22.414 L/mol


def test_thermodynamic_calculations() -> None:
    """Verify Gibbs free energy, equilibrium constant, and Arrhenius rate kinetics."""
    # Gibbs Free Energy: dG = dH - T * dS
    dH = -50000.0  # -50 kJ/mol (exothermic)
    dS = -100.0   # -100 J/(mol*K)
    T = 298.15    # K
    dG = calculate_gibbs_free_energy(enthalpy_j_mol=dH, entropy_j_mol_k=dS, temperature_k=T)
    assert math.isclose(dG, -50000.0 - 298.15 * (-100.0), rel_tol=1e-9)
    assert dG < 0.0  # Spontaneous

    # Equilibrium constant: K = exp(-dG / RT)
    K = calculate_equilibrium_constant(delta_g_j_mol=dG, temperature_k=T)
    expected_k = math.exp(-dG / (MOLAR_GAS_CONSTANT_R * T))
    assert math.isclose(K, expected_k, rel_tol=1e-9)

    # Delta G from K: dG = -RT ln(K)
    dG_recovered = calculate_delta_g_from_k(equilibrium_constant_k=K, temperature_k=T)
    assert math.isclose(dG_recovered, dG, rel_tol=1e-9)

    # Arrhenius equation: k = A * exp(-E_a / RT)
    A = 1e13  # frequency factor (s^-1)
    E_a = 50000.0  # 50 kJ/mol activation energy
    k_rate = calculate_arrhenius_rate_constant(pre_exponential_a=A, activation_energy_j_mol=E_a, temperature_k=T)
    expected_k_rate = A * math.exp(-E_a / (MOLAR_GAS_CONSTANT_R * T))
    assert math.isclose(k_rate, expected_k_rate, rel_tol=1e-9)

    # Thermal energy RT
    rt_kj = calculate_thermal_energy_rt(298.15, unit="kJ/mol")
    assert math.isclose(rt_kj, (8.31446261815324 * 298.15) / 1000.0, rel_tol=1e-9)

    rt_kcal = calculate_thermal_energy_rt(298.15, unit="kcal/mol")
    assert math.isclose(rt_kcal, rt_kj / 4.184, rel_tol=1e-9)

    rt_ev = calculate_thermal_energy_rt(298.15, unit="eV")
    assert math.isclose(rt_ev, 0.02569, rel_tol=1e-3)  # ~25.7 meV at room temp


def test_thermodynamic_state_model() -> None:
    """Verify ThermodynamicState Pydantic model properties, immutability, and validation."""
    state = ThermodynamicState(temperature=298.15, pressure=101325.0)

    assert state.temperature == 298.15
    assert state.pressure == 101325.0
    assert state.temperature_celsius == 25.0
    assert math.isclose(state.temperature_fahrenheit, 77.0, rel_tol=1e-4)
    assert math.isclose(state.pressure_atm, 1.0, rel_tol=1e-9)
    assert math.isclose(state.pressure_bar, 1.01325, rel_tol=1e-9)
    assert math.isclose(state.pressure_torr, 760.0, rel_tol=1e-9)
    assert state.is_standard_state is True
    assert state.is_stp is False
    assert math.isclose(state.thermal_energy_rt_kj_mol, 2.4789, rel_tol=1e-4)
    assert math.isclose(state.thermal_energy_rt_kcal_mol, 0.5925, rel_tol=1e-4)
    assert math.isclose(state.molar_volume_ideal_gas_liters_mol, 24.465, rel_tol=1e-3)

    # Immutability check
    with pytest.raises(ValidationError):
        state.temperature = 350.0  # type: ignore

    # Negative temperature validation check
    with pytest.raises(ValidationError):
        ThermodynamicState(temperature=-10.0, pressure=101325.0)

    # Negative pressure validation check
    with pytest.raises(ValidationError):
        ThermodynamicState(temperature=298.15, pressure=-50.0)


def test_reaction_thermodynamics_model() -> None:
    """Verify ReactionThermodynamics Pydantic model calculations."""
    rxn = ReactionThermodynamics(
        delta_h_j_mol=-100000.0,  # -100 kJ/mol
        delta_s_j_mol_k=-50.0,     # -50 J/(mol*K)
        temperature=298.15,
    )
    assert rxn.delta_h_j_mol == -100000.0
    assert rxn.delta_s_j_mol_k == -50.0
    assert rxn.temperature == 298.15

    expected_dg = -100000.0 - 298.15 * (-50.0)
    assert math.isclose(rxn.delta_g_j_mol, expected_dg, rel_tol=1e-9)
    assert math.isclose(rxn.delta_g_kj_mol, expected_dg / 1000.0, rel_tol=1e-9)
    assert math.isclose(rxn.delta_g_kcal_mol, (expected_dg / 1000.0) / 4.184, rel_tol=1e-9)
    assert rxn.is_spontaneous is True
    assert rxn.is_endergonic is False
    assert rxn.is_exothermic is True
    assert rxn.is_endothermic is False
    assert rxn.equilibrium_constant > 1.0


def test_thermo_constants_validator_backward_compatibility() -> None:
    """Verify 100% backward compatibility for legacy ThermoConstantsValidator methods."""
    # Temperature validation
    assert ThermoConstantsValidator.validate_temperature(298.15) is True
    assert ThermoConstantsValidator.validate_temperature(0.0) is True
    with pytest.raises(ValueError, match="Temperature cannot be negative"):
        ThermoConstantsValidator.validate_temperature(-0.1)

    # Pressure validation
    assert ThermoConstantsValidator.validate_pressure(101325.0) is True
    assert ThermoConstantsValidator.validate_pressure(0.0) is True
    with pytest.raises(ValueError, match="Pressure cannot be negative"):
        ThermoConstantsValidator.validate_pressure(-1.0)

    # Volume and moles validation
    assert ThermoConstantsValidator.validate_volume(1.0) is True
    with pytest.raises(ValueError, match="Volume cannot be negative"):
        ThermoConstantsValidator.validate_volume(-0.5)

    assert ThermoConstantsValidator.validate_moles(1.0) is True
    with pytest.raises(ValueError, match="Amount of substance cannot be negative"):
        ThermoConstantsValidator.validate_moles(-2.0)

    # Standard state check
    assert ThermoConstantsValidator.is_standard_state(298.15, 101325.0) is True
    assert ThermoConstantsValidator.is_standard_state(298.155, 101325.5, temp_tol=0.01, press_tol=1.0) is True
    assert ThermoConstantsValidator.is_standard_state(300.0, 101325.0) is False
    assert ThermoConstantsValidator.is_standard_state(298.15, 100000.0) is False

    # Negative inputs raise ValueError in is_standard_state
    with pytest.raises(ValueError):
        ThermoConstantsValidator.is_standard_state(-10.0, 101325.0)
    with pytest.raises(ValueError):
        ThermoConstantsValidator.is_standard_state(298.15, -100.0)

    # STP state check
    assert ThermoConstantsValidator.is_stp_state(273.15, 100000.0, convention="IUPAC") is True
    assert ThermoConstantsValidator.is_stp_state(273.15, 101325.0, convention="ATM") is True
    assert ThermoConstantsValidator.is_stp_state(298.15, 101325.0) is False

    # State validation factory & default state
    state = ThermoConstantsValidator.validate_state(300.0, 200000.0)
    assert isinstance(state, ThermodynamicState)
    assert state.temperature == 300.0
    assert state.pressure == 200000.0

    default_state = ThermoConstantsValidator.get_default_state()
    assert default_state.temperature == 298.15
    assert default_state.pressure == 101325.0