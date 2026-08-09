#!/usr/bin/env python3
"""
Test suite for CoChem-BASE Setup Orchestrator
"""

import os
import sys
import json
import tempfile
import unittest
from pathlib import Path

# Add the project root to the Python path so we can import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from setup.cochem_setup_orchestrator import (
    get_manifest_path,
    detect_cuda_capability,
    detect_hardware_capability,
    get_mlff_fallback_strategy,
    main
)

class TestSetupOrchestrator(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create a temporary manifest for testing
        self.temp_manifest = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        manifest_data = {
            "interaction_environment": "Local-Windows (WSL)",
            "calculation_environment": "Local-Linux (Deb)"
        }
        json.dump(manifest_data, self.temp_manifest)
        self.temp_manifest.close()
        
        # Mock the environment variable to point to our test manifest
        self.original_env = os.environ.get('COCHEM_ARTIFACT_DIR')
        os.environ['COCHEM_ARTIFACT_DIR'] = os.path.dirname(self.temp_manifest.name)
    
    def tearDown(self):
        """Clean up after each test method."""
        # Restore original environment variable
        if self.original_env is not None:
            os.environ['COCHEM_ARTIFACT_DIR'] = self.original_env
        else:
            os.environ.pop('COCHEM_ARTIFACT_DIR', None)
            
        # Clean up temporary manifest file
        try:
            os.unlink(self.temp_manifest.name)
        except OSError:
            pass

    def test_get_manifest_path(self):
        """Test that get_manifest_path returns the correct path."""
        manifest_path = get_manifest_path()
        self.assertTrue(manifest_path.exists())
        self.assertEqual(manifest_path.name, "cochem_deployment_manifest.json")
    
    def test_detect_cuda_capability(self):
        """Test CUDA capability detection."""
        # This test will simply check that the function doesn't crash
        result = detect_cuda_capability()
        self.assertIsInstance(result, bool)
    
    def test_detect_hardware_capability(self):
        """Test hardware capability detection."""
        result = detect_hardware_capability()
        self.assertIsInstance(result, dict)
        self.assertIn('cpu_count', result)
        self.assertIn('memory_gb', result)
        self.assertIn('cuda_available', result)
        self.assertIn('platform', result)
        self.assertIn('architecture', result)
    
    def test_get_mlff_fallback_strategy(self):
        """Test MLFF fallback strategy determination."""
        # Test with high-performance hardware
        high_perf_hardware = {
            'cpu_count': 16,
            'memory_gb': 32,
            'cuda_available': True
        }
        strategy = get_mlff_fallback_strategy(high_perf_hardware)
        self.assertIsInstance(strategy, str)
        self.assertTrue(len(strategy) > 0)
        
        # Test with low-performance hardware
        low_perf_hardware = {
            'cpu_count': 2,
            'memory_gb': 4,
            'cuda_available': False
        }
        strategy = get_mlff_fallback_strategy(low_perf_hardware)
        self.assertIsInstance(strategy, str)
        self.assertTrue(len(strategy) > 0)

if __name__ == '__main__':
    unittest.main()