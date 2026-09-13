"""Structured telemetry record specification and data contract.

Captures tool execution metrics, operating system process identifiers,
wall-clock duration, memory consumption, return codes, and cryptographic
hashes.

Governed by Method Matrix v4.2 and Anti-Spoofing Protocol v4.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union
import uuid

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


GENESIS_HASH: str = "0000000000000000000000000000000000000000000000000000000000000000"


def get_current_iso_timestamp() -> str:
    """Return high-precision UTC timestamp formatted as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class TimestampWindow:
    """Execution window timestamps recorded in UTC."""

    start_iso: str
    end_iso: str
    start_epoch_ms: int = 0
    end_epoch_ms: int = 0

    def __getitem__(self, item: str) -> str:
        """Allow dict-style key access for backward compatibility."""
        if item in ("start", "start_iso"):
            return self.start_iso
        if item in ("end", "end_iso"):
            return self.end_iso
        raise KeyError(item)

    def get(self, item: str, default: Any = None) -> Any:
        """Allow dict-style get access."""
        try:
            return self[item]
        except KeyError:
            return default

    @classmethod
    def from_datetimes(
        cls, start_dt: datetime, end_dt: datetime
    ) -> TimestampWindow:
        """Construct a TimestampWindow from datetime objects."""
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=timezone.utc)

        start_iso = start_dt.isoformat()
        end_iso = end_dt.isoformat()
        start_ms = int(start_dt.timestamp() * 1000)
        end_ms = int(end_dt.timestamp() * 1000)
        return cls(
            start_iso=start_iso,
            end_iso=end_iso,
            start_epoch_ms=start_ms,
            end_epoch_ms=end_ms,
        )

    @classmethod
    def from_iso_strings(
        cls, start_iso: str, end_iso: str
    ) -> TimestampWindow:
        """Construct a TimestampWindow from ISO 8601 formatted strings."""
        start_dt = datetime.fromisoformat(start_iso)
        end_dt = datetime.fromisoformat(end_iso)
        start_ms = int(start_dt.timestamp() * 1000)
        end_ms = int(end_dt.timestamp() * 1000)
        return cls(
            start_iso=start_iso,
            end_iso=end_iso,
            start_epoch_ms=start_ms,
            end_epoch_ms=end_ms,
        )

    @classmethod
    def now(cls) -> TimestampWindow:
        """Create a TimestampWindow representing the current instant."""
        current_dt = datetime.now(timezone.utc)
        return cls.from_datetimes(current_dt, current_dt)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the timestamp window to a dictionary."""
        return {
            "start_iso": self.start_iso,
            "end_iso": self.end_iso,
            "start_epoch_ms": self.start_epoch_ms,
            "end_epoch_ms": self.end_epoch_ms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TimestampWindow:
        """Deserialize from dictionary payload."""
        start_iso = str(data.get("start_iso", data.get("start", "")))
        end_iso = str(data.get("end_iso", data.get("end", start_iso)))
        start_ms = int(data.get("start_epoch_ms", 0))
        end_ms = int(data.get("end_epoch_ms", start_ms))

        if not start_iso:
            return cls.now()

        return cls(
            start_iso=start_iso,
            end_iso=end_iso,
            start_epoch_ms=start_ms,
            end_epoch_ms=end_ms,
        )


@dataclass(frozen=True, slots=True)
class TelemetryRecord:
    """Immutable telemetry data structure capturing tool execution metrics.

    Captures tool name, command string, PID, execution latency, memory footprint,
    exit code, and timestamps.
    """

    tool_name: str
    command_string: str
    pid: int
    execution_latency: float  # In seconds
    memory_footprint: int  # In bytes (RSS)
    exit_code: int
    timestamps: Optional[Any] = None
    start_timestamp: str = ""
    end_timestamp: str = ""
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    prev_hash: str = GENESIS_HASH
    record_hash: str = field(default="")
    ast_diff_length: int = 0
    stdout_tail: str = ""
    stderr_tail: str = ""
    seq: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate fields and calculate deterministic record hash."""
        # Tool name validation
        if not isinstance(self.tool_name, str) or not self.tool_name.strip():
            raise ValueError("tool_name must be a non-empty string")

        # Command string validation
        if not isinstance(self.command_string, str):
            raise TypeError("command_string must be a string")

        # PID validation
        if not isinstance(self.pid, int) or self.pid < 0:
            raise ValueError(f"pid must be a non-negative integer, got {self.pid}")

        # Execution latency validation
        if not isinstance(self.execution_latency, (int, float)) or self.execution_latency < 0.0:
            raise ValueError(f"execution_latency must be non-negative, got {self.execution_latency}")

        # Memory footprint validation
        if not isinstance(self.memory_footprint, (int, float)) or self.memory_footprint < 0:
            raise ValueError(f"memory_footprint must be a non-negative integer, got {self.memory_footprint}")

        # Exit code validation
        if not isinstance(self.exit_code, int):
            raise TypeError(f"exit_code must be an integer, got {type(self.exit_code)}")

        # Timestamp coercion and harmonization
        raw_ts = self.timestamps
        if isinstance(raw_ts, TimestampWindow):
            coerced_ts = raw_ts
        elif isinstance(raw_ts, dict):
            coerced_ts = TimestampWindow.from_dict(raw_ts)
        elif isinstance(raw_ts, (list, tuple)):
            if len(raw_ts) >= 2:
                coerced_ts = TimestampWindow.from_iso_strings(str(raw_ts[0]), str(raw_ts[1]))
            elif len(raw_ts) == 1:
                coerced_ts = TimestampWindow.from_iso_strings(str(raw_ts[0]), str(raw_ts[0]))
            else:
                coerced_ts = TimestampWindow.now()
        elif isinstance(raw_ts, str) and raw_ts.strip():
            coerced_ts = TimestampWindow.from_iso_strings(raw_ts, raw_ts)
        elif self.start_timestamp and self.end_timestamp:
            try:
                coerced_ts = TimestampWindow.from_iso_strings(self.start_timestamp, self.end_timestamp)
            except Exception as err:
                raise ValueError(f"start_timestamp or end_timestamp is not valid ISO 8601: {err}") from err
        else:
            coerced_ts = TimestampWindow.now()

        object.__setattr__(self, "timestamps", coerced_ts)
        object.__setattr__(self, "start_timestamp", coerced_ts.start_iso)
        object.__setattr__(self, "end_timestamp", coerced_ts.end_iso)

        # Validate start and end timestamps
        try:
            datetime.fromisoformat(self.start_timestamp)
        except Exception as err:
            raise ValueError(f"start_timestamp is not valid ISO 8601: {self.start_timestamp}") from err

        try:
            datetime.fromisoformat(self.end_timestamp)
        except Exception as err:
            raise ValueError(f"end_timestamp is not valid ISO 8601: {self.end_timestamp}") from err

        # Ensure execution latency is float
        if isinstance(self.execution_latency, int):
            object.__setattr__(self, "execution_latency", float(self.execution_latency))

        # Ensure memory footprint is int
        if isinstance(self.memory_footprint, float):
            object.__setattr__(self, "memory_footprint", int(self.memory_footprint))

        # Ensure record_id
        if not self.record_id:
            object.__setattr__(self, "record_id", str(uuid.uuid4()))

        # Compute deterministic SHA-256 hash if not explicitly provided
        if not self.record_hash:
            computed = self._calculate_canonical_hash()
            object.__setattr__(self, "record_hash", computed)

    def _calculate_canonical_hash(self) -> str:
        """Compute SHA-256 hash across canonical serialized representation."""
        canonical_dict = {
            "record_id": self.record_id,
            "tool_name": self.tool_name,
            "command_string": self.command_string,
            "pid": self.pid,
            "execution_latency": f"{self.execution_latency:.6f}",
            "memory_footprint": self.memory_footprint,
            "exit_code": self.exit_code,
            "timestamps": self.timestamps.to_dict(),
            "prev_hash": self.prev_hash,
            "stdout_tail": self.stdout_tail,
            "stderr_tail": self.stderr_tail,
        }
        canonical_str = json.dumps(canonical_dict, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

    def verify_integrity(self) -> bool:
        """Verify that record_hash matches the cryptographic digest of contents."""
        return self.record_hash == self._calculate_canonical_hash()

    @property
    def is_success(self) -> bool:
        """Return True if command finished with exit code 0."""
        return self.exit_code == 0

    @property
    def success(self) -> bool:
        """Boolean indicator verifying nominal exit status."""
        return self.exit_code == 0

    @property
    def execution_latency_ms(self) -> float:
        """Return execution latency in milliseconds."""
        return round(self.execution_latency * 1000.0, 3)

    @property
    def memory_footprint_mb(self) -> float:
        """Return memory footprint in megabytes."""
        return round(self.memory_footprint / (1024.0 * 1024.0), 3)

    @property
    def timestamp(self) -> str:
        """Return primary timestamp (start ISO 8601)."""
        return self.start_timestamp

    def to_dict(self) -> Dict[str, Any]:
        """Serialize record to dictionary."""
        return {
            "record_id": self.record_id,
            "tool_name": self.tool_name,
            "command_string": self.command_string,
            "pid": self.pid,
            "execution_latency": self.execution_latency,
            "execution_latency_ms": self.execution_latency_ms,
            "memory_footprint": self.memory_footprint,
            "memory_footprint_mb": self.memory_footprint_mb,
            "exit_code": self.exit_code,
            "timestamps": self.timestamps.to_dict(),
            "start_timestamp": self.start_timestamp,
            "end_timestamp": self.end_timestamp,
            "prev_hash": self.prev_hash,
            "record_hash": self.record_hash,
            "ast_diff_length": self.ast_diff_length,
            "stdout_tail": self.stdout_tail,
            "stderr_tail": self.stderr_tail,
            "seq": self.seq,
            "metadata": self.metadata,
        }

    def to_columnar_dict(self) -> Dict[str, List[Any]]:
        """Convert to single-row columnar dict for Apache Parquet ingestion (Task 1.04)."""
        return {
            "record_id": [self.record_id],
            "tool_name": [self.tool_name],
            "command_string": [self.command_string],
            "pid": [self.pid],
            "execution_latency": [float(self.execution_latency)],
            "execution_latency_ms": [float(self.execution_latency_ms)],
            "memory_footprint": [int(self.memory_footprint)],
            "memory_footprint_mb": [float(self.memory_footprint_mb)],
            "exit_code": [int(self.exit_code)],
            "start_timestamp": [self.start_timestamp],
            "end_timestamp": [self.end_timestamp],
            "prev_hash": [self.prev_hash],
            "record_hash": [self.record_hash],
            "ast_diff_length": [self.ast_diff_length],
            "stdout_tail": [self.stdout_tail],
            "stderr_tail": [self.stderr_tail],
            "seq": [self.seq],
            "metadata_json": [json.dumps(self.metadata, ensure_ascii=False)],
        }

    def to_json(self) -> str:
        """Serialize record to formatted JSON string."""
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TelemetryRecord:
        """Deserialize from dictionary payload."""
        timestamps_raw = data.get("timestamps")
        if isinstance(timestamps_raw, dict):
            timestamps = TimestampWindow.from_dict(timestamps_raw)
        elif "start_timestamp" in data and "end_timestamp" in data:
            timestamps = TimestampWindow.from_iso_strings(
                str(data["start_timestamp"]), str(data["end_timestamp"])
            )
        elif isinstance(timestamps_raw, TimestampWindow):
            timestamps = timestamps_raw
        else:
            timestamps = TimestampWindow.now()

        record = cls(
            tool_name=str(data["tool_name"]),
            command_string=str(data["command_string"]),
            pid=int(data["pid"]),
            execution_latency=float(data["execution_latency"]),
            memory_footprint=int(data["memory_footprint"]),
            exit_code=int(data["exit_code"]),
            timestamps=timestamps,
            start_timestamp=str(data.get("start_timestamp", timestamps.start_iso)),
            end_timestamp=str(data.get("end_timestamp", timestamps.end_iso)),
            record_id=str(data.get("record_id", uuid.uuid4())),
            prev_hash=str(data.get("prev_hash", GENESIS_HASH)),
            record_hash=str(data.get("record_hash", "")),
            ast_diff_length=int(data.get("ast_diff_length", 0)),
            stdout_tail=str(data.get("stdout_tail", "")),
            stderr_tail=str(data.get("stderr_tail", "")),
            seq=int(data.get("seq", 0)),
            metadata=dict(data.get("metadata", {})),
        )
        return record

    @classmethod
    def from_json(cls, raw_json: str) -> TelemetryRecord:
        """Deserialize record from JSON string."""
        data = json.loads(raw_json)
        return cls.from_dict(data)

    @classmethod
    def capture(
        cls,
        tool_name: str,
        command: Union[str, Sequence[str]],
        cwd: Optional[str] = None,
        timeout: float = 60.0,
        prev_hash: str = GENESIS_HASH,
        max_tail_chars: int = 4096,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TelemetryRecord:
        """Execute a physical command in real OS process and construct verified TelemetryRecord.

        Captures real OS PID, measures execution latency via high-resolution timer,
        records memory RSS via psutil, and extracts returncode.
        """
        if isinstance(command, str):
            cmd_str = command
            cmd_args = command
            use_shell = True
        else:
            cmd_str = " ".join(command)
            cmd_args = list(command)
            use_shell = False

        start_dt = datetime.now(timezone.utc)
        start_perf = time.perf_counter()

        proc = subprocess.Popen(
            cmd_args,
            shell=use_shell,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        assigned_pid = proc.pid
        peak_memory_bytes = 0

        # Query physical memory utilization
        if HAS_PSUTIL:
            try:
                ps_proc = psutil.Process(assigned_pid)
                mem_info = ps_proc.memory_info()
                peak_memory_bytes = max(peak_memory_bytes, mem_info.rss)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                peak_memory_bytes = 0

        try:
            stdout_raw, stderr_raw = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout_raw, stderr_raw = proc.communicate()
            exit_code = -9
        else:
            exit_code = proc.returncode

        end_perf = time.perf_counter()
        end_dt = datetime.now(timezone.utc)
        latency = max(0.0, end_perf - start_perf)

        # Final memory query if process still registered or fallback
        if HAS_PSUTIL and peak_memory_bytes == 0:
            try:
                current_proc = psutil.Process(os.getpid())
                peak_memory_bytes = current_proc.memory_info().rss
            except Exception:
                peak_memory_bytes = 0

        # Safe tail truncation to protect token context
        stdout_tail = stdout_raw[-max_tail_chars:] if len(stdout_raw) > max_tail_chars else stdout_raw
        stderr_tail = stderr_raw[-max_tail_chars:] if len(stderr_raw) > max_tail_chars else stderr_raw

        ts_window = TimestampWindow.from_datetimes(start_dt, end_dt)

        return cls(
            tool_name=tool_name,
            command_string=cmd_str,
            pid=assigned_pid,
            execution_latency=latency,
            memory_footprint=peak_memory_bytes,
            exit_code=exit_code,
            timestamps=ts_window,
            start_timestamp=ts_window.start_iso,
            end_timestamp=ts_window.end_iso,
            prev_hash=prev_hash,
            stdout_tail=stdout_tail,
            stderr_tail=stderr_tail,
            metadata=metadata or {},
        )


class PhysicalExecutionProfiler:
    """
    Context manager performing genuine OS resource and timing profiling.
    Zero mocks: directly queries OS PID, time.perf_counter, and psutil RSS memory.
    """

    def __init__(self, tool_name: str, command_string: str, seq: int = 0) -> None:
        self.tool_name = tool_name
        self.command_string = command_string
        self.seq = seq
        self.start_perf: float = 0.0
        self.start_dt: Optional[datetime] = None
        self.pid: int = os.getpid()

    def __enter__(self) -> PhysicalExecutionProfiler:
        self.start_perf = time.perf_counter()
        self.start_dt = datetime.now(timezone.utc)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        return None

    def create_record(
        self,
        exit_code: int,
        stdout_text: str = "",
        stderr_text: str = "",
        max_tail_chars: int = 2000,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TelemetryRecord:
        """Create TelemetryRecord from the monitored execution window."""
        end_perf = time.perf_counter()
        end_dt = datetime.now(timezone.utc)
        latency = max(0.0, end_perf - self.start_perf)
        start_datetime = self.start_dt or end_dt
        ts_window = TimestampWindow.from_datetimes(start_datetime, end_dt)

        peak_memory_bytes = 0
        if HAS_PSUTIL:
            try:
                proc = psutil.Process(self.pid)
                peak_memory_bytes = int(proc.memory_info().rss)
            except Exception:
                peak_memory_bytes = 0

        # Enforce log tail-truncation to prevent context saturation (Directive 3)
        truncated_stdout = stdout_text[-max_tail_chars:] if len(stdout_text) > max_tail_chars else stdout_text
        truncated_stderr = stderr_text[-max_tail_chars:] if len(stderr_text) > max_tail_chars else stderr_text

        meta = dict(metadata or {})
        if self.seq > 0:
            meta["seq"] = self.seq

        return TelemetryRecord(
            tool_name=self.tool_name,
            command_string=self.command_string,
            pid=self.pid,
            execution_latency=latency,
            memory_footprint=peak_memory_bytes,
            exit_code=exit_code,
            timestamps=ts_window,
            start_timestamp=ts_window.start_iso,
            end_timestamp=ts_window.end_iso,
            stdout_tail=truncated_stdout,
            stderr_tail=truncated_stderr,
            seq=self.seq,
            metadata=meta,
        )
