"""Thermodynamic and physical constants, unit converters, and equation of state solvers.

Implements CODATA 2018/2022 recommended fundamental physical constants,
IUPAC / NIST / STP standard state specifications, bidirectional unit conversions
(temperature, pressure, energy), and ideal gas / Gibbs free energy solvers.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional, Union

from pydantic import BaseModel, Field, ValidationError

# =============================================================================
# 1. Fundamental Physical Constants (CODATA 2018 / 2022)
# =============================================================================

MOLAR_GAS_CONSTANT_R: float = 8.31446261815324  # J/(mol*K)
GAS_CONSTANT_R: float = MOLAR_GAS_CONSTANT_R
BOLTZMANN_CONSTANT_K_B: float = 1.380649e-23  # J/K
AVOGADRO_CONSTANT_N_A: float = 6.02214076e23  # mol^-1
PLANCK_CONSTANT_H: float = 6.62607015e-34  # J*s
REDUCED_PLANCK_CONSTANT_HBAR: float = PLANCK_CONSTANT_H / (2.0 * math.pi)  # J*s
ELEMENTARY_CHARGE_E: float = 1.602176634e-19  # C
SPEED_OF_LIGHT_C: float = 299792458.0  # m/s
FARADAY_CONSTANT_F: float = AVOGADRO_CONSTANT_N_A * ELEMENTARY_CHARGE_E  # C/mol
BOHR_RADIUS_ANGSTROM: float = 0.529177210903  # Å

# =============================================================================
# 2. Standard State Conditions
# =============================================================================

STANDARD_TEMPERATURE: float = 298.15  # K (25 °C)
STANDARD_PRESSURE: float = 101325.0  # Pa (1 atm)
STANDARD_STATE_PRESSURE_IUPAC: float = 100000.0  # Pa (1 bar)
STP_TEMPERATURE: float = 273.15  # K (0 °C)
STP_PRESSURE: float = 100000.0  # Pa (1 bar - IUPAC standard since 1982)
STP_PRESSURE_ATM: float = 101325.0  # Pa (1 atm - traditional)
NIST_TEMPERATURE: float = 293.15  # K (20 °C)
NIST_PRESSURE: float = 101325.0  # Pa (1 atm)
ZERO_CELSIUS_IN_KELVIN: float = 273.15

# =============================================================================
# 3. Conversion Multipliers
# =============================================================================

ATMOSPHERE_TO_PASCAL: float = 101325.0
PASCAL_TO_ATMOSPHERE: float = 1.0 / 101325.0
BAR_TO_PASCAL: float = 100000.0
PASCAL_TO_BAR: float = 1.0 / 100000.0
TORR_TO_PASCAL: float = 101325.0 / 760.0
PASCAL_TO_TORR: float = 760.0 / 101325.0
PSI_TO_PASCAL: float = 6894.757293168
PASCAL_TO_PSI: float = 1.0 / 6894.757293168

CALORIE_TO_JOULE: float = 4.184
JOULE_TO_CALORIE: float = 1.0 / 4.184
EV_TO_JOULE: float = 1.602176634e-19
JOULE_TO_EV: float = 1.0 / 1.602176634e-19

HARTREE_TO_EV: float = 27.211386245988
EV_TO_HARTREE: float = 1.0 / 27.211386245988
HARTREE_TO_KCAL_MOL: float = 627.5094740631
KCAL_MOL_TO_HARTREE: float = 1.0 / 627.5094740631
HARTREE_TO_KJ_MOL: float = 2625.4996394799
KJ_MOL_TO_HARTREE: float = 1.0 / 2625.4996394799
HARTREE_TO_JOULE: float = 4.3597447222071e-18
JOULE_TO_HARTREE: float = 1.0 / 4.3597447222071e-18

EV_TO_KJ_MOL: float = 96.48533212331
KJ_MOL_TO_EV: float = 1.0 / 96.48533212331
EV_TO_KCAL_MOL: float = 23.06054801
KCAL_MOL_TO_EV: float = 1.0 / 23.06054801

KCAL_MOL_TO_KJ_MOL: float = 4.184
KJ_MOL_TO_KCAL_MOL: float = 1.0 / 4.184


# Validation Helper Models
class _NonNegativeKelvin(BaseModel):
    val: float = Field(..., ge=0.0)


class _NonNegativePressure(BaseModel):
    val: float = Field(..., ge=0.0)


# =============================================================================
# 4. Temperature Conversion Functions
# =============================================================================


def kelvin_to_celsius(k: float) -> float:
    _NonNegativeKelvin(val=k)
    return k - ZERO_CELSIUS_IN_KELVIN


def celsius_to_kelvin(c: float) -> float:
    k = c + ZERO_CELSIUS_IN_KELVIN
    _NonNegativeKelvin(val=k)
    return k


def kelvin_to_fahrenheit(k: float) -> float:
    _NonNegativeKelvin(val=k)
    c = k - ZERO_CELSIUS_IN_KELVIN
    return c * (9.0 / 5.0) + 32.0


def fahrenheit_to_kelvin(f: float) -> float:
    c = (f - 32.0) * (5.0 / 9.0)
    k = c + ZERO_CELSIUS_IN_KELVIN
    _NonNegativeKelvin(val=k)
    return k


def celsius_to_fahrenheit(c: float) -> float:
    celsius_to_kelvin(c)  # validates lower bound
    return c * (9.0 / 5.0) + 32.0


def fahrenheit_to_celsius(f: float) -> float:
    fahrenheit_to_kelvin(f)  # validates lower bound
    return (f - 32.0) * (5.0 / 9.0)


# =============================================================================
# 5. Pressure Conversion Functions
# =============================================================================


def pascal_to_atm(pa: float) -> float:
    _NonNegativePressure(val=pa)
    return pa * PASCAL_TO_ATMOSPHERE


def atm_to_pascal(atm: float) -> float:
    _NonNegativePressure(val=atm)
    return atm * ATMOSPHERE_TO_PASCAL


def pascal_to_bar(pa: float) -> float:
    _NonNegativePressure(val=pa)
    return pa * PASCAL_TO_BAR


def bar_to_pascal(bar: float) -> float:
    _NonNegativePressure(val=bar)
    return bar * BAR_TO_PASCAL


def pascal_to_torr(pa: float) -> float:
    _NonNegativePressure(val=pa)
    return pa * PASCAL_TO_TORR


def torr_to_pascal(torr: float) -> float:
    _NonNegativePressure(val=torr)
    return torr * TORR_TO_PASCAL


def pascal_to_psi(pa: float) -> float:
    _NonNegativePressure(val=pa)
    return pa * PASCAL_TO_PSI


def psi_to_pascal(psi: float) -> float:
    _NonNegativePressure(val=psi)
    return psi * PSI_TO_PASCAL


# =============================================================================
# 6. Energy Conversion Functions
# =============================================================================


def hartree_to_ev(h: float) -> float:
    return h * HARTREE_TO_EV


def ev_to_hartree(ev: float) -> float:
    return ev * EV_TO_HARTREE


def hartree_to_kcal_mol(h: float) -> float:
    return h * HARTREE_TO_KCAL_MOL


def kcal_mol_to_hartree(kcal: float) -> float:
    return kcal * KCAL_MOL_TO_HARTREE


def hartree_to_kj_mol(h: float) -> float:
    return h * HARTREE_TO_KJ_MOL


def kj_mol_to_hartree(kj: float) -> float:
    return kj * KJ_MOL_TO_HARTREE


def hartree_to_joules(h: float) -> float:
    return h * HARTREE_TO_JOULE


def joules_to_hartree(j: float) -> float:
    return j * JOULE_TO_HARTREE


def calories_to_joules(cal: float) -> float:
    return cal * CALORIE_TO_JOULE


def joules_to_calories(j: float) -> float:
    return j * JOULE_TO_CALORIE


def ev_to_joules(ev: float) -> float:
    return ev * EV_TO_JOULE


def joules_to_ev(j: float) -> float:
    return j * JOULE_TO_EV


def ev_to_kj_mol(ev: float) -> float:
    return ev * EV_TO_KJ_MOL


def kj_mol_to_ev(kj: float) -> float:
    return kj * KJ_MOL_TO_EV


def ev_to_kcal_mol(ev: float) -> float:
    return ev * EV_TO_KCAL_MOL


def kcal_mol_to_ev(kcal: float) -> float:
    return kcal * KCAL_MOL_TO_EV


def kcal_mol_to_kj_mol(kcal: float) -> float:
    return kcal * KCAL_MOL_TO_KJ_MOL


def kj_mol_to_kcal_mol(kj: float) -> float:
    return kj * KJ_MOL_TO_KCAL_MOL


# =============================================================================
# 7. Ideal Gas Law Solvers (PV = nRT)
# =============================================================================


def calculate_ideal_gas_volume(moles: float, temperature_k: float, pressure_pa: float) -> float:
    if pressure_pa <= 0:
        raise ValueError("Pressure must be strictly positive")
    if temperature_k < 0:
        raise ValueError("Temperature cannot be negative")
    if moles < 0:
        raise ValueError("Moles cannot be negative")
    return (moles * MOLAR_GAS_CONSTANT_R * temperature_k) / pressure_pa


def calculate_ideal_gas_pressure(moles: float, temperature_k: float, volume_m3: float) -> float:
    if volume_m3 <= 0:
        raise ValueError("Volume must be strictly positive")
    if temperature_k < 0:
        raise ValueError("Temperature cannot be negative")
    if moles < 0:
        raise ValueError("Moles cannot be negative")
    return (moles * MOLAR_GAS_CONSTANT_R * temperature_k) / volume_m3


def calculate_ideal_gas_moles(pressure_pa: float, volume_m3: float, temperature_k: float) -> float:
    if temperature_k <= 0:
        raise ValueError("Temperature must be strictly positive")
    if pressure_pa < 0:
        raise ValueError("Pressure cannot be negative")
    if volume_m3 < 0:
        raise ValueError("Volume cannot be negative")
    return (pressure_pa * volume_m3) / (MOLAR_GAS_CONSTANT_R * temperature_k)


def calculate_ideal_gas_temperature(pressure_pa: float, volume_m3: float, moles: float) -> float:
    if moles <= 0:
        raise ValueError("Moles must be strictly positive")
    if pressure_pa < 0:
        raise ValueError("Pressure cannot be negative")
    if volume_m3 < 0:
        raise ValueError("Volume cannot be negative")
    return (pressure_pa * volume_m3) / (moles * MOLAR_GAS_CONSTANT_R)


def calculate_molar_volume(temperature_k: float = STANDARD_TEMPERATURE, pressure_pa: float = STANDARD_PRESSURE) -> float:
    return calculate_ideal_gas_volume(1.0, temperature_k, pressure_pa)


def calculate_thermal_energy_rt(temperature_k: float, unit: str = "kJ/mol") -> float:
    rt_joules = MOLAR_GAS_CONSTANT_R * temperature_k
    u = unit.lower().replace(" ", "")
    if "kj" in u:
        return rt_joules / 1000.0
    if "kcal" in u:
        return (rt_joules / 1000.0) / 4.184
    if "ev" in u:
        return rt_joules / (FARADAY_CONSTANT_F / ELEMENTARY_CHARGE_E * 1.602176634e-19 * AVOGADRO_CONSTANT_N_A) or (rt_joules / (AVOGADRO_CONSTANT_N_A * EV_TO_JOULE))
    return rt_joules


# =============================================================================
# 8. Thermodynamics & Kinetics Calculations
# =============================================================================


def calculate_gibbs_free_energy(enthalpy_j_mol: float, entropy_j_mol_k: float, temperature_k: float) -> float:
    return enthalpy_j_mol - temperature_k * entropy_j_mol_k


def calculate_equilibrium_constant(delta_g_j_mol: float, temperature_k: float = STANDARD_TEMPERATURE) -> float:
    return math.exp(-delta_g_j_mol / (MOLAR_GAS_CONSTANT_R * temperature_k))


def calculate_delta_g_from_k(equilibrium_constant_k: float, temperature_k: float = STANDARD_TEMPERATURE) -> float:
    if equilibrium_constant_k <= 0:
        raise ValueError("Equilibrium constant K must be strictly positive")
    return -MOLAR_GAS_CONSTANT_R * temperature_k * math.log(equilibrium_constant_k)


def calculate_arrhenius_rate_constant(pre_exponential_a: float, activation_energy_j_mol: float, temperature_k: float) -> float:
    if pre_exponential_a < 0:
        raise ValueError("Pre-exponential factor A cannot be negative")
    return pre_exponential_a * math.exp(-activation_energy_j_mol / (MOLAR_GAS_CONSTANT_R * temperature_k))


# =============================================================================
# 9. Pydantic Models
# =============================================================================


class ThermodynamicState(BaseModel):
    """Immutable thermodynamic state definition."""

    temperature: float = Field(default=STANDARD_TEMPERATURE, ge=0.0)
    pressure: float = Field(default=STANDARD_PRESSURE, ge=0.0)

    model_config = {"frozen": True, "arbitrary_types_allowed": True}

    @property
    def temperature_celsius(self) -> float:
        return self.temperature - ZERO_CELSIUS_IN_KELVIN

    @property
    def temperature_fahrenheit(self) -> float:
        return (self.temperature - ZERO_CELSIUS_IN_KELVIN) * (9.0 / 5.0) + 32.0

    @property
    def pressure_atm(self) -> float:
        return self.pressure * PASCAL_TO_ATMOSPHERE

    @property
    def pressure_bar(self) -> float:
        return self.pressure * PASCAL_TO_BAR

    @property
    def pressure_torr(self) -> float:
        return self.pressure * PASCAL_TO_TORR

    @property
    def is_standard_state(self) -> bool:
        return (
            abs(self.temperature - STANDARD_TEMPERATURE) <= 0.01
            and abs(self.pressure - STANDARD_PRESSURE) <= 1.0
        )

    @property
    def is_stp(self) -> bool:
        return (
            abs(self.temperature - STP_TEMPERATURE) <= 0.01
            and abs(self.pressure - STP_PRESSURE) <= 1.0
        )

    @property
    def thermal_energy_rt_kj_mol(self) -> float:
        return (MOLAR_GAS_CONSTANT_R * self.temperature) / 1000.0

    @property
    def thermal_energy_rt_kcal_mol(self) -> float:
        return self.thermal_energy_rt_kj_mol / 4.184

    @property
    def molar_volume_ideal_gas_liters_mol(self) -> float:
        return ((MOLAR_GAS_CONSTANT_R * self.temperature) / self.pressure) * 1000.0


class ReactionThermodynamics(BaseModel):
    """Thermodynamics and equilibrium metrics for a chemical reaction."""

    delta_h_j_mol: float
    delta_s_j_mol_k: float
    temperature: float = Field(default=STANDARD_TEMPERATURE, ge=0.0)

    model_config = {"arbitrary_types_allowed": True}

    @property
    def delta_g_j_mol(self) -> float:
        return calculate_gibbs_free_energy(self.delta_h_j_mol, self.delta_s_j_mol_k, self.temperature)

    @property
    def delta_g_kj_mol(self) -> float:
        return self.delta_g_j_mol / 1000.0

    @property
    def delta_g_kcal_mol(self) -> float:
        return self.delta_g_kj_mol / 4.184

    @property
    def is_spontaneous(self) -> bool:
        return self.delta_g_j_mol < 0.0

    @property
    def is_endergonic(self) -> bool:
        return self.delta_g_j_mol > 0.0

    @property
    def is_exothermic(self) -> bool:
        return self.delta_h_j_mol < 0.0

    @property
    def is_endothermic(self) -> bool:
        return self.delta_h_j_mol > 0.0

    @property
    def equilibrium_constant(self) -> float:
        return calculate_equilibrium_constant(self.delta_g_j_mol, self.temperature)


# =============================================================================
# 10. Legacy Validator Backward Compatibility
# =============================================================================


class ThermoConstantsValidator:
    """Validates thermodynamic conditions against standard states and basic physical boundaries."""

    @staticmethod
    def validate_temperature(temperature: float) -> bool:
        if temperature < 0:
            raise ValueError(f"Temperature cannot be negative. Got {temperature} K.")
        return True

    @staticmethod
    def validate_pressure(pressure: float) -> bool:
        if pressure < 0:
            raise ValueError(f"Pressure cannot be negative. Got {pressure} Pa.")
        return True

    @staticmethod
    def validate_volume(volume: float) -> bool:
        if volume < 0:
            raise ValueError(f"Volume cannot be negative. Got {volume} m^3.")
        return True

    @staticmethod
    def validate_moles(moles: float) -> bool:
        if moles < 0:
            raise ValueError(f"Amount of substance cannot be negative. Got {moles} mol.")
        return True

    @classmethod
    def is_standard_state(
        cls,
        temperature: float,
        pressure: float,
        temp_tol: float = 0.01,
        press_tol: float = 1.0,
    ) -> bool:
        cls.validate_temperature(temperature)
        cls.validate_pressure(pressure)
        temp_match = abs(temperature - STANDARD_TEMPERATURE) <= temp_tol
        press_match = abs(pressure - STANDARD_PRESSURE) <= press_tol
        return temp_match and press_match

    @classmethod
    def is_stp_state(
        cls,
        temperature: float,
        pressure: float,
        convention: str = "IUPAC",
        temp_tol: float = 0.01,
        press_tol: float = 1.0,
    ) -> bool:
        cls.validate_temperature(temperature)
        cls.validate_pressure(pressure)
        temp_match = abs(temperature - STP_TEMPERATURE) <= temp_tol
        target_p = STP_PRESSURE if convention.upper() == "IUPAC" else STP_PRESSURE_ATM
        press_match = abs(pressure - target_p) <= press_tol
        return temp_match and press_match

    @classmethod
    def validate_state(cls, temperature: float, pressure: float) -> ThermodynamicState:
        return ThermodynamicState(temperature=temperature, pressure=pressure)

    @classmethod
    def get_default_state(cls) -> ThermodynamicState:
        return ThermodynamicState(temperature=STANDARD_TEMPERATURE, pressure=STANDARD_PRESSURE)


__all__ = [
    "ATMOSPHERE_TO_PASCAL",
    "AVOGADRO_CONSTANT_N_A",
    "BAR_TO_PASCAL",
    "BOHR_RADIUS_ANGSTROM",
    "BOLTZMANN_CONSTANT_K_B",
    "CALORIE_TO_JOULE",
    "ELEMENTARY_CHARGE_E",
    "EV_TO_HARTREE",
    "EV_TO_JOULE",
    "EV_TO_KCAL_MOL",
    "EV_TO_KJ_MOL",
    "FARADAY_CONSTANT_F",
    "GAS_CONSTANT_R",
    "HARTREE_TO_EV",
    "HARTREE_TO_JOULE",
    "HARTREE_TO_KCAL_MOL",
    "HARTREE_TO_KJ_MOL",
    "JOULE_TO_CALORIE",
    "JOULE_TO_EV",
    "JOULE_TO_HARTREE",
    "KCAL_MOL_TO_EV",
    "KCAL_MOL_TO_HARTREE",
    "KCAL_MOL_TO_KJ_MOL",
    "KJ_MOL_TO_EV",
    "KJ_MOL_TO_HARTREE",
    "KJ_MOL_TO_KCAL_MOL",
    "MOLAR_GAS_CONSTANT_R",
    "NIST_PRESSURE",
    "NIST_TEMPERATURE",
    "PASCAL_TO_ATMOSPHERE",
    "PASCAL_TO_BAR",
    "PASCAL_TO_PSI",
    "PASCAL_TO_TORR",
    "PLANCK_CONSTANT_H",
    "PSI_TO_PASCAL",
    "REDUCED_PLANCK_CONSTANT_HBAR",
    "ReactionThermodynamics",
    "SPEED_OF_LIGHT_C",
    "STANDARD_PRESSURE",
    "STANDARD_STATE_PRESSURE_IUPAC",
    "STANDARD_TEMPERATURE",
    "STP_PRESSURE",
    "STP_PRESSURE_ATM",
    "STP_TEMPERATURE",
    "TORR_TO_PASCAL",
    "ThermoConstantsValidator",
    "ThermodynamicState",
    "ZERO_CELSIUS_IN_KELVIN",
    "atm_to_pascal",
    "bar_to_pascal",
    "calculate_arrhenius_rate_constant",
    "calculate_delta_g_from_k",
    "calculate_equilibrium_constant",
    "calculate_gibbs_free_energy",
    "calculate_ideal_gas_moles",
    "calculate_ideal_gas_pressure",
    "calculate_ideal_gas_temperature",
    "calculate_ideal_gas_volume",
    "calculate_molar_volume",
    "calculate_thermal_energy_rt",
    "calories_to_joules",
    "celsius_to_fahrenheit",
    "celsius_to_kelvin",
    "ev_to_hartree",
    "ev_to_joules",
    "ev_to_kcal_mol",
    "ev_to_kj_mol",
    "fahrenheit_to_celsius",
    "fahrenheit_to_kelvin",
    "hartree_to_ev",
    "hartree_to_joules",
    "hartree_to_kcal_mol",
    "hartree_to_kj_mol",
    "joules_to_calories",
    "joules_to_ev",
    "joules_to_hartree",
    "kcal_mol_to_ev",
    "kcal_mol_to_hartree",
    "kcal_mol_to_kj_mol",
    "kelvin_to_celsius",
    "kelvin_to_fahrenheit",
    "kj_mol_to_ev",
    "kj_mol_to_hartree",
    "kj_mol_to_kcal_mol",
    "pascal_to_atm",
    "pascal_to_bar",
    "pascal_to_psi",
    "pascal_to_torr",
    "psi_to_pascal",
    "torr_to_pascal",
]

