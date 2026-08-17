#!/usr/bin/env python3
"""
CoChem-BASE Thermal Throttling Governor Daemon.
Monitors CPU temperatures during high-intensity calculations.
Issues POSIX SIGSTOP (or Windows suspend) if CPU temp > 90°C and SIGCONT (resume) when temp < 75°C.
"""

import logging
import os
import signal

import psutil

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


class ThermalGovernorDaemon:
    """Background daemon for thermal management."""
    def __init__(self, high_temp: float = 90.0, low_temp: float = 75.0, interval: float = 2.0) -> None:
        self.high_temp = high_temp
        self.low_temp = low_temp
        self.interval = interval
        self.pids: set[int] = set()
        self.paused_pids: set[int] = set()
        self.running: bool = False
        
        if not self._check_sensors_available():
            raise RuntimeError("[MISSING DATA] Thermal sensors are unavailable on this system/platform. Cannot enforce thermal limits.")

    def _check_sensors_available(self) -> bool:
        if not hasattr(psutil, "sensors_temperatures"):
            return False
        try:
            temps = psutil.sensors_temperatures()
            if not temps:
                return False
            all_temps = [entry.current for entries in temps.values() for entry in entries if hasattr(entry, 'current')]
            if not all_temps:
                return False
            return True
        except Exception:
            return False

    def register_pid(self, pid: int) -> None:
        self.pids.add(pid)

    def unregister_pid(self, pid: int) -> None:
        self.pids.discard(pid)
        self.paused_pids.discard(pid)

    def get_max_temp(self) -> float:
        """Queries hardware sensors for max CPU temperature."""
        if not hasattr(psutil, "sensors_temperatures"):
            raise RuntimeError("psutil.sensors_temperatures is not supported on this platform.")
        
        temps = psutil.sensors_temperatures()
        if not temps:
            raise RuntimeError("Thermal sensors returned empty data.")
            
        all_temps = [entry.current for entries in temps.values() for entry in entries if hasattr(entry, 'current')]
        if not all_temps:
            raise RuntimeError("Could not extract current temperatures from sensor data.")
            
        return float(max(all_temps))

    def pause_process(self, pid: int) -> None:
        try:
            if hasattr(signal, "SIGSTOP"):
                os.kill(pid, signal.SIGSTOP)
            else:
                proc = psutil.Process(pid)
                proc.suspend()
            self.paused_pids.add(pid)
            logger.warning(f"Issued pause (SIGSTOP/suspend) to PID {pid}")
        except (psutil.NoSuchProcess, ProcessLookupError) as e:
            logger.warning(f"Failed to pause PID {pid} (process not found): {e}. Unregistering PID.")
            self.unregister_pid(pid)
        except PermissionError as e:
            logger.error(f"Permission denied when pausing PID {pid}: {e}")
            raise

    def resume_process(self, pid: int) -> None:
        try:
            if hasattr(signal, "SIGCONT"):
                os.kill(pid, signal.SIGCONT)
            else:
                proc = psutil.Process(pid)
                proc.resume()
            logger.info(f"Issued resume (SIGCONT/resume) to PID {pid}")
            self.paused_pids.discard(pid)
        except (psutil.NoSuchProcess, ProcessLookupError) as e:
            logger.warning(f"Process PID {pid} dead or missing when resuming: {e}. Unregistering PID.")
            self.unregister_pid(pid)
        except PermissionError as e:
            logger.error(f"Permission denied when resuming PID {pid}: {e}")
            raise

    def poll(self) -> None:
        """Performs a single temperature check and action iteration."""
        cur_temp = self.get_max_temp()
        if cur_temp > self.high_temp:
            for pid in list(self.pids - self.paused_pids):
                logger.warning(f"CPU Temp {cur_temp}°C > {self.high_temp}°C! Throttling PID {pid}")
                self.pause_process(pid)
        elif cur_temp < self.low_temp and self.paused_pids:
            for pid in list(self.paused_pids):
                logger.info(f"CPU Temp cooled to {cur_temp}°C < {self.low_temp}°C. Resuming PID {pid}")
                self.resume_process(pid)


if __name__ == "__main__":
    governor = ThermalGovernorDaemon()
    logger.info(f"Thermal Governor initialized. Current CPU Max Temp: {governor.get_max_temp()}°C")
