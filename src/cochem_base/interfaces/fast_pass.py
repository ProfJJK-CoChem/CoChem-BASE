#!/usr/bin/env python3
"""CoChem-UNITY: Stage 0.2 - Legacy Fast Pass Geometry Triage Script.

Legacy geometry triage script referenced in SRS Document 2 Rectification Matrix;
superseded by interfaces/cochem_unity_fast_pass_widget.py for g-xTB/AIMNet2 MLFF triage.
Maintains full backward compatibility for legacy geometry triage invocations,
direct CLI execution, and re-exports canonical symbols from
cochem_base.interfaces.cochem_unity_fast_pass_widget.
Compliant with Method Matrix v4 Section 9B and Section 10.6.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from cochem_base.config_loader import get_artifact_dir
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

# Legacy aliases for backward compatibility
run_fast_pass = run_fast_pass_optimization
run_triage = run_fast_pass_optimization
triage_geometry = run_fast_pass_optimization
fast_pass_triage = run_fast_pass_optimization


def build_parser() -> argparse.ArgumentParser:
    """Constructs the command-line interface argument parser for geometry triage."""
    parser = argparse.ArgumentParser(
        description="CoChem Stage 0.2 Legacy Fast Pass Geometry Triage",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "query",
        nargs="?",
        default=None,
        help="SMILES string, PubChem CID, InChIKey, or compound name for triage",
    )
    parser.add_argument(
        "--smiles",
        "-s",
        type=str,
        default=None,
        help="Target SMILES string to optimize",
    )
    parser.add_argument(
        "--engine",
        "-e",
        type=str,
        default="gfn2-xtb",
        choices=["gfn2-xtb", "gfn-ff", "aimnet2", "mace-off", "rdkit-uff", "rdkit-mmff94"],
        help="Optimization compute engine",
    )
    parser.add_argument(
        "--forcefield",
        "-ff",
        type=str,
        default="MMFF94",
        choices=["MMFF94", "UFF"],
        help="Force field for initial 3D coordinate generation",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=500,
        help="Maximum optimization steps",
    )
    parser.add_argument(
        "--fmax",
        type=float,
        default=0.05,
        help="Force convergence threshold in eV/Angstrom",
    )
    parser.add_argument(
        "--tol-e",
        type=float,
        default=1e-5,
        help="Energy convergence tolerance (Hartree) for AIMNet2/GOAT compliance",
    )
    parser.add_argument(
        "--no-crest",
        action="store_true",
        help="Disable CREST conformer triage stage",
    )
    parser.add_argument(
        "--crest-args",
        type=str,
        default="--gfn2",
        help="Additional arguments forwarded to CREST binary",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="auto",
        choices=["auto", "cpu", "cuda"],
        help="Compute device for MLFF inference",
    )
    parser.add_argument(
        "--optimizer",
        type=str,
        default="BFGS",
        choices=["BFGS", "LBFGS", "FIRE"],
        help="ASE optimizer algorithm",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=str,
        default=None,
        help="Destination directory for output coordinates and artifacts",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch interactive Jupyter widget interface",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Main execution entrypoint for fast_pass triage CLI and interactive runner."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.gui:
        widget = FastPassWidget()
        widget.display()
        return 0

    target_smiles = args.smiles or args.query
    if not target_smiles:
        try:
            get_ipython = sys.modules.get("IPython")
            if get_ipython is not None:
                widget = FastPassWidget()
                widget.display()
                return 0
        except Exception as err:
            logger.debug("IPython widget launch fallback: %s", err)
        parser.print_help()
        return 1

    resolved_smiles = target_smiles
    if not any(target_smiles.startswith(p) for p in ("C", "c", "N", "O", "S", "P", "F", "Cl", "Br", "I", "[", "(")):
        try:
            pubchem_resp = query_pubchem_pug_rest(target_smiles)
            if pubchem_resp.property_table.properties:
                prop = pubchem_resp.property_table.properties[0]
                smi = prop.CanonicalSMILES or prop.IsomericSMILES
                if smi:
                    resolved_smiles = smi
                    logger.info("Resolved query '%s' to SMILES: %s", target_smiles, resolved_smiles)
        except Exception as err:
            logger.warning("PubChem query resolution fell back to direct interpretation: %s", err)

    out_dir = Path(args.output_dir) if args.output_dir else get_artifact_dir() / "fast_pass_triage"
    out_dir.mkdir(parents=True, exist_ok=True)

    config = FastPassOptConfig(
        engine=args.engine,
        forcefield=args.forcefield,
        steps=args.steps,
        fmax=args.fmax,
        tol_e=args.tol_e,
        use_crest=not args.no_crest,
        crest_args=args.crest_args,
        device=args.device,
        optimizer=args.optimizer,
    )

    result = run_fast_pass_optimization(
        smiles=resolved_smiles,
        output_dir=out_dir,
        config=config,
    )

    print(result.model_dump_json(indent=2))
    return 0 if result.success else 1


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
    "build_parser",
    "build_pubchem_pug_url",
    "compute_file_sha256",
    "count_xyz_atoms",
    "fast_pass_triage",
    "generate_3d_coordinates_obabel",
    "generate_3d_coordinates_rdkit",
    "get_ase_calculator",
    "logger",
    "main",
    "profile_hardware",
    "query_pubchem_pug_rest",
    "rdkit_mol_to_ase_atoms",
    "run_ase_optimization",
    "run_crest_conformer_triage",
    "run_fast_pass",
    "run_fast_pass_optimization",
    "run_triage",
    "smiles_to_rdkit_mol",
    "triage_geometry",
    "write_xyz_file",
    "xyz_file_to_ase_atoms",
]

if __name__ == "__main__":
    sys.exit(main())
