"""CoChem Mobile Inorganic Coordination Complex Module (SRS Chunk 06).

Zero-Mock implementation of touch-optimized Inorganic Complex Generator UI,
polyhedral coordinate templates (CN=2..9), chelate stereochemistry assemblers,
Pydantic v2 schemas, and dynamic Mendeleev atomic weight integration."""

from __future__ import annotations

from importlib import import_module

# Load optional UI and chemistry dependencies only when their exports are requested.
_EXPORTS = {
    'ChelateAssembler': ('cochem.mobile.inorganic.engine', 'ChelateAssembler'),
    'ComplexSummaryCard': ('cochem.mobile.inorganic.ui', 'ComplexSummaryCard'),
    'CoordinateAssembler': ('cochem.mobile.inorganic.engine', 'CoordinateAssembler'),
    'CoordinationGeometry': ('cochem.mobile.inorganic.models', 'CoordinationGeometry'),
    'CoordinationPolyhedron': ('cochem.mobile.inorganic.models', 'CoordinationPolyhedron'),
    'DonorAtom': ('cochem.mobile.inorganic.models', 'DonorAtom'),
    'HDF5InorganicSerializer': ('cochem.mobile.inorganic.storage', 'HDF5InorganicSerializer'),
    'InorganicAirGapClient': ('cochem.mobile.inorganic.storage', 'InorganicAirGapClient'),
    'InorganicAssemblyEngine': ('cochem.mobile.inorganic.engine', 'InorganicAssemblyEngine'),
    'InorganicAtom3D': ('cochem.mobile.inorganic.storage', 'InorganicAtom3D'),
    'InorganicBondRecord': ('cochem.mobile.inorganic.storage', 'InorganicBondRecord'),
    'InorganicBuilderScreen': ('cochem.mobile.inorganic.ui', 'InorganicBuilderScreen'),
    'InorganicBuilderWidget': ('cochem.mobile.inorganic.ui', 'InorganicBuilderWidget'),
    'InorganicComplex': ('cochem.mobile.inorganic.models', 'InorganicComplex'),
    'InorganicComplexSchema': ('cochem.mobile.inorganic.storage', 'InorganicComplexSchema'),
    'IsomerPickerWidget': ('cochem.mobile.inorganic.ui', 'IsomerPickerWidget'),
    'IsomerResolver': ('cochem.mobile.inorganic.engine', 'IsomerResolver'),
    'JSONInorganicSerializer': ('cochem.mobile.inorganic.storage', 'JSONInorganicSerializer'),
    'Ligand': ('cochem.mobile.inorganic.models', 'Ligand'),
    'LigandBudgetWidget': ('cochem.mobile.inorganic.ui', 'LigandBudgetWidget'),
    'LigandLibrary': ('cochem.mobile.inorganic.models', 'LigandLibrary'),
    'LigandSelectorDialog': ('cochem.mobile.inorganic.ui', 'LigandSelectorDialog'),
    'MetalCategory': ('cochem.mobile.inorganic.models', 'MetalCategory'),
    'MetalCenter': ('cochem.mobile.inorganic.models', 'MetalCenter'),
    'PolyhedronTemplateRegistry': ('cochem.mobile.inorganic.engine', 'PolyhedronTemplateRegistry'),
    'SQLiteInorganicStore': ('cochem.mobile.inorganic.storage', 'SQLiteInorganicStore'),
    'calculate_formula_weight': ('cochem.mobile.inorganic.models', 'calculate_formula_weight'),
    'complex_to_schema': ('cochem.mobile.inorganic.storage', 'complex_to_schema'),
    'get_polyhedron_coordination_number': ('cochem.mobile.inorganic.models', 'get_polyhedron_coordination_number'),
}

__all__ = list(_EXPORTS)


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
