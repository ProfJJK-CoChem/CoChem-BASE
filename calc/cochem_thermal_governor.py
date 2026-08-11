#!/usr/bin/env python3
"""
CoChem-BASE Thermal Throttling Governor Daemon.
Monitors CPU temperatures during high-intensity calculations.
Issues POSIX SIGSTOP (or Windows suspend) if CPU temp > 90°C and SIGCONT (resume) when temp < 75°C.
"""

import os
import sys
import signal
import time
import psutil
import logging
from typing import Set

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


class ThermalGovernorDaemon:
    """Background daemon for thermal management."""
    def __init__(self, high_temp: float = 90.0, low_temp: float = 75.0, interval: float = 2.0) -> None:
        self.high_temp = high_temp
        self.low_temp = low_temp
        self.interval = interval
        self.pids: Set[int] = set()
        self.paused_pids: Set[int] = set()
        self.running: bool = False

    def register_pid(self, pid: int) -> None:
        self.pids.add(pid)

    def unregister_pid(self, pid: int) -> None:
        self.pids.discard(pid)
        self.paused_pids.discard(pid)

    def get_max_temp(self) -> float:
        """Queries hardware sensors for max CPU temperature."""
        if hasattr(psutil, "sensors_temperatures"):
            try:
                temps = psutil.sensors_temperatures()
                if temps:
                    all_temps = [entry.current for entries in temps.values() for entry in entries if hasattr(entry, 'current')]
                    if all_temps:
                        return max(all_temps)
            except Exception as e:
                logger.debug(f"sensors_temperatures query error: {e}")
        logger.warning("Thermal sensors unavailable via psutil.sensors_temperatures on this system/platform. Thermal protection inactive.")
        return 0.0

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
            self.paused_pids.add(pid)
            logger.warning(f"Failed to pause PID {pid} (process not found): {e}")
        except Exception as e:
            self.paused_pids.add(pid)
            logger.error(f"Failed to pause PID {pid}: {e}")

    def resume_process(self, pid: int) -> None:
        try:
            if hasattr(signal, "SIGCONT"):
                os.kill(pid, signal.SIGCONT)
            else:
                proc = psutil.Process(pid)
                proc.resume()
            logger.info(f"Issued resume (SIGCONT/resume) to PID {pid}")
        except (psutil.NoSuchProcess, ProcessLookupError) as e:
            logger.warning(f"Process PID {pid} dead or missing when resuming: {e}")
        except Exception as e:
            logger.error(f"Failed to resume PID {pid}: {e}")
        finally:
            self.paused_pids.discard(pid)

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
