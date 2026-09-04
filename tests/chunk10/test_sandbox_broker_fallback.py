import sys

from cochem_mobile.core.sandbox_broker import (
    ContainerEngine,
    QuarantineConfig,
    SandboxBroker,
    is_apptainer_active,
    is_docker_active,
    is_podman_active,
)


def test_liveness_probes_do_not_hang():
    # Verify liveness checks return quickly without hanging
    doc = is_docker_active()
    assert isinstance(doc, bool)

    pod = is_podman_active()
    assert isinstance(pod, bool)

    app = is_apptainer_active()
    assert isinstance(app, bool)

def test_detect_available_engines_includes_subprocess():
    engines = SandboxBroker.detect_available_engines(probe_liveness=True)
    assert ContainerEngine.SUBPROCESS in engines

def test_build_sanitized_environment():
    broker = SandboxBroker()
    cfg = QuarantineConfig(enforce_cpu_vectorization=True, max_cpus=4)
    env = broker.build_sanitized_environment(cfg)
    assert env["CUDA_VISIBLE_DEVICES"] == ""
    assert env["JAX_PLATFORMS"] == "cpu"
    assert env["OMP_NUM_THREADS"] == "4"

def test_automated_downgrade_cascade_to_subprocess():
    # Initialize broker preferring Docker. If Docker daemon is absent or inactive,
    # execute() must automatically cascade down to Subprocess and execute cleanly.
    broker = SandboxBroker(preferred_engine=ContainerEngine.DOCKER)
    cmd = [sys.executable, "-c", "print('SANDBOX_CASCADE_OK')"]

    res = broker.execute(cmd, force_engine=ContainerEngine.DOCKER)
    assert res.exit_code == 0
    assert "SANDBOX_CASCADE_OK" in res.stdout
    assert res.engine_used in (ContainerEngine.DOCKER, ContainerEngine.SUBPROCESS)
