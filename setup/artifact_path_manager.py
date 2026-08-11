import os
import json
import logging
from pathlib import Path
from cochem_base.config_loader import get_artifact_dir as loader_get_artifact_dir

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-ArtifactPathManager")


def get_artifact_dir() -> Path:
    """Delegates to the central CoChem-BASE config loader for 4-tier dynamic resolution hierarchy."""
    return loader_get_artifact_dir()
