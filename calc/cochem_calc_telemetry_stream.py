#!/usr/bin/env python3
"""
CoChem-CORE Stage 2.3: Telemetry Streamer
Module: calc/cochem_calc_telemetry_stream.py
Purpose: Provides O(1) memory live-streaming of active logs. 
"""
import os
import re
import time
import json
import socket
from pathlib import Path
from typing import Generator, Dict, Any

class TelemetryStreamer:
    def __init__(self, log_path: str, socket_path: str = "/tmp/cochem_telemetry.sock"):
        self.log_path = Path(log_path).resolve()
        self.socket_path = socket_path
        self.scf_pattern = re.compile(r"^\s*(\d+)\s+([-+]?\d+\.\d+)\s+([-+]?\d+\.\d+)")
        self.maxcore_pattern = re.compile(r"(?:MaxCore in MB|%maxcore)\s*[:]?\s*(\d+)", re.IGNORECASE)
        
    def _emit_to_socket(self, payload: Dict[str, Any]) -> None:
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as s:
                s.connect(self.socket_path)
                s.sendall(json.dumps(payload).encode('utf-8'))
        except (FileNotFoundError, ConnectionRefusedError):
            pass

    def stream_telemetry(self, timeout_sec: int = 120) -> Generator[Dict[str, Any], None, None]:
        start_wait = time.time()
        while not self.log_path.exists():
            if time.time() - start_wait > timeout_sec:
                raise TimeoutError(f"Target log {self.log_path} failed to materialize.")
            time.sleep(0.5)

        with open(self.log_path, 'r', encoding='utf-8', errors='replace') as f:
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.1)
                    continue
                
                if "TERMINATED NORMALLY" in line:
                    payload = {"type": "status", "state": "COMPLETED"}
                    self._emit_to_socket(payload)
                    yield payload
                    break
                elif "TERMINATED WITH AN ERROR" in line:
                    payload = {"type": "status", "state": "FAILED"}
                    self._emit_to_socket(payload)
                    yield payload
                    break
                
                scf_match = self.scf_pattern.match(line)
                if scf_match:
                    payload = {
                        "type": "scf_step",
                        "iteration": int(scf_match.group(1)),
                        "energy_hartree": float(scf_match.group(2)),
                        "delta_e": float(scf_match.group(3))
                    }
                    self._emit_to_socket(payload)
                    yield payload