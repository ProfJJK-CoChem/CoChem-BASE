import logging
from pathlib import Path

from cochem_base.config_loader import get_artifact_dir as loader_get_artifact_dir

logger = logging.getLogger("CoChem-ArtifactPathManager")
logger.addHandler(logging.NullHandler())


def get_artifact_dir() -> Path:
    """Delegates to the central CoChem-BASE config loader for 4-tier dynamic resolution hierarchy."""
    return loader_get_artifact_dir()
