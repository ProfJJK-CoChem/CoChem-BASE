"""Zero-mock unit test for Consolidation of Shared ML Primitives under cochem_base.ml.

SRS Chunk 14 / Suggestion #138 / Method Matrix v4 §8C, §10.8 [M], [D].
Zero-Mock Mandate v3: Completely authentic standard namespace imports without sys.path hacks.
"""

from __future__ import annotations


def test_cochem_base_ml_exports() -> None:
    """Verify cochem_base.ml exports ConformalPredictor, KernelRidgeModel, and active learning managers [M]."""
    import cochem_base.ml as cml

    assert hasattr(cml, "ConformalPredictor"), "ConformalPredictor missing from cochem_base.ml"
    assert hasattr(cml, "KernelRidgeModel"), "KernelRidgeModel missing from cochem_base.ml"
    assert hasattr(cml, "ActiveLearningManager"), "ActiveLearningManager missing from cochem_base.ml"

    # Direct import check
    from cochem_base.ml import (
        ActiveLearningManager,
        ConformalPredictor,
        KernelRidgeModel,
    )

    assert ConformalPredictor is not None
    assert KernelRidgeModel is not None
    assert ActiveLearningManager is not None


def test_submodule_structure_and_no_sys_path_append() -> None:
    """Verify submodules exist under cochem_base.ml and are cleanly importable without sys.path hacks [M]."""
    import cochem_base.ml.active_learning as al
    import cochem_base.ml.baselines as base
    import cochem_base.ml.conformal as conf
    import cochem_base.ml.krr as krr

    assert hasattr(al, "ActiveLearningManager")
    assert hasattr(conf, "ConformalPredictor")
    assert hasattr(krr, "KernelRidgeModel")
    assert hasattr(base, "EMTBaselineEngine")
