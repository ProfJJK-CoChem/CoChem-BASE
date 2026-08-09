import os
import multiprocessing

class HardwareDiscovery:
    """Hardware discovery orchestrator for CoChem-BASE"""
    
    @staticmethod
    def get_cpu_cores():
        return multiprocessing.cpu_count()

    @staticmethod
    def get_gpu_availability():
        # Mock GPU detection for MVP
        # In a real environment, this might check nvidia-smi or PyTorch cuda.is_available()
        return {"available": False, "devices": []}
        
    @staticmethod
    def get_system_ram_gb():
        # Mock RAM detection or use psutil if available
        try:
            import psutil
            return round(psutil.virtual_memory().total / (1024.**3), 2)
        except ImportError:
            # Fallback mock for MVP
            return 16.0

    @classmethod
    def get_full_profile(cls):
        return {
            "cpu_cores": cls.get_cpu_cores(),
            "gpu": cls.get_gpu_availability(),
            "ram_gb": cls.get_system_ram_gb()
        }
