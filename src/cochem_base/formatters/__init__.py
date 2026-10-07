"""Formatter exports, loaded on demand to keep core preflight independent of catalog tooling."""

from importlib import import_module

_EXPORTS = {
    'BranchType': '.cochem_dark_branch_filter',
    'CitationManager': '.scribe_citation_api',
    'DarkBranchFilter': '.cochem_dark_branch_filter',
    'DarkBranchFilterConfig': '.cochem_dark_branch_filter',
    'DipoleType': '.cochem_dark_branch_filter',
    'FilterRejectionReason': '.cochem_dark_branch_filter',
    'FilterStatistics': '.cochem_dark_branch_filter',
    'InertialDefectValidationReport': '.cochem_inertial_defect_validator',
    'InertialDefectValidator': '.cochem_inertial_defect_validator',
    'InertialDefectValidatorConfig': '.cochem_inertial_defect_validator',
    'Jinja2Templater': '.scribe_templater',
    'MarkdownBuilder': '.scribe_md_generator',
    'MolecularInertialProperties': '.cochem_inertial_defect_validator',
    'PlanarityClassification': '.cochem_inertial_defect_validator',
    'ProductClass': '.cochem_inertial_defect_validator',
    'RotorType': '.cochem_inertial_defect_validator',
    'TransitionRecord': '.cochem_dark_branch_filter',
    'ValidationStatus': '.cochem_inertial_defect_validator',
    'VisualAssetBridge': '.scribe_viz_bridge',
    'calculate_inertial_properties': '.cochem_inertial_defect_validator',
    'classify_planarity': '.cochem_inertial_defect_validator',
    'classify_rotor_type': '.cochem_inertial_defect_validator',
    'compute_center_of_mass': '.cochem_inertial_defect_validator',
    'compute_inertia_tensor': '.cochem_inertial_defect_validator',
    'compute_inertial_defect': '.cochem_inertial_defect_validator',
    'compute_planar_moments': '.cochem_inertial_defect_validator',
    'compute_principal_moments_and_axes': '.cochem_inertial_defect_validator',
    'compute_rays_asymmetry_kappa': '.cochem_inertial_defect_validator',
    'compute_rotational_constants': '.cochem_inertial_defect_validator',
    'compute_wangs_asymmetry_parameters': '.cochem_inertial_defect_validator',
    'filter_dark_branches': '.cochem_dark_branch_filter',
    'filter_parquet_catalog': '.cochem_dark_branch_filter',
    'filter_spcat_catalog': '.cochem_dark_branch_filter',
    'generate_dark_branch_report': '.cochem_dark_branch_filter',
    'get_atomic_mass': '.cochem_inertial_defect_validator',
    'validate_inertial_defect': '.cochem_inertial_defect_validator',
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    try:
        module_name = _EXPORTS[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
    value = getattr(import_module(module_name, __name__), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))
