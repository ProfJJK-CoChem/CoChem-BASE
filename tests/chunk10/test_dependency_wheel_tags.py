from packaging.tags import sys_tags

from cochem_base.orchestrator.dependency_manager import (
    is_wheel_compatible,
    scan_for_local_wheel_fallback,
)


def test_is_wheel_compatible_universal():
    # py2.py3-none-any is universal across all Python interpreters and OS platforms
    universal_wheel = "test_pkg-1.0.0-py2.py3-none-any.whl"
    assert is_wheel_compatible(universal_wheel) is True

def test_is_wheel_compatible_mismatched_platform():
    # If host is Windows (or macOS), a Linux-only manylinux wheel with older CPython ABI must be rejected
    mismatched_wheel = "cochem_accel-2.0.0-cp38-cp38-manylinux_2_17_s390x.whl"
    assert is_wheel_compatible(mismatched_wheel) is False

    invalid_wheel = "not_a_valid_wheel_name.whl"
    assert is_wheel_compatible(invalid_wheel) is False

def test_is_wheel_compatible_host_native_tag():
    # Synthesize wheel name matching the host's primary native tag
    primary_tag = next(iter(sys_tags()))
    native_wheel = f"native_calc-1.5.0-{primary_tag.interpreter}-{primary_tag.abi}-{primary_tag.platform}.whl"
    assert is_wheel_compatible(native_wheel) is True

def test_scan_for_local_wheel_fallback_filters_incompatible(tmp_path):
    # Put incompatible wheel and universal wheel in directory
    incompatible = tmp_path / "mylib-1.0.0-cp37-cp37m-linux_armv7l.whl"
    incompatible.write_text("binary", encoding="utf-8")

    # Scanning for mylib should reject the incompatible wheel
    found = scan_for_local_wheel_fallback("mylib", search_dirs=[tmp_path])
    assert found is None

    # Now add compatible universal wheel
    compatible = tmp_path / "mylib-1.0.0-py3-none-any.whl"
    compatible.write_text("binary", encoding="utf-8")

    found_comp = scan_for_local_wheel_fallback("mylib", search_dirs=[tmp_path])
    assert found_comp is not None
    assert found_comp.resolve() == compatible.resolve()

def test_scan_for_local_wheel_fallback_env_artifacts(tmp_path):
    import os
    art_dir = tmp_path / "artifacts"
    art_dir.mkdir()
    wheel_dir = art_dir / "wheels"
    wheel_dir.mkdir()

    wheel_path = wheel_dir / "geomopt-0.5.0-py3-none-any.whl"
    wheel_path.write_text("binary", encoding="utf-8")

    old_val = os.environ.get("COCHEM_ARTIFACTS_DIR")
    os.environ["COCHEM_ARTIFACTS_DIR"] = str(art_dir)
    try:
        found = scan_for_local_wheel_fallback("geomopt")
        assert found is not None
        assert found.resolve() == wheel_path.resolve()
    finally:
        if old_val is None:
            os.environ.pop("COCHEM_ARTIFACTS_DIR", None)
        else:
            os.environ["COCHEM_ARTIFACTS_DIR"] = old_val
