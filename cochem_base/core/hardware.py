import os
import sys
import logging
import subprocess
import multiprocessing
import ctypes
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

try:
    from core_engine.cochem_core_subprocess_broker import safe_subprocess_run
except ImportError:
    safe_subprocess_run = None


class HardwareDiscovery:
    """Hardware discovery orchestrator for CoChem-BASE"""

    @staticmethod
    def get_cpu_cores() -> int:
        try:
            return multiprocessing.cpu_count()
        except Exception as e:
            logger.warning(f"multiprocessing.cpu_count() failed: {e}. Falling back to 1 core.")
            return 1

    @staticmethod
    def get_gpu_availability() -> Dict[str, Any]:
        devices: List[Dict[str, Any]] = []
        available = False
        fp64_capable = False

        # Method 1: PyTorch check
        try:
            import torch
            if torch.cuda.is_available():
                available = True
                for i in range(torch.cuda.device_count()):
                    props = torch.cuda.get_device_properties(i)
                    cap = (props.major, props.minor)
                    is_fp64 = cap[0] >= 7  # Volta/Ampere/Hopper/Ada support FP64
                    if is_fp64:
                        fp64_capable = True
                    devices.append({
                        "id": i,
                        "name": props.name,
                        "vram_gb": round(props.total_memory / (1024.**3), 2),
                        "compute_capability": f"{cap[0]}.{cap[1]}",
                        "fp64_capable": is_fp64
                    })
                return {"available": available, "fp64_capable": fp64_capable, "devices": devices}
        except ImportError as e:
            logger.debug(f"PyTorch unavailable for GPU check: {e}")
        except Exception as e:
            logger.warning(f"PyTorch GPU check failed: {e}")

        # Method 2: pynvml check
        try:
            import pynvml
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            if device_count > 0:
                available = True
                for i in range(device_count):
                    handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                    name = pynvml.nvmlDeviceGetName(handle)
                    if isinstance(name, bytes):
                        name = name.decode("utf-8")
                    mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    devices.append({
                        "id": i,
                        "name": name,
                        "vram_gb": round(mem_info.total / (1024.**3), 2),
                        "compute_capability": "unknown",
                        "fp64_capable": False
                    })
                pynvml.nvmlShutdown()
                return {"available": available, "fp64_capable": fp64_capable, "devices": devices}
        except Exception as e:
            logger.warning(f"pynvml GPU check failed: {e}")

        # Method 3: nvidia-smi fallback
        try:
            cmd = ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"]
            if safe_subprocess_run:
                res = safe_subprocess_run(cmd, timeout=10.0, check=True)
            else:
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=10.0, check=True)

            if res.returncode == 0 and res.stdout:
                lines = res.stdout.strip().splitlines()
                for idx, line in enumerate(lines):
                    if line:
                        parts = line.split(",")
                        name = parts[0].strip()
                        vram_mb = float(parts[1].strip()) if len(parts) > 1 else 0.0
                        devices.append({
                            "id": idx,
                            "name": name,
                            "vram_gb": round(vram_mb / 1024.0, 2),
                            "compute_capability": "unknown",
                            "fp64_capable": False
                        })
                if devices:
                    available = True
        except Exception as e:
            logger.warning(f"nvidia-smi fallback GPU check failed: {e}")

        return {"available": available, "fp64_capable": fp64_capable, "devices": devices}

    @staticmethod
    def get_core_pinning_config() -> str:
        """Generates environment string for P-core pinning on hybrid architectures (§8.4)."""
        return "KMP_HW_SUBSET=8c:intel_core,1t"

    @staticmethod
    def get_system_ram_gb() -> float:
        try:
            import psutil
            return round(psutil.virtual_memory().total / (1024.**3), 2)
        except Exception as e:
            logger.warning(f"psutil RAM detection failed ({e}), falling back to OS system RAM detection")
            if sys.platform == "win32":
                try:
                    class MEMORYSTATUSEX(ctypes.Structure):
                        _fields_ = [
                            ("dwLength", ctypes.c_ulong),
                            ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                        ]
                    stat = MEMORYSTATUSEX()
                    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
                    return round(stat.ullTotalPhys / (1024.**3), 2)
                except Exception as e:
                    logger.warning(f"Windows memory detection failed: {e}")
            elif os.path.exists("/proc/meminfo"):
                try:
                    with open("/proc/meminfo", "r", encoding="utf-8") as f:
                        for line in f:
                            if line.startswith("MemTotal:"):
                                parts = line.split()
                                kb = float(parts[1])
                                return round(kb / (1024.0 * 1024.0), 2)
                except Exception as e:
                    logger.warning(f"Linux /proc/meminfo reading failed: {e}")
            return 16.0

    @classmethod
    def get_full_profile(cls) -> Dict[str, Any]:
        return {
            "cpu_cores": cls.get_cpu_cores(),
            "gpu": cls.get_gpu_availability(),
            "ram_gb": cls.get_system_ram_gb()
        }
