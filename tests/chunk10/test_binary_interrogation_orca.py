import sys

from cochem_base.orchestrator.cochem_setup_phase_3 import (
    extract_semantic_version,
    interrogate_binary_version,
)


def test_extract_semantic_version_orca_banners():
    orca4 = "\n* O R C A *\nProgram Version 4.2.1 - RELEASE\n"
    assert extract_semantic_version(orca4, "orca") == "4.2.1"

    orca5 = "\n* O R C A *\nVersion 5.0.4 - RELEASE\n"
    assert extract_semantic_version(orca5, "orca") == "5.0.4"

    orca6 = "\n* O R C A *\nProgram Version 6.0.1 - RELEASE\n"
    assert extract_semantic_version(orca6, "orca") == "6.0.1"

def test_extract_semantic_version_heterogeneous_engines():
    xtb_out = "   * xtb version 6.6.1 (ca8354c) compiled by ..."
    assert extract_semantic_version(xtb_out, "xtb") == "6.6.1"

    crest_out = "CREST Version 3.0.2, a conformational search program"
    assert extract_semantic_version(crest_out, "crest") == "3.0.2"

    cfour_out = "CFOUR version 2.1 Copyright (c) 2020 CFOUR authors"
    assert extract_semantic_version(cfour_out, "cfour") == "2.1"

    mpi_out = "mpirun (Open MPI) 4.1.6"
    assert extract_semantic_version(mpi_out, "mpirun") == "4.1.6"

def test_interrogate_binary_version_real_executable(tmp_path):
    script_path = tmp_path / "fake_orca.py"
    script_path.write_text('print("Program Version 6.0.0 - RELEASE")\n', encoding="utf-8")

    if sys.platform == "win32":
        launcher = tmp_path / "orca.bat"
        launcher.write_text(f'@echo off\n"{sys.executable}" "{script_path}"\n', encoding="utf-8")
    else:
        launcher = tmp_path / "orca"
        launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script_path}"\n', encoding="utf-8")
        launcher.chmod(0o755)

    ver, err = interrogate_binary_version(launcher, "orca", timeout_seconds=5.0)
    assert err is None
    assert ver == "6.0.0"
