"""CoChem-TORQ: Test Full GOAT + CREST Conformer Union Pipeline & Deduplication.

Compliant with Method Matrix v4 §8A, §9B.1-§9B.3, and Anti-Spoofing Directives.
Verifies Deliverable 10:
1. Conformer exploration integration through standardized ConformerGenerator interface.
2. Union deduplication via Rotational Constant Clustering (Delta B / B < 0.005, 0.5%).
3. Heavy-Atom RMSD filtering (Kabsch superposition with threshold < 0.15 A).
4. Full stage conformer pool processing without shortcuts or synthetic fallbacks.
"""

import numpy as np
import pytest
from cochem_base.interfaces.conformer import ConformerGenerator
from cochem_base.schemas import ConformerEnsemblePayload
from Libraries.cochem_torq_pipeline import deduplicate_conformer_union
from src.cochem_torq.conformer.orchestrator import (
    ConformerOrchestrator,
    deduplicate_union_ensemble,
    kabsch_rmsd,
)


def test_conformer_orchestrator_implements_interface():
    """Verify ConformerOrchestrator inherits from ConformerGenerator ABC."""
    assert issubclass(ConformerOrchestrator, ConformerGenerator)
    orchestrator = ConformerOrchestrator()
    assert hasattr(orchestrator, "generate_conformers")


def test_two_stage_union_deduplication_rotational_and_rmsd():
    """Verify union deduplication merges duplicates based on Delta B / B < 0.005 and RMSD < 0.15 A."""
    # Authentic ethanol conformers:
    # Conf 1: Anti conformer (trans, Cs symmetry)
    symbols = ["C", "C", "O", "H", "H", "H", "H", "H", "H"]
    anti_coords = [
        [1.226, -0.245, 0.000],
        [0.000, 0.589, 0.000],
        [-1.173, -0.222, 0.000],
        [-1.936, 0.366, 0.000],
        [0.038, 1.237, 0.887],
        [0.038, 1.237, -0.887],
        [2.138, 0.360, 0.000],
        [1.233, -0.883, 0.887],
        [1.233, -0.883, -0.887],
    ]
    # Gauche conformer (C1 symmetry, distinct dihedral)
    gauche_coords = [
        [1.218, -0.270, 0.000],
        [0.000, 0.575, 0.000],
        [-1.144, -0.254, 0.000],
        [-1.156, -0.814, 0.784],
        [0.040, 1.220, 0.885],
        [0.040, 1.220, -0.885],
        [2.126, 0.342, 0.000],
        [1.230, -0.905, 0.886],
        [1.230, -0.905, -0.886],
    ]
    # Duplicate Anti conformer with minute coordinate shift (< 0.05 A, RMSD < 0.15 A)
    anti_duplicate_coords = [
        [1.227, -0.244, 0.001],
        [0.001, 0.590, -0.001],
        [-1.172, -0.221, 0.001],
        [-1.935, 0.367, 0.000],
        [0.039, 1.238, 0.888],
        [0.037, 1.236, -0.886],
        [2.139, 0.361, 0.001],
        [1.234, -0.882, 0.888],
        [1.232, -0.884, -0.886],
    ]

    conf_anti = {
        "symbols": symbols,
        "coordinates": anti_coords,
        "energy_hartree": -154.9812,
        "rotational_constants_mhz": (34870.0, 9325.0, 8140.0),
        "origin": "GOAT",
    }
    conf_gauche = {
        "symbols": symbols,
        "coordinates": gauche_coords,
        "energy_hartree": -154.9805,
        "rotational_constants_mhz": (30450.0, 9110.0, 8420.0),
        "origin": "CREST",
    }
    conf_anti_duplicate = {
        "symbols": symbols,
        "coordinates": anti_duplicate_coords,
        "energy_hartree": -154.9811,
        "rotational_constants_mhz": (34875.0, 9323.0, 8142.0),
        "origin": "CREST",
    }

    pool = [conf_anti, conf_gauche, conf_anti_duplicate]

    # Deduplication with delta_b_rel_threshold=0.005 and rmsd_threshold=0.15
    deduped = deduplicate_union_ensemble(
        pool,
        delta_b_rel_threshold=0.005,
        rmsd_threshold=0.15,
    )

    # Must retain exactly 2 unique conformers (Anti and Gauche), merging the duplicate Anti
    assert len(deduped) == 2

    # Also test via pipeline deduplicate_conformer_union wrapper
    deduped_pipeline = deduplicate_conformer_union(
        pool,
        delta_b_rel_threshold=0.005,
        rmsd_threshold=0.15,
    )
    assert len(deduped_pipeline) == 2


def test_conformer_orchestrator_generates_ensemble_payload(tmp_path):
    """Verify ConformerOrchestrator generates a validated ConformerEnsemblePayload contract."""
    symbols = ["C", "C", "O", "H", "H", "H", "H", "H", "H"]
    anti_coords = [
        [1.226, -0.245, 0.000],
        [0.000, 0.589, 0.000],
        [-1.173, -0.222, 0.000],
        [-1.936, 0.366, 0.000],
        [0.038, 1.237, 0.887],
        [0.038, 1.237, -0.887],
        [2.138, 0.360, 0.000],
        [1.233, -0.883, 0.887],
        [1.233, -0.883, -0.887],
    ]

    orchestrator = ConformerOrchestrator()
    ensemble = orchestrator.generate_conformers(
        symbols=symbols,
        coordinates=anti_coords,
        ensemble_id="ethanol_test_ensemble",
    )

    assert isinstance(ensemble, ConformerEnsemblePayload)
    assert ensemble.ensemble_id == "ethanol_test_ensemble"
    assert ensemble.origin_engine == "UNION"
    assert ensemble.provenance_tag == "[M]"
    assert len(ensemble.conformers) >= 1
