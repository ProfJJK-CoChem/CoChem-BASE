from pathlib import Path

from cochem_base.core.dispatcher import SubprocessBroker as CoreSubprocessBroker
from core_engine.cochem_core_subprocess_broker import SubprocessBroker


def test_core_brokers_default_to_artifact_scratch(monkeypatch, tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(artifact_dir))

    engine_broker = SubprocessBroker()
    core_broker = CoreSubprocessBroker()

    assert engine_broker.cwd == artifact_dir / "Scratch"
    assert core_broker.working_dir == artifact_dir / "Scratch" / "subprocess"


def test_relative_broker_working_directory_uses_default_anchor(monkeypatch, tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(artifact_dir))

    broker = SubprocessBroker(cwd="job-a")

    assert broker.cwd == (artifact_dir / "Scratch" / "job-a").resolve()
