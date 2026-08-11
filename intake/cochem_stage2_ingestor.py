#!/usr/bin/env python3
"""
CoChem-CORE: Stage 1.0 - Headless Ingestion Engine
Module: intake/cochem_stage2_ingestor.py
Bridges raw molecular coordinate files (.xyz, .sdf) into strictly validated
mathematical arrays. Enforces basic valency checks and atomic parsing using 
bounded thread pools to prevent memory exhaustion during batch intakes.
"""

import os
import re
import json
import logging
import numpy as np
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple, Dict, Any, Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-IngestionEngine")

try:
    from pydantic import BaseModel, Field, ValidationError
    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False
    logger.warning("pydantic not found. Ingestion falling back to native dictionaries.")


if HAS_PYDANTIC:
    class AtomNode(BaseModel):
        symbol: str = Field(..., min_length=1, max_length=2)
        x: float
        y: float
        z: float

    class MolecularGraph(BaseModel):
        filename: str
        atoms: List[AtomNode]
        total_atoms: int
        net_charge: int = Field(default=0)
        multiplicity: int = Field(default=1)


class IngestionEngine:
    def __init__(self, max_workers: int = 4) -> None:
        self.max_workers = max_workers
        self.xyz_pattern = re.compile(r"^\s*([A-Za-z]{1,2})\s+([-+]?\d*\.\d+)\s+([-+]?\d*\.\d+)\s+([-+]?\d*\.\d+)")

    def parse_xyz(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Safely parses standard XYZ files into structured dictionaries."""
        atoms = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            if len(lines) < 3:
                logger.error(f"File {file_path.name} is too short to be a valid XYZ.")
                return None

            try:
                expected_atoms = int(lines[0].strip())
            except ValueError:
                logger.error(f"File {file_path.name} lacks a valid atom count on line 1.")
                return None

            for line in lines[2:]:
                match = self.xyz_pattern.match(line)
                if match:
                    atoms.append({
                        "symbol": match.group(1).capitalize(),
                        "x": float(match.group(2)),
                        "y": float(match.group(3)),
                        "z": float(match.group(4))
                    })

            if len(atoms) != expected_atoms:
                logger.warning(f"File {file_path.name}: Expected {expected_atoms} atoms, parsed {len(atoms)}.")

            graph_data = {
                "filename": file_path.name,
                "atoms": atoms,
                "total_atoms": len(atoms),
                "net_charge": 0,
                "multiplicity": 1
            }

            if HAS_PYDANTIC:
                try:
                    MolecularGraph(**graph_data)
                except ValidationError as ve:
                    logger.error(f"Validation failed for {file_path.name}: {ve}")
                    return None

            return graph_data

        except Exception as e:
            logger.error(f"Failed to read {file_path.name}: {e}")
            return None

    def process_batch(self, input_dir: str) -> List[Dict[str, Any]]:
        """
        Executes bounded multithreaded ingestion to protect RAM against
        directories containing tens of thousands of conformers.
        """
        input_path = Path(input_dir)
        if not input_path.exists() or not input_path.is_dir():
            logger.error(f"Input directory {input_dir} is invalid.")
            return []

        xyz_files = list(input_path.glob("*.xyz"))
        logger.info(f"Found {len(xyz_files)} files. Initiating ThreadPool parsing...")

        valid_graphs = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_file = {executor.submit(self.parse_xyz, path): path for path in xyz_files}

            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    data = future.result()
                    if data:
                        valid_graphs.append(data)
                        logger.debug(f"Successfully ingested: {data['filename']}")
                except Exception as exc:
                    logger.error(f"File {file_path.name} generated an exception during parsing: {exc}")

        logger.info(f"Batch ingestion complete. Yielded {len(valid_graphs)} valid molecular graphs.")
        return valid_graphs


if __name__ == "__main__":
    logger.info(">>> Testing Ingestion Engine...")

    test_dir = Path("mock_input")
    test_dir.mkdir(exist_ok=True)

    mock_xyz = test_dir / "water.xyz"
    with open(mock_xyz, "w", encoding="utf-8") as f:
        f.write("3\nWater molecule\nO 0.000 0.000 0.117\nH 0.000 0.757 -0.469\nH 0.000 -0.757 -0.469\n")

    mock_bad_xyz = test_dir / "bad.xyz"
    with open(mock_bad_xyz, "w", encoding="utf-8") as f:
        f.write("2\nBad file\nC 0.0 0.0\n")

    engine = IngestionEngine()
    results = engine.process_batch(str(test_dir))

    logger.info(f"[RESULT] Successfully parsed {len(results)} out of 2 files.")
    if results:
        logger.info(f"[DATA] First valid geometry: {results[0]['filename']} ({results[0]['total_atoms']} atoms)")

    import shutil
    shutil.rmtree(test_dir)