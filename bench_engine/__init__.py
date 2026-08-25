"""CoChem Bench Engine: Core Scientific Extrapolation & Benchmark Engines (Stages 1.0 - 5.0)."""

from __future__ import annotations

from bench_engine.cochem_bench_cbs import (
    DualBasisDispatcher,
    HelgakerExtrapolator,
    ResidualFitAnalyzer,
    SlowConvInterceptor,
    CBSExtrapolationResult,
    SlowConvInterceptionResult,
    commit_cbs_to_hdf5,
    read_cbs_from_hdf5,
    run_cbs_pipeline,
    HARTREE_TO_KCAL_MOL,
    CBS_UNCERTAINTY_THRESHOLD_KCAL_MOL,
    PARAMETER_MATRIX,
)

__all__ = [
    "DualBasisDispatcher",
    "HelgakerExtrapolator",
    "ResidualFitAnalyzer",
    "SlowConvInterceptor",
    "CBSExtrapolationResult",
    "SlowConvInterceptionResult",
    "commit_cbs_to_hdf5",
    "read_cbs_from_hdf5",
    "run_cbs_pipeline",
    "HARTREE_TO_KCAL_MOL",
    "CBS_UNCERTAINTY_THRESHOLD_KCAL_MOL",
    "PARAMETER_MATRIX",
]
