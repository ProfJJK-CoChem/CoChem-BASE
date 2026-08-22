import os
import sys
import pytest
from pathlib import Path

# Ensure CoChem-BASE is in path
cochem_base_path = Path("D:/__CoChem/GitHub-Repo/CoChem-BASE").resolve()
if str(cochem_base_path) not in sys.path:
    sys.path.insert(0, str(cochem_base_path))

from test_suite.test_environment import check_artifacts_dir, check_cochem_base_silo

def test_keep_previous_setup_silo():
    silo_ok, silo_msg = check_cochem_base_silo()
    print(f"Silo OK: {silo_ok}, Msg: {silo_msg}")
    # We might not be in the conda env right now, but we want to know the result.

def test_keep_previous_setup_artifacts():
    art_ok, art_msg = check_artifacts_dir()
    print(f"Art OK: {art_ok}, Msg: {art_msg}")
    assert art_ok, f"Artifact validation failed: {art_msg}"

