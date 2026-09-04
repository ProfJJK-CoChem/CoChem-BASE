# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Unit test for Deliverable 10 (Suggestion #80):
Eradication of Synthetic CREST Fallback Ensemble.
Verifies that when the crest executable is missing from PATH, BinaryNotFoundError
is raised with [MISSING DATA] and zero synthetic coordinates or fallback ensembles are produced.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
import pytest

from Libraries.cochem_torq_crest import CrestRunner, CrestConfig
from cochem_base.exceptions import BinaryNotFoundError


def test_crest_missing_binary_raises_typed_error() -> None:
    """Verify that attempting to execute CREST when binary is absent raises

    BinaryNotFoundError with '[MISSING DATA]' and halts cleanly without synthesizing coordinates.
    """
    with tempfile.TemporaryDirectory() as td:
        xyz_path = Path(td) / "seed_molecule.xyz"
        xyz_path.write_text(
            "3\nWater test\nO 0.0 0.0 0.0\nH 0.0 0.757 0.586\nH 0.0 -0.757 0.586\n",
            encoding="utf-8",
        )

        # Configure runner pointing to an intentionally non-existent binary
        config = CrestConfig(crest_bin="non_existent_crest_binary_xyz_12345")
        runner = CrestRunner(config=config)

        with pytest.raises(BinaryNotFoundError) as exc_info:
            runner.run_crest(input_xyz=xyz_path)

        assert "[MISSING DATA]" in str(exc_info.value)
        assert "CREST executable not discovered" in str(exc_info.value)
