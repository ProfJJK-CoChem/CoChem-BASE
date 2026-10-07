"""CFOUR distribution and inventory boundary tests using text-only control data.

These tests create no substitute executable or physical result. Real licensed
runtime availability and scientific acceptance are verified in dedicated jobs.
"""

import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from scripts.provision_cfour import (
    DEFAULT_MANIFEST, cfour_version, github_environment, load_distribution_manifest,
    provision, require_platform, verify_inventory,
)
from scripts.provision_orca import extract_verified_archive, sha256_file
from cochem_base.core_engine.cfour_runtime import (
    APPROVED_ARCHIVE_SHA256, APPROVED_INVENTORY_SHA256, APPROVED_SOURCE_SHA256,
    _file, _packaged_inventory, verify_cfour_runtime,
)


def inventory_boundary(prefix: Path) -> tuple[dict, Path]:
    """Construct explicit metadata-control input with a single ordinary text file."""
    prefix.mkdir()
    distribution = load_distribution_manifest()
    text = prefix / "boundary.txt"
    text.write_text("Explicit text-only inventory control; not a CFOUR runtime.\n")
    inventory = {
        "schema_version": 1, "software": "CFOUR", "version": "2.1",
        "source_sha256": distribution["source_sha256"], "platform": "linux-x86_64",
        "minimum_glibc": "2.35", "mpi": False, "openmp": True,
        "fortran_integer_bits": 64, "blas": "ILP64 OpenBLAS pthread",
        "files": [{"path": "boundary.txt", "size": text.stat().st_size,
                   "sha256": sha256_file(text)}],
    }
    metadata = prefix / "manifest.json"
    metadata.write_text(json.dumps(inventory))
    distribution["runtime_manifest_sha256"] = sha256_file(metadata)
    return distribution, metadata


def rewrite_inventory(metadata: Path, distribution: dict, transform) -> None:
    inventory = json.loads(metadata.read_text())
    transform(inventory)
    metadata.write_text(json.dumps(inventory))
    distribution["runtime_manifest_sha256"] = sha256_file(metadata)


def test_approved_runtime_identity_and_threading_are_pinned():
    distribution = load_distribution_manifest()
    assert distribution["repository"] == "ProfJJK-CoChem/CoChem-CFOUR"
    assert distribution["release_tag"] == "cfour-2.1-runtime-20261007"
    assert distribution["sha256"] == "19ea269fcc7a13eb059bf43d34f0ef32e07cc9bb98f4ce84bdc4d0d7b20ccd63"
    assert distribution["runtime_manifest_sha256"] == "e9a59cfcaeed3df210d8276b7d3055aed68ba082b2dbc31e826b8eafebd4e286"
    assert distribution["mpi"] is False
    assert distribution["openmp"] is True
    assert distribution["sha256"] == APPROVED_ARCHIVE_SHA256
    assert distribution["runtime_manifest_sha256"] == APPROVED_INVENTORY_SHA256
    assert distribution["source_sha256"] == APPROVED_SOURCE_SHA256


def test_instructor_can_relocate_the_private_release_without_changing_the_build(tmp_path):
    distribution = load_distribution_manifest()
    distribution.update(repository="Course-Organization/Private-Engines", release_tag="course-cfour-2.1")
    path = tmp_path / "distribution.json"
    path.write_text(json.dumps(distribution))
    assert load_distribution_manifest(path) == distribution


@pytest.mark.parametrize("field,value", [
    ("repository", "https://github.com/course/engines"),
    ("release_tag", "cfour\nINJECTED=true"),
    ("archive_name", "../unreviewed.tar.xz"),
    ("sha256", "NOT-A-CHECKSUM"),
    ("runtime_manifest_sha256", "e9a5"),
    ("architecture", "aarch64"),
    ("minimum_glibc", "2.17"),
    ("mpi", True),
    ("openmp", False),
    ("fortran_integer_bits", 32),
])
def test_unsupported_or_unsafe_distribution_fields_are_rejected(tmp_path, field, value):
    distribution = load_distribution_manifest()
    distribution[field] = value
    path = tmp_path / "distribution.json"
    path.write_text(json.dumps(distribution))
    with pytest.raises(ValueError):
        load_distribution_manifest(path)


@pytest.mark.parametrize("system,machine,glibc", [
    ("Linux", "aarch64", "glibc 2.39"),
    ("Darwin", "x86_64", "2.39"),
    ("Windows", "AMD64", "2.39"),
    ("Linux", "x86_64", "glibc 2.34"),
    ("Linux", "x86_64", "musl 1.2.5"),
    ("Linux", "x86_64", ""),
])
def test_host_compatibility_is_explicit(system, machine, glibc):
    with pytest.raises(ValueError):
        require_platform(system, machine, glibc, load_distribution_manifest())


@pytest.mark.parametrize("glibc", ["glibc 2.35", "2.39", "glibc 2.40.1"])
def test_supported_glibc_versions(glibc):
    require_platform("Linux", "x86_64", glibc, load_distribution_manifest())


@pytest.mark.parametrize("output", [
    "Version 2.1", "CFOUR 2.1", "Other package Version 2.1",
    "CFOUR Coupled-Cluster techniques for Computational Chemistry\nVersion 2.10",
    "CFOUR Coupled-Cluster techniques for Computational Chemistry\nVersion 2.1.0",
    "CFOUR Coupled-Cluster techniques for Computational Chemistry\nVersion 2.1\n"
    "CFOUR Coupled-Cluster techniques for Computational Chemistry\nVersion 2.0",
])
def test_version_parser_rejects_unqualified_wrong_or_ambiguous_banners(output):
    with pytest.raises(ValueError, match="Expected native CFOUR version"):
        cfour_version(output, "2.1")


def test_native_version_parser_requires_the_cfour_qualified_banner():
    assert cfour_version("CFOUR Coupled-Cluster techniques for Computational Chemistry\n"
                         "Department and copyright metadata\nVersion 2.1\n", "2.1") == "2.1"


def test_embedded_inventory_is_hashed_before_its_json_is_read(tmp_path):
    distribution, metadata = inventory_boundary(tmp_path / "inventory")
    metadata.write_text("Explicit corrupted metadata control, not JSON.")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verify_inventory(metadata.parent, distribution)


def test_inventory_detects_changes_to_a_file_after_receipt(tmp_path):
    distribution, metadata = inventory_boundary(tmp_path / "inventory")
    original = verify_inventory(metadata.parent, distribution)
    assert len(original["files"]) == 1
    text = metadata.parent / "boundary.txt"
    text.write_bytes(text.read_bytes().replace(b"text-only", b"TEXT-ONLY"))
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verify_inventory(metadata.parent, distribution)


def test_inventory_rejects_missing_and_unrecorded_files(tmp_path):
    distribution, metadata = inventory_boundary(tmp_path / "inventory")
    extra = metadata.parent / "unrecorded.txt"
    extra.write_text("Unrecorded text-only control.")
    with pytest.raises(ValueError, match="unexpected=.*unrecorded.txt"):
        verify_inventory(metadata.parent, distribution)
    extra.unlink()
    (metadata.parent / "boundary.txt").unlink()
    with pytest.raises(ValueError, match="file mismatch"):
        verify_inventory(metadata.parent, distribution)


@pytest.mark.parametrize("name", ["../outside.txt", "/absolute.txt", "bin\\invalid", "bin//file", "bin/./file"])
def test_inventory_rejects_unsafe_or_ambiguous_paths(tmp_path, name):
    distribution, metadata = inventory_boundary(tmp_path / "inventory")
    rewrite_inventory(metadata, distribution, lambda inventory: inventory["files"][0].update(path=name))
    with pytest.raises(ValueError, match="inventory path"):
        verify_inventory(metadata.parent, distribution)


def test_inventory_rejects_duplicate_records_and_wrong_build_identity(tmp_path):
    distribution, metadata = inventory_boundary(tmp_path / "inventory")
    rewrite_inventory(metadata, distribution, lambda inventory: inventory["files"].append(inventory["files"][0]))
    with pytest.raises(ValueError, match="Duplicate"):
        verify_inventory(metadata.parent, distribution)
    rewrite_inventory(metadata, distribution, lambda inventory: inventory.update(mpi=True))
    with pytest.raises(ValueError, match="threading identity"):
        verify_inventory(metadata.parent, distribution)


@pytest.mark.parametrize("size,checksum", [(-1, "a" * 64), (True, "a" * 64), (1, None)])
def test_inventory_rejects_invalid_file_record_types(tmp_path, size, checksum):
    distribution, metadata = inventory_boundary(tmp_path / "inventory")
    if checksum is None:
        size = (metadata.parent / "boundary.txt").stat().st_size
    rewrite_inventory(metadata, distribution,
                      lambda inventory: inventory["files"][0].update(size=size, sha256=checksum))
    with pytest.raises(ValueError, match="Invalid CFOUR inventory"):
        verify_inventory(metadata.parent, distribution)


def test_archive_link_parents_are_rejected_before_extraction(tmp_path):
    archive = tmp_path / "explicit-adversarial-text-archive.tar.xz"
    with tarfile.open(archive, "w:xz") as bundle:
        alias = tarfile.TarInfo("cfour-2.1/bin")
        alias.type = tarfile.SYMTYPE
        alias.linkname = "basis"
        bundle.addfile(alias)
        text = tarfile.TarInfo("cfour-2.1/bin/not-an-engine.txt")
        content = b"Explicit text-only traversal control."
        text.size = len(content)
        bundle.addfile(text, io.BytesIO(content))
    destination = tmp_path / "extraction"
    with pytest.raises(ValueError, match="non-directory parent"):
        extract_verified_archive(archive, destination, sha256_file(archive))
    assert not destination.exists()


def test_existing_installation_is_preserved_without_opening_the_archive(tmp_path):
    archive = tmp_path / load_distribution_manifest()["archive_name"]
    destination = tmp_path / "existing"
    destination.mkdir()
    sentinel = destination / "original.txt"
    sentinel.write_text("Keep this existing user installation.")
    if sys.platform == "linux":
        with pytest.raises(ValueError, match="already exists"):
            provision(archive, destination)
    else:
        with pytest.raises(ValueError, match="requires Linux"):
            provision(archive, destination)
    assert sentinel.read_text() == "Keep this existing user installation."


def test_cli_rejects_corrupted_download_without_creating_installation(tmp_path):
    distribution = load_distribution_manifest()
    archive = tmp_path / distribution["archive_name"]
    archive.write_text("Explicit corrupt download control; never a native engine.")
    destination = tmp_path / "new-installation"
    result = subprocess.run([
        sys.executable, str(DEFAULT_MANIFEST.with_name("provision_cfour.py")),
        "--archive", str(archive), "--install-root", str(destination),
    ], capture_output=True, text=True, check=False)
    assert result.returncode == 1
    assert "CFOUR provisioning failed:" in result.stderr
    assert not destination.exists()


def environment_control() -> dict:
    return {"executable": "/approved/bin/xcfour", "cfour_home": "/approved",
            "cfour_bin": "/approved/bin", "genbas": "/approved/basis/GENBAS",
            "ecpdata": "/approved/basis/ECPDATA", "ld_library_path": "/approved/lib/runtime",
            "provenance": "/approved/provenance.json", "path_entries": ["/approved/bin"]}


def test_environment_exports_engine_specific_libraries_and_basis_without_global_ld_override(tmp_path):
    env_file, path_file = tmp_path / "environment", tmp_path / "path"
    github_environment(environment_control(), env_file, path_file)
    fields = dict(line.split("=", 1) for line in env_file.read_text().splitlines())
    assert fields["COCHEM_CFOUR_BIN"] == fields["COCHEM_XCFOUR_BIN"] == "/approved/bin/xcfour"
    assert fields["COCHEM_CFOUR_GENBAS"] == "/approved/basis/GENBAS"
    assert fields["COCHEM_CFOUR_MPI_AVAILABLE"] == "false"
    assert fields["COCHEM_CFOUR_OPENMP_AVAILABLE"] == "true"
    assert fields["COCHEM_CFOUR_LD_LIBRARY_PATH"] == "/approved/lib/runtime"
    assert "LD_LIBRARY_PATH" not in fields
    assert path_file.read_text() == "/approved/bin\n"


@pytest.mark.parametrize("field", ["executable", "genbas", "ecpdata", "ld_library_path"])
def test_actions_environment_rejects_multiline_paths_before_any_write(tmp_path, field):
    result = environment_control()
    result[field] += "\nINJECTED=yes"
    env_file, path_file = tmp_path / "environment", tmp_path / "path"
    with pytest.raises(ValueError, match="Multiline"):
        github_environment(result, env_file, path_file)
    assert not env_file.exists()
    assert not path_file.exists()


def test_native_file_identity_checks_a_genuine_interpreter_without_cfour_acceptance():
    # Native file metadata is tested on Python itself; this makes no CFOUR
    # readiness claim and creates no substitute engine binary.
    if sys.platform in ("linux", "darwin"):
        record = _file(Path(sys.executable), executable=True, native=True)
        assert record["sha256"] == sha256_file(Path(sys.executable).resolve())
    else:
        with pytest.raises(ValueError, match="must be native"):
            _file(Path(sys.executable), executable=True, native=True)


def test_text_is_rejected_as_a_native_companion_without_execution(tmp_path):
    control = tmp_path / "explicit-nonnative-text-control"
    control.write_text("Text-only negative file-type boundary; never a CFOUR companion.")
    control.chmod(0o755)
    with pytest.raises(ValueError, match="must be native"):
        _file(control, executable=True, native=True)


def test_installable_runtime_verifier_rejects_multiline_executable_paths():
    with pytest.raises(ValueError, match="single-line"):
        verify_cfour_runtime("/selected/runtime\nINJECTED=yes", environment={})


def test_installable_inventory_gate_rejects_corrupted_metadata_before_parsing(tmp_path):
    prefix = tmp_path / "explicit-corrupt-inventory-control"
    prefix.mkdir()
    (prefix / "manifest.json").write_text("Explicit malformed inventory boundary; not a CFOUR runtime.")
    with pytest.raises(ValueError, match="inventory checksum"):
        _packaged_inventory(prefix)


def test_unsealed_native_interpreter_is_not_misclassified_as_ready_cfour(tmp_path):
    # A real native executable alone does not establish the required CFOUR
    # basis and companion environment.
    with pytest.raises((ValueError, OSError)):
        verify_cfour_runtime(sys.executable, environment={"COCHEM_CFOUR_GENBAS": str(tmp_path / "absent-GENBAS")})


def test_inventory_regular_file_gate_rejects_metadata_symlinks(tmp_path):
    prefix = tmp_path / "inventory"
    distribution, metadata = inventory_boundary(prefix)
    target = tmp_path / "same-inventory.json"
    metadata.rename(target)
    metadata.symlink_to(target)
    with pytest.raises(ValueError, match="regular file"):
        verify_inventory(prefix, distribution)
