"""Compatibility entrypoint for the actual native BASE setup service and GUI."""
from cochem_base.interfaces.cochem_unity_installer_dashboard import (
    DeploymentManifest, ECOSYSTEM_REGISTRY, SynapInstallerGUI, main, run_headless,
)

__all__ = ["DeploymentManifest", "ECOSYSTEM_REGISTRY", "SynapInstallerGUI", "run_headless", "main"]

if __name__ == "__main__":
    raise SystemExit(main())
