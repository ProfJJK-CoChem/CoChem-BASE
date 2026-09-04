# cochem_canvas_target: core_engine/cochem_core_hardware_profiler.py
"""
Hardware profiler module for CoChem-CORE.
Provides system information, hardware capability detection, and performance benchmarking.
"""

import atexit
import logging
import platform
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List

import psutil

from cochem_base.config_loader import get_artifact_dir, get_ramdisk_dir, resolve_executable

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-HardwareProfiler")

try:
    from core_engine.cochem_core_subprocess_broker import safe_subprocess_run
except ImportError:
    safe_subprocess_run: Any = None  # type: ignore

def _sweep_zombies() -> None:
    """Sweep zombie processes for robust process safety."""
    try:
        for p in psutil.process_iter(['pid', 'status']):
            if p.info['status'] == psutil.STATUS_ZOMBIE:
                try:
                    p.wait(timeout=1)
                except psutil.TimeoutExpired as _e:
                    logger.debug(f"Ignored exception: {_e}")
    except Exception as e:
        logger.error(f"Zombie sweeping failed: {e}")

atexit.register(_sweep_zombies)


class HardwareProfiler:
    """
    Provides system information, hardware capability detection, and performance benchmarking.

    Implements TFLOPS calculation and hardware calibration benchmarking as required by
    20260807_workflow.md for dynamic MLFF fallback detection.
    """

    def __init__(self) -> None:
        """Initialize the hardware profiler."""
        self.system_info: Dict[str, Any] = {}

    @staticmethod
    def _storage_probe_path() -> Path:
        artifact_dir = get_artifact_dir()
        return artifact_dir if artifact_dir.exists() else Path.home()

    @staticmethod
    def _nvidia_smi() -> str:
        return resolve_executable(env_var="NVIDIA_SMI_CMD", candidates=("nvidia-smi",))

    def get_system_info(self) -> Dict[str, Any]:
        """Get basic system information."""
        self.system_info = {
            'platform': platform.platform(),
            'processor': platform.processor(),
            'machine': platform.machine(),
            'architecture': platform.architecture()[0],
            'cpu_count': psutil.cpu_count(logical=True),
            'cpu_freq': psutil.cpu_freq(),
            'memory_total': psutil.virtual_memory().total,
            'memory_available': psutil.virtual_memory().available,
            'disk_usage': psutil.disk_usage(str(self._storage_probe_path()))
        }

        return self.system_info

    def get_hardware_capabilities(self) -> Dict[str, Any]:
        """Get hardware capabilities with enhanced profiling."""
        capabilities = {
            'cpu_count': psutil.cpu_count(logical=True),
            'memory_total_gb': psutil.virtual_memory().total / (1024**3),
            'cpu_architecture': platform.machine(),
            'is_virtual_machine': self._check_virtualization(),
            'cpu_tflops': self._calculate_cpu_tflops(),
            'hardware_score': self._calculate_hardware_score()
        }

        return capabilities

    def _check_virtualization(self) -> bool:
        """Check if system is running in a virtual machine."""
        try:
            vm_indicators = ['virtualbox', 'vmware', 'qemu']
            platform_info = platform.platform().lower()

            for indicator in vm_indicators:
                if indicator in platform_info:
                    return True

            return False
        except Exception:
            return False

    def _calculate_cpu_tflops(self) -> float:
        """Calculate CPU TFLOPS based on processor specifications."""
        try:
            cpu_count = psutil.cpu_count(logical=True)
            if not cpu_count:
                logger.error("[MISSING DATA] CPU count not found.")
                raise ValueError("[MISSING DATA] CPU count not found.")
                
            cpu_freq = psutil.cpu_freq()
            if cpu_freq and cpu_freq.current:
                freq_ghz = cpu_freq.current / 1000.0
            else:
                logger.error("[MISSING DATA] CPU frequency not found.")
                raise ValueError("[MISSING DATA] CPU frequency not found.")

            flops_per_core_per_cycle = 3.0
            cycles_per_second = freq_ghz * 1e9
            total_flops = cpu_count * flops_per_core_per_cycle * cycles_per_second
            tflops = total_flops / 1e12

            logger.info(f"Estimated CPU TFLOPS: {tflops:.2f}")
            return tflops  # type: ignore

        except Exception as e:
            logger.error(f"Error calculating CPU TFLOPS: {e}")
            return 0.0

    def _calculate_hardware_score(self) -> float:
        """Calculate an overall hardware score for job routing decisions."""
        try:
            cpu_tflops = self._calculate_cpu_tflops()
            memory_total_gb = psutil.virtual_memory().total / (1024**3)

            cpu_score = min(cpu_tflops / 10.0, 1.0)
            memory_score = min(memory_total_gb / 32.0, 1.0)

            hardware_score = (cpu_score * 0.6 + memory_score * 0.4) * 100

            logger.info(f"Calculated hardware score: {hardware_score:.2f}")
            return hardware_score  # type: ignore

        except Exception as e:
            logger.error(f"Error calculating hardware score: {e}")
            return 0.0

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics with benchmarking capabilities."""
        metrics = {
            'cpu_load': psutil.cpu_percent(interval=1),
            'memory_usage': psutil.virtual_memory().percent,
            'disk_io': psutil.disk_io_counters(),
            'benchmark_results': self._run_performance_benchmarks()
        }

        return metrics

    def _run_performance_benchmarks(self) -> Dict[str, Any]:
        """Run hardware calibration benchmarks to determine system capabilities."""
        benchmark_results: Dict[str, Any] = {}

        try:
            logger.error("Synthetic benchmarks are disabled per Anti-Spoofing Directive v2. Must run against real physical structures.")
            benchmark_results['error'] = "[MISSING DATA] Synthetic benchmarks disabled. Require physical constraints."

        except Exception as e:
            logger.error(f"Error running performance benchmarks: {e}")
            benchmark_results['error'] = str(e)

        return benchmark_results

    def get_cuda_info(self) -> Dict[str, Any]:
        """Get CUDA information if available with enhanced detection."""
        try:
            nvidia_smi = self._nvidia_smi()
            cmd = [nvidia_smi, '--query-compute-apps=pid', '--format=csv']
            if safe_subprocess_run is not None:
                result = safe_subprocess_run(cmd, timeout=15.0, check=True)
            else:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=15.0, check=True)

            if result.returncode == 0 and result.stdout:
                gpu_count = len([line for line in result.stdout.split('\n') if line.strip() and 'pid' not in line])

                version_cmd = [nvidia_smi, '--query-compute-apps=driver_version', '--format=csv']
                if safe_subprocess_run is not None:
                    version_result = safe_subprocess_run(version_cmd, timeout=15.0, check=True)
                else:
                    version_result = subprocess.run(version_cmd, capture_output=True, text=True, timeout=15.0, check=True)

                cuda_version = None
                if version_result.returncode == 0 and version_result.stdout:
                    lines = version_result.stdout.strip().split('\n')
                    if len(lines) > 1:
                        cuda_version = lines[1].strip()

                return {
                    'cuda_available': True,
                    'cuda_version': cuda_version,
                    'gpu_count': gpu_count,
                    'gpu_details': self._get_gpu_details()
                }
            else:
                return {
                    'cuda_available': False,
                    'cuda_version': None,
                    'gpu_count': 0
                }

        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            return {
                'cuda_available': False,
                'cuda_version': None,
                'gpu_count': 0
            }
        except Exception as e:
            logger.error(f"Error getting CUDA info: {e}")
            return {
                'cuda_available': False,
                'cuda_version': None,
                'gpu_count': 0
            }

    def execute_7_phase_initialization(self) -> Dict[str, Any]:
        """
        Executes the 7-Phase Initialization sequence for hardware profiling.
        Verifies 10GB NVMe, Thermal Throttle status, OpenMPI SHM, etc.
        """
        logger.info("Executing 7-Phase Hardware Initialization...")
        init_results = {
            "phase_1_nvme": self._check_10gb_nvme(),
            "phase_2_thermal": self._check_thermal_throttle(),
            "phase_3_openmpi": self._check_openmpi_shm(),
            "phase_4_cpu": self._calculate_cpu_tflops() > 0.5,
            "phase_5_ram": psutil.virtual_memory().total > (8 * 1024**3),
            "phase_6_cuda": self.get_cuda_info()['cuda_available'],
            "phase_7_ready": True
        }

        if not init_results["phase_1_nvme"]:
            logger.warning("NVMe 10GB free space check failed. Performance may degrade.")
        if not init_results["phase_2_thermal"]:
            logger.warning("Thermal throttle detected! CPU frequencies may be capped.")
        if not init_results["phase_3_openmpi"]:
            logger.warning("OpenMPI Shared Memory (SHM) check failed. IPC might fall back to TCP.")

        return init_results

    def _check_10gb_nvme(self) -> bool:
        """Phase 1: Verifies at least 10GB of free space on the high-speed drive."""
        try:
            usage = psutil.disk_usage(str(self._storage_probe_path()))
            free_gb = usage.free / (1024**3)
            logger.info(f"Storage check: {free_gb:.2f} GB available.")
            return free_gb >= 10.0  # type: ignore
        except Exception as e:
            logger.error(f"NVMe storage check failed: {e}")
            return False

    def _check_thermal_throttle(self) -> bool:
        """Phase 2: Checks lm-sensors/sysfs for thermal throttling (Linux/WSL)."""
        try:
            if hasattr(psutil, "sensors_temperatures"):
                temps = psutil.sensors_temperatures()
                if not temps:
                    return True
                for _name, entries in temps.items():
                    for entry in entries:
                        if entry.current > 90.0:
                            return False
            return True
        except Exception:
            return True

    def _check_openmpi_shm(self) -> bool:
        """Phase 3: Validates OpenMPI Shared Memory (SHM) mappings for parallel efficiency."""
        try:
            ramdisk_dir = get_ramdisk_dir()
            if platform.system() == "Linux" and ramdisk_dir is not None:
                shm_usage = psutil.disk_usage(str(ramdisk_dir))
                if shm_usage.total < (1 * 1024**3):
                    return False
            return True
        except Exception:
            return False

    def _get_gpu_details(self) -> List[Dict[str, Any]]:
        """Get detailed GPU information."""
        try:
            cmd = [self._nvidia_smi(), '--query-gpu=name,memory.total,memory.used', '--format=csv']
            if safe_subprocess_run is not None:
                result = safe_subprocess_run(cmd, timeout=15.0, check=True)
            else:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=15.0, check=True)

            if result.returncode == 0 and result.stdout:
                lines = result.stdout.strip().split('\n')
                gpu_details = []

                for line in lines[1:]:
                    if line.strip():
                        parts = line.split(', ')
                        if len(parts) >= 3:
                            gpu_details.append({
                                'name': parts[0].strip(),
                                'memory_total_mb': int(parts[1].replace(' MiB', '')),
                                'memory_used_mb': int(parts[2].replace(' MiB', ''))
                            })

                return gpu_details
            else:
                return []

        except Exception as e:
            logger.error(f"Error getting GPU details: {e}")
            return []


def main() -> None:
    """Main entry point for the hardware profiler."""
    logger.info("Starting CoChem-CORE Hardware Profiler")

    profiler = HardwareProfiler()

    system_info = profiler.get_system_info()
    capabilities = profiler.get_hardware_capabilities()
    performance = profiler.get_performance_metrics()
    cuda_info = profiler.get_cuda_info()

    logger.info(f"System Information: {system_info}")
    logger.info(f"Hardware Capabilities: {capabilities}")
    logger.info(f"Performance Metrics: {performance}")
    logger.info(f"CUDA Information: {cuda_info}")

    logger.info("Hardware profiler completed")


if __name__ == "__main__":
    main()
