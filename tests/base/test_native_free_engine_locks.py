"""Native package integrity contracts; these checks do not claim Mac execution."""

import hashlib
import platform

import pytest

from scripts.install_native_free_engines import download_verified, inventory, load_lock, native_subdir, owned_path, retain_interrupted_prefix


@pytest.mark.parametrize("subdir", ["osx-64", "osx-arm64"])
def test_reviewed_native_locks_have_closed_dependencies_and_exact_science_versions(subdir):
    lock = load_lock(subdir)
    packages = {record["name"]: record for record in lock["packages"]}
    assert packages["xtb"]["version"] == "6.7.1"
    assert packages["crest"]["version"] == "3.0.2"
    for package in packages.values():
        for dependency in package["depends"]:
            name = dependency.split()[0]
            assert name.startswith("__") or name in packages, f"Unclosed package requirement: {dependency}"
    assert lock["provenance"]["native_execution_verified"] is False


def test_actual_host_architecture_cannot_be_substituted_with_a_requested_macos_name():
    if platform.system() == "Darwin":
        assert native_subdir() in {"osx-64", "osx-arm64"}
    else:
        with pytest.raises(RuntimeError, match="real macOS host"):
            native_subdir()


def test_download_checks_actual_bytes_before_an_archive_can_be_installed(tmp_path):
    original = tmp_path / "original-package.bin"
    original.write_bytes(b"Actual isolated package integrity boundary\n")
    digest = hashlib.sha256(original.read_bytes()).hexdigest()
    cached = tmp_path / "packages/accepted-package.bin"
    assert download_verified(original.as_uri(), digest, cached).read_bytes() == original.read_bytes()
    cached.write_bytes(b"Altered package contents\n")
    with pytest.raises(RuntimeError, match="published SHA-256"):
        download_verified(original.as_uri(), digest, cached)
    assert cached.read_bytes() == b"Altered package contents\n"


def test_actual_runtime_inventory_detects_byte_and_executable_mode_changes(tmp_path):
    binary = tmp_path / "bin/chemistry-engine"
    binary.parent.mkdir()
    binary.write_bytes(b"Preserved binary-package integrity data\n")
    binary.chmod(0o700)
    previous = inventory(tmp_path)
    binary.chmod(0o600)
    assert inventory(tmp_path) != previous
    binary.chmod(0o700)
    assert inventory(tmp_path) == previous
    binary.write_bytes(b"Changed accepted runtime data\n")
    assert inventory(tmp_path) != previous


def test_owned_native_package_path_rejects_redirect_before_writing(tmp_path):
    root = tmp_path / "engines"
    root.mkdir()
    outside = tmp_path / "student-inputs"
    outside.mkdir()
    (root / "packages").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="owned directory"):
        owned_path(root, "packages/new-package.conda")
    assert list(outside.iterdir()) == []


def test_retry_retains_actual_interrupted_files_and_never_replaces_an_accepted_runtime(tmp_path):
    prefix = tmp_path / "prefixes/osx-arm64-owned-attempt"
    prefix.mkdir(parents=True)
    diagnostic = prefix / "partial-download-data"
    diagnostic.write_bytes(b"Retained interrupted installation bytes\n")
    retained = retain_interrupted_prefix(tmp_path, prefix)
    assert retained is not None and not prefix.exists()
    assert (retained / diagnostic.name).read_bytes() == b"Retained interrupted installation bytes\n"
    assert retained.with_suffix(".json").is_file()
    prefix.mkdir()
    (prefix / "accepted-input").write_bytes(b"Do not alter accepted runtime\n")
    (tmp_path / "installation.json").write_text('{}\n', encoding="utf-8")
    with pytest.raises(RuntimeError, match="must be verified"):
        retain_interrupted_prefix(tmp_path, prefix)
    assert (prefix / "accepted-input").read_bytes() == b"Do not alter accepted runtime\n"
