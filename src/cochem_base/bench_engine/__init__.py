"""Lazy compatibility exports for the separately provisioned BENCH interfaces.

Importing a data-only schema must not initialize unrelated scientific backends.
Actual BENCH execution still requires its genuine isolated runtime and receipts.
"""

from __future__ import annotations

from importlib import import_module

_EXPORTS = {
    "BenchConfigSchema": ("cochem_base.bench_engine.cochem_bench_ingest", "BenchConfigSchema"),
    "BenchHardwareSchema": ("cochem_base.bench_engine.cochem_bench_ingest", "BenchHardwareSchema"),
    "BenchRunContext": ("cochem_base.bench_engine.cochem_bench_ingest", "BenchRunContext"),
    "BenchSiloPathsSchema": (
        "cochem_base.bench_engine.cochem_bench_ingest",
        "BenchSiloPathsSchema",
    ),
    "HardwareGovernor": ("cochem_base.bench_engine.cochem_bench_ingest", "HardwareGovernor"),
    "HardwareGovernorResult": (
        "cochem_base.bench_engine.cochem_bench_ingest",
        "HardwareGovernorResult",
    ),
    "PreFlightVerification": (
        "cochem_base.bench_engine.cochem_bench_ingest",
        "PreFlightVerification",
    ),
    "RegistryHandshake": ("cochem_base.bench_engine.cochem_bench_ingest", "RegistryHandshake"),
    "ResourceGuardError": ("cochem_base.bench_engine.cochem_bench_ingest", "ResourceGuardError"),
    "SiloIntegrityAssert": ("cochem_base.bench_engine.cochem_bench_ingest", "SiloIntegrityAssert"),
    "SiloIntegrityError": ("cochem_base.bench_engine.cochem_bench_ingest", "SiloIntegrityError"),
    "cleanse_ld_library_path": (
        "cochem_base.bench_engine.cochem_bench_ingest",
        "cleanse_ld_library_path",
    ),
    "extract_orca_path": ("cochem_base.bench_engine.cochem_bench_ingest", "extract_orca_path"),
    "run_bench_ingest_pipeline": (
        "cochem_base.bench_engine.cochem_bench_ingest",
        "run_bench_ingest_pipeline",
    ),
    "CBSExtrapolationResult": (
        "cochem_base.bench_engine.cochem_bench_cbs",
        "CBSExtrapolationResult",
    ),
    "DualBasisDispatcher": ("cochem_base.bench_engine.cochem_bench_cbs", "DualBasisDispatcher"),
    "HelgakerExtrapolator": ("cochem_base.bench_engine.cochem_bench_cbs", "HelgakerExtrapolator"),
    "ResidualFitAnalyzer": ("cochem_base.bench_engine.cochem_bench_cbs", "ResidualFitAnalyzer"),
    "SlowConvInterceptionResult": (
        "cochem_base.bench_engine.cochem_bench_cbs",
        "SlowConvInterceptionResult",
    ),
    "SlowConvInterceptor": ("cochem_base.bench_engine.cochem_bench_cbs", "SlowConvInterceptor"),
    "commit_cbs_to_hdf5": ("cochem_base.bench_engine.cochem_bench_cbs", "commit_cbs_to_hdf5"),
    "read_cbs_from_hdf5": ("cochem_base.bench_engine.cochem_bench_cbs", "read_cbs_from_hdf5"),
    "run_cbs_pipeline": ("cochem_base.bench_engine.cochem_bench_cbs", "run_cbs_pipeline"),
    "CBS_UNCERTAINTY_THRESHOLD_KCAL_MOL": (
        "cochem_base.bench_engine.cochem_bench_cbs",
        "CBS_UNCERTAINTY_THRESHOLD_KCAL_MOL",
    ),
    "PARAMETER_MATRIX": ("cochem_base.bench_engine.cochem_bench_cbs", "PARAMETER_MATRIX"),
    "CoreValenceMapper": ("cochem_base.bench_engine.cochem_bench_cv", "CoreValenceMapper"),
    "CVCorrectionResult": ("cochem_base.bench_engine.cochem_bench_cv", "CVCorrectionResult"),
    "DeltaExtractor": ("cochem_base.bench_engine.cochem_bench_cv", "DeltaExtractor"),
    "DualCorrelationEngine": ("cochem_base.bench_engine.cochem_bench_cv", "DualCorrelationEngine"),
    "commit_cv_to_hdf5": ("cochem_base.bench_engine.cochem_bench_cv", "commit_cv_to_hdf5"),
    "read_cv_from_hdf5": ("cochem_base.bench_engine.cochem_bench_cv", "read_cv_from_hdf5"),
    "DeltaRelExtractor": ("cochem_base.bench_engine.cochem_bench_rel", "DeltaRelExtractor"),
    "RelCorrectionResult": ("cochem_base.bench_engine.cochem_bench_rel", "RelCorrectionResult"),
    "RelativisticExecutionError": (
        "cochem_base.bench_engine.cochem_bench_rel",
        "RelativisticExecutionError",
    ),
    "RelativisticHamiltonianInjector": (
        "cochem_base.bench_engine.cochem_bench_rel",
        "RelativisticHamiltonianInjector",
    ),
    "RelativisticInputError": (
        "cochem_base.bench_engine.cochem_bench_rel",
        "RelativisticInputError",
    ),
    "SpinOrbitCoupler": ("cochem_base.bench_engine.cochem_bench_rel", "SpinOrbitCoupler"),
    "X2CDivergenceError": ("cochem_base.bench_engine.cochem_bench_rel", "X2CDivergenceError"),
    "X2CHandler": ("cochem_base.bench_engine.cochem_bench_rel", "X2CHandler"),
    "commit_rel_to_hdf5": ("cochem_base.bench_engine.cochem_bench_rel", "commit_rel_to_hdf5"),
    "read_rel_from_hdf5": ("cochem_base.bench_engine.cochem_bench_rel", "read_rel_from_hdf5"),
    "run_rel_pipeline": ("cochem_base.bench_engine.cochem_bench_rel", "run_rel_pipeline"),
    "DEFAULT_RELATIVISTIC_Z_THRESHOLD": (
        "cochem_base.bench_engine.cochem_bench_rel",
        "DEFAULT_RELATIVISTIC_Z_THRESHOLD",
    ),
    "HARTREE_TO_KCAL_MOL": ("cochem_base.bench_engine.cochem_bench_rel", "HARTREE_TO_KCAL_MOL"),
    "AirGapPackageMissingError": (
        "cochem_base.bench_engine.cochem_bench_export",
        "AirGapPackageMissingError",
    ),
    "AirGapVerifier": ("cochem_base.bench_engine.cochem_bench_export", "AirGapVerifier"),
    "CompositeAggregator": ("cochem_base.bench_engine.cochem_bench_export", "CompositeAggregator"),
    "CompositeEnergyRecord": (
        "cochem_base.bench_engine.cochem_bench_export",
        "CompositeEnergyRecord",
    ),
    "ExportPipelineResult": (
        "cochem_base.bench_engine.cochem_bench_export",
        "ExportPipelineResult",
    ),
    "HDF5SchemaError": ("cochem_base.bench_engine.cochem_bench_export", "HDF5SchemaError"),
    "LaTeXExportConfig": ("cochem_base.bench_engine.cochem_bench_export", "LaTeXExportConfig"),
    "MissingZPVEError": ("cochem_base.bench_engine.cochem_bench_export", "MissingZPVEError"),
    "PublicationArchiver": ("cochem_base.bench_engine.cochem_bench_export", "PublicationArchiver"),
    "ProvenanceStamper": ("cochem_base.bench_engine.cochem_bench_export", "ProvenanceStamper"),
    "SiunitxLaTeXCompiler": (
        "cochem_base.bench_engine.cochem_bench_export",
        "SiunitxLaTeXCompiler",
    ),
    "run_export_pipeline": ("cochem_base.bench_engine.cochem_bench_export", "run_export_pipeline"),
}

__all__ = [
    # Stage 1.0 Ingest & Handshake
    "BenchConfigSchema",
    "BenchHardwareSchema",
    "BenchRunContext",
    "BenchSiloPathsSchema",
    "HardwareGovernor",
    "HardwareGovernorResult",
    "PreFlightVerification",
    "RegistryHandshake",
    "ResourceGuardError",
    "SiloIntegrityError",
    "cleanse_ld_library_path",
    "extract_orca_path",
    "run_bench_ingest_pipeline",
    # Stage 2.0 CBS
    "DualBasisDispatcher",
    "HelgakerExtrapolator",
    "ResidualFitAnalyzer",
    "SlowConvInterceptor",
    "CBSExtrapolationResult",
    "SlowConvInterceptionResult",
    "commit_cbs_to_hdf5",
    "read_cbs_from_hdf5",
    "run_cbs_pipeline",
    "CBS_UNCERTAINTY_THRESHOLD_KCAL_MOL",
    "PARAMETER_MATRIX",
    # Stage 3.0 CV
    "CoreValenceMapper",
    "DualCorrelationEngine",
    "DeltaExtractor",
    "CVCorrectionResult",
    "commit_cv_to_hdf5",
    "read_cv_from_hdf5",
    # Stage 4.0 Relativistic & SOC
    "RelativisticHamiltonianInjector",
    "X2CHandler",
    "X2CDivergenceError",
    "RelativisticExecutionError",
    "RelativisticInputError",
    "SpinOrbitCoupler",
    "DeltaRelExtractor",
    "RelCorrectionResult",
    "commit_rel_to_hdf5",
    "read_rel_from_hdf5",
    "run_rel_pipeline",
    "DEFAULT_RELATIVISTIC_Z_THRESHOLD",
    "HARTREE_TO_KCAL_MOL",
    # Stage 5.0 Exporter
    "CompositeAggregator",
    "CompositeEnergyRecord",
    "ExportPipelineResult",
    "SiunitxLaTeXCompiler",
    "LaTeXExportConfig",
    "ProvenanceStamper",
    "AirGapVerifier",
    "PublicationArchiver",
    "MissingZPVEError",
    "AirGapPackageMissingError",
    "HDF5SchemaError",
    "run_export_pipeline",
]


def __getattr__(name: str):
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module, attribute = target
    value = getattr(import_module(module), attribute)
    globals()[name] = value
    return value
