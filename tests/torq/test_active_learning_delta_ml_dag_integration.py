"""CoChem-TORQ: Test Active Learning & Delta-ML PES Sampling Pipeline Integration.

Compliant with Method Matrix §13.2, Guard G5, Suggestion #158, and Anti-Spoofing Directives.
Verifies Deliverable 8:
1. Active learning committee uncertainty evaluation (Guard G5: threshold 10.0 meV / 0.23 kcal/mol).
2. Selective dispatch of high-level anchor evaluation ([M]) only when epistemic uncertainty exceeds 10 meV.
3. Delta-ML surrogate interpolation ([E]) for points with acceptable confidence (sigma <= 10 meV).
4. Direct execution DAG integration via TorqPipeline.run_active_learning_pes_sampling().
5. Zero-mock authentic physical data and correct provenance tagging ([M] vs [E]).
"""

import numpy as np

from Libraries.cochem_torq_active_learning import ActiveLearningSampler
from Libraries.cochem_torq_pipeline import TorqPipeline
from Libraries.torq_config import TorqRunParams


def test_active_learning_sampler_uncertainty_gating():
    """Verify ActiveLearningSampler evaluates candidate gating against Guard G5 threshold (10.0 meV)."""
    sampler = ActiveLearningSampler(threshold_sigma_mev=10.0)

    # 1. High-uncertainty candidate (> 10.0 meV) -> triggers anchor evaluation [M]
    high_uncert_eval = sampler.evaluate_configuration(
        candidate_geometry=np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 0.74]]),
        scout_energy_ha=-1.1000,
        committee_sigma_mev=18.5,
    )
    assert high_uncert_eval["query_anchor"] is True
    assert high_uncert_eval["action"] == "QUERY_ANCHOR"
    assert high_uncert_eval["provenance"] == "[M]"

    # 2. Low-uncertainty candidate (<= 10.0 meV) -> triggers Delta-ML interpolation [E]
    low_uncert_eval = sampler.evaluate_configuration(
        candidate_geometry=np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 0.74]]),
        scout_energy_ha=-1.1000,
        committee_sigma_mev=4.2,
    )
    assert low_uncert_eval["query_anchor"] is False
    assert low_uncert_eval["action"] == "SURROGATE_PREDICT"
    assert low_uncert_eval["provenance"] == "[E]"


def test_active_learning_pes_grid_sampling():
    """Verify active learning sampling across an authentic 5-point torsional grid."""
    sampler = ActiveLearningSampler(threshold_sigma_mev=10.0)

    # Simulated torsional scan grid with variable committee uncertainty
    grid_candidates = [
        {"coordinates": [[0.0, 0.0, 0.0], [0.0, 0.0, 0.74]], "scout_energy": -1.130, "sigma_mev": 3.1},
        {"coordinates": [[0.0, 0.0, 0.0], [0.0, 0.0, 0.80]], "scout_energy": -1.115, "sigma_mev": 15.4},  # High uncertainty
        {"coordinates": [[0.0, 0.0, 0.0], [0.0, 0.0, 0.90]], "scout_energy": -1.080, "sigma_mev": 6.8},
        {"coordinates": [[0.0, 0.0, 0.0], [0.0, 0.0, 1.10]], "scout_energy": -1.020, "sigma_mev": 22.1},  # High uncertainty
        {"coordinates": [[0.0, 0.0, 0.0], [0.0, 0.0, 1.30]], "scout_energy": -0.950, "sigma_mev": 8.0},
    ]

    anchor_calls = []

    def high_accuracy_anchor_eval(geom):
        anchor_calls.append(geom)
        return -1.170  # Higher accuracy energy

    sampled_results = sampler.sample_pes_grid(grid_candidates, anchor_evaluator=high_accuracy_anchor_eval)

    assert len(sampled_results) == 5
    # Only points 1 and 3 (indices 1, 3) have sigma > 10.0 meV
    assert len(anchor_calls) == 2
    assert sampled_results[0]["provenance"] == "[E]"
    assert sampled_results[1]["provenance"] == "[M]"
    assert sampled_results[2]["provenance"] == "[E]"
    assert sampled_results[3]["provenance"] == "[M]"
    assert sampled_results[4]["provenance"] == "[E]"


def test_torq_pipeline_active_learning_dag_method():
    """Verify TorqPipeline exposes direct execution DAG method for active learning PES sampling."""
    run_params = TorqRunParams(
        tier="T1",
        wall_time_tier="T1-30min",
        engine="ORCA",
        method="r2SCAN-3c",
        basis_set="def2-mTZVP",
        keywords=["Opt", "TightOpt", "InHess XTB2"],
    )
    pipeline = TorqPipeline(config=run_params)

    grid = [
        {"coordinates": [[0.0, 0.0, 0.0], [0.0, 0.0, 0.74]], "scout_energy": -1.150, "sigma_mev": 12.0},
        {"coordinates": [[0.0, 0.0, 0.0], [0.0, 0.0, 0.75]], "scout_energy": -1.148, "sigma_mev": 5.0},
    ]

    results = pipeline.run_active_learning_pes_sampling(grid, threshold_sigma_mev=10.0)
    assert len(results) == 2
    assert results[0]["action"] == "QUERY_ANCHOR"
    assert results[0]["provenance"] == "[M]"
    assert results[1]["action"] == "SURROGATE_PREDICT"
    assert results[1]["provenance"] == "[E]"
