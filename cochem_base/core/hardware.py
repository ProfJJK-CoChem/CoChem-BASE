import os
import sys
import logging
import subprocess
import multiprocessing
import ctypes

logger = logging.getLogger(__name__)

class HardwareDiscovery:
    """Hardware discovery orchestrator for CoChem-BASE"""
    
    @staticmethod
    def get_cpu_cores():
        return multiprocessing.cpu_count()

    @staticmethod
    def get_gpu_availability():
        devices = []
        available = False
        
        # Method 1: PyTorch check
        try:
            import torch
            if torch.cuda.is_available():
                available = True
                for i in range(torch.cuda.device_count()):
                    props = torch.cuda.get_device_properties(i)
                    devices.append({
                        "id": i,
                        "name": props.name,
                        "vram_gb": round(props.total_memory / (1024.**3), 2)
                    })
                return {"available": available, "devices": devices}
        except ImportError:
            pass

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
                        "vram_gb": round(mem_info.total / (1024.**3), 2)
                    })
                pynvml.nvmlShutdown()
                return {"available": available, "devices": devices}
        except Exception:
            pass

        # Method 3: nvidia-smi fallback
        try:
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            if res.returncode == 0:
                lines = res.stdout.strip().splitlines()
                for idx, line in enumerate(lines):
                    if line:
                        parts = line.split(",")
                        name = parts[0].strip()
                        vram_mb = float(parts[1].strip()) if len(parts) > 1 else 0.0
                        devices.append({"id": idx, "name": name, "vram_gb": round(vram_mb / 1024.0, 2)})
                if devices:
                    available = True
        except Exception:
            pass

        return {"available": available, "devices": devices}
        
    @staticmethod
    def get_system_ram_gb():
        try:
            import psutil
            return round(psutil.virtual_memory().total / (1024.**3), 2)
        except ImportError:
            logger.warning("psutil not installed, falling back to OS system RAM detection")
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
                    with open("/proc/meminfo", "r") as f:
                        for line in f:
                            if line.startswith("MemTotal:"):
                                parts = line.split()
                                kb = float(parts[1])
                                return round(kb / (1024.0 * 1024.0), 2)
                except Exception as e:
                    logger.warning(f"Linux /proc/meminfo reading failed: {e}")
            return 16.0

    @classmethod
    def get_full_profile(cls):
        return {
            "cpu_cores": cls.get_cpu_cores(),
            "gpu": cls.get_gpu_availability(),
            "ram_gb": cls.get_system_ram_gb()
        }

