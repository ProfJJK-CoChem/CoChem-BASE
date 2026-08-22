#!/usr/bin/env python3
"""CoChem-UNITY: Stage 0.2 - Legacy entrypoint for Fast Pass Widget.

Re-exports canonical symbols from cochem_base.interfaces.cochem_unity_fast_pass_widget.
"""

from __future__ import annotations

from cochem_base.interfaces.cochem_unity_fast_pass_widget import (
    HAS_3DMOL,
    INCHIKEY_REGEX,
    FastPassOptConfig,
    FastPassOptResult,
    FastPassWidget,
    PubChemProperty,
    PubChemPropertyTable,
    PubChemResponse,
    build_pubchem_pug_url,
    compute_file_sha256,
    count_xyz_atoms,
    generate_3d_coordinates_obabel,
    logger,
    query_pubchem_pug_rest,
    run_crest_conformer_triage,
    run_fast_pass_optimization,
)

__all__ = [
    "HAS_3DMOL",
    "INCHIKEY_REGEX",
    "FastPassOptConfig",
    "FastPassOptResult",
    "FastPassWidget",
    "PubChemProperty",
    "PubChemPropertyTable",
    "PubChemResponse",
    "build_pubchem_pug_url",
    "compute_file_sha256",
    "count_xyz_atoms",
    "generate_3d_coordinates_obabel",
    "logger",
    "query_pubchem_pug_rest",
    "run_crest_conformer_triage",
    "run_fast_pass_optimization",
]

if __name__ == "__main__":
    w = FastPassWidget()
    w.display()
