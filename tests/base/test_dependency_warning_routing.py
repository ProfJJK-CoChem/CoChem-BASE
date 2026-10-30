"""Actual Python warnings and filesystem IO; no replacement NVML devices."""
from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from cochem_base.core_engine.cochem_core_telemetry_logger import (
    DEFAULT_MAX_LOG_BYTES,
    DEFAULT_ROTATING_LOG_FILENAME,
    TelemetryLogger,
    _PYNVML_DEPRECATION_MESSAGE,
    _route_known_nvml_deprecation,
)


class OtherFutureWarning(FutureWarning):
    pass


def test_exact_notice_is_buffered_then_retained_without_console_output(tmp_path, capsys):
    target = tmp_path / "diagnostics"
    with warnings.catch_warnings(record=True) as shown:
        warnings.simplefilter("always")
        original = warnings.showwarning
        filters = list(warnings.filters)
        with _route_known_nvml_deprecation(target):
            warnings.warn(_PYNVML_DEPRECATION_MESSAGE, FutureWarning)
            assert not target.exists(), "Do not resolve/import diagnostic paths inside the warning callback"
        assert warnings.showwarning is original
        assert warnings.filters == filters
    assert shown == [] and capsys.readouterr().err == ""
    retained = (target / DEFAULT_ROTATING_LOG_FILENAME).read_text()
    assert "DEPENDENCY_NOTICE FutureWarning" in retained
    assert _PYNVML_DEPRECATION_MESSAGE in retained
    assert str(Path(__file__)) in retained


@pytest.mark.parametrize("message,category", [
    ("A different optional-library warning", FutureWarning),
    (_PYNVML_DEPRECATION_MESSAGE + " Additional detail.", FutureWarning),
    (_PYNVML_DEPRECATION_MESSAGE.upper(), FutureWarning),
    (_PYNVML_DEPRECATION_MESSAGE, UserWarning),
    (_PYNVML_DEPRECATION_MESSAGE, OtherFutureWarning),
    ("Scientific convergence requires attention", RuntimeWarning),
])
def test_other_warnings_retain_original_message_category_and_source(tmp_path, message, category):
    with warnings.catch_warnings(record=True) as shown:
        warnings.simplefilter("always")
        with _route_known_nvml_deprecation(tmp_path / "unused"):
            warnings.warn(message, category)
    assert len(shown) == 1
    assert str(shown[0].message) == message and shown[0].category is category
    assert shown[0].filename == __file__
    assert not (tmp_path / "unused").exists()


@pytest.mark.parametrize("message,category", [
    (_PYNVML_DEPRECATION_MESSAGE, FutureWarning),
    (_PYNVML_DEPRECATION_MESSAGE.upper(), FutureWarning),
    (_PYNVML_DEPRECATION_MESSAGE, OtherFutureWarning),
    ("Unrelated future behavior", FutureWarning),
    ("Scientific convergence requires attention", RuntimeWarning),
])
def test_warning_error_policy_still_raises_and_restores_context(tmp_path, message, category):
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        original = warnings.showwarning
        filters = list(warnings.filters)
        with pytest.raises(category) as failure:
            with _route_known_nvml_deprecation(tmp_path / "unused"):
                warnings.warn(message, category)
        assert str(failure.value) == message
        assert warnings.showwarning is original and warnings.filters == filters
    assert not (tmp_path / "unused").exists()


def test_caller_ignore_policy_for_exact_notice_is_not_overridden(tmp_path):
    with warnings.catch_warnings(record=True) as shown:
        warnings.simplefilter("ignore", FutureWarning)
        filters = list(warnings.filters)
        with _route_known_nvml_deprecation(tmp_path / "unused"):
            warnings.warn(_PYNVML_DEPRECATION_MESSAGE, FutureWarning)
        assert warnings.filters == filters
    assert shown == [] and not (tmp_path / "unused").exists()


def test_real_filesystem_failure_shows_original_notice_once_after_restoration(tmp_path):
    obstruction = tmp_path / "regular-file"
    obstruction.write_text("A file cannot contain a diagnostic directory")
    with warnings.catch_warnings(record=True) as shown:
        warnings.simplefilter("always")
        original = warnings.showwarning
        filters = list(warnings.filters)
        with _route_known_nvml_deprecation(obstruction / "logs"):
            warnings.warn(_PYNVML_DEPRECATION_MESSAGE, FutureWarning)
        assert warnings.showwarning is original and warnings.filters == filters
    assert len(shown) == 1
    assert str(shown[0].message) == _PYNVML_DEPRECATION_MESSAGE
    assert shown[0].category is FutureWarning and shown[0].filename == __file__
    assert obstruction.read_text() == "A file cannot contain a diagnostic directory"


def test_notice_is_retained_while_original_exception_propagates(tmp_path):
    failure = RuntimeError("The original operation failed")
    with warnings.catch_warnings(record=True) as shown:
        warnings.simplefilter("always")
        original = warnings.showwarning
        filters = list(warnings.filters)
        with pytest.raises(RuntimeError) as observed:
            with _route_known_nvml_deprecation(tmp_path):
                warnings.warn(_PYNVML_DEPRECATION_MESSAGE, FutureWarning)
                raise failure
        assert warnings.showwarning is original and warnings.filters == filters
    assert observed.value is failure and shown == []
    assert _PYNVML_DEPRECATION_MESSAGE in (tmp_path / DEFAULT_ROTATING_LOG_FILENAME).read_text()


def test_retention_keeps_existing_bounded_rotation_and_original_bytes(tmp_path):
    original = b"x" * DEFAULT_MAX_LOG_BYTES
    path = tmp_path / DEFAULT_ROTATING_LOG_FILENAME
    path.write_bytes(original)
    with warnings.catch_warnings(record=True) as shown:
        warnings.simplefilter("always")
        with _route_known_nvml_deprecation(tmp_path):
            warnings.warn(_PYNVML_DEPRECATION_MESSAGE, FutureWarning)
    assert shown == []
    assert path.with_name(path.name + ".1").read_bytes() == original
    assert _PYNVML_DEPRECATION_MESSAGE in path.read_text()
    assert path.stat().st_size < DEFAULT_MAX_LOG_BYTES


def test_dependency_notice_is_not_a_scientific_event_or_warning_counter(tmp_path):
    with TelemetryLogger(log_dir=tmp_path) as telemetry:
        with warnings.catch_warnings(record=True) as shown:
            warnings.simplefilter("always")
            with _route_known_nvml_deprecation(tmp_path):
                warnings.warn(_PYNVML_DEPRECATION_MESSAGE, FutureWarning)
        assert shown == []
        assert telemetry.warnings_count == telemetry.errors_count == 0
        assert telemetry.stream_path.read_text() == ""
        assert _PYNVML_DEPRECATION_MESSAGE in telemetry.rotating_log_path.read_text()
