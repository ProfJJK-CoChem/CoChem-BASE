#!/usr/bin/env python3
"""
CoChem-CORE Stage 2.3: Telemetry Streamer
Module: calc/cochem_calc_telemetry_stream.py
Purpose: Provides O(1) memory live-streaming of active logs with cryptographic provenance and cross-platform socket handling.
"""

import hashlib
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, Generator, Optional, Union

from pydantic import BaseModel, Field

from cochem_base.config_loader import get_artifact_dir, resolve_mapped_path
from cochem_base.telemetry_transport import send_telemetry_payload

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-TelemetryStreamer")

class StatusPayload(BaseModel):
    type: str = Field(default="status")
    state: str

class SCFStepPayload(BaseModel):
    type: str = Field(default="scf_step")
    iteration: int
    energy_hartree: float
    delta_e: float

TelemetryPayload = Union[StatusPayload, SCFStepPayload]

class TelemetryStreamer:
    def __init__(self, log_path: Union[str, Path], socket_path: Optional[Union[str, Path]] = None) -> None:
        self.log_path = Path(resolve_mapped_path(str(log_path), get_artifact_dir() / "Scratch"))
        if socket_path:
            os.environ["COCHEM_TELEMETRY_SOCKET"] = str(resolve_mapped_path(str(socket_path)))
            
        self.scf_pattern = re.compile(r"^\s*(\d+)\s+([-+]?\d+\.\d+)\s+([-+]?\d+\.\d+)")
        self.maxcore_pattern = re.compile(r"(?:MaxCore in MB|%maxcore)\s*[:]?\s*(\d+)", re.IGNORECASE)

    def _emit_to_socket(self, payload: TelemetryPayload) -> None:
        try:
            send_telemetry_payload(payload.model_dump())
        except OSError as exc:
            logger.debug(f"Telemetry endpoint unavailable: {exc}")
        except Exception as exc:
            logger.error(f"Unexpected error emitting telemetry: {exc}")

    def stream_telemetry(self, timeout_sec: int = 120, idle_timeout_sec: int = 86400) -> Generator[Dict[str, Any], None, None]:
        start_wait = time.time()
        while not self.log_path.exists():
            if time.time() - start_wait > timeout_sec:
                raise TimeoutError(f"Target log {self.log_path} failed to materialize.")
            time.sleep(0.5)

        # Hash check on log artifact (initial chunk)
        if self.log_path.suffix in (".out", ".gbw") and self.log_path.exists():
            try:
                with open(self.log_path, 'rb') as f_bin:
                    sha256 = hashlib.sha256(f_bin.read(65536)).hexdigest()
                    logger.info(f"Telemetry stream initial hash check on {self.log_path.name}: {sha256} [M]")
            except Exception as e:
                logger.warning(f"Could not hash artifact {self.log_path}: {e}")

        with open(self.log_path, 'r', encoding='utf-8', errors='replace') as f:
            last_update = time.time()
            while True:
                line = f.readline()
                if not line:
                    if time.time() - last_update > idle_timeout_sec:
                        logger.error(f"Stream idle timeout exceeded ({idle_timeout_sec}s). Aborting.")
                        payload = StatusPayload(state="ERR_TIMEOUT")
                        self._emit_to_socket(payload)
                        yield payload.model_dump()
                        break
                    time.sleep(0.1)
                    continue

                last_update = time.time()

                if "TERMINATED NORMALLY" in line:
                    payload = StatusPayload(state="COMPLETED")
                    self._emit_to_socket(payload)
                    yield payload.model_dump()
                    break
                elif "TERMINATED WITH AN ERROR" in line:
                    payload = StatusPayload(state="FAILED")
                    self._emit_to_socket(payload)
                    yield payload.model_dump()
                    break

                scf_match = self.scf_pattern.match(line)
                if scf_match:
                    payload_scf = SCFStepPayload(
                        iteration=int(scf_match.group(1)),
                        energy_hartree=float(scf_match.group(2)),
                        delta_e=float(scf_match.group(3))
                    )
                    self._emit_to_socket(payload_scf)
                    yield payload_scf.model_dump()

        # Final hash check upon completion
        if self.log_path.suffix in (".out", ".gbw") and self.log_path.exists():
            try:
                with open(self.log_path, 'rb') as f_bin:
                    file_hash = hashlib.sha256()
                    while chunk := f_bin.read(8192):
                        file_hash.update(chunk)
                    sha256_final = file_hash.hexdigest()
                    logger.info(f"Final cryptographic hash for {self.log_path.name}: {sha256_final} [M]")
            except Exception as e:
                logger.warning(f"Could not hash final artifact {self.log_path}: {e}")
