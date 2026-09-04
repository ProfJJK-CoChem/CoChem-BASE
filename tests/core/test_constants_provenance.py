"""Physical verification of physical constants provenance and symbol aliases.
Strictly adheres to Method Matrix v4, CODATA 2022 standards, and Zero-Mock Protocol.
"""

from __future__ import annotations

import pytest

from cochem.core.cochem_constants import (
    C_ROT_MHZ_U_ANG2,
    PhysicalConstantsRegistry,
)
from cochem_base.core.cochem_constants import (
    C_ROT_MHZ_U_ANG2 as BASE_C_ROT,
    PhysicalConstantsRegistry as BaseRegistry,
)


def test_fundamental_constants_provenance() -> None:
    """Verify fundamental SI standards carry provenance tag [M] and correct values."""
    # Lookup by symbol
    h_const = PhysicalConstantsRegistry.get_constant("h")
    assert h_const.provenance == "[M]"
    assert h_const.value == pytest.approx(6.62607015e-34, rel=1e-15)

    c_const = PhysicalConstantsRegistry.get_constant("c")
    assert c_const.provenance == "[M]"
    assert c_const.value == pytest.approx(299792458.0, rel=1e-15)

    e_const = PhysicalConstantsRegistry.get_constant("e")
    assert e_const.provenance == "[M]"
    assert e_const.value == pytest.approx(1.602176634e-19, rel=1e-15)

    kb_const = PhysicalConstantsRegistry.get_constant("k_B")
    assert kb_const.provenance == "[M]"
    assert kb_const.value == pytest.approx(1.380649e-23, rel=1e-15)

    u_const = PhysicalConstantsRegistry.get_constant("u")
    assert u_const.provenance == "[M]"

    # Lookup by full name
    h_full = PhysicalConstantsRegistry.get_constant("Planck constant")
    assert h_full.provenance == "[M]"
    assert h_full.value == h_const.value

    c_full = PhysicalConstantsRegistry.get_constant("speed of light in vacuum")
    assert c_full.provenance == "[M]"
    assert c_full.value == c_const.value


def test_derived_rotational_constant_provenance() -> None:
    """Verify derived analytical rotational constant carries provenance tag [D] and exact value."""
    c_rot_const = PhysicalConstantsRegistry.get_constant("C_rot")
    assert c_rot_const.provenance == "[D]"
    assert c_rot_const.value == pytest.approx(505379.0084350172, abs=1e-9)

    c_rot_key = PhysicalConstantsRegistry.get_constant("C_ROT_MHZ_U_ANG2")
    assert c_rot_key.provenance == "[D]"
    assert c_rot_key.value == pytest.approx(505379.0084350172, abs=1e-9)

    # Constant export equality
    assert C_ROT_MHZ_U_ANG2 == 505379.0084350172
    assert BASE_C_ROT == C_ROT_MHZ_U_ANG2
    assert BaseRegistry.get_constant("C_rot").provenance == "[D]"
