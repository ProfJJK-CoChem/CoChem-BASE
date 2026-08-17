from core_engine.cochem_core_workspace_manager import WorkspaceManager


def test_workspace_scaffolding_and_cleanup():
    """Validates real filesystem scaffolding without mocks."""
    manager = WorkspaceManager()

    # 1. Test core directory creation
    success = manager.scaffold_core_directories()
    assert success is True

    # Verify directories exist
    base = manager.base_path
    for d in manager.CORE_DIRECTORIES:
        assert (base / d).exists()
        assert (base / d).is_dir()

    # 2. Test job provisioning
    job_id = "TEST_ORCA_RUN_999"
    job_path = manager.provision_job_workspace(job_id)
    assert job_path.exists()
    assert job_path.parent.name == "Scratch"

    # 3. Test zombie sweeping
    swept = manager.sweep_zombie_directories()
    # It should sweep at least 1 (our test job)
    assert swept >= 1
    assert not job_path.exists()
