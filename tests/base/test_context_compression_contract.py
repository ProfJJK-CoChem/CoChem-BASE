"""Tensor API contracts are independent of explicitly requested trajectory compression."""

import json

import h5py
import numpy as np
import pytest

from cochem_base.cochem_core.ai.context_compression import (
    ContextCompressor,
    TensorSummaryModel,
    compress_tensors_for_llm,
    compress_trajectory_for_llm,
)


@pytest.mark.parametrize("rows", [600, 5000])
def test_two_column_matrix_honors_exact_element_threshold_and_model_contract(rows):
    # Arithmetic-series data checks API behavior, not a measured physical trajectory.
    matrix = np.arange(rows * 2, dtype=float).reshape(rows, 2)
    assert compress_tensors_for_llm(matrix, threshold=matrix.size + 1) == matrix.tolist()
    expected = {"Min": 0.0, "Max": float(matrix.size - 1),
                "Mean": (matrix.size - 1) / 2, "Variance": (matrix.size**2 - 1) / 12}
    assert compress_tensors_for_llm(matrix, threshold=matrix.size) == pytest.approx(expected)
    model = compress_tensors_for_llm(matrix, threshold=matrix.size, return_models=True)
    assert isinstance(model, TensorSummaryModel)
    assert model.to_dict() == pytest.approx(expected)


def test_generic_nested_lists_and_trajectory_key_do_not_infer_semantics():
    matrix = np.arange(1200, dtype=float).reshape(600, 2)
    payload = {"trajectory": matrix, "arbitrary_pairs": matrix.tolist()}
    assert compress_tensors_for_llm(payload, threshold=10000) == {
        "trajectory": matrix.tolist(), "arbitrary_pairs": matrix.tolist(),
    }
    assert ContextCompressor(tensor_threshold=1200).compress_payload(matrix)["Mean"] == 599.5


def test_nonfinite_two_column_tensor_retains_finite_statistics_and_json_sanitization():
    matrix = np.full((600, 2), 4.0)
    matrix[0] = [np.nan, np.inf]
    matrix[1, 0] = -np.inf
    assert compress_tensors_for_llm(matrix, threshold=1200) == {
        "Min": 4.0, "Max": 4.0, "Mean": 4.0, "Variance": 0.0,
    }
    document = json.loads(ContextCompressor(tensor_threshold=1201).to_json(matrix))
    assert document[:2] == [[None, None], [None, 4.0]]
    assert len(document) == 600


@pytest.mark.parametrize("invalid", [np.nan, np.inf, -np.inf])
def test_all_nonfinite_two_column_tensor_preserves_unavailable_statistics(invalid):
    matrix = np.full((600, 2), invalid)
    unavailable = {"Min": None, "Max": None, "Mean": None, "Variance": None}
    assert compress_tensors_for_llm(matrix, threshold=1200) == unavailable
    model = compress_tensors_for_llm(matrix, threshold=1200, return_models=True)
    assert isinstance(model, TensorSummaryModel)
    assert model.to_dict() == unavailable
    assert json.loads(model.model_dump_json()) == unavailable
    assert json.loads(ContextCompressor(tensor_threshold=1200).to_json(matrix)) == unavailable


def test_missing_observations_are_distinct_from_finite_zero_values():
    empty = np.empty((0, 2))
    assert compress_tensors_for_llm(empty) == []
    assert compress_tensors_for_llm(empty, threshold=0) == {
        "Min": None, "Max": None, "Mean": None, "Variance": None,
    }
    assert compress_tensors_for_llm(np.zeros((600, 2)), threshold=1200) == {
        "Min": 0.0, "Max": 0.0, "Mean": 0.0, "Variance": 0.0,
    }


def test_hdf5_two_column_dataset_uses_tensor_threshold_and_summary_model(tmp_path):
    matrix = np.full((600, 2), 7.0)
    matrix[0, 0] = np.nan
    with h5py.File(tmp_path / "tensor.h5", "w") as archive:
        dataset = archive.create_dataset("arbitrary_pairs", data=matrix)
        retained = compress_tensors_for_llm(dataset, threshold=1201)
        np.testing.assert_equal(retained, matrix)
        summary = compress_tensors_for_llm(dataset, threshold=1200, return_models=True)
        assert isinstance(summary, TensorSummaryModel)
        assert summary.to_dict() == {"Min": 7.0, "Max": 7.0, "Mean": 7.0, "Variance": 0.0}
        unavailable = archive.create_dataset("missing_values", data=np.full((600, 2), np.nan))
        assert compress_tensors_for_llm(unavailable, threshold=1200, return_models=True).to_dict() == {
            "Min": None, "Max": None, "Mean": None, "Variance": None,
        }


def test_explicit_trajectory_rejects_nonfinite_observations():
    observations = np.column_stack((np.arange(600), np.ones(600)))
    observations[0, 1] = np.nan
    with pytest.raises(ValueError, match="finite"):
        compress_trajectory_for_llm(observations)
    with pytest.raises(ValueError, match="finite"):
        ContextCompressor(tensor_threshold=100000).compress_trajectory(observations)


@pytest.mark.parametrize("values", [[], [np.nan], [np.inf, -np.inf], [np.nan, np.inf, -np.inf]])
def test_core_summary_and_telemetry_keep_missing_observations_unknown(values):
    from cochem_base.core_engine.cochem_core_context_compressor import (
        ContextCompressor as CoreContextCompressor,
        compress_array_to_summary,
        compress_tensors_for_llm as compress_core_tensors,
        intercept_and_compress,
    )

    model = compress_array_to_summary(values)
    summary = model.to_dict()
    assert {key: summary[key] for key in ("Min", "Max", "Mean", "Variance", "Last_Value")} == {
        "Min": None, "Max": None, "Mean": None, "Variance": None, "Last_Value": None,
    }
    assert summary["Count"] == len(values)
    assert summary["Shape"] == [len(values)]
    assert json.loads(model.model_dump_json())["Last_Value"] is None
    assert all(value is None for value in model.to_telemetry_dict().values())
    assert all(value is None for value in CoreContextCompressor().compress_to_dict(values).values())
    assert compress_core_tensors(np.asarray(values), threshold=0) == {
        "Min": None, "Max": None, "Mean": None, "Variance": None,
    }
    if values:
        assert all(value is None for value in intercept_and_compress(values, threshold=0).values())


def test_core_summary_never_substitutes_zero_or_maximum_for_missing_final_value():
    from cochem_base.core_engine.cochem_core_context_compressor import compress_array_to_summary

    model = compress_array_to_summary([0.0, 4.0, np.nan])
    assert model.to_dict() == {"Min": 0.0, "Max": 4.0, "Mean": 2.0, "Variance": 4.0,
                               "Last_Value": None, "Count": 3, "Shape": [3], "Dtype": "float64"}
    assert model.to_telemetry_dict() == {"Array_Min": 0.0, "Array_Max": 4.0,
                                        "Array_Mean": 2.0, "Array_Variance": 4.0, "Last_Value": None}
    finite_zero = compress_array_to_summary([0.0, 0.0])
    assert all(value == 0.0 for value in finite_zero.to_telemetry_dict().values())


def test_core_hdf5_missing_tensor_serializes_as_null_without_losing_shape(tmp_path):
    from cochem_base.core_engine.cochem_core_context_compressor import (
        compress_tensors_for_llm as compress_core_tensors,
        to_rfc8259_json,
    )

    with h5py.File(tmp_path / "missing-core.h5", "w") as archive:
        dataset = archive.create_dataset("unavailable", data=np.full((600, 2), np.nan))
        model = compress_core_tensors(dataset, threshold=1200, return_models=True)
        document = json.loads(to_rfc8259_json(model))
        assert document["Min"] is None and document["Variance"] is None
        assert document["Last_Value"] is None
        assert document["Shape"] == [600, 2] and document["Count"] == 1200
