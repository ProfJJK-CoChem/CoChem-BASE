"""Archive-boundary tests using explicit text-only, nonphysical test archives.

These tests never create a substitute ORCA executable or certify an installation.
Authentic ORCA/MPI execution is covered only by the licensed Actions acceptance.
"""

import io
import json
import shutil
import tarfile
from pathlib import Path

import pytest

from scripts.provision_orca import (
    DEFAULT_MANIFEST,
    INSTALLATION_RESERVE_BYTES,
    archive_space_preflight,
    exact_version,
    extract_verified_archive,
    github_environment,
    installation_space_requirement,
    native_executable,
    require_platform,
    sha256_file,
)


def text_archive(path: Path, entries: list[tuple[str, str, str]]) -> Path:
    with tarfile.open(path, "w:xz") as archive:
        for name, kind, value in entries:
            entry = tarfile.TarInfo(name)
            if kind == "text":
                content = value.encode()
                entry.size = len(content)
                archive.addfile(entry, io.BytesIO(content))
            else:
                entry.type = {"symlink": tarfile.SYMTYPE, "hardlink": tarfile.LNKTYPE,
                              "directory": tarfile.DIRTYPE, "fifo": tarfile.FIFOTYPE}[kind]
                entry.linkname = value
                archive.addfile(entry)
    return path


def test_reviewed_distribution_is_pinned():
    manifest = json.loads(DEFAULT_MANIFEST.read_text())
    assert manifest["repository"] == "ProfJJK-CoChem/CoChem-ORCA"
    assert manifest["release_tag"] == "orca-6.1.1"
    assert manifest["archive_name"] == "orca_6_1_1_linux_x86-64_shared_openmpi418.tar.xz"
    assert manifest["sha256"] == "a0bc1d6d2c3c00620367bbc5dbf2b3a7018abc92d1ff65f06cec46f75350b9be"
    assert manifest["orca_version"] == "6.1.1"
    assert manifest["openmpi_version"] == "4.1.8"


def test_disk_preflight_accounts_for_actual_expansion_and_job_reserve():
    # The selected 471 MB compressed release expands to about 16.24 GiB.
    expanded = 17_442_002_115
    required = expanded + INSTALLATION_RESERVE_BYTES
    with pytest.raises(ValueError, match="Insufficient installation disk space"):
        installation_space_requirement(expanded, required - 1)
    result = installation_space_requirement(expanded, required)
    assert result == {"uncompressed_archive_bytes": expanded,
                      "reserve_bytes": 4 * 1024**3,
                      "required_free_bytes": required, "available_free_bytes": required}


@pytest.mark.parametrize("expanded,free", [(-1, 100), (100, -1)])
def test_disk_preflight_rejects_invalid_byte_counts(expanded, free):
    with pytest.raises(ValueError, match="nonnegative"):
        installation_space_requirement(expanded, free)


def test_archive_preflight_reads_expanded_bytes_and_existing_ancestor(tmp_path):
    archive = text_archive(tmp_path / "metadata.tar.xz", [
        ("distribution", "directory", ""),
        ("distribution/repeated.txt", "text", "A" * 8192),
        ("distribution/unicode.txt", "text", "Å\n"),
        ("distribution/alias", "symlink", "repeated.txt"),
        ("distribution/hard-alias", "hardlink", "distribution/repeated.txt"),
    ])
    # Count UTF-8 file bytes, not compressed bytes, link names or tar padding.
    expected_bytes = 8195
    assert archive.stat().st_size < expected_bytes
    destination = tmp_path / "absent" / "nested" / "installation"
    digest = sha256_file(archive)
    if shutil.disk_usage(tmp_path).free < expected_bytes + INSTALLATION_RESERVE_BYTES:
        # The metadata boundary remains testable on a small local filesystem;
        # it must report the genuine archive size before refusing installation.
        with pytest.raises(ValueError, match="archive expands to 8,195 bytes"):
            archive_space_preflight(archive, destination, digest)
    else:
        result = archive_space_preflight(archive, destination, digest)
        assert result["uncompressed_archive_bytes"] == expected_bytes
        assert result["available_free_bytes"] >= result["required_free_bytes"]
    assert not (tmp_path / "absent").exists()


def test_archive_preflight_verifies_checksum_before_parsing(tmp_path):
    archive = tmp_path / "corrupted.tar.xz"
    archive.write_text("Explicit malformed archive boundary input, not a scientific fixture.")
    destination = tmp_path / "absent" / "installation"
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        archive_space_preflight(archive, destination, "0" * 64)
    assert not destination.parent.exists()


def test_integrity_is_checked_before_tar_parsing_or_extraction(tmp_path):
    archive = tmp_path / "not-an-archive.tar.xz"
    archive.write_text("Explicit corrupted archive test input, not a scientific fixture.")
    destination = tmp_path / "install"
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        extract_verified_archive(archive, destination, "0" * 64)
    assert not destination.exists()


def test_valid_text_archive_preserves_contained_relative_links(tmp_path):
    archive = text_archive(tmp_path / "text.tar.xz", [
        ("distribution/data/readme.txt", "text", "Text-only archive boundary test."),
        ("distribution/links/readme.txt", "symlink", "../data/readme.txt"),
        ("distribution/copy.txt", "hardlink", "distribution/data/readme.txt"),
    ])
    destination = tmp_path / "install"
    digest = sha256_file(archive)
    assert extract_verified_archive(archive, destination, digest) == digest
    assert (destination / "distribution/links/readme.txt").is_symlink()
    assert (destination / "distribution/copy.txt").read_text() == "Text-only archive boundary test."


def test_source_timestamps_preserve_generated_file_order_without_following_links(tmp_path):
    archive = tmp_path / "source.tar.xz"
    with tarfile.open(archive, "w:xz") as bundle:
        directory = tarfile.TarInfo("source")
        directory.type = tarfile.DIRTYPE
        directory.mtime = 50
        bundle.addfile(directory)
        # The generated file is archived before its older input. Extraction
        # order must not cause make to regenerate it using absent Autotools.
        for name, timestamp in [("configure", 200), ("configure.ac", 100)]:
            entry = tarfile.TarInfo(f"source/{name}")
            content = b"Text-only timestamp preservation test.\n"
            entry.size = len(content)
            entry.mtime = timestamp
            bundle.addfile(entry, io.BytesIO(content))
        for name, kind, target in [("alias", tarfile.SYMTYPE, "configure"),
                                   ("hard-alias", tarfile.LNKTYPE, "source/configure")]:
            entry = tarfile.TarInfo(f"source/{name}")
            entry.type, entry.linkname, entry.mtime = kind, target, 300
            bundle.addfile(entry)
    destination = tmp_path / "extracted"
    extract_verified_archive(archive, destination, sha256_file(archive))
    source = destination / "source"
    assert source.stat().st_mtime == 50
    assert (source / "configure").stat().st_mtime == 200
    assert (source / "configure.ac").stat().st_mtime == 100
    assert (source / "hard-alias").stat().st_mtime == 200
    assert (source / "alias").is_symlink()


@pytest.mark.parametrize("entries", [
    [("../escaped.txt", "text", "rejected")],
    [("/absolute.txt", "text", "rejected")],
    [("directory\\escaped.txt", "text", "rejected")],
    [("link", "symlink", "../escaped.txt")],
    [("link", "symlink", "/tmp/escaped.txt")],
    [("link", "hardlink", "../escaped.txt")],
    [("fifo", "fifo", "")],
    [("duplicate", "text", "first"), ("duplicate", "text", "second")],
    [("parent", "symlink", "data"), ("parent/file", "text", "rejected")],
    [("parent", "text", "file"), ("parent/file", "text", "rejected")],
    [("hard", "hardlink", "missing")],
])
def test_unsafe_archive_members_are_rejected_before_writing(tmp_path, entries):
    archive = text_archive(tmp_path / "adversarial.tar.xz", entries)
    destination = tmp_path / "install"
    with pytest.raises(ValueError):
        extract_verified_archive(archive, destination, sha256_file(archive))
    assert not destination.exists()
    assert not (tmp_path / "escaped.txt").exists()


@pytest.mark.parametrize("entries", [
    [("link", "symlink", "missing")],
    [("link", "symlink", "cycle"), ("cycle", "symlink", "link")],
])
def test_broken_or_cyclic_archive_links_are_not_accepted(tmp_path, entries):
    archive = text_archive(tmp_path / "links.tar.xz", entries)
    with pytest.raises(ValueError, match="broken or cyclic"):
        extract_verified_archive(archive, tmp_path / "install", sha256_file(archive))


def test_extraction_does_not_overwrite_an_existing_installation(tmp_path):
    archive = text_archive(tmp_path / "text.tar.xz", [("existing", "text", "replacement")])
    destination = tmp_path / "install"
    destination.mkdir()
    original = destination / "existing"
    original.write_text("original")
    with pytest.raises(ValueError, match="must be empty"):
        extract_verified_archive(archive, destination, sha256_file(archive))
    assert original.read_text() == "original"


@pytest.mark.parametrize("system,machine", [("Darwin", "arm64"), ("Linux", "aarch64"),
                                            ("Windows", "AMD64")])
def test_linux_distribution_is_not_installed_on_an_incompatible_host(system, machine):
    with pytest.raises(ValueError, match="corresponding local/HPC distribution"):
        require_platform(system, machine, json.loads(DEFAULT_MANIFEST.read_text()))


def test_text_is_never_accepted_as_a_native_engine(tmp_path):
    file = tmp_path / "explicit-text-fixture"
    file.write_text("Text-only boundary test: this is not an ORCA binary.")
    file.chmod(0o755)
    with pytest.raises(ValueError, match="native Linux x86-64 ELF"):
        native_executable(file)


@pytest.mark.parametrize("engine,text,expected", [
    ("orca", "Program Version 6.1.0", "6.1.1"),
    ("orca", "Program Version 6.1.10", "6.1.1"),
    ("orca", "Program Version 6.1.1\nProgram Version 6.0.0", "6.1.1"),
    ("openmpi", "mpirun (Open MPI) 4.1.6", "4.1.8"),
    ("openmpi", "Open MPI v5.0.7", "4.1.8"),
    ("orca", "Missing shared library", "6.1.1"),
])
def test_wrong_or_ambiguous_version_banners_are_rejected(engine, text, expected):
    with pytest.raises(ValueError, match="Expected"):
        exact_version(text, engine, expected)


def test_actions_environment_rejects_newline_injection(tmp_path):
    env_path, path_path = tmp_path / "env", tmp_path / "path"
    result = {"executable": "/example/orca\nINJECTED=yes", "mpirun": "/example/mpirun",
              "mpi_prefix": "/example", "ld_library_path": "/example/lib",
              "provenance": "/example/evidence.json", "path_entries": ["/example"]}
    with pytest.raises(ValueError, match="Multiline"):
        github_environment(result, env_path, path_path)
    assert not env_path.exists()
    assert not path_path.exists()


def test_actions_export_keeps_other_engine_libraries_and_mpi_unchanged(tmp_path):
    """Configuration-only test; these paths do not represent installed engines."""
    env_path, path_path = tmp_path / "env", tmp_path / "path"
    env_path.write_text("LD_LIBRARY_PATH=/site/qe/lib\nMPI_HOME=/site/mpi\n")
    path_path.write_text("/site/mpi/bin\n")
    result = {"executable": "/configuration-example/orca", "mpirun": "/configuration-example/mpi/bin/mpirun",
              "mpi_prefix": "/configuration-example/mpi", "ld_library_path": "/configuration-example/mpi/lib",
              "provenance": "/configuration-example/evidence.json",
              "path_entries": ["/configuration-example", "/configuration-example/mpi/bin"]}
    github_environment(result, env_path, path_path)
    lines = env_path.read_text().splitlines()
    assert [line for line in lines if line.startswith("LD_LIBRARY_PATH=")] == ["LD_LIBRARY_PATH=/site/qe/lib"]
    assert [line for line in lines if line.startswith("MPI_HOME=")] == ["MPI_HOME=/site/mpi"]
    assert "COCHEM_ORCA_LD_LIBRARY_PATH=/configuration-example/mpi/lib" in lines
    assert "COCHEM_ORCA_MPIRUN_BIN=/configuration-example/mpi/bin/mpirun" in lines
    assert "COCHEM_MPIEXEC_BIN=/configuration-example/mpi/bin/mpiexec" in lines
    assert path_path.read_text() == "/site/mpi/bin\n/configuration-example\n"
    assert "/configuration-example/mpi/bin\n" not in path_path.read_text()
