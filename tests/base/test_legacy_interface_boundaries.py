"""Legacy entrypoints expose real BASE contracts instead of circular/error shells."""
import importlib

import pytest


@pytest.mark.parametrize("name,module", [
    ("cochem_pgopher_bridge", "spycfit"), ("cochem_dock_main", "dock"),
    ("cochem_vibspyc_snap", "spycfit"), ("cochem_dock_visuals_api", "dock"),
    ("oet_gxtb", "base"), ("cochem_pyckett_bridge", "spycfit"), ("dock_main", "dock"),
])
def test_legacy_interface_prepares_a_verified_pending_handoff(name, module, tmp_path):
    interface = importlib.import_module("cochem_base.interfaces." + name)
    capability = interface.get_capability()
    assert capability.module_id == module
    assert capability.execution_verified is False
    source = tmp_path / "water.xyz"
    source.write_text("3\nWater geometry supplied for ingestion\nO 0 0 0\nH 0.7586 0 0.5043\nH -0.7586 0 0.5043\n")
    handoff = interface.prepare_handoff(source, tmp_path / "package")
    assert handoff.status == "pending_integration"
    assert handoff.scientific_execution_performed is False
    assert (tmp_path / "package" / "artifact.xyz").read_bytes() == source.read_bytes()
    assert not list(tmp_path.rglob("result.json"))


def test_unity_compatibility_uses_real_base_gui_and_setup():
    from cochem_base.interfaces.cochem_unity_installer_dashboard import DeploymentManifest, SynapInstallerGUI
    from cochem_base.interfaces.cochem_unity_fast_pass_widget import FastPassWidget
    from ui.voila_layout.cochem_gui import CoChemGUI
    assert SynapInstallerGUI is CoChemGUI
    assert issubclass(FastPassWidget, CoChemGUI)
    manifest = DeploymentManifest(selected_repositories=["CoChem-CORE", "CoChem-MInt", "CoChem-TORQ"])
    assert manifest.selected_repositories == ["CoChem-BASE", "CoChem-TORQ"]
