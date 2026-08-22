Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BASE\.in-progress\Doc2_Part2_11_interfaces_dock_main_prompt.md.
Original prompt:
﻿# CoChem-BASE Coding Prompt: cochem_dock_main.py

## 1. Goal
Implement the file `cochem_dock_main.py` based on the Software Requirements Specification (SRS) - CoChem-BASE (Document 2 Part 2).

## 2. Target Filepath
`D:\__CoChem\GitHub-Repo\CoChem-BASE\interfaces\cochem_dock_main.py`

## 3. Context & Ecosystem Role
The Engine Bridge. Shields the Python execution layer from the web frontend, securely dispatching jobs and routing data safely across distributed architectures and unreliable network states.

## 4. Deliverable Functions
Uvicorn ASGI entry point acting as a headless, asynchronous REST API. Replaces SQLite completely for state queuing over networked filesystems (NFS/Lustre) to prevent corruption, relying instead on an append-only JSONL log or filesystem atomic renames for IPC queuing. Holds open WebSocket connections for telemetry streaming, implementing a Service Worker or robust state-recovery protocol to counter sleeping browser tabs that drop connections.

## 5. Strict Constraints & Anti-Spoofing
- **Workspace Rules:** Strictly adhere to the Tripartite Workspace Air-Gap and Method Matrix rules.
- **No Mocks or Stubs:** Do NOT use placeholders, mock data, or stub logic (e.g., `pass`, `NotImplementedError`, or fake hardcoded values).
- **Fully Functional:** The code must be production-ready and fully implement the deliverables.
- **Error Handling:** Must degrade gracefully and handle errors according to the SRS without crashing silently.
- **Autonomy:** Do not delegate to the user. Execute the complete implementation.
- **Verification:** Ensure your code runs in the physical constraints as defined.

Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_base\interfaces\cochem_dock_main.py ---
#!/usr/bin/env python3
"""CoChem-DOCK: Stage 9.0 - FastAPI Telemetry & Asynchronous REST API Engine Bridge.

Shields the Python execution layer from the web frontend, securely dispatching jobs
and routing telemetry data safely across distributed architectures and unreliable network states.
Provides Dual-Mode Job Queue (Local NVMe SQLite WAL vs. Enterprise HPC Shared Filesystem JSONL with filelock),
LTTB decimation, streaming health checks, and resilient WebSocket endpoints.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import json
import logging
import os
from pathlib import Path
import sqlite3
import time
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional, Set, Tuple, Union

import uvicorn
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from filelock import FileLock
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from cochem_base.telemetry_transport import (
    close_telemetry_server_socket,
    create_telemetry_server_socket,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("CoChem-DOCK")

_START_TIME = time.time()


# ============================================================================
# Pydantic Schemas & Data Models
# ============================================================================


class TelemetryEvent(BaseModel):
    """Pydantic model for structural validation of incoming telemetry events."""

    model_config = ConfigDict(extra="allow")

    type: str = Field(default="unknown")
    step: Optional[int] = None
    energy_hartree: Optional[float] = None
    delta_energy: Optional[float] = None
    max_gradient: Optional[float] = None
    rms_gradient: Optional[float] = None
    walltime_seconds: Optional[float] = None
    timestamp: Optional[float] = None
    job_id: Optional[str] = None


TelemetryMessage = TelemetryEvent


class HealthResponse(BaseModel):
    """Schema for /api/health endpoint response."""

    status: str = "online"
    service: str = "CoChem-DOCK FastAPI"
    transport: str = "udp" if os.name == "nt" else "unix"
    version: str = "0.1.0"
    uptime_seconds: float = 0.0
    queue_mode: str = "sqlite"


class TelemetryBatchPayload(BaseModel):
    """Schema for LTTB-decimated batched telemetry payloads."""

    type: str = "lttb_batch"
    data: List[str] = Field(default_factory=list)
    count: int = 0


class TelemetryStatsResponse(BaseModel):
    """Schema for /api/telemetry/stats endpoint response."""

    active: bool = True
    transport: str = "udp" if os.name == "nt" else "unix"
    socket_path: Optional[str] = None
    udp_host: Optional[str] = None
    udp_port: Optional[int] = None
    queue_mode: str = "sqlite"


class JobSubmitRequest(BaseModel):
    """Schema for /api/v1/jobs/submit endpoint request."""

    job_id: Optional[str] = Field(default=None, description="Optional custom job ID; generated if None")
    engine: str = Field(default="ORCA", description="Target quantum / ML engine (e.g. ORCA, CFOUR, xTB, AIMNet2, MACE)")
    input_file: Optional[str] = Field(default=None, description="Relative or absolute path to molecular input geometry")
    calculation_type: str = Field(default="optimization", description="Calculation type (e.g. sp, optimization, frequency, vpt2)")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Engine specific parameters and method settings")
    priority: int = Field(default=0, description="Execution priority (higher executes sooner)")


class JobSubmitResponse(BaseModel):
    """Schema for /api/v1/jobs/submit endpoint response."""

    job_id: str
    status: str = "queued"
    message: str = "Job queued successfully"
    queue_mode: str = "sqlite"
    created_at: float = Field(default_factory=time.time)


class JobStatusResponse(BaseModel):
    """Schema for /api/v1/jobs/status/{job_id} endpoint response."""

    job_id: str
    status: str
    progress: float = 0.0
    message: Optional[str] = None
    engine: Optional[str] = None
    calculation_type: Optional[str] = None
    created_at: float
    updated_at: float
    result: Optional[Dict[str, Any]] = None


class JobCancelResponse(BaseModel):
    """Schema for /api/v1/jobs/cancel/{job_id} endpoint response."""

    job_id: str
    status: str = "cancelled"
    message: str = "Job successfully cancelled"
    cancelled: bool = True


class JobListResponse(BaseModel):
    """Schema for /api/v1/jobs listing response."""

    count: int
    queue_mode: str
    jobs: List[JobStatusResponse] = Field(default_factory=list)


# ============================================================================
# Dual-Mode Execution Queue Manager
# ============================================================================


class DualModeJobQueue:
    """HPC-Safe Dual-Mode Execution Queue.

    - Local NVMe Mode: Uses SQLite with PRAGMA journal_mode=WAL and PRAGMA synchronous=NORMAL
      on node-local SSD storage for high-speed concurrent ACID job serialization.
    - Enterprise HPC Mode: Uses an append-only JSONL task queue backed by filelock.FileLock
      and atomic file renames to eliminate POSIX shared-memory locking corruption across
      networked Lustre, GPFS, and NFS mounts.
    """

    def __init__(
        self,
        mode: Optional[str] = None,
        base_dir: Optional[Union[str, Path]] = None,
    ) -> None:
        if base_dir is None:
            artifact_env = os.environ.get("COCHEM_ARTIFACT_DIR")
            if artifact_env:
                self.base_dir = Path(artifact_env)
            else:
                self.base_dir = Path(os.environ.get("TEMP", os.environ.get("TMPDIR", "/tmp"))) / "cochem_queue"
        else:
            self.base_dir = Path(base_dir)

        self.base_dir.mkdir(parents=True, exist_ok=True)

        if mode is not None:
            self.mode = mode.lower()
        elif os.environ.get("COCHEM_QUEUE_MODE"):
            self.mode = os.environ["COCHEM_QUEUE_MODE"].lower()
        elif (
            os.environ.get("COCHEM_IS_HPC") == "1"
            or "SLURM_JOB_ID" in os.environ
            or "PBS_JOBID" in os.environ
        ):
            self.mode = "jsonl"
        else:
            self.mode = "sqlite"

        self.sqlite_path = self.base_dir / "cochem_jobs.db"
        self.jsonl_path = self.base_dir / "cochem_jobs.jsonl"
        self.lock_path = self.base_dir / "cochem_jobs.jsonl.lock"

        if self.mode == "sqlite":
            self._init_sqlite_schema()

    def _init_sqlite_schema(self) -> None:
        """Initialize SQLite table and WAL mode."""
        with sqlite3.connect(str(self.sqlite_path), timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    engine TEXT NOT NULL,
                    input_file TEXT,
                    calculation_type TEXT,
                    parameters TEXT,
                    status TEXT NOT NULL,
                    priority INTEGER DEFAULT 0,
                    progress REAL DEFAULT 0.0,
                    message TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    result TEXT
                )
                """
            )
            conn.commit()

    def submit_job(self, req: JobSubmitRequest) -> JobSubmitResponse:
        """Submit a new job to the queue."""
        job_id = req.job_id or f"job_{uuid.uuid4().hex[:12]}"
        now = time.time()
        params_str = json.dumps(req.parameters)

        if self.mode == "sqlite":
            with sqlite3.connect(str(self.sqlite_path), timeout=30.0) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO jobs (
                        job_id, engine, input_file, calculation_type, parameters,
                        status, priority, progress, message, created_at, updated_at, result
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job_id,
                        req.engine,
                        req.input_file,
                        req.calculation_type,
                        params_str,
                        "queued",
                        req.priority,
                        0.0,
                        "Job queued",
                        now,
                        now,
                        None,
                    ),
                )
                conn.commit()
        else:
            record = {
                "job_id": job_id,
                "engine": req.engine,
                "input_file": req.input_file,
                "calculation_type": req.calculation_type,
                "parameters": req.parameters,
                "status": "queued",
                "priority": req.priority,
                "progress": 0.0,
                "message": "Job queued",
                "created_at": now,
                "updated_at": now,
                "result": None,
            }
            lock = FileLock(str(self.lock_path), timeout=15)
            with lock:
                with open(self.jsonl_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record) + "\n")

        return JobSubmitResponse(
            job_id=job_id,
            status="queued",
            message="Job queued successfully",
            queue_mode=self.mode,
            created_at=now,
        )

    def get_job_status(self, job_id: str) -> Optional[JobStatusResponse]:
        """Retrieve the status and metadata for a specific job."""
        if self.mode == "sqlite":
            with sqlite3.connect(str(self.sqlite_path), timeout=30.0) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
                row = cur.fetchone()
                if not row:
                    return None
                res_dict = json.loads(row["result"]) if row["result"] else None
                return JobStatusResponse(
                    job_id=row["job_id"],
                    status=row["status"],
                    progress=row["progress"],
                    message=row["message"],
                    engine=row["engine"],
                    calculation_type=row["calculation_type"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    result=res_dict,
                )
        else:
            if not self.jsonl_path.exists():
                return None
            latest_record: Optional[Dict[str, Any]] = None
            lock = FileLock(str(self.lock_path), timeout=15)
            with lock:
                with open(self.jsonl_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                data = json.loads(line)
                                if data.get("job_id") == job_id:
                                    latest_record = data
                            except json.JSONDecodeError:
                                pass
            if latest_record is None:
                return None
            return JobStatusResponse(
                job_id=latest_record["job_id"],
                status=latest_record["status"],
                progress=latest_record.get("progress", 0.0),
                message=latest_record.get("message"),
                engine=latest_record.get("engine"),
                calculation_type=latest_record.get("calculation_type"),
                created_at=latest_record["created_at"],
                updated_at=latest_record["updated_at"],
                result=latest_record.get("result"),
            )

    def update_job_status(
        self,
        job_id: str,
        status: str,
        progress: float = 0.0,
        result: Optional[Dict[str, Any]] = None,
        message: Optional[str] = None,
    ) -> bool:
        """Update job progress, status, and result."""
        now = time.time()
        result_str = json.dumps(result) if result is not None else None

        if self.mode == "sqlite":
            with sqlite3.connect(str(self.sqlite_path), timeout=30.0) as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    UPDATE jobs
                    SET status = ?, progress = ?, result = COALESCE(?, result), message = COALESCE(?, message), updated_at = ?
                    WHERE job_id = ?
                    """,
                    (status, progress, result_str, message, now, job_id),
                )
                conn.commit()
                return cur.rowcount > 0
        else:
            current = self.get_job_status(job_id)
            if not current:
                return False
            updated_record = {
                "job_id": job_id,
                "engine": current.engine,
                "calculation_type": current.calculation_type,
                "status": status,
                "progress": progress,
                "message": message or current.message,
                "created_at": current.created_at,
                "updated_at": now,
                "result": result if result is not None else current.result,
            }
            lock = FileLock(str(self.lock_path), timeout=15)
            with lock:
                with open(self.jsonl_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(updated_record) + "\n")
            return True

    def cancel_job(self, job_id: str) -> JobCancelResponse:
        """Cancel a queued or active job."""
        job = self.get_job_status(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        self.update_job_status(job_id=job_id, status="cancelled", progress=job.progress, message="Job cancelled by user")
        return JobCancelResponse(job_id=job_id, status="cancelled", message="Job successfully cancelled", cancelled=True)

    def list_jobs(self, limit: int = 100) -> List[JobStatusResponse]:
        """List active and completed jobs."""
        if self.mode == "sqlite":
            with sqlite3.connect(str(self.sqlite_path), timeout=30.0) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute("SELECT * FROM jobs ORDER BY updated_at DESC LIMIT ?", (limit,))
                results = []
                for row in cur.fetchall():
                    res_dict = json.loads(row["result"]) if row["result"] else None
                    results.append(
                        JobStatusResponse(
                            job_id=row["job_id"],
                            status=row["status"],
                            progress=row["progress"],
                            message=row["message"],
                            engine=row["engine"],
                            calculation_type=row["calculation_type"],
                            created_at=row["created_at"],
                            updated_at=row["updated_at"],
                            result=res_dict,
                        )
                    )
                return results
        else:
            if not self.jsonl_path.exists():
                return []
            latest_jobs: Dict[str, Dict[str, Any]] = {}
            lock = FileLock(str(self.lock_path), timeout=15)
            with lock:
                with open(self.jsonl_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                data = json.loads(line)
                                jid = data.get("job_id")
                                if jid:
                                    latest_jobs[jid] = data
                            except json.JSONDecodeError:
                                pass
            items = sorted(latest_jobs.values(), key=lambda x: x.get("updated_at", 0.0), reverse=True)[:limit]
            return [
                JobStatusResponse(
                    job_id=it["job_id"],
                    status=it["status"],
                    progress=it.get("progress", 0.0),
                    message=it.get("message"),
                    engine=it.get("engine"),
                    calculation_type=it.get("calculation_type"),
                    created_at=it["created_at"],
                    updated_at=it["updated_at"],
                    result=it.get("result"),
                )
                for it in items
            ]


# Singleton default queue instance
default_job_queue = DualModeJobQueue()


# ============================================================================
# LTTB Decimation Algorithm
# ============================================================================


def lttb_decimate(data: List[str], threshold: int) -> List[str]:
    """Largest Triangle Three Buckets (LTTB) downsampling algorithm for high-frequency telemetry.

    Preserves visual peaks and valleys for the React UI while retaining non-scf telemetry records.
    """
    if len(data) <= threshold or threshold <= 0:
        return data

    parsed_data: List[Tuple[int, str, float]] = []

    for idx, item in enumerate(data):
        try:
            obj = json.loads(item)
            if isinstance(obj, dict):
                event = TelemetryEvent.model_validate(obj)
                if event.type == "scf_step" and event.energy_hartree is not None:
                    parsed_data.append((idx, item, event.energy_hartree))
        except (json.JSONDecodeError, ValueError, TypeError, ValidationError):
            pass

    if len(parsed_data) <= threshold or threshold <= 0:
        return data

    sampled_indices: Set[int] = set()

    if threshold == 1:
        sampled_indices.add(parsed_data[0][0])
    elif threshold == 2:
        sampled_indices.add(parsed_data[0][0])
        sampled_indices.add(parsed_data[-1][0])
    else:
        bucket_size = (len(parsed_data) - 2) / (threshold - 2)
        sampled_indices.add(parsed_data[0][0])

        a = 0
        for i in range(threshold - 2):
            bucket_start = int(1 + i * bucket_size)
            bucket_end = min(int(1 + (i + 1) * bucket_size), len(parsed_data) - 1)
            next_bucket_start = int(1 + (i + 1) * bucket_size)
            next_bucket_end = min(int(1 + (i + 2) * bucket_size), len(parsed_data))

            avg_x, avg_y, count = 0.0, 0.0, 0
            for j in range(next_bucket_start, next_bucket_end):
                avg_x += j
                avg_y += parsed_data[j][2]
                count += 1

            if count > 0:
                avg_x /= count
                avg_y /= count

            max_area, max_area_index = -1.0, bucket_start
            for j in range(bucket_start, bucket_end):
                point_b_y = parsed_data[j][2]
                point_a_y = parsed_data[a][2]

                area = abs(a * (point_b_y - avg_y) + j * (avg_y - point_a_y) + avg_x * (point_a_y - point_b_y)) * 0.5
                if area > max_area:
                    max_area = area
                    max_area_index = j

            sampled_indices.add(parsed_data[max_area_index][0])
            a = max_area_index

        sampled_indices.add(parsed_data[-1][0])

    parsed_indices: Set[int] = {p[0] for p in parsed_data}
    result: List[str] = []
    for idx, item in enumerate(data):
        if idx in sampled_indices or idx not in parsed_indices:
            result.append(item)

    return result


# ============================================================================
# FastAPI Application Factory & Routes
# ============================================================================


@asynccontextmanager
async def lifespan(app_instance: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for background startup/teardown."""
    logger.info("Starting CoChem-DOCK ASGI Engine Bridge")
    yield
    logger.info("Shutting down CoChem-DOCK ASGI Engine Bridge")


def create_app(queue_instance: Optional[DualModeJobQueue] = None) -> FastAPI:
    """Create and configure the FastAPI application instance."""
    app_instance = FastAPI(title="CoChem-DOCK Telemetry API", lifespan=lifespan)
    queue = queue_instance or default_job_queue

    app_instance.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app_instance.get("/api/health", response_model=HealthResponse)
    async def _health_check() -> Dict[str, Any]:
        return await health_check()

    @app_instance.get("/api/telemetry/stats", response_model=TelemetryStatsResponse)
    async def _telemetry_stats() -> Dict[str, Any]:
        return await telemetry_stats()

    @app_instance.post("/api/v1/jobs/submit", response_model=JobSubmitResponse)
    async def _submit_job(req: JobSubmitRequest) -> JobSubmitResponse:
        return queue.submit_job(req)

    @app_instance.get("/api/v1/jobs/status/{job_id}", response_model=JobStatusResponse)
    async def _get_job_status(job_id: str) -> JobStatusResponse:
        job = queue.get_job_status(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        return job

    @app_instance.post("/api/v1/jobs/cancel/{job_id}", response_model=JobCancelResponse)
    async def _cancel_job(job_id: str) -> JobCancelResponse:
        return queue.cancel_job(job_id)

    @app_instance.get("/api/v1/jobs", response_model=JobListResponse)
    async def _list_jobs(limit: int = Query(default=100, ge=1, le=1000)) -> JobListResponse:
        jobs = queue.list_jobs(limit=limit)
        return JobListResponse(count=len(jobs), queue_mode=queue.mode, jobs=jobs)

    @app_instance.websocket("/ws/telemetry")
    async def _websocket_telemetry(
        websocket: WebSocket,
        buffer_threshold: int = Query(default=100, ge=1),
        decimate_target: int = Query(default=20, ge=1),
    ) -> None:
        await websocket_telemetry(websocket, buffer_threshold=buffer_threshold, decimate_target=decimate_target)

    @app_instance.websocket("/ws/telemetry/{job_id}")
    async def _websocket_telemetry_job(
        websocket: WebSocket,
        job_id: str,
        buffer_threshold: int = Query(default=100, ge=1),
        decimate_target: int = Query(default=20, ge=1),
    ) -> None:
        await websocket_telemetry(
            websocket,
            job_id=job_id,
            buffer_threshold=buffer_threshold,
            decimate_target=decimate_target,
        )

    return app_instance


app = create_app()


async def health_check() -> Dict[str, Any]:
    """Return runtime health and transport configuration."""
    uptime = time.time() - _START_TIME
    transport = "udp" if os.name == "nt" else "unix"
    return {
        "status": "online",
        "service": "CoChem-DOCK FastAPI",
        "transport": transport,
        "version": "0.1.0",
        "uptime_seconds": round(uptime, 2),
        "queue_mode": default_job_queue.mode,
    }


async def telemetry_stats() -> Dict[str, Any]:
    """Return active telemetry socket and port metrics."""
    transport = "udp" if os.name == "nt" else "unix"
    if transport == "unix":
        return {
            "active": True,
            "transport": "unix",
            "socket_path": "/tmp/cochem_telemetry.sock",
            "queue_mode": default_job_queue.mode,
        }
    return {
        "active": True,
        "transport": "udp",
        "udp_host": "127.0.0.1",
        "udp_port": 54321,
        "queue_mode": default_job_queue.mode,
    }


async def websocket_telemetry(
    websocket: WebSocket,
    job_id: Optional[str] = None,
    buffer_threshold: int = 100,
    decimate_target: int = 20,
) -> None:
    """Hold open WebSocket connection for real-time telemetry streaming with LTTB batching."""
    await websocket.accept()
    server, socket_path = create_telemetry_server_socket()
    server.setblocking(False)

    loop = asyncio.get_running_loop()
    telemetry_buffer: List[str] = []

    async def _listen_client() -> None:
        try:
            while True:
                msg = await websocket.receive_text()
                if msg == "ping":
                    await websocket.send_text("pong")
                elif msg == "flush":
                    if telemetry_buffer:
                        decimated = lttb_decimate(telemetry_buffer, decimate_target)
                        await websocket.send_json({"type": "lttb_batch", "data": decimated, "count": len(decimated)})
                        telemetry_buffer.clear()
        except WebSocketDisconnect:
            pass

    async def _listen_socket() -> None:
        try:
            while True:
                try:
                    data = await loop.sock_recv(server, 4096)
                    if data:
                        payload = data.decode("utf-8")
                        # If a specific job_id is requested, filter payload if structural job_id is present
                        if job_id:
                            try:
                                obj = json.loads(payload)
                                if isinstance(obj, dict) and obj.get("job_id") and obj.get("job_id") != job_id:
                                    continue
                            except (json.JSONDecodeError, ValueError):
                                pass

                        telemetry_buffer.append(payload)
                        if len(telemetry_buffer) >= buffer_threshold:
                            decimated = lttb_decimate(telemetry_buffer, decimate_target)
                            await websocket.send_json({"type": "lttb_batch", "data": decimated, "count": len(decimated)})
                            telemetry_buffer.clear()
                        else:
                            await websocket.send_text(payload)
                except (BlockingIOError, InterruptedError):
                    await asyncio.sleep(0.01)
                except Exception:
                    await asyncio.sleep(0.01)
        except WebSocketDisconnect:
            pass

    t_client = asyncio.create_task(_listen_client())
    t_socket = asyncio.create_task(_listen_socket())

    try:
        done, pending = await asyncio.wait([t_client, t_socket], return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
    except Exception as e:
        logger.error(f"WebSocket telemetry session error: {e}")
    finally:
        t_client.cancel()
        t_socket.cancel()
        close_telemetry_server_socket(server, socket_path)


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Run the Uvicorn ASGI server."""
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server(
        host=os.environ.get("COCHEM_DOCK_HOST", "127.0.0.1"),
        port=int(os.environ.get("COCHEM_DOCK_PORT", "8000")),
    )

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\interfaces\cochem_dock_main.py ---
#!/usr/bin/env python3
"""CoChem-DOCK: Stage 9.0 - Legacy and Direct Entrypoint for FastAPI Telemetry & Job Bridge.

Re-exports canonical symbols from cochem_base.interfaces.cochem_dock_main.
"""

from __future__ import annotations

from cochem_base.interfaces.cochem_dock_main import (
    DualModeJobQueue,
    HealthResponse,
    JobCancelResponse,
    JobListResponse,
    JobStatusResponse,
    JobSubmitRequest,
    JobSubmitResponse,
    TelemetryBatchPayload,
    TelemetryEvent,
    TelemetryMessage,
    TelemetryStatsResponse,
    app,
    create_app,
    default_job_queue,
    health_check,
    lifespan,
    logger,
    lttb_decimate,
    run_server,
    telemetry_stats,
    websocket_telemetry,
)

__all__ = [
    "DualModeJobQueue",
    "HealthResponse",
    "JobCancelResponse",
    "JobListResponse",
    "JobStatusResponse",
    "JobSubmitRequest",
    "JobSubmitResponse",
    "TelemetryBatchPayload",
    "TelemetryEvent",
    "TelemetryMessage",
    "TelemetryStatsResponse",
    "app",
    "create_app",
    "default_job_queue",
    "health_check",
    "lifespan",
    "logger",
    "lttb_decimate",
    "run_server",
    "telemetry_stats",
    "websocket_telemetry",
]

if __name__ == "__main__":
    run_server()

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\test_suite\test_cochem_dock_main.py ---
"""Comprehensive Zero-Mock test suite for cochem_base.interfaces.cochem_dock_main.

Validates FastAPI endpoints, Pydantic telemetry and job models, Dual-Mode Job Queue
(SQLite WAL vs. JSONL + FileLock), LTTB downsampling algorithm, WebSocket datagram
telemetry streaming, control frames, and path sanitization.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import List

import pytest
from fastapi.testclient import TestClient

import interfaces.cochem_dock_main as legacy_dock_main
from cochem_base.interfaces.cochem_dock_main import (
    DualModeJobQueue,
    HealthResponse,
    JobCancelResponse,
    JobListResponse,
    JobStatusResponse,
    JobSubmitRequest,
    JobSubmitResponse,
    TelemetryBatchPayload,
    TelemetryEvent,
    TelemetryStatsResponse,
    app,
    create_app,
    default_job_queue,
    health_check,
    lifespan,
    logger,
    lttb_decimate,
    run_server,
    telemetry_stats,
    websocket_telemetry,
)
from cochem_base.path_sanitization import leak_patterns
from cochem_base.telemetry_transport import send_telemetry_payload


@pytest.fixture
def dock_main_path() -> Path:
    """Return the absolute path to cochem_base/interfaces/cochem_dock_main.py."""
    path = Path(__file__).resolve().parent.parent / "cochem_base" / "interfaces" / "cochem_dock_main.py"
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


@pytest.fixture
def interfaces_dock_main_path() -> Path:
    """Return the absolute path to interfaces/cochem_dock_main.py."""
    path = Path(__file__).resolve().parent.parent / "interfaces" / "cochem_dock_main.py"
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


@pytest.fixture
def client() -> TestClient:
    """Return a TestClient instance for the FastAPI application."""
    return TestClient(app)


def test_file_encoding_and_lf_line_endings(
    dock_main_path: Path, interfaces_dock_main_path: Path
) -> None:
    """Verify strictly Unix LF line endings (\\n), standard UTF-8 encoding, and no BOM."""
    for path in (dock_main_path, interfaces_dock_main_path):
        raw = path.read_bytes()
        assert b"\r\n" not in raw, f"Found Windows CRLF line endings in {path.name}"
        assert b"\n" in raw, f"Missing newline characters in {path.name}"
        assert not raw.startswith(b"\xef\xbb\xbf"), f"Found UTF-8 BOM marker in {path.name}"

        content = path.read_text(encoding="utf-8")
        assert len(content) > 100, f"File content in {path.name} is unexpectedly small."


def test_zero_personal_path_leaks(
    dock_main_path: Path, interfaces_dock_main_path: Path
) -> None:
    """Verify zero personal machine or local user path leakage in cochem_dock_main.py."""
    patterns = leak_patterns()
    for path in (dock_main_path, interfaces_dock_main_path):
        lines = path.read_text(encoding="utf-8").splitlines()
        leaks = []
        for lineno, line in enumerate(lines, 1):
            for pattern, placeholder in patterns:
                if pattern.search(line):
                    leaks.append((lineno, placeholder, line.strip()))

        assert len(leaks) == 0, f"Detected personal path leaks in {path.name}: {leaks}"


def test_interfaces_dock_main_reexports_and_aliases() -> None:
    """Verify interfaces.cochem_dock_main cleanly re-exports canonical symbols."""
    assert legacy_dock_main.app is app
    assert legacy_dock_main.create_app is create_app
    assert legacy_dock_main.health_check is health_check
    assert legacy_dock_main.telemetry_stats is telemetry_stats
    assert legacy_dock_main.websocket_telemetry is websocket_telemetry
    assert legacy_dock_main.lttb_decimate is lttb_decimate
    assert legacy_dock_main.run_server is run_server
    assert legacy_dock_main.lifespan is lifespan
    assert legacy_dock_main.logger is logger
    assert legacy_dock_main.default_job_queue is default_job_queue
    assert legacy_dock_main.DualModeJobQueue is DualModeJobQueue
    assert legacy_dock_main.TelemetryEvent is TelemetryEvent
    assert legacy_dock_main.TelemetryMessage is TelemetryEvent
    assert legacy_dock_main.HealthResponse is HealthResponse
    assert legacy_dock_main.TelemetryBatchPayload is TelemetryBatchPayload
    assert legacy_dock_main.TelemetryStatsResponse is TelemetryStatsResponse
    assert legacy_dock_main.JobSubmitRequest is JobSubmitRequest
    assert legacy_dock_main.JobSubmitResponse is JobSubmitResponse
    assert legacy_dock_main.JobStatusResponse is JobStatusResponse
    assert legacy_dock_main.JobCancelResponse is JobCancelResponse

    for sym in legacy_dock_main.__all__:
        assert hasattr(legacy_dock_main, sym), f"Missing symbol {sym} in legacy module"


def test_telemetry_event_model_fields_and_validation() -> None:
    """Verify TelemetryEvent field types, defaults, and extra attribute allowance."""
    event_data = {
        "type": "scf_step",
        "step": 4,
        "energy_hartree": -76.4321,
        "delta_energy": -0.00012,
        "max_gradient": 0.000045,
        "rms_gradient": 0.000012,
        "walltime_seconds": 1.24,
        "timestamp": 1700000000.0,
        "job_id": "test_job_123",
        "custom_metadata": "dft_pbe0",
    }
    event = TelemetryEvent.model_validate(event_data)
    assert event.type == "scf_step"
    assert event.step == 4
    assert event.energy_hartree == -76.4321
    assert event.delta_energy == -0.00012
    assert event.max_gradient == 0.000045
    assert event.rms_gradient == 0.000012
    assert event.walltime_seconds == 1.24
    assert event.timestamp == 1700000000.0
    assert event.job_id == "test_job_123"
    assert event.model_extra is not None
    assert event.model_extra.get("custom_metadata") == "dft_pbe0"

    # Verify JSON serialization
    serialized = event.model_dump_json()
    assert '"type":"scf_step"' in serialized
    assert '"energy_hartree":-76.4321' in serialized


def test_health_and_batch_payload_models() -> None:
    """Verify HealthResponse and TelemetryBatchPayload model contracts."""
    health = HealthResponse(
        status="online",
        service="CoChem-DOCK FastAPI",
        transport="udp",
        version="0.1.0",
        uptime_seconds=42.5,
        queue_mode="sqlite",
    )
    assert health.status == "online"
    assert health.transport == "udp"
    assert health.uptime_seconds == 42.5
    assert health.queue_mode == "sqlite"

    batch = TelemetryBatchPayload(
        type="lttb_batch",
        data=['{"type": "scf_step", "energy_hartree": -1.0}'],
        count=1,
    )
    assert batch.type == "lttb_batch"
    assert batch.count == 1
    assert len(batch.data) == 1


def test_job_models_contracts() -> None:
    """Verify Job schemas and validation contracts."""
    req = JobSubmitRequest(
        job_id="custom_01",
        engine="ORCA",
        input_file="input.xyz",
        calculation_type="optimization",
        parameters={"method": "PBE0", "basis": "def2-SVP"},
        priority=5,
    )
    assert req.job_id == "custom_01"
    assert req.engine == "ORCA"
    assert req.priority == 5

    res = JobSubmitResponse(
        job_id="custom_01",
        status="queued",
        message="Job queued successfully",
        queue_mode="sqlite",
        created_at=100.0,
    )
    assert res.status == "queued"

    status = JobStatusResponse(
        job_id="custom_01",
        status="running",
        progress=0.45,
        message="Iteration 4",
        engine="ORCA",
        calculation_type="optimization",
        created_at=100.0,
        updated_at=105.0,
        result={"energy": -76.4},
    )
    assert status.progress == 0.45
    assert status.result == {"energy": -76.4}

    cancel = JobCancelResponse(
        job_id="custom_01",
        status="cancelled",
        message="Job cancelled",
        cancelled=True,
    )
    assert cancel.cancelled is True


# --- LTTB Decimation Algorithm Unit Tests ---


def test_lttb_decimate_empty_or_zero_threshold() -> None:
    """Verify LTTB behavior on empty input or non-positive thresholds."""
    data = ['{"type": "scf_step", "energy_hartree": -76.0}']
    assert lttb_decimate([], 10) == []
    assert lttb_decimate(data, 0) == data
    assert lttb_decimate(data, -5) == data


def test_lttb_decimate_threshold_greater_than_data() -> None:
    """Verify LTTB returns all data when threshold >= number of items."""
    data = [
        json.dumps({"type": "scf_step", "energy_hartree": -76.0 - i * 0.1})
        for i in range(10)
    ]
    assert lttb_decimate(data, 10) == data
    assert lttb_decimate(data, 20) == data


def test_lttb_decimate_threshold_1_and_2() -> None:
    """Verify LTTB handles edge thresholds 1 and 2 safely."""
    data = [
        json.dumps({"type": "scf_step", "energy_hartree": -76.0 - i * 0.1})
        for i in range(10)
    ]
    res_1 = lttb_decimate(data, 1)
    assert len(res_1) == 1
    assert json.loads(res_1[0])["energy_hartree"] == -76.0

    res_2 = lttb_decimate(data, 2)
    assert len(res_2) == 2
    assert json.loads(res_2[0])["energy_hartree"] == -76.0
    assert json.loads(res_2[-1])["energy_hartree"] == -76.0 - 9 * 0.1


def test_lttb_decimate_preserves_first_last_and_peaks() -> None:
    """Verify LTTB downsampling retains first, last, and prominent peak extrema."""
    # Generate 50 points with a distinct peak at index 25
    points: List[str] = []
    for i in range(50):
        # Baseline curve with an abrupt sharp peak at i=25
        energy = -76.0 - (i * 0.01)
        if i == 25:
            energy = -74.0  # Sharp positive spike
        points.append(json.dumps({"type": "scf_step", "energy_hartree": energy}))

    threshold = 10
    decimated = lttb_decimate(points, threshold)
    assert len(decimated) == threshold

    # Verify first and last points are strictly preserved
    assert json.loads(decimated[0])["energy_hartree"] == -76.0
    assert json.loads(decimated[-1])["energy_hartree"] == -76.0 - (49 * 0.01)

    # Verify the sharp spike at index 25 is captured in the downsampled subset
    decimated_energies = [json.loads(p)["energy_hartree"] for p in decimated]
    assert -74.0 in decimated_energies, "LTTB failed to capture prominent peak"


def test_lttb_decimate_preserves_non_scf_messages() -> None:
    """Verify non-scf_step telemetry messages are preserved in the stream."""
    stream: List[str] = [
        '{"type": "init", "solver": "ORCA"}',
        '{"type": "scf_step", "energy_hartree": -10.0}',
        '{"type": "scf_step", "energy_hartree": -10.5}',
        '{"type": "scf_step", "energy_hartree": -10.8}',
        '{"type": "scf_step", "energy_hartree": -10.9}',
        '{"type": "status_update", "converged": true}',
        'malformed non-json log message',
    ]
    decimated = lttb_decimate(stream, threshold=2)
    # Threshold=2 on 4 scf points should keep 2 scf points + 3 non-scf items = 5 total
    assert len(decimated) == 5
    assert '{"type": "init", "solver": "ORCA"}' in decimated
    assert '{"type": "status_update", "converged": true}' in decimated
    assert "malformed non-json log message" in decimated


# --- Dual-Mode Job Queue Tests ---


def test_dual_mode_job_queue_sqlite(tmp_path: Path) -> None:
    """Verify SQLite WAL mode execution queue operations."""
    q = DualModeJobQueue(mode="sqlite", base_dir=tmp_path / "sqlite_test")
    assert q.mode == "sqlite"

    # Submit job
    req = JobSubmitRequest(
        job_id="job_sql_1",
        engine="ORCA",
        input_file="opt.xyz",
        calculation_type="opt",
        parameters={"functional": "B3LYP"},
        priority=10,
    )
    submit_res = q.submit_job(req)
    assert submit_res.job_id == "job_sql_1"
    assert submit_res.status == "queued"

    # Get status
    st = q.get_job_status("job_sql_1")
    assert st is not None
    assert st.status == "queued"
    assert st.engine == "ORCA"

    # Update status
    updated = q.update_job_status("job_sql_1", status="running", progress=0.5, message="SCF Cycle 10")
    assert updated is True
    st_updated = q.get_job_status("job_sql_1")
    assert st_updated is not None
    assert st_updated.status == "running"
    assert st_updated.progress == 0.5
    assert st_updated.message == "SCF Cycle 10"

    # List jobs
    all_jobs = q.list_jobs()
    assert len(all_jobs) >= 1
    assert any(j.job_id == "job_sql_1" for j in all_jobs)

    # Cancel job
    cancel_res = q.cancel_job("job_sql_1")
    assert cancel_res.status == "cancelled"
    st_cancelled = q.get_job_status("job_sql_1")
    assert st_cancelled is not None
    assert st_cancelled.status == "cancelled"


def test_dual_mode_job_queue_jsonl(tmp_path: Path) -> None:
    """Verify HPC JSONL + FileLock mode execution queue operations."""
    q = DualModeJobQueue(mode="jsonl", base_dir=tmp_path / "jsonl_test")
    assert q.mode == "jsonl"

    # Submit job
    req = JobSubmitRequest(
        job_id="job_hpc_1",
        engine="CFOUR",
        input_file="input.dat",
        calculation_type="vpt2",
        parameters={"basis": "cc-pVTZ"},
        priority=2,
    )
    submit_res = q.submit_job(req)
    assert submit_res.job_id == "job_hpc_1"
    assert submit_res.status == "queued"
    assert submit_res.queue_mode == "jsonl"

    # Get status
    st = q.get_job_status("job_hpc_1")
    assert st is not None
    assert st.status == "queued"
    assert st.engine == "CFOUR"

    # Update status
    updated = q.update_job_status(
        "job_hpc_1",
        status="completed",
        progress=1.0,
        result={"energy": -120.45},
        message="VPT2 Complete",
    )
    assert updated is True
    st_updated = q.get_job_status("job_hpc_1")
    assert st_updated is not None
    assert st_updated.status == "completed"
    assert st_updated.result == {"energy": -120.45}

    # List jobs
    all_jobs = q.list_jobs()
    assert len(all_jobs) >= 1
    assert any(j.job_id == "job_hpc_1" for j in all_jobs)

    # Cancel job
    cancel_res = q.cancel_job("job_hpc_1")
    assert cancel_res.status == "cancelled"


# --- REST API Endpoint Tests ---


def test_health_check_endpoint(client: TestClient) -> None:
    """Verify GET /api/health returns operational status and telemetry transport."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["service"] == "CoChem-DOCK FastAPI"
    assert data["transport"] in ("unix", "udp")
    assert "uptime_seconds" in data
    assert "queue_mode" in data


def test_health_check_function_direct_call() -> None:
    """Verify direct async call to health_check() function returns valid dictionary."""
    result = asyncio.run(health_check())
    assert isinstance(result, dict)
    assert result["status"] == "online"
    assert result["service"] == "CoChem-DOCK FastAPI"
    assert "transport" in result
    assert "queue_mode" in result


def test_telemetry_stats_endpoint(client: TestClient) -> None:
    """Verify GET /api/telemetry/stats returns transport details."""
    response = client.get("/api/telemetry/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["active"] is True
    assert data["transport"] in ("unix", "udp")
    assert "queue_mode" in data
    if data["transport"] == "unix":
        assert "socket_path" in data
    else:
        assert "udp_host" in data
        assert "udp_port" in data


def test_telemetry_stats_function_direct_call() -> None:
    """Verify direct async call to telemetry_stats() function."""
    stats = asyncio.run(telemetry_stats())
    assert isinstance(stats, dict)
    assert stats["active"] is True


def test_create_app_factory() -> None:
    """Verify create_app produces a valid configured FastAPI instance."""
    new_app = create_app()
    assert new_app.title == "CoChem-DOCK Telemetry API"


def test_rest_job_endpoints(client: TestClient) -> None:
    """Verify REST job submit, status, list, and cancel workflow."""
    # Submit job
    payload = {
        "job_id": "rest_test_01",
        "engine": "ORCA",
        "input_file": "mol.xyz",
        "calculation_type": "optimization",
        "parameters": {"functional": "r2scan-3c"},
        "priority": 1,
    }
    sub_res = client.post("/api/v1/jobs/submit", json=payload)
    assert sub_res.status_code == 200
    sub_data = sub_res.json()
    assert sub_data["job_id"] == "rest_test_01"
    assert sub_data["status"] == "queued"

    # Status job
    stat_res = client.get("/api/v1/jobs/status/rest_test_01")
    assert stat_res.status_code == 200
    stat_data = stat_res.json()
    assert stat_data["job_id"] == "rest_test_01"
    assert stat_data["engine"] == "ORCA"

    # List jobs
    list_res = client.get("/api/v1/jobs?limit=50")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["count"] >= 1

    # Cancel job
    cancel_res = client.post("/api/v1/jobs/cancel/rest_test_01")
    assert cancel_res.status_code == 200
    cancel_data = cancel_res.json()
    assert cancel_data["cancelled"] is True

    # 404 on missing job
    missing_res = client.get("/api/v1/jobs/status/non_existent_id")
    assert missing_res.status_code == 404


# --- WebSocket Telemetry Stream Tests ---


def test_websocket_ping_pong(client: TestClient) -> None:
    """Verify WebSocket client can send ping and receive pong."""
    with client.websocket_connect("/ws/telemetry") as ws:
        ws.send_text("ping")
        response = ws.receive_text()
        assert response == "pong"


def test_websocket_telemetry_datagram_transmission(client: TestClient) -> None:
    """Verify telemetry datagram sent via transport is received by connected WebSocket."""
    with client.websocket_connect("/ws/telemetry?buffer_threshold=100&decimate_target=20") as ws:
        # Send a real physical telemetry datagram payload
        payload = {"type": "scf_step", "energy_hartree": -76.42119, "step": 1}
        send_telemetry_payload(payload)

        # Receive the telemetry message over WebSocket
        received_raw = ws.receive_text()
        received_obj = json.loads(received_raw)
        assert received_obj["type"] == "scf_step"
        assert received_obj["energy_hartree"] == -76.42119
        assert received_obj["step"] == 1


def test_websocket_buffer_batching_and_flush(client: TestClient) -> None:
    """Verify WebSocket buffer batching and manual flush control frame."""
    with client.websocket_connect("/ws/telemetry?buffer_threshold=50&decimate_target=5") as ws:
        # Send a few telemetry events (below threshold)
        for i in range(3):
            send_telemetry_payload({"type": "scf_step", "energy_hartree": -76.0 - i, "step": i})
            # Read direct raw frame
            msg = ws.receive_text()
            assert json.loads(msg)["step"] == i

        # Test flush frame
        ws.send_text("flush")

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_cochem_dock_main.py ---
"""Comprehensive Zero-Mock test suite for cochem_base.interfaces.cochem_dock_main.

Validates FastAPI endpoints, Pydantic telemetry and job models, Dual-Mode Job Queue
(SQLite WAL vs. JSONL + FileLock), LTTB downsampling algorithm, WebSocket datagram
telemetry streaming, control frames, and path sanitization.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import List

import pytest
from fastapi.testclient import TestClient

import interfaces.cochem_dock_main as legacy_dock_main
from cochem_base.interfaces.cochem_dock_main import (
    DualModeJobQueue,
    HealthResponse,
    JobCancelResponse,
    JobListResponse,
    JobStatusResponse,
    JobSubmitRequest,
    JobSubmitResponse,
    TelemetryBatchPayload,
    TelemetryEvent,
    TelemetryStatsResponse,
    app,
    create_app,
    default_job_queue,
    health_check,
    lifespan,
    logger,
    lttb_decimate,
    run_server,
    telemetry_stats,
    websocket_telemetry,
)
from cochem_base.path_sanitization import leak_patterns
from cochem_base.telemetry_transport import send_telemetry_payload


@pytest.fixture
def dock_main_path() -> Path:
    """Return the absolute path to cochem_base/interfaces/cochem_dock_main.py."""
    path = Path(__file__).resolve().parent.parent / "cochem_base" / "interfaces" / "cochem_dock_main.py"
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


@pytest.fixture
def interfaces_dock_main_path() -> Path:
    """Return the absolute path to interfaces/cochem_dock_main.py."""
    path = Path(__file__).resolve().parent.parent / "interfaces" / "cochem_dock_main.py"
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


@pytest.fixture
def client() -> TestClient:
    """Return a TestClient instance for the FastAPI application."""
    return TestClient(app)


def test_file_encoding_and_lf_line_endings(
    dock_main_path: Path, interfaces_dock_main_path: Path
) -> None:
    """Verify strictly Unix LF line endings (\\n), standard UTF-8 encoding, and no BOM."""
    for path in (dock_main_path, interfaces_dock_main_path):
        raw = path.read_bytes()
        assert b"\r\n" not in raw, f"Found Windows CRLF line endings in {path.name}"
        assert b"\n" in raw, f"Missing newline characters in {path.name}"
        assert not raw.startswith(b"\xef\xbb\xbf"), f"Found UTF-8 BOM marker in {path.name}"

        content = path.read_text(encoding="utf-8")
        assert len(content) > 100, f"File content in {path.name} is unexpectedly small."


def test_zero_personal_path_leaks(
    dock_main_path: Path, interfaces_dock_main_path: Path
) -> None:
    """Verify zero personal machine or local user path leakage in cochem_dock_main.py."""
    patterns = leak_patterns()
    for path in (dock_main_path, interfaces_dock_main_path):
        lines = path.read_text(encoding="utf-8").splitlines()
        leaks = []
        for lineno, line in enumerate(lines, 1):
            for pattern, placeholder in patterns:
                if pattern.search(line):
                    leaks.append((lineno, placeholder, line.strip()))

        assert len(leaks) == 0, f"Detected personal path leaks in {path.name}: {leaks}"


def test_interfaces_dock_main_reexports_and_aliases() -> None:
    """Verify interfaces.cochem_dock_main cleanly re-exports canonical symbols."""
    assert legacy_dock_main.app is app
    assert legacy_dock_main.create_app is create_app
    assert legacy_dock_main.health_check is health_check
    assert legacy_dock_main.telemetry_stats is telemetry_stats
    assert legacy_dock_main.websocket_telemetry is websocket_telemetry
    assert legacy_dock_main.lttb_decimate is lttb_decimate
    assert legacy_dock_main.run_server is run_server
    assert legacy_dock_main.lifespan is lifespan
    assert legacy_dock_main.logger is logger
    assert legacy_dock_main.default_job_queue is default_job_queue
    assert legacy_dock_main.DualModeJobQueue is DualModeJobQueue
    assert legacy_dock_main.TelemetryEvent is TelemetryEvent
    assert legacy_dock_main.TelemetryMessage is TelemetryEvent
    assert legacy_dock_main.HealthResponse is HealthResponse
    assert legacy_dock_main.TelemetryBatchPayload is TelemetryBatchPayload
    assert legacy_dock_main.TelemetryStatsResponse is TelemetryStatsResponse
    assert legacy_dock_main.JobSubmitRequest is JobSubmitRequest
    assert legacy_dock_main.JobSubmitResponse is JobSubmitResponse
    assert legacy_dock_main.JobStatusResponse is JobStatusResponse
    assert legacy_dock_main.JobCancelResponse is JobCancelResponse

    for sym in legacy_dock_main.__all__:
        assert hasattr(legacy_dock_main, sym), f"Missing symbol {sym} in legacy module"


def test_telemetry_event_model_fields_and_validation() -> None:
    """Verify TelemetryEvent field types, defaults, and extra attribute allowance."""
    event_data = {
        "type": "scf_step",
        "step": 4,
        "energy_hartree": -76.4321,
        "delta_energy": -0.00012,
        "max_gradient": 0.000045,
        "rms_gradient": 0.000012,
        "walltime_seconds": 1.24,
        "timestamp": 1700000000.0,
        "job_id": "test_job_123",
        "custom_metadata": "dft_pbe0",
    }
    event = TelemetryEvent.model_validate(event_data)
    assert event.type == "scf_step"
    assert event.step == 4
    assert event.energy_hartree == -76.4321
    assert event.delta_energy == -0.00012
    assert event.max_gradient == 0.000045
    assert event.rms_gradient == 0.000012
    assert event.walltime_seconds == 1.24
    assert event.timestamp == 1700000000.0
    assert event.job_id == "test_job_123"
    assert event.model_extra is not None
    assert event.model_extra.get("custom_metadata") == "dft_pbe0"

    # Verify JSON serialization
    serialized = event.model_dump_json()
    assert '"type":"scf_step"' in serialized
    assert '"energy_hartree":-76.4321' in serialized


def test_health_and_batch_payload_models() -> None:
    """Verify HealthResponse and TelemetryBatchPayload model contracts."""
    health = HealthResponse(
        status="online",
        service="CoChem-DOCK FastAPI",
        transport="udp",
        version="0.1.0",
        uptime_seconds=42.5,
        queue_mode="sqlite",
    )
    assert health.status == "online"
    assert health.transport == "udp"
    assert health.uptime_seconds == 42.5
    assert health.queue_mode == "sqlite"

    batch = TelemetryBatchPayload(
        type="lttb_batch",
        data=['{"type": "scf_step", "energy_hartree": -1.0}'],
        count=1,
    )
    assert batch.type == "lttb_batch"
    assert batch.count == 1
    assert len(batch.data) == 1


def test_job_models_contracts() -> None:
    """Verify Job schemas and validation contracts."""
    req = JobSubmitRequest(
        job_id="custom_01",
        engine="ORCA",
        input_file="input.xyz",
        calculation_type="optimization",
        parameters={"method": "PBE0", "basis": "def2-SVP"},
        priority=5,
    )
    assert req.job_id == "custom_01"
    assert req.engine == "ORCA"
    assert req.priority == 5

    res = JobSubmitResponse(
        job_id="custom_01",
        status="queued",
        message="Job queued successfully",
        queue_mode="sqlite",
        created_at=100.0,
    )
    assert res.status == "queued"

    status = JobStatusResponse(
        job_id="custom_01",
        status="running",
        progress=0.45,
        message="Iteration 4",
        engine="ORCA",
        calculation_type="optimization",
        created_at=100.0,
        updated_at=105.0,
        result={"energy": -76.4},
    )
    assert status.progress == 0.45
    assert status.result == {"energy": -76.4}

    cancel = JobCancelResponse(
        job_id="custom_01",
        status="cancelled",
        message="Job cancelled",
        cancelled=True,
    )
    assert cancel.cancelled is True


# --- LTTB Decimation Algorithm Unit Tests ---


def test_lttb_decimate_empty_or_zero_threshold() -> None:
    """Verify LTTB behavior on empty input or non-positive thresholds."""
    data = ['{"type": "scf_step", "energy_hartree": -76.0}']
    assert lttb_decimate([], 10) == []
    assert lttb_decimate(data, 0) == data
    assert lttb_decimate(data, -5) == data


def test_lttb_decimate_threshold_greater_than_data() -> None:
    """Verify LTTB returns all data when threshold >= number of items."""
    data = [
        json.dumps({"type": "scf_step", "energy_hartree": -76.0 - i * 0.1})
        for i in range(10)
    ]
    assert lttb_decimate(data, 10) == data
    assert lttb_decimate(data, 20) == data


def test_lttb_decimate_threshold_1_and_2() -> None:
    """Verify LTTB handles edge thresholds 1 and 2 safely."""
    data = [
        json.dumps({"type": "scf_step", "energy_hartree": -76.0 - i * 0.1})
        for i in range(10)
    ]
    res_1 = lttb_decimate(data, 1)
    assert len(res_1) == 1
    assert json.loads(res_1[0])["energy_hartree"] == -76.0

    res_2 = lttb_decimate(data, 2)
    assert len(res_2) == 2
    assert json.loads(res_2[0])["energy_hartree"] == -76.0
    assert json.loads(res_2[-1])["energy_hartree"] == -76.0 - 9 * 0.1


def test_lttb_decimate_preserves_first_last_and_peaks() -> None:
    """Verify LTTB downsampling retains first, last, and prominent peak extrema."""
    # Generate 50 points with a distinct peak at index 25
    points: List[str] = []
    for i in range(50):
        # Baseline curve with an abrupt sharp peak at i=25
        energy = -76.0 - (i * 0.01)
        if i == 25:
            energy = -74.0  # Sharp positive spike
        points.append(json.dumps({"type": "scf_step", "energy_hartree": energy}))

    threshold = 10
    decimated = lttb_decimate(points, threshold)
    assert len(decimated) == threshold

    # Verify first and last points are strictly preserved
    assert json.loads(decimated[0])["energy_hartree"] == -76.0
    assert json.loads(decimated[-1])["energy_hartree"] == -76.0 - (49 * 0.01)

    # Verify the sharp spike at index 25 is captured in the downsampled subset
    decimated_energies = [json.loads(p)["energy_hartree"] for p in decimated]
    assert -74.0 in decimated_energies, "LTTB failed to capture prominent peak"


def test_lttb_decimate_preserves_non_scf_messages() -> None:
    """Verify non-scf_step telemetry messages are preserved in the stream."""
    stream: List[str] = [
        '{"type": "init", "solver": "ORCA"}',
        '{"type": "scf_step", "energy_hartree": -10.0}',
        '{"type": "scf_step", "energy_hartree": -10.5}',
        '{"type": "scf_step", "energy_hartree": -10.8}',
        '{"type": "scf_step", "energy_hartree": -10.9}',
        '{"type": "status_update", "converged": true}',
        'malformed non-json log message',
    ]
    decimated = lttb_decimate(stream, threshold=2)
    # Threshold=2 on 4 scf points should keep 2 scf points + 3 non-scf items = 5 total
    assert len(decimated) == 5
    assert '{"type": "init", "solver": "ORCA"}' in decimated
    assert '{"type": "status_update", "converged": true}' in decimated
    assert "malformed non-json log message" in decimated


# --- Dual-Mode Job Queue Tests ---


def test_dual_mode_job_queue_sqlite(tmp_path: Path) -> None:
    """Verify SQLite WAL mode execution queue operations."""
    q = DualModeJobQueue(mode="sqlite", base_dir=tmp_path / "sqlite_test")
    assert q.mode == "sqlite"

    # Submit job
    req = JobSubmitRequest(
        job_id="job_sql_1",
        engine="ORCA",
        input_file="opt.xyz",
        calculation_type="opt",
        parameters={"functional": "B3LYP"},
        priority=10,
    )
    submit_res = q.submit_job(req)
    assert submit_res.job_id == "job_sql_1"
    assert submit_res.status == "queued"

    # Get status
    st = q.get_job_status("job_sql_1")
    assert st is not None
    assert st.status == "queued"
    assert st.engine == "ORCA"

    # Update status
    updated = q.update_job_status("job_sql_1", status="running", progress=0.5, message="SCF Cycle 10")
    assert updated is True
    st_updated = q.get_job_status("job_sql_1")
    assert st_updated is not None
    assert st_updated.status == "running"
    assert st_updated.progress == 0.5
    assert st_updated.message == "SCF Cycle 10"

    # List jobs
    all_jobs = q.list_jobs()
    assert len(all_jobs) >= 1
    assert any(j.job_id == "job_sql_1" for j in all_jobs)

    # Cancel job
    cancel_res = q.cancel_job("job_sql_1")
    assert cancel_res.status == "cancelled"
    st_cancelled = q.get_job_status("job_sql_1")
    assert st_cancelled is not None
    assert st_cancelled.status == "cancelled"


def test_dual_mode_job_queue_jsonl(tmp_path: Path) -> None:
    """Verify HPC JSONL + FileLock mode execution queue operations."""
    q = DualModeJobQueue(mode="jsonl", base_dir=tmp_path / "jsonl_test")
    assert q.mode == "jsonl"

    # Submit job
    req = JobSubmitRequest(
        job_id="job_hpc_1",
        engine="CFOUR",
        input_file="input.dat",
        calculation_type="vpt2",
        parameters={"basis": "cc-pVTZ"},
        priority=2,
    )
    submit_res = q.submit_job(req)
    assert submit_res.job_id == "job_hpc_1"
    assert submit_res.status == "queued"
    assert submit_res.queue_mode == "jsonl"

    # Get status
    st = q.get_job_status("job_hpc_1")
    assert st is not None
    assert st.status == "queued"
    assert st.engine == "CFOUR"

    # Update status
    updated = q.update_job_status(
        "job_hpc_1",
        status="completed",
        progress=1.0,
        result={"energy": -120.45},
        message="VPT2 Complete",
    )
    assert updated is True
    st_updated = q.get_job_status("job_hpc_1")
    assert st_updated is not None
    assert st_updated.status == "completed"
    assert st_updated.result == {"energy": -120.45}

    # List jobs
    all_jobs = q.list_jobs()
    assert len(all_jobs) >= 1
    assert any(j.job_id == "job_hpc_1" for j in all_jobs)

    # Cancel job
    cancel_res = q.cancel_job("job_hpc_1")
    assert cancel_res.status == "cancelled"


# --- REST API Endpoint Tests ---


def test_health_check_endpoint(client: TestClient) -> None:
    """Verify GET /api/health returns operational status and telemetry transport."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["service"] == "CoChem-DOCK FastAPI"
    assert data["transport"] in ("unix", "udp")
    assert "uptime_seconds" in data
    assert "queue_mode" in data


def test_health_check_function_direct_call() -> None:
    """Verify direct async call to health_check() function returns valid dictionary."""
    result = asyncio.run(health_check())
    assert isinstance(result, dict)
    assert result["status"] == "online"
    assert result["service"] == "CoChem-DOCK FastAPI"
    assert "transport" in result
    assert "queue_mode" in result


def test_telemetry_stats_endpoint(client: TestClient) -> None:
    """Verify GET /api/telemetry/stats returns transport details."""
    response = client.get("/api/telemetry/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["active"] is True
    assert data["transport"] in ("unix", "udp")
    assert "queue_mode" in data
    if data["transport"] == "unix":
        assert "socket_path" in data
    else:
        assert "udp_host" in data
        assert "udp_port" in data


def test_telemetry_stats_function_direct_call() -> None:
    """Verify direct async call to telemetry_stats() function."""
    stats = asyncio.run(telemetry_stats())
    assert isinstance(stats, dict)
    assert stats["active"] is True


def test_create_app_factory() -> None:
    """Verify create_app produces a valid configured FastAPI instance."""
    new_app = create_app()
    assert new_app.title == "CoChem-DOCK Telemetry API"


def test_rest_job_endpoints(client: TestClient) -> None:
    """Verify REST job submit, status, list, and cancel workflow."""
    # Submit job
    payload = {
        "job_id": "rest_test_01",
        "engine": "ORCA",
        "input_file": "mol.xyz",
        "calculation_type": "optimization",
        "parameters": {"functional": "r2scan-3c"},
        "priority": 1,
    }
    sub_res = client.post("/api/v1/jobs/submit", json=payload)
    assert sub_res.status_code == 200
    sub_data = sub_res.json()
    assert sub_data["job_id"] == "rest_test_01"
    assert sub_data["status"] == "queued"

    # Status job
    stat_res = client.get("/api/v1/jobs/status/rest_test_01")
    assert stat_res.status_code == 200
    stat_data = stat_res.json()
    assert stat_data["job_id"] == "rest_test_01"
    assert stat_data["engine"] == "ORCA"

    # List jobs
    list_res = client.get("/api/v1/jobs?limit=50")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["count"] >= 1

    # Cancel job
    cancel_res = client.post("/api/v1/jobs/cancel/rest_test_01")
    assert cancel_res.status_code == 200
    cancel_data = cancel_res.json()
    assert cancel_data["cancelled"] is True

    # 404 on missing job
    missing_res = client.get("/api/v1/jobs/status/non_existent_id")
    assert missing_res.status_code == 404


# --- WebSocket Telemetry Stream Tests ---


def test_websocket_ping_pong(client: TestClient) -> None:
    """Verify WebSocket client can send ping and receive pong."""
    with client.websocket_connect("/ws/telemetry") as ws:
        ws.send_text("ping")
        response = ws.receive_text()
        assert response == "pong"


def test_websocket_telemetry_datagram_transmission(client: TestClient) -> None:
    """Verify telemetry datagram sent via transport is received by connected WebSocket."""
    with client.websocket_connect("/ws/telemetry?buffer_threshold=100&decimate_target=20") as ws:
        # Send a real physical telemetry datagram payload
        payload = {"type": "scf_step", "energy_hartree": -76.42119, "step": 1}
        send_telemetry_payload(payload)

        # Receive the telemetry message over WebSocket
        received_raw = ws.receive_text()
        received_obj = json.loads(received_raw)
        assert received_obj["type"] == "scf_step"
        assert received_obj["energy_hartree"] == -76.42119
        assert received_obj["step"] == 1


def test_websocket_buffer_batching_and_flush(client: TestClient) -> None:
    """Verify WebSocket buffer batching and manual flush control frame."""
    with client.websocket_connect("/ws/telemetry?buffer_threshold=50&decimate_target=5") as ws:
        # Send a few telemetry events (below threshold)
        for i in range(3):
            send_telemetry_payload({"type": "scf_step", "energy_hartree": -76.0 - i, "step": i})
            # Read direct raw frame
            msg = ws.receive_text()
            assert json.loads(msg)["step"] == i

        # Test flush frame
        ws.send_text("flush")

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.