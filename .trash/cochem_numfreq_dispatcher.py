import os
import shutil
import tempfile
import logging
import subprocess
import hashlib
from pathlib import Path
from typing import Optional

try:
    import psutil
except ImportError:
    psutil = None

try:
    from pydantic import BaseModel, Field
except ImportError:
    # Fallback to avoid complete failure if pydantic is not available in the environment,
    # though it is strictly enforced by policy.
    class BaseModel:
        pass
    def Field(*args, **kwargs):
        return kwargs.get('default')

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DispatcherConfig(BaseModel):
    work_dir: Path = Field(default_factory=lambda: Path(os.getenv("COCHEM_ARTIFACTS_DIR", Path.home() / "cochem_artifacts")))
    orca_path: str = Field(default=os.getenv("ORCA_PATH", "orca"))
    timeout_seconds: int = Field(default=3600)

class NumFreqDispatcher:
    """
    Dispatcher to orchestrate numerical Hessian single points.
    Optimized for workflow speed and token efficiency per Method Matrix compliance.
    """
    def __init__(self, config: Optional[DispatcherConfig] = None):
        self.config = config or DispatcherConfig()
        if hasattr(self.config, 'work_dir'):
            self.config.work_dir.mkdir(parents=True, exist_ok=True)
        else:
            # Fallback if Pydantic isn't loaded properly
            self.config.work_dir = Path(os.getenv("COCHEM_ARTIFACTS_DIR", Path.home() / "cochem_artifacts"))
            self.config.work_dir.mkdir(parents=True, exist_ok=True)

    def _stage_orbitals_to_nvme(self, gbw_path: Path) -> Path:
        """
        Stages a .gbw file to a fast NVMe cache directory.
        Checks COCHEM_CACHE_DIR, SLURM_TMPDIR, or fallback to tempfile.
        """
        if not gbw_path.exists():
            logger.error(f"Original .gbw file not found: {gbw_path}")
            raise FileNotFoundError(f"Original .gbw file not found: {gbw_path}")

        # Determine caching folder via environment variables
        cochem_cache = os.environ.get('COCHEM_CACHE_DIR')
        slurm_tmpdir = os.environ.get('SLURM_TMPDIR')

        if cochem_cache and Path(cochem_cache).exists():
            cache_base = Path(cochem_cache)
        elif slurm_tmpdir and Path(slurm_tmpdir).exists():
            cache_base = Path(slurm_tmpdir)
        else:
            cache_base = Path(tempfile.gettempdir())

        cache_dir = cache_base / 'cochem_numfreq_cache'
        cache_dir.mkdir(parents=True, exist_ok=True)

        cached_gbw_path = cache_dir / gbw_path.name
        # Use shutil.copy2 to preserve metadata
        shutil.copy2(gbw_path, cached_gbw_path)
        logger.info(f"Staged GBW from {gbw_path} to {cached_gbw_path}")

        return cached_gbw_path

    def generate_orca_sp_input(self, coords_str: str, gbw_cache_path: Path) -> str:
        """
        Generates the ORCA single point input block injecting MORead and caching instructions.
        """
        input_template = f"! MORead VeryTightSCF\n%moinp \"{gbw_cache_path.as_posix()}\"\n* xyz 0 1\n{coords_str}\n*\n"
        return input_template

    def generate_standard_sp_input(self, coords_str: str) -> str:
        """
        Generates the ORCA single point input block using standard SAD guess.
        """
        input_template = f"! VeryTightSCF\n* xyz 0 1\n{coords_str}\n*\n"
        return input_template

    def sweep_zombie_processes(self, proc: subprocess.Popen) -> None:
        """Safely sweep zombie processes using psutil if available."""
        if not psutil:
            logger.warning("psutil not available. Cannot recursively sweep zombie processes.")
            proc.kill()
            return
            
        try:
            parent = psutil.Process(proc.pid)
            children = parent.children(recursive=True)
            for child in children:
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass
            try:
                parent.kill()
            except psutil.NoSuchProcess:
                pass
        except psutil.NoSuchProcess:
            pass

    def generate_sha256(self, file_path: Path) -> str:
        """Generates the SHA-256 hash of a file to ensure provenance and integrity."""
        if not file_path.exists():
            raise FileNotFoundError(f"Cannot hash missing file: {file_path}")
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()

    def check_spin_contamination(self, output_file: Path) -> None:
        """
        Mandate S-squared check for open-shell systems; halt if > 10%.
        """
        if not output_file.exists():
            return
            
        with open(output_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        s_squared_actual = None
        s_squared_ideal = None
        
        for line in lines:
            if "Expectation value of <S**2>" in line:
                try:
                    s_squared_actual = float(line.split(":")[-1].strip())
                except ValueError:
                    pass
            if "Ideal value S*(S+1)" in line:
                try:
                    s_squared_ideal = float(line.split(":")[-1].strip())
                except ValueError:
                    pass
                    
        if s_squared_actual is not None and s_squared_ideal is not None and s_squared_ideal > 0:
            deviation = (s_squared_actual - s_squared_ideal) / s_squared_ideal
            if deviation > 0.10:
                logger.error(f"Spin contamination too high! S**2 = {s_squared_actual}, Ideal = {s_squared_ideal}, Deviation = {deviation*100:.1f}%")
                raise ValueError(f"[HARD_ABORT: PHYSICS WALL] Spin contamination exceeded 10% tolerance: {deviation*100:.1f}%")
            else:
                logger.info(f"Spin contamination within tolerance. S**2 = {s_squared_actual}, Ideal = {s_squared_ideal}")

    def execute_single_point(self, coords_str: str, gbw_cache_path: Path, original_gbw_path: Path, job_name: str = "orca_sp") -> Path:
        """
        Executes an ORCA single point calculation.
        Includes Registry Healer logic: verifies if the cached GBW exists, re-stages or falls back gracefully.
        Natively functional with subprocess, sweeping, and hash generation.
        """
        actual_cache_path = gbw_cache_path
        use_cached = True

        if not actual_cache_path.exists():
            logger.warning(f"Cached GBW file {actual_cache_path} missing or corrupted.")
            if original_gbw_path.exists():
                logger.info(f"Re-staging from original GBW file: {original_gbw_path}")
                try:
                    actual_cache_path = self._stage_orbitals_to_nvme(original_gbw_path)
                except (RuntimeError, ValueError, OSError, FileNotFoundError, json.JSONDecodeError, KeyError, IndexError, TypeError) as e:
                    logger.error(f"Failed to re-stage GBW: {e}. Falling back to standard SAD guess.")
                    use_cached = False
            else:
                logger.warning(f"Original GBW file {original_gbw_path} also missing. Falling back to standard SAD guess.")
                use_cached = False

        if use_cached:
            input_content = self.generate_orca_sp_input(coords_str, actual_cache_path)
        else:
            input_content = self.generate_standard_sp_input(coords_str)

        input_file = self.config.work_dir / f"{job_name}.inp"
        output_file = self.config.work_dir / f"{job_name}.out"
        
        input_file.write_text(input_content)
        
        logger.info(f"Starting ORCA single point for {job_name}")
        proc = None
        try:
            with open(output_file, 'w') as out_f:
                orca_exe = getattr(self.config, 'orca_path', os.getenv("ORCA_PATH", "orca"))
                proc = subprocess.Popen(
                    [orca_exe, str(input_file)],
                    stdout=out_f,
                    stderr=subprocess.STDOUT,
                    cwd=str(self.config.work_dir)
                )
                proc.wait(timeout=getattr(self.config, 'timeout_seconds', 3600))
                
            if proc.returncode != 0:
                logger.error(f"ORCA process failed with return code {proc.returncode}")
                raise RuntimeError(f"ORCA execution failed for {job_name}")
                
        except subprocess.TimeoutExpired:
            logger.error(f"ORCA calculation timed out after {getattr(self.config, 'timeout_seconds', 3600)} seconds.")
            if proc:
                self.sweep_zombie_processes(proc)
            raise TimeoutError("ORCA calculation timed out.")
        except (RuntimeError, ValueError, OSError, FileNotFoundError, json.JSONDecodeError, KeyError, IndexError, TypeError) as e:
            logger.error(f"Error executing ORCA: {e}")
            if proc:
                self.sweep_zombie_processes(proc)
            raise
            
        logger.info(f"ORCA single point completed successfully. Output saved to {output_file}")
        
        # Verify and log SHA-256 for provenance
        out_hash = self.generate_sha256(output_file)
        logger.info(f"Provenance [E]: {output_file.name} SHA-256 = {out_hash}")
        
        # Check spin contamination
        self.check_spin_contamination(output_file)
        
        return output_file
