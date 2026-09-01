#!/usr/bin/env python3
"""CoChem-INTERFACES: ORCA ExtOpt External Optimizer Wrapper for MACE-OFF (Direct Entrypoint).

Re-exports canonical symbols from cochem_base.interfaces.oet_maceoff.
Method Matrix v4 Section 10.7 Compliant.
"""

from __future__ import annotations

import sys
from cochem_base.interfaces.oet_maceoff import (
    ANGSTROM_TO_BOHR,
    BOHR_PER_A,
    BOHR_TO_ANGSTROM,
    EH_PER_EV,
    EV_PER_ANG_TO_EH_PER_BOHR,
    EV_TO_HARTREE,
    HARTREE_TO_EV,
    HARTREE_TO_KCAL_MOL,
    HARTREE_TO_KJ_MOL,
    EngradResult,
    ExtInpData,
    MACEOFFConfig,
    compute_committee_uncertainty,
    compute_maceoff_energy_gradient,
    create_maceoff_calculator,
    get_element_atomic_mass,
    get_element_atomic_number,
    logger,
    main,
    read_extinp,
    read_xyz,
    run_oet_maceoff,
    validate_maceoff_constraints,
    write_engrad,
    write_xyz,
)

__all__ = [
    "ANGSTROM_TO_BOHR",
    "BOHR_PER_A",
    "BOHR_TO_ANGSTROM",
    "EH_PER_EV",
    "EV_PER_ANG_TO_EH_PER_BOHR",
    "EV_TO_HARTREE",
    "HARTREE_TO_EV",
    "HARTREE_TO_KCAL_MOL",
    "HARTREE_TO_KJ_MOL",
    "EngradResult",
    "ExtInpData",
    "MACEOFFConfig",
    "compute_committee_uncertainty",
    "compute_maceoff_energy_gradient",
    "create_maceoff_calculator",
    "get_element_atomic_mass",
    "get_element_atomic_number",
    "logger",
    "main",
    "read_extinp",
    "read_xyz",
    "run_oet_maceoff",
    "validate_maceoff_constraints",
    "write_engrad",
    "write_xyz",
]

if __name__ == "__main__":
    sys.exit(main())
