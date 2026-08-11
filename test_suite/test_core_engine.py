import pytest
import asyncio
import numpy as np
from pathlib import Path
from core_engine.cochem_base_daemon import ZeroMQDaemon, BaseDaemon
from core_engine.cochem_base_hdf5 import HDF5OntologyEnforcer, CoChemHDF5Manager, BasinRecord


def test_zeromq_daemon_lifecycle() -> None:
    async def _test() -> None:
        daemon = BaseDaemon(pub_port=5577, sub_port=5578)
        await daemon.start()
        assert daemon._running is True

        await daemon.publish("test_topic", {"key": "val"})
        await daemon.stop()
        assert daemon._running is False

    asyncio.run(_test())


def test_hdf5_ontology_enforcer(tmp_path: Path) -> None:
    h5_file = tmp_path / "test_state.h5"
    enforcer = CoChemHDF5Manager(hdf5_path=h5_file)

    valid_record = {
        "molecule_name": "water",
        "xyz_coordinates": [[0.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
        "energy": -76.4,
        "symmetry_group": "C2v",
        "LAM_TRIGGER_REQUIRED": False
    }

    enforcer.write_record("basins/water", valid_record)
    assert h5_file.exists()

    invalid_record = {
        "xyz_coordinates": "invalid",
    }
    with pytest.raises(ValueError, match="HDF5 metadata schema validation failed"):
        enforcer.write_record("basins/invalid", invalid_record)
