import importlib.util
from pathlib import Path
import sys

_mint_path = Path(__file__).resolve().parent / "CoChem-MInt.py"
if _mint_path.is_file():
    _spec = importlib.util.spec_from_file_location("intake.cochem_mint", str(_mint_path))
    if _spec and _spec.loader:
        _mod = importlib.util.module_from_spec(_spec)
        sys.modules["intake.cochem_mint"] = _mod
        sys.modules["intake.CoChem_MInt"] = _mod
        _spec.loader.exec_module(_mod)
        
        # Export all public symbols
        CoChemIngestionError = _mod.CoChemIngestionError
        AtomMetadata = _mod.AtomMetadata
        MolecularGeometryPayload = _mod.MolecularGeometryPayload
        BatchIngestionSummary = _mod.BatchIngestionSummary
        MIntIngestor = _mod.MIntIngestor
        CoChemMInt = _mod.CoChemMInt
        IngestionEngine = _mod.IngestionEngine
        ingest_file = _mod.ingest_file
        ingest_xyz = _mod.ingest_xyz
        ingest_mol = _mod.ingest_mol
        ingest_string = _mod.ingest_string
        scan_batch_directory = _mod.scan_batch_directory
        resolve_io_scratch_directory = _mod.resolve_io_scratch_directory
        bind_system_config = _mod.bind_system_config
        compute_sha256 = _mod.compute_sha256

__all__ = [
    "CoChemIngestionError",
    "AtomMetadata",
    "MolecularGeometryPayload",
    "BatchIngestionSummary",
    "MIntIngestor",
    "CoChemMInt",
    "IngestionEngine",
    "ingest_file",
    "ingest_xyz",
    "ingest_mol",
    "ingest_string",
    "scan_batch_directory",
    "resolve_io_scratch_directory",
    "bind_system_config",
    "compute_sha256",
]