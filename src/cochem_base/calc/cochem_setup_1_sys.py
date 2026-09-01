#!/usr/bin/env python3
"""
CoChem-BASE Setup Stage 1: System Environment & Offline Tarball Fallback Manager.
Performs pre-flight environment checks and routes download requests to local archives in air-gapped environments.
"""

import logging
import os
import socket
import tarfile
import zipfile
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def is_online(host: Optional[str] = None, port: int = 53, timeout: float = 2.0) -> bool:
    """Checks internet connectivity via socket connection safely."""
    # Use environment variable for host if not provided, fallback to 1.1.1.1
    host = host or os.environ.get("COCHEM_CONNECTIVITY_HOST", "1.1.1.1")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((host, port))
        return True
    except (socket.timeout, socket.error, Exception):
        return False


def _safe_extract_tar(tar: tarfile.TarFile, dest_dir: Path) -> None:
    """Safely extract tarball to avoid path traversal vulnerabilities."""
    def is_within_directory(directory: Path, target: Path) -> bool:
        try:
            target.resolve().relative_to(directory.resolve())
            return True
        except ValueError:
            return False

    for member in tar.getmembers():
        member_path = dest_dir / member.name
        if not is_within_directory(dest_dir, member_path):
            raise Exception(f"Attempted Path Traversal in Tar File: {member.name}")
        tar.extract(member, path=dest_dir)


def _extract_archive(archive_path: Path, dest_dir: Path) -> None:
    """Helper method to handle extraction based on extension."""
    if archive_path.suffix.lower() == ".zip":
        with zipfile.ZipFile(archive_path, "r") as z:
            z.extractall(dest_dir)
    else:
        with tarfile.open(archive_path, "r:*") as tar:
            _safe_extract_tar(tar, dest_dir)


def fetch_or_extract_archive(archive_name: str, url: str, local_archive: Path, dest_dir: Path) -> bool:
    """Extracts local tarball/zip if offline; downloads and extracts if online."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    if not is_online():
        logger.info(f"Air-gapped/Offline mode active. Extracting local archive: {local_archive}")
        if local_archive.exists():
            _extract_archive(local_archive, dest_dir)
            return True
        else:
            raise FileNotFoundError(f"Offline mode active but local archive missing: {local_archive}")
    else:
        logger.info(f"Online mode active. Extracting or downloading {archive_name}")
        if local_archive.exists():
            _extract_archive(local_archive, dest_dir)
            return True
            
        if not url:
            logger.error(f"[MISSING DATA] URL is absent for {archive_name}.")
            raise ValueError(f"[MISSING DATA] URL is absent for {archive_name}.")
            
        logger.info(f"Downloading {archive_name} from {url} to {local_archive}...")
        local_archive.parent.mkdir(parents=True, exist_ok=True)
        try:
            urllib.request.urlretrieve(url, str(local_archive))
            _extract_archive(local_archive, dest_dir)
            return True
        except urllib.error.URLError as e:
            logger.error(f"Download failed for {archive_name}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during provision of {archive_name}: {e}")
            raise


if __name__ == "__main__":
    online = is_online()
    logger.info(f"System Online Status: {online}")
