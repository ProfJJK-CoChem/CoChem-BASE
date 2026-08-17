from core_engine.cochem_core_scheduler import CoreScheduler


def test_core_scheduler_lifecycle():
    scheduler = CoreScheduler()

    assert not scheduler.is_running
    scheduler.start_scheduling()
    assert scheduler.is_running

    task_id_1 = "test_task_101"
    task_data_1 = {"type": "dft", "n_atoms": 5}

    task_id_2 = "test_task_102"
    task_data_2 = {"type": "opt", "n_atoms": 10}

    # Add tasks
    scheduler.add_task(task_id_1, task_data_1)
    scheduler.add_task(task_id_2, task_data_2)

    assert len(scheduler.task_queue) == 2

    # Wait for the background thread to schedule the first task
    import time
    time.sleep(0.5)

    # After 0.5s, tasks should be picked up from the queue
    assert len(scheduler.task_queue) == 0

    status = scheduler.get_task_status(task_id_1)
    assert status['status'] == 'running'

    # Complete task
    scheduler.complete_task(task_id_1)
    status = scheduler.get_task_status(task_id_1)
    assert status['status'] == 'completed'

    scheduler.stop_scheduling()
    assert not scheduler.is_running
