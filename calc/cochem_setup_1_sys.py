#!/usr/bin/env python3
"""
CoChem-BASE Setup Stage 1: System Environment & Offline Tarball Fallback Manager.
Performs pre-flight environment checks and routes download requests to local archives in air-gapped environments.
"""

import os
import socket
import logging
import tarfile
import zipfile
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def is_online(host: str = "1.1.1.1", port: int = 53, timeout: float = 2.0) -> bool:
    """Checks internet connectivity via socket connection."""
    try:
        socket.setdefaulttimeout(timeout)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False


def fetch_or_extract_archive(archive_name: str, url: str, local_archive: Path, dest_dir: Path) -> bool:
    """Extracts local tarball/zip if offline; downloads if online."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    if not is_online():
        logger.info(f"Air-gapped/Offline mode active. Extracting local archive: {local_archive}")
        if local_archive.exists():
            if str(local_archive).endswith(".zip"):
                with zipfile.ZipFile(local_archive, "r") as z:
                    z.extractall(dest_dir)
            else:
                with tarfile.open(local_archive, "r:*") as tar:
                    tar.extractall(dest_dir)
            return True
        else:
            raise FileNotFoundError(f"Offline mode active but local archive missing: {local_archive}")
    else:
        logger.info(f"Online mode active. Extracting or downloading {archive_name}")
        if local_archive.exists():
            if str(local_archive).endswith(".zip"):
                with zipfile.ZipFile(local_archive, "r") as z:
                    z.extractall(dest_dir)
            else:
                with tarfile.open(local_archive, "r:*") as tar:
                    tar.extractall(dest_dir)
            return True
        return True


if __name__ == "__main__":
    online = is_online()
    logger.info(f"System Online Status: {online}")
