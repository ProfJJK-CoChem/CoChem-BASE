"""CoChem-Mobile: Cloud backend and thin-client orchestration engine for the CoChem ecosystem."""

from __future__ import annotations

from importlib import import_module

# Load optional UI and chemistry dependencies only when their exports are requested.
_EXPORTS = {
    'AtomCoordinate3DRecord': ('cochem.mobile.rdkit_bridge', 'AtomCoordinate3DRecord'),
    'ChelateAssembler': ('cochem.mobile.inorganic', 'ChelateAssembler'),
    'ComplexSummaryCard': ('cochem.mobile.inorganic', 'ComplexSummaryCard'),
    'ConformerEmbeddingError': ('cochem.mobile.rdkit_bridge', 'ConformerEmbeddingError'),
    'CoordinateAssembler': ('cochem.mobile.inorganic', 'CoordinateAssembler'),
    'CoordinationGeometry': ('cochem.mobile.inorganic', 'CoordinationGeometry'),
    'CoordinationPolyhedron': ('cochem.mobile.inorganic', 'CoordinationPolyhedron'),
    'DonorAtom': ('cochem.mobile.inorganic', 'DonorAtom'),
    'HDF5InorganicSerializer': ('cochem.mobile.inorganic', 'HDF5InorganicSerializer'),
    'InorganicAirGapClient': ('cochem.mobile.inorganic', 'InorganicAirGapClient'),
    'InorganicAssemblyEngine': ('cochem.mobile.inorganic', 'InorganicAssemblyEngine'),
    'InorganicAtom3D': ('cochem.mobile.inorganic', 'InorganicAtom3D'),
    'InorganicBondRecord': ('cochem.mobile.inorganic', 'InorganicBondRecord'),
    'InorganicBuilderScreen': ('cochem.mobile.inorganic', 'InorganicBuilderScreen'),
    'InorganicBuilderWidget': ('cochem.mobile.inorganic', 'InorganicBuilderWidget'),
    'InorganicComplex': ('cochem.mobile.inorganic', 'InorganicComplex'),
    'InorganicComplexSchema': ('cochem.mobile.inorganic', 'InorganicComplexSchema'),
    'InvalidSmilesError': ('cochem.mobile.rdkit_bridge', 'InvalidSmilesError'),
    'IsomerPickerWidget': ('cochem.mobile.inorganic', 'IsomerPickerWidget'),
    'IsomerResolver': ('cochem.mobile.inorganic', 'IsomerResolver'),
    'JSONInorganicSerializer': ('cochem.mobile.inorganic', 'JSONInorganicSerializer'),
    'Ligand': ('cochem.mobile.inorganic', 'Ligand'),
    'LigandBudgetWidget': ('cochem.mobile.inorganic', 'LigandBudgetWidget'),
    'LigandLibrary': ('cochem.mobile.inorganic', 'LigandLibrary'),
    'LigandSelectorDialog': ('cochem.mobile.inorganic', 'LigandSelectorDialog'),
    'MetalCategory': ('cochem.mobile.inorganic', 'MetalCategory'),
    'MetalCenter': ('cochem.mobile.inorganic', 'MetalCenter'),
    'PolyhedronTemplateRegistry': ('cochem.mobile.inorganic', 'PolyhedronTemplateRegistry'),
    'RDKit3DResult': ('cochem.mobile.rdkit_bridge', 'RDKit3DResult'),
    'SQLiteInorganicStore': ('cochem.mobile.inorganic', 'SQLiteInorganicStore'),
    'Smiles3DConformerEngine': ('cochem.mobile.rdkit_bridge', 'Smiles3DConformerEngine'),
    'calculate_formula_weight': ('cochem.mobile.inorganic', 'calculate_formula_weight'),
    'complex_to_schema': ('cochem.mobile.inorganic', 'complex_to_schema'),
    'core': ('cochem_mobile.core', None),
    'generate_deterministic_3d_coordinates': ('cochem.mobile.rdkit_bridge', 'generate_deterministic_3d_coordinates'),
    'get_polyhedron_coordination_number': ('cochem.mobile.inorganic', 'get_polyhedron_coordination_number'),
    'relax_geometry_and_calculate_energy': ('cochem.mobile.rdkit_bridge', 'relax_geometry_and_calculate_energy'),
    'smiles_to_3d': ('cochem.mobile.rdkit_bridge', 'smiles_to_3d'),
    'smiles_to_3d_async': ('cochem.mobile.rdkit_bridge', 'smiles_to_3d_async'),
    'validate_and_sanitize_smiles': ('cochem.mobile.rdkit_bridge', 'validate_and_sanitize_smiles'),
}

__all__ = list(_EXPORTS)

__version__ = "0.1.0"


def __getattr__(name: str):
    try:
        module_name, attribute = _EXPORTS[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
    module = import_module(module_name)
    value = module if attribute is None else getattr(module, attribute)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
