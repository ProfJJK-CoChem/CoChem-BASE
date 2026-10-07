"""Real CPU network training and numerical differentiation, not quantum certification."""

import numpy as np
import pytest

from cochem_base.core_engine.cochem_core_auto_pes import (
    AutoPESOrchestrator,
    DeltaFittingConfig,
    DeltaPESModel,
    FittingBackend,
    NeuralCommitteeEstimator,
    generate_benchmark_intermolecular_pes_data,
)


def _configuration(**overrides):
    settings = dict(
        backend=FittingBackend.NEURAL_COMMITTEE,
        neural_hidden_layers=(8,),
        neural_committee_size=3,
        neural_max_iterations=120,
        neural_random_seed=17,
    )
    settings.update(overrides)
    return DeltaFittingConfig(**settings)


def test_networks_train_reproducibly_and_report_actual_member_spread():
    # An analytical numerical function verifies regression without a fictitious engine label.
    features = np.linspace(-1.0, 1.0, 40)[:, np.newaxis]
    targets = 0.1 + 0.01 * np.sin(features[:, 0])
    estimator = NeuralCommitteeEstimator(_configuration()).fit(features, targets)
    repeat = NeuralCommitteeEstimator(_configuration()).fit(features, targets)
    np.testing.assert_array_equal(estimator.weights, repeat.weights)
    evaluation = np.linspace(-0.98, 0.98, 31)[:, np.newaxis]
    exact = 0.1 + 0.01 * np.sin(evaluation[:, 0])
    mean, spread, members = estimator.predict_with_uncertainty(evaluation)
    assert np.sqrt(np.mean((mean - exact) ** 2)) < 5e-5
    np.testing.assert_allclose(mean, np.mean(members, axis=0))
    np.testing.assert_allclose(spread, np.std(members, axis=0, ddof=1))
    assert np.any(spread > 0.0)
    assert members.shape == (3, 31)
    np.testing.assert_array_equal(estimator.predict(evaluation, batch_size=5), mean)
    training_rows, validation_rows = set(estimator.training_indices), set(estimator.validation_indices)
    assert training_rows.isdisjoint(validation_rows)
    assert training_rows | validation_rows == set(range(len(features)))
    assert set(estimator.member_training_indices.ravel()) <= training_rows
    np.testing.assert_allclose(estimator.feature_mean, np.mean(features[estimator.training_indices], axis=0))
    assert all("optimizer_success" in entry for entry in estimator.training_history)


@pytest.mark.parametrize("energy_reference", ["absolute", "interaction_zero_asymptote"])
def test_backpropagation_and_feature_gradients_match_independent_finite_differences(energy_reference):
    values = np.linspace(-1.0, 1.0, 21)
    features = np.column_stack((values, values ** 2))
    targets = np.sin(values) * 0.01
    estimator = NeuralCommitteeEstimator(_configuration(neural_hidden_layers=(5, 4), energy_reference=energy_reference)).fit(features, targets)
    parameters = estimator.weights[0].copy()
    normalized = (features - estimator.feature_mean) / estimator.feature_scale
    normalized_targets = (targets - estimator.y_mean) / estimator.y_scale
    _, analytical_parameters = estimator._objective(parameters, normalized, normalized_targets)
    numerical_parameters = np.empty_like(parameters)
    step = 1e-6
    for index in range(len(parameters)):
        plus, minus = parameters.copy(), parameters.copy()
        plus[index] += step
        minus[index] -= step
        numerical_parameters[index] = (
            estimator._objective(plus, normalized, normalized_targets)[0]
            - estimator._objective(minus, normalized, normalized_targets)[0]
        ) / (2.0 * step)
    np.testing.assert_allclose(analytical_parameters, numerical_parameters, atol=1e-8, rtol=1e-5)
    point = np.array([0.13, 0.2])
    numerical_features = np.empty((3, 2))
    for axis in range(2):
        shift = np.zeros(2)
        shift[axis] = step
        numerical_features[:, axis] = (
            estimator.predict_members(point + shift) - estimator.predict_members(point - shift)
        ) / (2.0 * step)
    np.testing.assert_allclose(estimator.predict_member_gradients_wrt_features(point), numerical_features, atol=1e-9)
    if energy_reference == "interaction_zero_asymptote":
        np.testing.assert_allclose(estimator.predict_members(np.array([0.0, 0.0])), 0.0, atol=1e-14)
        restored = NeuralCommitteeEstimator.from_arrays(estimator.to_arrays("test_"), "test_")
        np.testing.assert_array_equal(restored.predict_members(point), estimator.predict_members(point))


def test_neural_campaign_forces_uncertainty_and_npz_round_trip(tmp_path):
    symbols, geometries, empirical, transformed = generate_benchmark_intermolecular_pes_data(50)
    orchestrator = AutoPESOrchestrator(symbols=symbols, low_method="ase_emt", high_method="numerical_affine_emt_target", fit_config=_configuration())
    model, summary = orchestrator.fit_delta_surface_from_data(
        train_geoms=geometries[:40], train_low_energies=empirical[:40], train_high_energies=transformed[:40],
        held_out_geoms=geometries[40:], held_out_low_energies=empirical[40:], held_out_high_energies=transformed[40:],
    )
    assert summary.backend == "neural_committee"
    assert isinstance(model.krr_estimator, NeuralCommitteeEstimator)
    assert isinstance(model.low_level_estimator, NeuralCommitteeEstimator)
    assert summary.model_parameters["estimator_type"] == "neural_committee"
    assert summary.n_base_dft_points == 40
    geometry = geometries[42]
    step = 1e-5
    numerical_forces = np.empty_like(geometry)
    for atom in range(len(symbols)):
        for axis in range(3):
            plus, minus = geometry.copy(), geometry.copy()
            plus[atom, axis] += step
            minus[atom, axis] -= step
            numerical_forces[atom, axis] = -(
                model.predict_total_energy(plus, allow_unvalidated_baseline=True)
                - model.predict_total_energy(minus, allow_unvalidated_baseline=True)
            ) / (2 * step)
    np.testing.assert_allclose(model.predict_forces(geometry), numerical_forces, atol=1e-7, rtol=1e-5)
    mean_force, spread_force, member_forces = model.predict_delta_forces_with_uncertainty(geometry)
    np.testing.assert_allclose(mean_force, member_forces.mean(axis=0))
    np.testing.assert_allclose(spread_force, member_forces.std(axis=0, ddof=1))
    np.testing.assert_allclose(mean_force.sum(axis=0), 0.0, atol=1e-12)
    path = model.save_npz(tmp_path / "neural-pes.npz")
    restored = DeltaPESModel.load_npz(path)
    np.testing.assert_array_equal(
        restored.predict_total_energy(geometries, allow_unvalidated_baseline=True),
        model.predict_total_energy(geometries, allow_unvalidated_baseline=True),
    )
    np.testing.assert_array_equal(restored.predict_forces(geometry), model.predict_forces(geometry))
    for expected, actual in zip(model.predict_delta_with_uncertainty(geometries), restored.predict_delta_with_uncertainty(geometries)):
        np.testing.assert_array_equal(actual, expected)
    assert restored.krr_estimator.training_history == model.krr_estimator.training_history
    with np.load(path, allow_pickle=False) as archive:
        corrupted = {key: archive[key].copy() for key in archive.files}
    corrupted["neural_delta_feature_scale"][0] = np.nan
    corrupt_path = tmp_path / "invalid-neural-pes.npz"
    np.savez_compressed(corrupt_path, **corrupted)
    with pytest.raises(ValueError, match="finite and valid"):
        DeltaPESModel.load_npz(corrupt_path)


def test_external_validation_labels_do_not_influence_neural_training_or_checkpoint_selection():
    symbols, geometries, empirical, transformed = generate_benchmark_intermolecular_pes_data(25)
    orchestrator = AutoPESOrchestrator(
        symbols=symbols, low_method="ase_emt", high_method="numerical_affine_emt_target", fit_config=_configuration(neural_committee_size=2, neural_max_iterations=40),
    )
    arguments = dict(
        train_geoms=geometries[:20], train_low_energies=empirical[:20], train_high_energies=transformed[:20],
        held_out_geoms=geometries[20:], held_out_low_energies=empirical[20:], held_out_high_energies=transformed[20:],
    )
    original, _ = orchestrator.fit_delta_surface_from_data(**arguments)
    arguments["held_out_low_energies"] = empirical[20:] + 3.0
    arguments["held_out_high_energies"] = transformed[20:] + 5.0
    changed, summary = orchestrator.fit_delta_surface_from_data(**arguments)
    for name in ("krr_estimator", "low_level_estimator"):
        np.testing.assert_array_equal(getattr(original, name).weights, getattr(changed, name).weights)
        assert getattr(original, name).training_history == getattr(changed, name).training_history
    assert not summary.metrics.spectroscopic_grade


@pytest.mark.parametrize("invalid", [np.nan, np.inf])
def test_neural_training_rejects_nonfinite_labels(invalid):
    with pytest.raises(ValueError, match="finite"):
        NeuralCommitteeEstimator(_configuration()).fit(np.arange(5.0)[:, np.newaxis], np.array([0.0, 1.0, invalid, 2.0, 3.0]))
