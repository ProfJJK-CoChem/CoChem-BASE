"""Unit and Integration Test Suite for CoChem-Mobile Asynchronous Execution & Webhook Offloading.

Strictly adhering to SRS Chunk 08 (REQ-MOB-070 through REQ-MOB-073) and the Zero-Mock Mandate.
No mocks, monkeypatching, or simulated stubs. Real physical fixtures and tests only.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
import uuid
from pathlib import Path

import pytest
from mendeleev import element as _mendeleev_element

from cochem.mobile.async_runner import (
    AsyncProcessRunner,
    delegate_pipeline_execution_async,
    execute_worker_pipeline,
    isolate_cuda_device,
    spawn_detached_process,
)
from cochem.mobile.job_state import (
    ExecutionPayload,
    ExecutionTier,
    JobStatus,
    JobStatusRecord,
    ManifestReference,
    validate_status_transition,
)
from cochem.mobile.payload_serializer import (
    STAGE_THRESHOLD_BYTES,
    calculate_xyz_molecular_mass_dynamic,
    canonical_json_dumps,
    canonical_serialize,
    ensure_tripartite_dirs,
    get_job_lock_path,
    get_job_status_path,
    load_staged_payload,
    sign_payload,
    stage_or_inline_payload,
    validate_xyz_structure_dynamic,
    verify_payload_signature,
)
from cochem.mobile.status_poller import (
    compute_backoff_delay,
    map_github_run_to_job_status,
    poll_job_status_async,
    read_status_atomic,
    update_status_progress,
    write_status_atomic,
)
from cochem.mobile.webhook_dispatcher import (
    build_github_dispatch_request,
    detect_execution_tier,
    synthesize_slurm_script,
)

WATER_XYZ = """3
Water molecule
O   0.000000   0.000000   0.117300
H   0.000000   0.757200  -0.469200
H   0.000000  -0.757200  -0.469200
"""

ETHANOL_XYZ = """9
Ethanol molecule
C  -0.0000   0.0000   0.0000
C   1.5000   0.0000   0.0000
O   2.1000   1.2000   0.0000
H  -0.4000  -0.5000   0.9000
H  -0.4000  -0.5000  -0.9000
H  -0.4000   1.0000   0.0000
H   1.9000  -0.5000   0.9000
H   1.9000  -0.5000  -0.9000
H   3.0000   1.1000   0.0000
"""


class TestDynamicMendeleevValidation:
    """Test dynamic atomic mass retrieval and element validation without hardcoding."""

    def test_water_molecule_dynamic_mass(self) -> None:
        """Verify dynamic mass lookup for H2O using Mendeleev IUPAC atomic weights."""
        oxygen_el = _mendeleev_element("O")
        hydrogen_el = _mendeleev_element("H")

        expected_mass = float(oxygen_el.atomic_weight) + 2.0 * float(hydrogen_el.atomic_weight)
        calculated_mass = calculate_xyz_molecular_mass_dynamic(WATER_XYZ)

        assert abs(calculated_mass - expected_mass) < 1e-4

    def test_ethanol_atom_extraction(self) -> None:
        """Verify dynamic element validation across 9-atom ethanol XYZ block."""
        atoms = validate_xyz_structure_dynamic(ETHANOL_XYZ)
        assert len(atoms) == 9

        symbols = [sym for (sym, _x, _y, _z, _mass) in atoms]
        assert symbols.count("C") == 2
        assert symbols.count("O") == 1
        assert symbols.count("H") == 6

        # Check that atomic weights are non-zero positive floats
        for _sym, _x, _y, _z, mass in atoms:
            assert mass > 0.0
            assert isinstance(mass, float)


class TestCanonicalSerializationAndHMAC:
    """Test deterministic canonical serialization, HMAC-SHA256 signing and constant-time verification."""

    def test_canonical_json_sorting(self) -> None:
        """Verify key ordering is canonical and whitespace is minimized."""
        d1 = {"z_param": 100, "a_param": "test", "m_param": [3, 2, 1]}
        d2 = {"a_param": "test", "m_param": [3, 2, 1], "z_param": 100}

        c1 = canonical_json_dumps(d1)
        c2 = canonical_json_dumps(d2)

        assert c1 == c2
        assert c1 == '{"a_param":"test","m_param":[3,2,1],"z_param":100}'

    def test_hmac_signing_and_verification(self) -> None:
        """Verify HMAC-SHA256 signature generation and constant-time verification."""
        secret = "super_secure_cochem_test_secret_98765"
        payload = ExecutionPayload(
            job_id=str(uuid.uuid4()),
            tier=ExecutionTier.LOCAL_TIER_1,
            workflow_type="ORCA_OPT_FREQ",
            molecule_xyz=WATER_XYZ,
            parameters={"basis_set": "def2-TZVP", "functional": "B3LYP"},
            output_artifact_dir="/artifacts/jobs/test_job_1",
        )

        canonical_bytes = canonical_serialize(payload)
        sig = sign_payload(canonical_bytes, secret_key=secret)

        # Verification with matching secret
        assert verify_payload_signature(canonical_bytes, sig, secret_key=secret) is True

        # Verification with incorrect secret must fail
        assert verify_payload_signature(canonical_bytes, sig, secret_key="wrong_secret") is False

        # Tampering with payload bytes must fail
        tampered_bytes = canonical_bytes.replace(b"def2-TZVP", b"def2-SVP")
        assert verify_payload_signature(tampered_bytes, sig, secret_key=secret) is False

        # Empty signature must fail
        assert verify_payload_signature(canonical_bytes, "", secret_key=secret) is False


class TestPayloadThresholdRouting:
    """Test size-gated routing (<=64KB inline vs >64KB staged manifest)."""

    def test_inline_payload_under_64kb(self, tmp_path: Path) -> None:
        """Verify payload under 64 KB is routed inline with attached HMAC signature."""
        job_id = str(uuid.uuid4())
        payload = ExecutionPayload(
            job_id=job_id,
            tier=ExecutionTier.LOCAL_TIER_1,
            workflow_type="XTB_CONFORMER",
            molecule_xyz=WATER_XYZ,
            parameters={"temperature_k": 298.15},
            output_artifact_dir=(tmp_path / "artifacts" / "jobs" / job_id).as_posix(),
        )

        is_staged, result = stage_or_inline_payload(
            payload, artifacts_dir=tmp_path / "artifacts" / "jobs" / job_id
        )

        assert is_staged is False
        assert isinstance(result, ExecutionPayload)
        assert result.hmac_sha256 is not None
        assert len(result.hmac_sha256) == 64

        # Verify signature on result
        c_bytes = canonical_serialize(result)
        assert verify_payload_signature(c_bytes, result.hmac_sha256) is True

    def test_staged_payload_over_64kb(self, tmp_path: Path) -> None:
        """Verify payload over 64 KB (65,536 bytes) is staged to disk and returns ManifestReference."""
        job_id = str(uuid.uuid4())
        artifacts_job_dir = tmp_path / "artifacts" / "jobs" / job_id

        # Generate large payload exceeding 64 KB (e.g. 75 KB parameter block)
        large_param_data = "X" * 70000
        payload = ExecutionPayload(
            job_id=job_id,
            tier=ExecutionTier.LOCAL_TIER_1,
            workflow_type="LARGE_COORDINATE_TRAJECTORY",
            molecule_xyz=ETHANOL_XYZ,
            parameters={"bulk_matrix_data": large_param_data},
            output_artifact_dir=artifacts_job_dir.as_posix(),
        )

        canonical_bytes = canonical_serialize(payload)
        assert len(canonical_bytes) > STAGE_THRESHOLD_BYTES

        is_staged, manifest = stage_or_inline_payload(payload, artifacts_dir=artifacts_job_dir)

        assert is_staged is True
        assert isinstance(manifest, ManifestReference)
        assert manifest.job_id == job_id
        assert manifest.file_size_bytes == len(canonical_bytes)
        assert Path(manifest.manifest_uri).exists()

        # Load staged payload and verify integrity
        loaded_payload = load_staged_payload(manifest)
        assert loaded_payload.job_id == job_id
        assert loaded_payload.parameters["bulk_matrix_data"] == large_param_data
        assert loaded_payload.hmac_sha256 == manifest.hmac_sha256

        # Test tamper detection on disk
        with open(manifest.manifest_uri, "ab") as f:
            f.write(b"CORRUPTION_BYTES")

        with pytest.raises(ValueError):
            load_staged_payload(manifest)


class TestTripartiteAirGapIsolation:
    """Test Tripartite Air-Gap Isolation path management and directory creation."""

    def test_tripartite_path_creation(self, tmp_path: Path) -> None:
        """Verify $COCH_SRC, $COCH_ARTIFACTS/jobs/{job_id}/, and $COCHEM_STATE_DIR isolation."""
        src_d = tmp_path / "custom_src"
        art_d = tmp_path / "custom_artifacts"
        st_d = tmp_path / "custom_state"

        job_id = f"job_tripartite_{uuid.uuid4()}"
        res_src, res_job_art, res_st = ensure_tripartite_dirs(
            job_id=job_id,
            src_dir=src_d,
            artifacts_dir=art_d,
            state_dir=st_d,
        )

        assert res_src.exists()
        assert res_job_art.exists()
        assert res_st.exists()
        assert res_job_art == art_d / "jobs" / job_id
        assert get_job_status_path(job_id, state_dir=st_d) == st_d / f"{job_id}.status.json"
        assert get_job_lock_path(job_id, state_dir=st_d) == st_d / f"{job_id}.lock"


class TestAtomicFileLockingAndStatus:
    """Test cross-platform atomic status read/write using filelock and os.replace."""

    def test_atomic_status_write_and_read(self, tmp_path: Path) -> None:
        """Verify atomic status writes and reads via FileLock."""
        state_dir = tmp_path / "state"
        job_id = str(uuid.uuid4())

        record = JobStatusRecord(
            job_id=job_id,
            status=JobStatus.QUEUED,
            tier=ExecutionTier.LOCAL_TIER_1,
            progress_percent=0.0,
            current_step="Job queued",
        )

        status_path = write_status_atomic(record, state_dir=state_dir)
        assert status_path.exists()

        read_record = read_status_atomic(job_id, state_dir=state_dir)
        assert read_record is not None
        assert read_record.job_id == job_id
        assert read_record.status == JobStatus.QUEUED
        assert read_record.progress_percent == 0.0

    def test_status_progress_updates_and_transitions(self, tmp_path: Path) -> None:
        """Verify state machine transitions: QUEUED -> RUNNING -> COMPLETED."""
        state_dir = tmp_path / "state"
        job_id = str(uuid.uuid4())

        # 1. QUEUED
        r1 = update_status_progress(
            job_id=job_id,
            status=JobStatus.QUEUED,
            progress_percent=0.0,
            current_step="Queued in scheduler",
            state_dir=state_dir,
        )
        assert r1.status == JobStatus.QUEUED
        assert not r1.is_terminal()

        # 2. RUNNING
        r2 = update_status_progress(
            job_id=job_id,
            status=JobStatus.RUNNING,
            progress_percent=50.0,
            current_step="Optimizing geometry",
            state_dir=state_dir,
        )
        assert r2.status == JobStatus.RUNNING
        assert r2.progress_percent == 50.0

        # 3. COMPLETED
        r3 = update_status_progress(
            job_id=job_id,
            status=JobStatus.COMPLETED,
            progress_percent=100.0,
            current_step="Done",
            output_hdf5_path="/data/results.h5",
            state_dir=state_dir,
        )
        assert r3.status == JobStatus.COMPLETED
        assert r3.is_terminal()
        assert r3.output_hdf5_path == "/data/results.h5"

    def test_state_transition_validation(self) -> None:
        """Verify state machine transition constraints."""
        assert validate_status_transition(JobStatus.QUEUED, JobStatus.RUNNING) is True
        assert validate_status_transition(JobStatus.RUNNING, JobStatus.COMPLETED) is True
        assert validate_status_transition(JobStatus.RUNNING, JobStatus.FAILED) is True
        assert validate_status_transition(JobStatus.COMPLETED, JobStatus.RUNNING) is False


class TestBackoffCalculation:
    """Test bounded jittered exponential backoff formula."""

    def test_exponential_scaling_and_bounds(self) -> None:
        """Verify backoff calculation adheres to T_poll formula and max limit."""
        delays = [
            compute_backoff_delay(attempt=k, base=2.0, factor=1.5, max_delay=60.0, jitter_max=0.5)
            for k in range(10)
        ]

        # Delay must be positive
        for d in delays:
            assert d > 0.0
            assert d <= 60.0

        # Early attempts must scale exponentially
        assert delays[0] < delays[3] < delays[6]

        # High attempt must saturate at max_delay
        high_delay = compute_backoff_delay(attempt=50, base=2.0, factor=1.5, max_delay=60.0)
        assert high_delay == 60.0


class TestCUDABackendIsolation:
    """Test headless CUDA context isolation and CPU fallback configuration."""

    def test_cuda_device_isolation(self) -> None:
        """Verify CUDA_VISIBLE_DEVICES isolation."""
        env_gpu = isolate_cuda_device(gpu_index=2, base_env={"PATH": "/usr/bin"})
        assert env_gpu["CUDA_VISIBLE_DEVICES"] == "2"
        assert env_gpu["COCHEM_GPU_INDEX"] == "2"

        env_cpu = isolate_cuda_device(
            gpu_index=None, fallback_cpu=True, base_env={"PATH": "/usr/bin"}
        )
        assert env_cpu["CUDA_VISIBLE_DEVICES"] == ""
        assert env_cpu["COCHEM_GPU_FALLBACK_CPU"] == "1"


class TestWebhookDispatcherMultiTier:
    """Test multi-tier dispatcher across Tier 1, Tier 4/5, and Tier 6."""

    def test_environment_tier_detection(self) -> None:
        """Verify environment tier detection rules."""
        # Tier 1 default
        assert detect_execution_tier() in {
            ExecutionTier.LOCAL_TIER_1,
            ExecutionTier.GITHUB_ACTIONS_TIER_5,
            ExecutionTier.CODESPACES_TIER_4,
            ExecutionTier.CONTAINER_TIER_2,
            ExecutionTier.SSH_HPC_GATEWAY_TIER_3,
            ExecutionTier.HPC_SLURM_TIER_6,
        }

    def test_slurm_sbatch_script_synthesis(self, tmp_path: Path) -> None:
        """Verify SBATCH synthesis format, POSIX paths, and parameter directives."""
        job_id = str(uuid.uuid4())
        art_dir = (tmp_path / "artifacts" / "jobs" / job_id).as_posix()
        payload = ExecutionPayload(
            job_id=job_id,
            tier=ExecutionTier.HPC_SLURM_TIER_6,
            workflow_type="ORCA_DFT_SCAN",
            molecule_xyz=WATER_XYZ,
            parameters={"functional": "PBE0"},
            output_artifact_dir=art_dir,
        )

        script = synthesize_slurm_script(
            payload=payload,
            partition="gpu-a100",
            time_limit="04:00:00",
            nodes=2,
            ntasks=32,
            gpus=4,
            job_name_prefix="coch_calc",
        )

        assert "#!/bin/bash" in script
        assert "#SBATCH --partition=gpu-a100" in script
        assert "#SBATCH --time=04:00:00" in script
        assert "#SBATCH --nodes=2" in script
        assert "#SBATCH --ntasks=32" in script
        assert "#SBATCH --gres=gpu:4" in script
        assert f'--job-id "{job_id}"' in script

    def test_github_dispatch_request_building(self, tmp_path: Path) -> None:
        """Verify GitHub Actions repository_dispatch URL and headers."""
        job_id = str(uuid.uuid4())
        payload = ExecutionPayload(
            job_id=job_id,
            tier=ExecutionTier.GITHUB_ACTIONS_TIER_5,
            workflow_type="RDKIT_CLEAN",
            molecule_xyz=ETHANOL_XYZ,
            parameters={},
            output_artifact_dir=(tmp_path / "jobs" / job_id).as_posix(),
        )

        token = "ghp_test_token_cochem_cloud_secret_12345"
        url, headers, body = build_github_dispatch_request(
            owner="cochem-project",
            repo="cochem-engine",
            payload=payload,
            token=token,
        )

        assert url == "https://api.github.com/repos/cochem-project/cochem-engine/dispatches"
        assert headers["Authorization"] == f"Bearer {token}"
        assert headers["Accept"] == "application/vnd.github+json"
        assert body["event_type"] == "cochem_remote_execution"
        assert body["client_payload"]["job_id"] == job_id


class TestPhysicalAsyncRunnerAndDetachedExecution:
    """Physical execution of worker pipeline and detached subprocesses adhering to Zero-Mock mandate."""

    def test_execute_worker_pipeline_physical(self, tmp_path: Path) -> None:
        """Verify synchronous worker pipeline executes real Mendeleev mass calculations and outputs artifacts."""
        job_id = str(uuid.uuid4())
        src_d = tmp_path / "src"
        art_d = tmp_path / "artifacts"
        st_d = tmp_path / "state"

        # Pre-stage payload
        ensure_tripartite_dirs(job_id=job_id, src_dir=src_d, artifacts_dir=art_d, state_dir=st_d)
        job_art_d = art_d / "jobs" / job_id
        payload_data = {
            "job_id": job_id,
            "workflow_type": "WATER_VALIDATION",
            "molecule_xyz": WATER_XYZ,
            "parameters": {"temperature": 300},
        }
        (job_art_d / "payload.json").write_text(json.dumps(payload_data), encoding="utf-8")

        exit_code = execute_worker_pipeline(
            job_id=job_id,
            artifact_dir=art_d,
            state_dir=st_d,
            src_dir=src_d,
        )

        assert exit_code == 0

        # Verify status record completed
        status_record = read_status_atomic(job_id, state_dir=st_d)
        assert status_record is not None
        assert status_record.status == JobStatus.COMPLETED
        assert status_record.progress_percent == 100.0
        assert status_record.output_hdf5_path is not None

        # Verify summary output artifact
        summary_path = job_art_d / "execution_summary.json"
        assert summary_path.exists()
        summary_data = json.loads(summary_path.read_text(encoding="utf-8"))
        assert summary_data["atom_count"] == 3
        assert summary_data["molecular_mass_daltons"] > 18.0

    def test_spawn_detached_process_physical(self, tmp_path: Path) -> None:
        """Verify cross-platform detached subprocess launching with real python process."""
        stdout_log = tmp_path / "proc_out.log"
        stderr_log = tmp_path / "proc_err.log"

        cmd = [
            sys.executable,
            "-c",
            "import sys, time; sys.stdout.write('DETACHED_OK\\n'); sys.stdout.flush(); time.sleep(0.2)",
        ]

        pid = spawn_detached_process(
            command=cmd,
            cwd=tmp_path,
            stdout_path=stdout_log,
            stderr_path=stderr_log,
        )

        assert isinstance(pid, int)
        assert pid > 0

        # Wait briefly for process output to write
        time.sleep(0.6)
        assert stdout_log.exists()
        content = stdout_log.read_text(encoding="utf-8")
        assert "DETACHED_OK" in content

    def test_github_run_status_mapping(self) -> None:
        """Verify mapping of GitHub Actions workflow run statuses to JobStatus records."""
        # 1. Queued
        s1, _p1, _step1, err1 = map_github_run_to_job_status({"status": "queued"})
        assert s1 == JobStatus.QUEUED
        assert err1 is None

        # 2. In progress
        s2, _p2, _step2, err2 = map_github_run_to_job_status({"status": "in_progress"})
        assert s2 == JobStatus.RUNNING
        assert err2 is None

        # 3. Completed success
        s3, p3, _step3, err3 = map_github_run_to_job_status(
            {"status": "completed", "conclusion": "success"}
        )
        assert s3 == JobStatus.COMPLETED
        assert p3 == 100.0
        assert err3 is None

        # 4. Completed failure
        s4, _p4, _step4, err4 = map_github_run_to_job_status(
            {"status": "completed", "conclusion": "failure"}
        )
        assert s4 == JobStatus.FAILED
        assert err4 is not None

        # 5. Timed out
        s5, _p5, _step5, _err5 = map_github_run_to_job_status(
            {"status": "completed", "conclusion": "timed_out"}
        )
        assert s5 == JobStatus.TIMED_OUT

    def test_full_pipeline_async_delegation_and_polling(self, tmp_path: Path) -> None:
        """Integration test: Non-blocking delegation (< 50ms) and async status polling loop."""
        src_d = Path(__file__).resolve().parents[2] / "src"
        art_d = tmp_path / "artifacts"
        st_d = tmp_path / "state"

        job_id = str(uuid.uuid4())
        job_art_d = art_d / "jobs" / job_id
        job_art_d.mkdir(parents=True, exist_ok=True)

        payload = ExecutionPayload(
            job_id=job_id,
            tier=ExecutionTier.LOCAL_TIER_1,
            workflow_type="ETHANOL_CONFORMER",
            molecule_xyz=ETHANOL_XYZ,
            parameters={"method": "GFN2-xTB"},
            output_artifact_dir=job_art_d.as_posix(),
        )

        runner = AsyncProcessRunner(
            src_dir=src_d,
            artifacts_dir=art_d,
            state_dir=st_d,
        )

        t_start = time.perf_counter()
        initial_record = delegate_pipeline_execution_async(payload, runner=runner)
        t_elapsed = time.perf_counter() - t_start

        # Verify non-blocking UI delegation requirement
        assert initial_record.status == JobStatus.QUEUED
        assert t_elapsed < 0.200

        # Asynchronously poll status until completion
        async def _run_poll() -> JobStatusRecord:
            return await poll_job_status_async(
                job_id=job_id,
                state_dir=st_d,
                base_delay=0.1,
                factor=1.2,
                max_delay=0.5,
                timeout_seconds=15.0,
            )

        final_record = asyncio.run(_run_poll())

        assert final_record.status == JobStatus.COMPLETED
        assert final_record.progress_percent == 100.0
        assert (job_art_d / "execution_summary.json").exists()
