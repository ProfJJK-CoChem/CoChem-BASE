"""Native filesystem-event acceptance for the notebook intake watcher."""
from pathlib import Path
import threading

from ase.build import molecule
from ase.io import write
from watchdog.observers import Observer

from cochem_base.intake.cochem_mint_ingestor import IngestionWatchdog


def test_native_observer_reports_created_xyz_files_only(tmp_path: Path) -> None:
    notifications = []
    received = threading.Event()

    def collect(message: str) -> None:
        notifications.append(message)
        received.set()

    observer = Observer()
    observer.schedule(IngestionWatchdog(collect), str(tmp_path), recursive=False)
    observer.start()
    try:
        (tmp_path / "directory.xyz").mkdir()
        (tmp_path / "readme.txt").write_text("non-geometry content", encoding="utf-8")
        write(tmp_path / "water.xyz", molecule("H2O"))
        assert received.wait(5), "The native filesystem observer did not deliver the created geometry"
    finally:
        observer.stop()
        observer.join(timeout=5)
    assert not observer.is_alive()
    assert notifications == ["Detected: water.xyz"]
