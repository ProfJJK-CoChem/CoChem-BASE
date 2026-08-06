# cochem_canvas_target: core_engine/cochem_core_hardware_profiler.py
"""
Hardware profiler module for CoChem-CORE.
Profiles system hardware to optimize computational chemistry workflows.
"""

import platform
import psutil
import time
from pathlib import Path

class HardwareProfiler:
    """
    Profiles system hardware to determine optimal resource allocation.
    """
    
    def __init__(self):
        """Initialize the hardware profiler."""
        self.hardware_info = {}
        
    def profile_system(self) -> dict:
        """Profile the entire system hardware."""
        print("🔬 Profiling system hardware...")
        
        # Get basic system information
        self.hardware_info['platform'] = platform.system()
        self.hardware_info['processor'] = platform.processor()
        self.hardware_info['architecture'] = platform.machine()
        
        # Get CPU information
        self.hardware_info['cpu_count'] = psutil.cpu_count(logical=True)
        self.hardware_info['cpu_freq'] = psutil.cpu_freq()
        
        # Get memory information
        memory = psutil.virtual_memory()
        self.hardware_info['memory_total_gb'] = round(memory.total / (1024**3), 2)
        self.hardware_info['memory_available_gb'] = round(memory.available / (1024**3), 2)
        
        # Get disk information
        disk = psutil.disk_usage('/')
        self.hardware_info['disk_total_gb'] = round(disk.total / (1024**3), 2)
        self.hardware_info['disk_available_gb'] = round(disk.free / (1024**3), 2)
        
        print(f"✅ Hardware profiling completed")
        return self.hardware_info
        
    def get_optimal_resources(self) -> dict:
        """Determine optimal resource allocation based on hardware profile."""
        print("⚙️  Determining optimal resources...")
        
        # This is a placeholder for actual resource optimization logic
        # In a real implementation, this would analyze the hardware profile
        # and recommend optimal resource allocation
        
        return {
            'max_concurrent_jobs': min(4, self.hardware_info.get('cpu_count', 4)),
            'memory_per_job_gb': max(1, self.hardware_info.get('memory_total_gb', 8) // 8),
            'recommended_partition': 'compute' if self.hardware_info.get('cpu_count', 0) > 8 else 'small'
        }
        
    def export_profile(self, filename: str = "hardware_profile.json"):
        """Export the hardware profile to a JSON file."""
        import json
        with open(filename, 'w') as f:
            json.dump(self.hardware_info, f, indent=2)
        print(f"💾 Hardware profile exported to {filename}")

def main():
    """Main entry point for the hardware profiler."""
    print("Starting CoChem-CORE Hardware Profiler")
    
    profiler = HardwareProfiler()
    profile = profiler.profile_system()
    resources = profiler.get_optimal_resources()
    
    print("Hardware Profile:", profile)
    print("Recommended Resources:", resources)
    
    profiler.export_profile()

if __name__ == "__main__":
    main()