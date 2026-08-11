import pytest
from typing import Any
from unittest.mock import patch
from cochem_base.core.hardware import HardwareDiscovery
from cochem_base.core.dispatcher import TaskDispatcher


def test_hardware_discovery() -> None:
    profile = HardwareDiscovery.get_full_profile()
    assert "cpu_cores" in profile
    assert "ram_gb" in profile


def submit_task_with_preemption(dispatcher: TaskDispatcher, task_id: str, command: str, required_ram_gb: float) -> None:
    """Simulates a task submission with hardware preemption."""
    available_ram = HardwareDiscovery.get_system_ram_gb()
    if required_ram_gb > available_ram:
        raise MemoryError(f"Preemption: Task requires {required_ram_gb}GB, but only {available_ram}GB available.")
    dispatcher.submit_task(task_id, command)


@patch('cochem_base.core.hardware.HardwareDiscovery.get_system_ram_gb')
def test_hardware_preemption_rejection(mock_get_ram: Any) -> None:
    # Simulate a node with only 8GB of RAM
    mock_get_ram.return_value = 8.0

    dispatcher = TaskDispatcher()

    # Task requires 16GB, should be preempted
    with pytest.raises(MemoryError, match="Preemption: Task requires 16.0GB, but only 8.0GB available."):
        submit_task_with_preemption(dispatcher, "task_heavy_ccsd", "echo 'Running'", required_ram_gb=16.0)

    # Task requires 4GB, should succeed
    submit_task_with_preemption(dispatcher, "task_light_dft", "echo 'Running'", required_ram_gb=4.0)
    assert dispatcher.task_queue.qsize() == 1
