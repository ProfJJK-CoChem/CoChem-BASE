"""Precise refusal of retired scientific object APIs; no producer or RPC."""

from __future__ import annotations

_CAPABILITIES = {
    "BaselinePhysicsEngine": "baseline/delta-model and dispersion",
    "DeltaMLEngine": "baseline/delta-model and dispersion",
    "EMTBaselineEngine": "baseline/delta-model and dispersion",
    "GFN2xTBEngine": "baseline/delta-model and dispersion",
    "LennardJonesBaselineEngine": "baseline/delta-model and dispersion",
    "PM6Engine": "baseline/delta-model and dispersion",
    "UnitHarmonizer": "baseline/delta-model and dispersion",
    "DispersionD3Layer": "baseline/delta-model and dispersion",
    "DispersionD3Config": "baseline/delta-model and dispersion",
    "compute_coordination_numbers": "baseline/delta-model and dispersion",
    "CalibrationSample": "independent conformal calibration",
    "ConformalPredictor": "independent conformal calibration",
    "ConformalPredictorConfig": "independent conformal calibration",
    "ConformalInterval": "independent conformal calibration",
    "ANI2xModel": "trained-model and force-matching",
    "ForceMatchingLoss": "trained-model and force-matching",
    "compute_angular_cosine_similarity": "trained-model and force-matching",
    "compute_conservative_forces": "trained-model and force-matching",
    "huber_force_loss": "trained-model and force-matching",
    "huber_scalar_loss": "trained-model and force-matching",
    "cosine_cutoff_envelope": "trained-model and force-matching",
    "quintic_c2_envelope": "trained-model and force-matching",
    "CommitteeEnsemble": "committee-model inference",
    "CommitteePrediction": "committee-model inference",
    "compute_committee_moments": "committee-model inference",
    "get_available_vram_mb": "committee-model inference",
}


def unavailable_attribute(module: str, name: str, known_names: tuple[str, ...]):
    """Known retired names explain the missing contract; typos stay AttributeError."""
    if name not in known_names:
        raise AttributeError(f"module {module!r} has no attribute {name!r}")
    capability = _CAPABILITIES[name]
    raise ImportError(
        f"{module}.{name} is unavailable: canonical TORQ has no verified managed "
        f"{capability} operation for this legacy Python-object API. "
        "Use the supported BASE calculation/model APIs where applicable; "
        "this name does not import a sibling checkout or substitute another model."
    )
