from pathlib import Path

from cochem.runners.cuda_budget import CudaExecutionBudget


def test_prepare_worker_environment_mps_pipe_isolation(tmp_path):
    import os
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    old_val = os.environ.get("COCH_SCRATCH")
    os.environ["COCH_SCRATCH"] = str(scratch)
    try:
        budget = CudaExecutionBudget(allow_cpu_fallback=True)
        env = budget.prepare_worker_environment(device_id=0, worker_id="worker_99")

        assert env["CUDA_VISIBLE_DEVICES"] == "0"
        assert env["PYTORCH_CUDA_ALLOC_CONF"] == "expandable_segments:True"
        assert "CUDA_MPS_PIPE_DIRECTORY" in env
        pipe_path = Path(env["CUDA_MPS_PIPE_DIRECTORY"])
        assert pipe_path.name == "pipe_worker_99"
        assert pipe_path.exists()
    finally:
        if old_val is None:
            os.environ.pop("COCH_SCRATCH", None)
        else:
            os.environ["COCH_SCRATCH"] = old_val

def test_prepare_worker_environment_cpu_fallback():
    budget = CudaExecutionBudget(allow_cpu_fallback=True)
    env = budget.prepare_worker_environment(device_id=None)
    assert env["CUDA_VISIBLE_DEVICES"] == ""

def test_consumer_gpu_context_limit():
    budget = CudaExecutionBudget(allow_cpu_fallback=True)
    dev_id = 0

    initial_count = budget._active_contexts

    # If consumer GPU, max 4 contexts allowed
    success_count = 0
    for _ in range(6):
        if budget.register_context(dev_id):
            success_count += 1

    if budget.is_consumer_gpu(dev_id):
        assert success_count <= 4
        assert budget._active_contexts <= 4

    # Release registered contexts
    for _ in range(success_count):
        budget.release_context(dev_id)

    assert budget._active_contexts == initial_count

def test_resolve_gpu_or_cpu_fallback():
    import os
    # In CI/test environment without dedicated hardware, verify clean CPU fallback
    old_val = os.environ.get("GITHUB_ACTIONS")
    os.environ["GITHUB_ACTIONS"] = "true"
    try:
        budget = CudaExecutionBudget(allow_cpu_fallback=True)
        selected = budget.resolve_gpu_or_cpu(required_mb=2048)
        assert selected is None
    finally:
        if old_val is None:
            os.environ.pop("GITHUB_ACTIONS", None)
        else:
            os.environ["GITHUB_ACTIONS"] = old_val
