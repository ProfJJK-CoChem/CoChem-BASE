#!/usr/bin/env python3
"""CoChem-UNITY: Stage 0.2 - Legacy entrypoint for Fast Pass Widget.

Re-exports canonical symbols from cochem_base.interfaces.cochem_unity_fast_pass_widget.
"""

from __future__ import annotations

from cochem_base.interfaces.cochem_unity_fast_pass_widget import (
    HAS_3DMOL,
    HAS_ASE,
    HAS_RDKIT,
    INCHIKEY_REGEX,
    KCAL_MOL_TO_EV,
    FastPassOptConfig,
    FastPassOptResult,
    FastPassWidget,
    HardwareProfile,
    PubChemProperty,
    PubChemPropertyTable,
    PubChemResponse,
    RDKitForceFieldCalculator,
    ase_atoms_to_xyz_string,
    build_pubchem_pug_url,
    compute_file_sha256,
    count_xyz_atoms,
    generate_3d_coordinates_obabel,
    generate_3d_coordinates_rdkit,
    get_ase_calculator,
    logger,
    profile_hardware,
    query_pubchem_pug_rest,
    rdkit_mol_to_ase_atoms,
    run_ase_optimization,
    run_crest_conformer_triage,
    run_fast_pass_optimization,
    smiles_to_rdkit_mol,
    write_xyz_file,
    xyz_file_to_ase_atoms,
)

__all__ = [
    "HAS_3DMOL",
    "HAS_ASE",
    "HAS_RDKIT",
    "INCHIKEY_REGEX",
    "KCAL_MOL_TO_EV",
    "FastPassOptConfig",
    "FastPassOptResult",
    "FastPassWidget",
    "HardwareProfile",
    "PubChemProperty",
    "PubChemPropertyTable",
    "PubChemResponse",
    "RDKitForceFieldCalculator",
    "ase_atoms_to_xyz_string",
    "build_pubchem_pug_url",
    "compute_file_sha256",
    "count_xyz_atoms",
    "generate_3d_coordinates_obabel",
    "generate_3d_coordinates_rdkit",
    "get_ase_calculator",
    "logger",
    "profile_hardware",
    "query_pubchem_pug_rest",
    "rdkit_mol_to_ase_atoms",
    "run_ase_optimization",
    "run_crest_conformer_triage",
    "run_fast_pass_optimization",
    "smiles_to_rdkit_mol",
    "write_xyz_file",
    "xyz_file_to_ase_atoms",
]

if __name__ == "__main__":
    w = FastPassWidget()
    w.display()
