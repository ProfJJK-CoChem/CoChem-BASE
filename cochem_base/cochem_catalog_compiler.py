"""Re-export module for cochem_catalog_compiler within the cochem_base package hierarchy."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure root path is accessible
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from cochem_catalog_compiler import (  # noqa: E402
    SPECTRAL_CATALOG_SCHEMA,
    CoChemPathManager,
    InactiveRotorError,
    apply_readonly_chmod,
    buffer_lock_sync,
    deduplicate_bibtex,
    generate_methods_latex,
    inactive_rotor_catcher,
    isolated_workspace_generator,
    parallel_temperature_compiler,
    parse_spcat_cat_line,
    parse_spcat_cat_stream,
    purge_ghost_outputs,
    pyarrow_chunked_serializer,
    remove_readonly_seal,
)

__all__ = [
    "SPECTRAL_CATALOG_SCHEMA",
    "InactiveRotorError",
    "CoChemPathManager",
    "apply_readonly_chmod",
    "remove_readonly_seal",
    "buffer_lock_sync",
    "purge_ghost_outputs",
    "isolated_workspace_generator",
    "inactive_rotor_catcher",
    "parse_spcat_cat_line",
    "parse_spcat_cat_stream",
    "pyarrow_chunked_serializer",
    "parallel_temperature_compiler",
    "generate_methods_latex",
    "deduplicate_bibtex",
]
