# cochem_canvas_target: core_engine/cochem_core_hardware_profiler.py
"""
Hardware profiler module for CoChem-CORE.
Provides system information, hardware capability detection, and performance benchmarking.
"""

import psutil
import platform
import time
import subprocess
from typing import Dict, List, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-HardwareProfiler")

class HardwareProfiler:
    """
    Provides system information, hardware capability detection, and performance benchmarking.
    
    Implements TFLOPS calculation and hardware calibration benchmarking as required by 
    20260807_workflow.md for dynamic MLFF fallback detection.
    """
    
    def __init__(self):
        """Initialize the hardware profiler."""
        self.system_info = {}
        
    def get_system_info(self) -> Dict:
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
            'disk_usage': psutil.disk_usage('/')
        }
        
        return self.system_info
        
    def get_hardware_capabilities(self) -> Dict:
        """Get hardware capabilities with enhanced profiling."""
        capabilities = {
            'cpu_count': psutil.cpu_count(logical=True),
            'memory_total_gb': psutil.virtual_memory().total / (1024**3),
            'cpu_architecture': platform.machine(),
            'is_virtual_machine': self._check_virtualization(),
            'cpu_tflops': self._calculate_cpu_tflops(),  # Enhanced with TFLOPS calculation
            'hardware_score': self._calculate_hardware_score()  # Overall hardware score
        }
        
        return capabilities
        
    def _check_virtualization(self) -> bool:
        """Check if system is running in a virtual machine."""
        try:
            # Check for common VM indicators
            vm_indicators = ['virtualbox', 'vmware', 'qemu', 'vmware']
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
            # This is a simplified estimation - in practice, you'd use more sophisticated benchmarks
            cpu_count = psutil.cpu_count(logical=True)
            
            # Get CPU frequency (in GHz)
            cpu_freq = psutil.cpu_freq()
            if cpu_freq and cpu_freq.current:
                freq_ghz = cpu_freq.current / 1000.0
            else:
                # Fallback to typical values
                freq_ghz = 2.5  # Default CPU frequency in GHz
            
            # Estimate FLOPS per core (this is a rough approximation)
            # Modern CPUs can do ~2-4 FLOPS/core/cycle depending on architecture and operation type
            flops_per_core_per_cycle = 3.0  # Average estimate
            
            # Estimate cycles per second (frequency in Hz)
            cycles_per_second = freq_ghz * 1e9
            
            # Total estimated FLOPS for all cores
            total_flops = cpu_count * flops_per_core_per_cycle * cycles_per_second
            
            # Convert to TFLOPS (10^12 FLOPS)
            tflops = total_flops / 1e12
            
            logger.info(f"Estimated CPU TFLOPS: {tflops:.2f}")
            return tflops
            
        except Exception as e:
            logger.error(f"Error calculating CPU TFLOPS: {e}")
            return 0.0
            
    def _calculate_hardware_score(self) -> float:
        """Calculate an overall hardware score for job routing decisions."""
        try:
            # Direct computation to avoid infinite recursion with get_hardware_capabilities()
            cpu_tflops = self._calculate_cpu_tflops()
            memory_total_gb = psutil.virtual_memory().total / (1024**3)
            
            # Weighted scoring system (simplified)
            cpu_score = min(cpu_tflops / 10.0, 1.0)  # Normalize to 0-1
            memory_score = min(memory_total_gb / 32.0, 1.0)  # Normalize to 0-1
            
            # Simple weighted average (you can adjust weights as needed)
            hardware_score = (cpu_score * 0.6 + memory_score * 0.4) * 100
            
            logger.info(f"Calculated hardware score: {hardware_score:.2f}")
            return hardware_score
            
        except Exception as e:
            logger.error(f"Error calculating hardware score: {e}")
            return 0.0

    def get_performance_metrics(self) -> Dict:
        """Get performance metrics with benchmarking capabilities."""
        # This includes basic performance metrics plus system benchmarks
        metrics = {
            'cpu_load': psutil.cpu_percent(interval=1),
            'memory_usage': psutil.virtual_memory().percent,
            'disk_io': psutil.disk_io_counters(),
            'benchmark_results': self._run_performance_benchmarks()  # Run system benchmarks
        }
        
        return metrics
        
    def _run_performance_benchmarks(self) -> Dict:
        """Run hardware calibration benchmarks to determine system capabilities."""
        benchmark_results = {}
        
        try:
            # CPU benchmark - simple arithmetic operations
            start_time = time.time()
            
            # Perform a series of mathematical operations to measure CPU performance
            total = 0
            for i in range(1000000):
                total += i * i
            
            cpu_benchmark_time = time.time() - start_time
            benchmark_results['cpu_benchmark'] = {
                'time_seconds': cpu_benchmark_time,
                'operations_per_second': 1000000 / cpu_benchmark_time if cpu_benchmark_time > 0 else 0,
                'result': total
            }
            
            # Memory benchmark - simple allocation test
            start_time = time.time()
            memory_test = [0] * (1024 * 1024)  # Allocate 1MB array
            memory_benchmark_time = time.time() - start_time
            benchmark_results['memory_benchmark'] = {
                'time_seconds': memory_benchmark_time,
                'allocation_size_mb': len(memory_test) / (1024 * 1024),
                'result': "Memory allocation successful"
            }
            
            logger.info("Hardware benchmarks completed successfully")
            
        except Exception as e:
            logger.error(f"Error running performance benchmarks: {e}")
            benchmark_results['error'] = str(e)
            
        return benchmark_results
        
    def get_cuda_info(self) -> Dict:
        """Get CUDA information if available with enhanced detection."""
        try:
            # Try to run nvidia-smi command to check for CUDA availability
            result = subprocess.run(['nvidia-smi', '--query-compute-apps=pid', '--format=csv'], 
                                   capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                # NVIDIA GPU detected
                gpu_count = len([line for line in result.stdout.split('\n') if line.strip() and 'pid' not in line])
                
                # Get CUDA version info
                version_result = subprocess.run(['nvidia-smi', '--query-compute-apps=driver_version', '--format=csv'], 
                                              capture_output=True, text=True, timeout=10)
                
                cuda_version = None
                if version_result.returncode == 0:
                    # Parse version from the output
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
                # No CUDA detected
                return {
                    'cuda_available': False,
                    'cuda_version': None,
                    'gpu_count': 0
                }
                
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # NVIDIA-SMI not available or command failed
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
            
    def execute_7_phase_initialization(self) -> Dict:
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
        
        # Check if critical checks passed
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
            usage = psutil.disk_usage('/')
            free_gb = usage.free / (1024**3)
            logger.info(f"Storage check: {free_gb:.2f} GB available.")
            return free_gb >= 10.0
        except Exception as e:
            logger.error(f"NVMe storage check failed: {e}")
            return False

    def _check_thermal_throttle(self) -> bool:
        """Phase 2: Checks lm-sensors/sysfs for thermal throttling (Linux/WSL)."""
        try:
            if hasattr(psutil, "sensors_temperatures"):
                temps = psutil.sensors_temperatures()
                if not temps:
                    return True # Cannot determine, assume safe
                for name, entries in temps.items():
                    for entry in entries:
                        if entry.current > 90.0: # 90C threshold
                            return False
            return True
        except Exception:
            return True

    def _check_openmpi_shm(self) -> bool:
        """Phase 3: Validates OpenMPI Shared Memory (SHM) mappings for parallel efficiency."""
        # Simple heuristic checking for /dev/shm availability and size
        try:
            if platform.system() == "Linux":
                shm_usage = psutil.disk_usage('/dev/shm')
                if shm_usage.total < (1 * 1024**3): # Needs at least 1GB SHM
                    return False
            return True
        except Exception:
            return False

    def _get_gpu_details(self) -> List[Dict]:
        """Get detailed GPU information."""
        try:
            result = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total,memory.used', '--format=csv'], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                gpu_details = []
                
                for line in lines[1:]:  # Skip header
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

def main():
    """Main entry point for the hardware profiler."""
    logger.info("Starting CoChem-CORE Hardware Profiler")
    
    profiler = HardwareProfiler()
    
    # Example usage
    system_info = profiler.get_system_info()
    capabilities = profiler.get_hardware_capabilities()
    performance = profiler.get_performance_metrics()
    cuda_info = profiler.get_cuda_info()
    
    print("System Information:", system_info)
    print("Hardware Capabilities:", capabilities)
    print("Performance Metrics:", performance)
    print("CUDA Information:", cuda_info)
    
    logger.info("Hardware profiler completed")

if __name__ == "__main__":
    main()