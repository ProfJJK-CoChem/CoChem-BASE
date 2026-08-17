import asyncio
import os
from pathlib import Path

import pytest

from core_engine.cochem_base_daemon import BaseDaemon
from core_engine.cochem_base_hdf5 import CoChemHDF5Manager


def test_zeromq_daemon_lifecycle() -> None:
    async def _test() -> None:
        pub_port = int(os.getenv("COCHEM_PUB_PORT", "5577"))
        sub_port = int(os.getenv("COCHEM_SUB_PORT", "5578"))
        daemon = BaseDaemon(pub_port=pub_port, sub_port=sub_port)
        await daemon.start()
        assert daemon._running is True

        payload = {
            "node_id": "cochem_worker_1",
            "state": "IDLE",
            "uptime_seconds": 0
        }
        await daemon.publish("system/status", payload)
        await daemon.stop()
        assert daemon._running is False

    asyncio.run(_test())


def test_hdf5_ontology_enforcer(tmp_path: Path) -> None:
    h5_file = tmp_path / "test_state.h5"
    enforcer = CoChemHDF5Manager(hdf5_path=h5_file)

    valid_record = {
        "molecule_name": "water",
        "xyz_coordinates": [
            [0.000000000, 0.000000000, 0.000000000],
            [0.000000000, -0.757160000, 0.586260000],
            [0.000000000, 0.757160000, 0.586260000]
        ],
        "energy": -76.4,
        "symmetry_group": "C2v",
        "LAM_TRIGGER_REQUIRED": False
    }

    enforcer.write_record("basins/water", valid_record)
    assert h5_file.exists()

    invalid_record = {
        "xyz_coordinates": "invalid_structure_no_lists",
    }
    with pytest.raises(ValueError, match="HDF5 metadata schema validation failed"):
        enforcer.write_record("basins/invalid", invalid_record)
