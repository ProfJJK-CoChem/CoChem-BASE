import json
import os
import platform
import threading
import time

import h5py
import numpy as np

from cochem_base.cochem_h5_healer import (
    create_swmr_lock,
    detect_zombie_pids,
    get_lease_metadata_path,
    get_lock_file_path,
    init_swmr_database,
    remove_swmr_lock,
    swmr_locked_session,
)


def test_init_swmr_database(tmp_path):
    h5_file = tmp_path / 'test_swmr.h5'
    datasets = {
        'conformers': ((10, 3, 3), np.float64),
        'energies': ((10,), np.float64),
    }
    created = init_swmr_database(h5_file, datasets=datasets)
    assert created.exists()

    with h5py.File(h5_file, 'r') as fp:
        assert 'conformers' in fp
        assert 'energies' in fp
        assert fp['conformers'].fletcher32 is True
        assert fp['conformers'].chunks is not None
        assert fp['energies'].shape == (10,)

def test_swmr_lock_and_lease_lifecycle(tmp_path):
    h5_file = tmp_path / 'lease_test.h5'
    init_swmr_database(h5_file)

    lock_path = create_swmr_lock(h5_file)
    assert lock_path.exists()

    lease_path = get_lease_metadata_path(h5_file)
    assert lease_path.exists()

    with open(lease_path, 'r', encoding='utf-8') as f:
        meta = json.load(f)
    assert meta['pid'] == os.getpid()
    assert meta['hostname'] == platform.node()
    assert 'timestamp' in meta

    # Release lock
    removed = remove_swmr_lock(h5_file)
    assert removed is True
    assert not lock_path.exists()
    assert not lease_path.exists()

def test_zombie_pid_eviction_local_and_remote(tmp_path):
    h5_file = tmp_path / 'zombie_test.h5'
    init_swmr_database(h5_file)
    lock_file = get_lock_file_path(h5_file)
    lease_file = get_lease_metadata_path(h5_file)

    # Local host with dead PID (e.g. 999999999)
    dead_pid = 999999999
    with open(lock_file, 'w', encoding='utf-8') as f:
        json.dump({'pid': dead_pid, 'hostname': platform.node(), 'timestamp': time.time()}, f)
    with open(lease_file, 'w', encoding='utf-8') as f:
        json.dump({'pid': dead_pid, 'hostname': platform.node(), 'timestamp': time.time()}, f)

    zombies = detect_zombie_pids(h5_file)
    assert dead_pid in zombies

    # Remote host with expired lease (> 60s)
    remote_pid = 4321
    with open(lease_file, 'w', encoding='utf-8') as f:
        json.dump({
            'pid': remote_pid,
            'hostname': 'remote-cluster-node-99',
            'timestamp': time.time() - 75.0,  # 75s old -> expired
        }, f)

    zombies_remote_expired = detect_zombie_pids(h5_file)
    assert remote_pid in zombies_remote_expired

    # Remote host with fresh lease (< 60s) -> should NOT be evicted
    with open(lease_file, 'w', encoding='utf-8') as f:
        json.dump({
            'pid': remote_pid,
            'hostname': 'remote-cluster-node-99',
            'timestamp': time.time() - 5.0,  # 5s old -> active
        }, f)

    zombies_remote_fresh = detect_zombie_pids(h5_file)
    assert remote_pid not in zombies_remote_fresh

    # Clean up
    remove_swmr_lock(h5_file)

def test_swmr_locked_session_concurrency(tmp_path):
    h5_file = tmp_path / 'threaded_test.h5'
    init_swmr_database(h5_file, datasets={'counter': ((1,), np.int64)})

    def worker(val):
        with swmr_locked_session(h5_file, mode='a') as fp:
            fp['counter'][0] += val

    threads = []
    for _ in range(5):
        t = threading.Thread(target=worker, args=(1,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    with h5py.File(h5_file, 'r') as fp:
        assert fp['counter'][0] == 5
