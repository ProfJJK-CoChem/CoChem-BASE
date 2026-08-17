#!/usr/bin/env python3
"""
Test suite for CoChem-BASE Setup Orchestrator
"""

import json
import logging
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from setup.cochem_setup_orchestrator import (
    CALC_MAP,
    INTERACT_MAP,
    detect_cuda_capability,
    detect_default_environments,
    detect_hardware_capability,
    get_manifest_path,
    get_mlff_fallback_strategy,
)


class TestSetupOrchestrator(unittest.TestCase):

    def setUp(self) -> None:
        """Set up test fixtures before each test method."""
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        registry_dir = Path(self.temp_dir.name) / "Registry"
        registry_dir.mkdir(parents=True, exist_ok=True)
        manifest_file = registry_dir / "cochem_deployment_manifest.json"

        interact, calc = detect_default_environments()
        manifest_data = {
            "interaction_environment": interact,
            "calculation_environment": calc
        }
        with open(manifest_file, 'w', encoding='utf-8') as f:
            json.dump(manifest_data, f)

        self.original_env = os.environ.get('COCHEM_ARTIFACT_DIR')
        os.environ['COCHEM_ARTIFACT_DIR'] = self.temp_dir.name

    def tearDown(self) -> None:
        """Clean up after each test method."""
        if self.original_env is not None:
            os.environ['COCHEM_ARTIFACT_DIR'] = self.original_env
        else:
            os.environ.pop('COCHEM_ARTIFACT_DIR', None)

        try:
            self.temp_dir.cleanup()
        except OSError as e:
            logging.getLogger(__name__).warning("Failed to clean up temporary directory %s: %s", self.temp_dir.name, e)
    def test_get_manifest_path(self) -> None:
        """Test that get_manifest_path returns the correct path."""
        manifest_path = get_manifest_path()
        self.assertTrue(manifest_path.exists())
        self.assertEqual(manifest_path.name, "cochem_deployment_manifest.json")

    def test_all_environment_routes_have_scripts(self) -> None:
        setup_dir = Path(__file__).resolve().parent
        for script_name in (*INTERACT_MAP.values(), *CALC_MAP.values()):
            self.assertTrue((setup_dir / script_name).is_file(), script_name)

    def test_default_environment_mapping_is_host_native(self) -> None:
        import platform
        sys_os = platform.system()
        interact, calc = detect_default_environments()
        if sys_os == "Darwin":
            self.assertEqual((interact, calc), ("Local-MacOS (OrbStack)", "Local-MacOS (OrbStack)"))
        elif sys_os == "Windows":
            self.assertEqual((interact, calc), ("Local-Windows (WSL)", "Local-Windows (WSL)"))
        elif sys_os == "Linux":
            self.assertEqual((interact, calc), ("Local-Linux (Deb)", "Local-Linux (Deb)"))

    def test_detect_cuda_capability(self) -> None:
        """Test CUDA capability detection."""
        result = detect_cuda_capability()
        self.assertIsInstance(result, bool)

    def test_detect_hardware_capability(self) -> None:
        """Test hardware capability detection."""
        result = detect_hardware_capability()
        self.assertIsInstance(result, dict)
        self.assertIn('cpu_count', result)
        self.assertIn('memory_gb', result)
        self.assertIn('cuda_available', result)
        self.assertIn('platform', result)
        self.assertIn('architecture', result)

    def test_get_mlff_fallback_strategy(self) -> None:
        """Test MLFF fallback strategy determination against real hardware capabilities."""
        hardware = detect_hardware_capability()
        strategy = get_mlff_fallback_strategy(hardware)
        self.assertIsInstance(strategy, str)
        self.assertTrue(len(strategy) > 0)


if __name__ == '__main__':
    unittest.main()
