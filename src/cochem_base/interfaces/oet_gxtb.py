#!/usr/bin/env python3
"""CoChem-INTERFACES: ORCA ExtOpt External Optimizer Wrapper for g-xTB (Direct Entrypoint).

Re-exports canonical symbols from cochem_base.interfaces.oet_gxtb.
Method Matrix v4 Section 10.6 Compliant.
"""

from __future__ import annotations

import sys
from cochem_base.interfaces.oet_gxtb import (
    ANGSTROM_TO_BOHR,
    BOHR_PER_A,
    BOHR_TO_ANGSTROM,
    EH_PER_EV,
    EV_TO_HARTREE,
    HARTREE_TO_EV,
    HARTREE_TO_KCAL_MOL,
    HARTREE_TO_KJ_MOL,
    EngradResult,
    ExtInpData,
    GXTBConfig,
    compute_numerical_gradient,
    find_xtb_binary,
    get_element_atomic_mass,
    logger,
    main,
    parse_xtb_energy,
    parse_xtb_gradient,
    read_extinp,
    read_xyz,
    run_oet_gxtb,
    run_xtb_single_point,
    write_engrad,
    write_xyz,
)

__all__ = [
    "ANGSTROM_TO_BOHR",
    "BOHR_PER_A",
    "BOHR_TO_ANGSTROM",
    "EH_PER_EV",
    "EV_TO_HARTREE",
    "HARTREE_TO_EV",
    "HARTREE_TO_KCAL_MOL",
    "HARTREE_TO_KJ_MOL",
    "EngradResult",
    "ExtInpData",
    "GXTBConfig",
    "compute_numerical_gradient",
    "find_xtb_binary",
    "get_element_atomic_mass",
    "logger",
    "main",
    "parse_xtb_energy",
    "parse_xtb_gradient",
    "read_extinp",
    "read_xyz",
    "run_oet_gxtb",
    "run_xtb_single_point",
    "write_engrad",
    "write_xyz",
]

if __name__ == "__main__":
    sys.exit(main())
