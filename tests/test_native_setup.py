import io
import tarfile
from pathlib import Path

from setup.calc_native import locate_orca


def test_orca_archive_without_executable_stops_after_one_extraction(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("ORCA_CMD", raising=False)
    monkeypatch.setattr("setup.calc_native.shutil.which", lambda _: None)
    archive_path = tmp_path / "orca-empty.tar.gz"
    payload = b"not an executable"
    info = tarfile.TarInfo("README.txt")
    info.size = len(payload)
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.addfile(info, io.BytesIO(payload))

    assert locate_orca(tmp_path) is None
    assert (tmp_path / "README.txt").is_file()
