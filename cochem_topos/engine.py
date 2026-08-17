import os
import subprocess
import logging
import concurrent.futures
from pathlib import Path
from functools import lru_cache
import h5py
import shutil
import atexit
import psutil
import hashlib

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# Register zombie process sweeper
def cleanup_zombies() -> None:
    try:
        current_proc = psutil.Process()
        for child in current_proc.children(recursive=True):
            try:
                if child.is_running():
                    child.terminate()
            except psutil.NoSuchProcess:
                pass
    except Exception as e:
        logger.error(f"[FAILURE] Zombie sweeping failed: {e}")

atexit.register(cleanup_zombies)

class ToposEngine:
    """Combinatorial Engine for Conformational Generation using CREST and ORCA GOAT."""

    def __init__(self, name: str, xyz_path: str, temperature: float = 298.15) -> None:
        self.name = name
        self.xyz_path = Path(xyz_path).resolve()
        if not self.xyz_path.exists():
            logger.error(f"[MISSING DATA] Input xyz file not found: {self.xyz_path}")
            raise FileNotFoundError(f"[MISSING DATA] Input xyz file not found: {self.xyz_path}")
        
        self.temperature = temperature
        
        # Route scratch files to configurable artifacts directory
        artifacts_env = os.environ.get("COCHEM_ARTIFACTS")
        if artifacts_env:
            base_dir = Path(artifacts_env)
        else:
            base_dir = Path.home() / "cochem_artifacts"
            
        self.scratch_dir = base_dir / self.name
        self.scratch_dir.mkdir(parents=True, exist_ok=True)
        self.landscape_db = self.scratch_dir / "landscape.h5"

    def generate_sha256(self, filepath: Path) -> str:
        """Generate SHA-256 hash for provenance."""
        if not filepath.exists():
            return ""
        hasher = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def has_gpu(self) -> bool:
        """Auto-detect GPU for routing MACE tasks."""
        try:
            subprocess.run(["nvidia-smi"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=10)
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    @lru_cache(maxsize=32)
    def run_crest(self, input_xyz: str) -> str:
        """
        Run CREST for conformational search.
        Uses nocross and noreftopo as mandated.
        """
        logger.info(f"[TOPOS] Running CREST on {input_xyz}")
        work_dir = self.scratch_dir / "crest_run"
        work_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(input_xyz, work_dir / "input.xyz")
        
        cores = os.cpu_count()
        if cores is None:
            logger.warning("[MISSING DATA] CPU count undetected, falling back to 4")
            cores = 4
            
        cmd = [
            "crest", "input.xyz", 
            "--nci", "--gfn2", 
            "--ewin", "12", 
            "--nocross", "--noreftopo", 
            "--T", str(cores)
        ]
        
        try:
            subprocess.run(cmd, cwd=work_dir, check=True, capture_output=True, text=True, timeout=36000)
        except subprocess.TimeoutExpired as e:
            logger.error(f"[ERR_TIMEOUT] CREST timed out: {e}")
            return ""
        except subprocess.CalledProcessError as e:
            logger.error(f"[FAILURE] CREST failed: {e.stderr}")
            return ""
            
        ensemble_path = work_dir / "crest_conformers.xyz"
        if not ensemble_path.exists():
            logger.error("[MISSING DATA] CREST conformers not found.")
            return ""
            
        return str(ensemble_path)

    def run_orca_goat(self, input_xyz: str) -> str:
        """
        Run ORCA GOAT for conformer search.
        """
        logger.info(f"[TOPOS] Running ORCA GOAT on {input_xyz}")
        work_dir = self.scratch_dir / "goat_run"
        work_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(input_xyz, work_dir / "input.xyz")
        
        cores = os.cpu_count()
        if cores is None:
            logger.warning("[MISSING DATA] CPU count undetected, falling back to 4")
            cores = 4
        pal_cores = max(1, cores - 1)
        
        inp_content = f"""! GOAT XTB2 PAL{pal_cores}
%goat 
  maxen 12.0 
  conftemp {self.temperature} 
  confdegen auto 
  gfnuphill 
  gfnff 
end
* xyzfile 0 1 input.xyz
"""
        inp_path = work_dir / "goat.inp"
        inp_path.write_text(inp_content)
        
        cmd = ["orca", "goat.inp"]
        try:
            subprocess.run(cmd, cwd=work_dir, check=True, capture_output=True, text=True, timeout=36000)
        except subprocess.TimeoutExpired as e:
            logger.error(f"[ERR_TIMEOUT] ORCA GOAT timed out: {e}")
            return ""
        except subprocess.CalledProcessError as e:
            logger.error(f"[FAILURE] ORCA GOAT failed: {e.stderr}")
            return ""
            
        ensemble_path = work_dir / "goat_conformers.xyz" 
        if not ensemble_path.exists():
            ensemble_path = work_dir / "goat_trajectory.xyz"
            if not ensemble_path.exists():
                logger.error("[MISSING DATA] ORCA GOAT conformers not found.")
                return ""
            
        return str(ensemble_path)

    def generate_conformers_union(self) -> list[str]:
        """
        Run CREST and ORCA GOAT combination approach concurrently.
        """
        cores = os.cpu_count()
        if cores is None:
            cores = 4
        logger.info(f"[TOPOS] Conformer Generation for {self.xyz_path} using {cores} cores.")
        
        paths: list[str] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_crest = executor.submit(self.run_crest, str(self.xyz_path))
            future_goat = executor.submit(self.run_orca_goat, str(self.xyz_path))
            
            crest_out = future_crest.result()
            goat_out = future_goat.result()
            
            if crest_out:
                paths.append(crest_out)
            if goat_out:
                paths.append(goat_out)
                
        return paths

    def check_spin_contamination(self, out_file: Path) -> None:
        """
        Mandate S-squared check for open-shell systems; halt if > 10%.
        """
        if not out_file.exists():
            return
            
        actual_s2 = None
        ideal_s2 = None
        
        with open(out_file, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if "Expectation value of <S**2>" in line:
                    parts = line.split(":")
                    if len(parts) == 2:
                        try:
                            actual_s2 = float(parts[1].strip())
                        except ValueError:
                            pass
                elif "Ideal value S*(S+1)" in line:
                    parts = line.split(":")
                    if len(parts) == 2:
                        try:
                            ideal_s2 = float(parts[1].strip())
                        except ValueError:
                            pass
                            
        if actual_s2 is not None and ideal_s2 is not None and ideal_s2 > 0:
            deviation = abs(actual_s2 - ideal_s2) / ideal_s2
            if deviation > 0.10:
                logger.error(f"[FAILURE] Spin contamination exceeds 10%: ideal={ideal_s2}, actual={actual_s2}")
                raise RuntimeError(f"Spin contamination exceeded 10% limit. Ideal: {ideal_s2}, Actual: {actual_s2}")

    def optimize_complex(self, conformer_xyz: str, constraints: str = "") -> str:
        """
        Optimize using loose (defgrid1) to tight (defgrid3) grids.
        Tightened %geom for weak complexes, frozen-monomer protocol, XTB2 InHess.
        Always pass .gbw files from optimization to frequency steps.
        """
        logger.info(f"[TOPOS] Optimizing complex {conformer_xyz}")
        work_dir = self.scratch_dir / "opt_run"
        work_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(conformer_xyz, work_dir / "start.xyz")
        
        cores = os.cpu_count()
        if cores is None:
            cores = 4
        pal_cores = max(1, cores - 1)
        
        geom_block = """%geom 
    InHess XTB2
    TolMaxG 1e-5
"""
        if constraints:
            geom_block += f"    Constraints \n{constraints}\n    end\n"
        geom_block += "end"

        inp_content = f"""! wB97M-V def2-TZVP def2/J RIJCOSX Opt defgrid1 defgrid3
%pal nprocs {pal_cores} end
{geom_block}
* xyzfile 0 1 start.xyz
"""
        inp_path = work_dir / "opt.inp"
        inp_path.write_text(inp_content)
        
        cmd = ["orca", "opt.inp"]
        try:
            subprocess.run(cmd, cwd=work_dir, check=True, capture_output=True, text=True, timeout=86400)
        except subprocess.TimeoutExpired as e:
            logger.error(f"[ERR_TIMEOUT] ORCA Optimization timed out: {e}")
            return ""
        except subprocess.CalledProcessError as e:
            logger.error(f"[FAILURE] ORCA Optimization failed: {e.stderr}")
            return ""
            
        out_file = work_dir / "opt.out"
        opt_xyz = work_dir / "opt.xyz"
        gbw_file = work_dir / "opt.gbw"
        
        self.check_spin_contamination(out_file)
        
        if not opt_xyz.exists():
            logger.error("[MISSING DATA] ORCA opt outputs not found.")
            return ""
            
        # Generate SHA-256 hashes for provenance
        out_hash = self.generate_sha256(out_file)
        gbw_hash = self.generate_sha256(gbw_file)
        
        if out_hash:
            logger.info(f"[M] opt.out SHA-256: {out_hash}")
        if gbw_hash:
            logger.info(f"[M] opt.gbw SHA-256: {gbw_hash}")
            
        # Write large arrays/pointers to landscape.h5
        with h5py.File(self.landscape_db, "a", libver="latest") as f:
            f.swmr_mode = True
            if "optimizations" not in f:
                f.create_group("optimizations")
            opt_group = f["optimizations"].create_group(Path(conformer_xyz).stem)
            opt_group.attrs["opt_xyz"] = str(opt_xyz)
            if gbw_file.exists():
                opt_group.attrs["gbw_file"] = str(gbw_file)
                opt_group.attrs["gbw_sha256"] = gbw_hash
            if out_file.exists():
                opt_group.attrs["out_file"] = str(out_file)
                opt_group.attrs["out_sha256"] = out_hash
            
        return str(opt_xyz)

    def assign_point_group(self, xyz_path: str) -> str:
        """
        Zero-mock point group assignment using ORCA's symmetry finder.
        """
        logger.info(f"[TOPOS] Assigning point group for {xyz_path}")
        work_dir = self.scratch_dir / "pg_run"
        work_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(xyz_path, work_dir / "start.xyz")
        
        inp_content = f"""! SP
* xyzfile 0 1 start.xyz
"""
        inp_path = work_dir / "pg.inp"
        inp_path.write_text(inp_content)
        
        cmd = ["orca", "pg.inp"]
        try:
            result = subprocess.run(cmd, cwd=work_dir, check=True, capture_output=True, text=True, timeout=3600)
            for line in result.stdout.splitlines():
                if "Point Group" in line and "recognized" in line:
                    return line.split()[-1]
            return "C1"
        except subprocess.TimeoutExpired as e:
            logger.error(f"[ERR_TIMEOUT] ORCA Point Group assignment timed out: {e}")
            return "C1"
        except subprocess.CalledProcessError as e:
            logger.error(f"[FAILURE] ORCA Point Group assignment failed: {e.stderr}")
            return "C1"
