#!/usr/bin/env python3
"""
CoChem-Viewer Dashboard
Polls the Scratch/ directory for QCSchema JSONs and PESStore HDF5 files.
Provides a diagnostic view of current artifacts.
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("CoChem-Viewer")

# Try to import rich for dashboard, fallback to simple print if unavailable.
try:
    from rich.console import Console
    from rich.live import Live
    from rich.table import Table
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

try:
    import h5py
    H5PY_AVAILABLE = True
except ImportError:
    H5PY_AVAILABLE = False

# Assuming this script is run from within the CoChem-BASE or similar environment
# where cochem_base is importable. If not, one might need to adjust sys.path,
# but per standard module structure it should be available.
from cochem_base.config_loader import get_artifact_dir  # noqa: E402


def get_scratch_dir() -> Path:
    return get_artifact_dir() / "Scratch"

def scan_artifacts(scratch_dir: Path):
    """Scan for QCSchema and HDF5 files."""
    json_files: list[tuple[str, str]] = []
    hdf5_files: list[tuple[str, str]] = []

    if not scratch_dir.exists():
        return json_files, hdf5_files

    for p in scratch_dir.glob("*_qcschema.json"):
        try:
            from calc.cochem_calc_output_parser import QCSchemaMolecule
            with open(p, 'r', encoding='utf-8') as f:
                data = json.load(f)
                schema = QCSchemaMolecule.model_validate(data) if hasattr(QCSchemaMolecule, 'model_validate') else QCSchemaMolecule.parse_obj(data)
            energy = schema.properties.return_energy
            scf_stat = schema.properties.scf_iterations
            json_files.append((p.name, f"Energy: {energy} | SCF: {scf_stat}"))
        except Exception as e:
            raise ValueError(f"CRITICAL: Corrupted QCSchema artifact detected at {p}: {e}. Log-and-ignore patterns are forbidden. Fix the upstream generator.") from e

    for ext in ("*.h5", "*.hdf5"):
        for p in scratch_dir.glob(ext):
            if H5PY_AVAILABLE:
                try:
                    with h5py.File(p, mode='r', swmr=True) as f:
                        keys = list(f.keys())
                        hdf5_files.append((p.name, f"Groups: {len(keys)} (SWMR mode read)"))
                except Exception as e:
                    raise ValueError(f"CRITICAL: Corrupted HDF5 artifact detected at {p}: {e}. Log-and-ignore patterns are forbidden. Fix the upstream generator.") from e
            else:
                hdf5_files.append((p.name, "h5py not installed"))

    return json_files, hdf5_files

def generate_table(json_files, hdf5_files, scratch_dir) -> "Table":
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    table = Table(title=f"CoChem-Viewer: Diagnostic Dashboard\n[Polling: {scratch_dir}]\nLast Update: {now_str}")
    table.add_column("Artifact Type", style="cyan")
    table.add_column("Filename", style="magenta")
    table.add_column("Status / Data", style="green")

    for f, d in sorted(json_files):
        table.add_row("QCSchema JSON", f, d)
    for f, d in sorted(hdf5_files):
        table.add_row("HDF5 Store", f, d)

    if not json_files and not hdf5_files:
        table.add_row("Info", "No artifacts found", "Waiting for data...")

    return table

def run_dashboard():
    scratch_dir = get_scratch_dir()
    poll_rate = 5 # seconds limit for reasonable performance

    if RICH_AVAILABLE:
        console = Console()
        console.print(f"[bold blue]Starting CoChem-Viewer...[/bold blue] Polling [bold]{scratch_dir}[/bold] every {poll_rate}s. Press Ctrl+C to stop.")
        try:
            with Live(generate_table([], [], scratch_dir), refresh_per_second=1) as live:
                while True:
                    j_files, h_files = scan_artifacts(scratch_dir)
                    live.update(generate_table(j_files, h_files, scratch_dir))
                    time.sleep(poll_rate)
        except KeyboardInterrupt:
            console.print("[bold red]Viewer stopped.[/bold red]")
    else:
        logger.info(f"Starting simple CoChem-Viewer (Rich not installed). Polling {scratch_dir} every {poll_rate}s. Press Ctrl+C to stop.")
        try:
            while True:
                j_files, h_files = scan_artifacts(scratch_dir)
                now_str = datetime.now().strftime("%H:%M:%S")
                logger.info(f"--- Poll Update ({now_str}) ---")
                if not j_files and not h_files:
                    logger.info("No artifacts found.")
                for f, d in sorted(j_files):
                    logger.info(f"[JSON] {f}: {d}")
                for f, d in sorted(h_files):
                    logger.info(f"[HDF5] {f}: {d}")
                time.sleep(poll_rate)
        except KeyboardInterrupt:
            logger.info("Viewer stopped.")

if __name__ == "__main__":
    run_dashboard()
