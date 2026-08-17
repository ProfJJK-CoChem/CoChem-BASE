import asyncio
import sys

from core_engine.cochem_core_job_manager import JobManager


def test_job_manager_lifecycle():
    manager = JobManager()

    async def run_test():
        py_cmd = sys.executable
        job_config = {
            'command': [py_cmd, '-c', 'print("hello native execution")'],
            'product_class': 'Product_C_Differences',
            'n_atoms': 5
        }

        job_id = await manager.submit_job(job_config)
        assert job_id in manager.jobs

        await manager.start_job(job_id)
        await asyncio.sleep(1.0)

        status = manager.get_job_status(job_id)
        assert status is not None
        assert status['status'] == 'completed'
        assert status['return_code'] == 0

    asyncio.run(run_test())

def test_job_manager_timeout():
    manager = JobManager()

    async def run_test():
        py_cmd = sys.executable
        # Tier 1 is assigned for Product_C_Differences with n_atoms < 20 (10 seconds timeout)
        job_config = {
            'command': [py_cmd, '-c', 'import time; time.sleep(12)'],
            'product_class': 'Product_C_Differences',
            'n_atoms': 5
        }

        job_id = await manager.submit_job(job_config)

        await manager.start_job(job_id)
        # Wait slightly longer than the 10-second Tier 1 timeout + 2s termination grace period
        await asyncio.sleep(13.5)

        status = manager.get_job_status(job_id)
        assert status['status'] == 'completed'
        assert status['return_code'] != 0

    asyncio.run(run_test())
