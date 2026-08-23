# -*- coding: utf-8 -*-
"""CoChem Stage 5.0: Multi-Dimensional Physics & JAX Solvers Engine (cochem_base module).

Re-exports core physics routines from cochem_jax_builder.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure root is in sys.path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from cochem_jax_builder import (  # noqa: E402
    CoChemPrecisionError,
    LocalizedVPT2Result,
    build_cli_parser,
    build_dvr_hamiltonian,
    enforce_jax_precision,
    jit_eigen_solver,
    localized_vpt2_coupling,
    main,
    nan_tensor_watchdog,
)

__all__ = [
    "CoChemPrecisionError",
    "LocalizedVPT2Result",
    "build_cli_parser",
    "build_dvr_hamiltonian",
    "enforce_jax_precision",
    "jit_eigen_solver",
    "localized_vpt2_coupling",
    "main",
    "nan_tensor_watchdog",
]
