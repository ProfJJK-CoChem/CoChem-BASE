"""Pure boundary checks; these tests do not claim installed MPI/ORCA acceptance."""

from pathlib import Path

import pytest

from scripts import install_openmpi


@pytest.mark.parametrize("output", [
    "mpirun (Open MPI) 4.1.8\n",
    "mpiexec (Open MPI) 4.1.8\n",
    "Open MPI v4.1.8\n",
])
def test_exact_launcher_and_info_version(output: str) -> None:
    assert install_openmpi.exact_openmpi_version(output) == "4.1.8"


@pytest.mark.parametrize("output", [
    "mpirun (Open MPI) 4.1.80", "mpirun (Open MPI) 4.1.8rc1",
    "mpirun (Open MPI) 5.0.0", "MPICH Version: 4.1.8", "4.1.8",
    "mpirun (Open MPI) 4.1.8\nOpen MPI: 4.1.7",
])
def test_unexpected_or_ambiguous_version_is_rejected(output: str) -> None:
    with pytest.raises(ValueError, match="Expected Open MPI"):
        install_openmpi.exact_openmpi_version(output)


def test_source_checkout_cannot_hold_installation_or_evidence() -> None:
    with pytest.raises(ValueError, match="outside the source checkout"):
        install_openmpi.external_path(install_openmpi.REPOSITORY_ROOT / "runtime")


def test_existing_corrupt_source_is_rejected_without_download(tmp_path: Path) -> None:
    archive = tmp_path / "openmpi-4.1.8.tar.bz2"
    archive.write_bytes(b"incomplete cached source download")
    with pytest.raises(ValueError, match="differs from the pinned archive"):
        install_openmpi.download_source(tmp_path)
    assert archive.read_bytes() == b"incomplete cached source download"


def test_source_cache_cannot_redirect_through_symlink(tmp_path: Path) -> None:
    other = tmp_path / "other-source"
    other.write_bytes(b"invalid source archive")
    (tmp_path / "openmpi-4.1.8.tar.bz2").symlink_to(other)
    with pytest.raises(ValueError, match="differs from the pinned archive"):
        install_openmpi.download_source(tmp_path)


def test_installed_link_cannot_escape_recorded_prefix(tmp_path: Path) -> None:
    prefix = tmp_path / "mpi"
    prefix.mkdir()
    outside = tmp_path / "other-runtime"
    outside.write_bytes(b"outside installation")
    (prefix / "library").symlink_to(outside)
    with pytest.raises(ValueError, match="escapes its prefix"):
        install_openmpi.file_inventory(prefix)


def test_installed_regular_file_inventory_tracks_content(tmp_path: Path) -> None:
    library = tmp_path / "library"
    library.write_bytes(b"first inventory content")
    first = install_openmpi.file_inventory(tmp_path)
    library.write_bytes(b"changed inventory content")
    second = install_openmpi.file_inventory(tmp_path)
    assert first["library"]["sha256"] != second["library"]["sha256"]
    assert second["library"]["bytes"] == len(b"changed inventory content")


@pytest.mark.parametrize("value", ["0", "-1", "33"])
def test_build_parallelism_is_bounded(value: str) -> None:
    import argparse
    with pytest.raises(argparse.ArgumentTypeError, match="between 1 and 32"):
        install_openmpi.bounded_jobs(value)
