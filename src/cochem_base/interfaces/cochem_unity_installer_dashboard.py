"""Legacy UNITY names mapped to the native BASE installation controller.

CORE, MInt, SYNAP and UNITY were consolidated into BASE. Future workflow
repositories are optional consumers of its artifact contracts, not mandatory
prerequisites for initializing this repository.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator

from cochem_base.orchestrator.bootstrap_service import run_setup
from .module_registry import canonical_module_id, list_module_capabilities
from ui.voila_layout.cochem_gui import CoChemGUI

SynapInstallerGUI = CoChemGUI
ECOSYSTEM_REGISTRY = {
    capability.name: {"desc": capability.responsibility, "mandatory": capability.module_id == "base",
                      "module_id": capability.module_id}
    for capability in list_module_capabilities()
}


class DeploymentManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    version: str = "cochem.deployment/1"
    selected_repositories: list[str] = Field(default_factory=lambda: ["CoChem-BASE"])

    @field_validator("selected_repositories")
    @classmethod
    def known_repositories(cls, value: list[str]) -> list[str]:
        names = {cap.module_id: cap.name for cap in list_module_capabilities()}
        selected = [names[canonical_module_id(name)] for name in value]
        return list(dict.fromkeys(["CoChem-BASE", *selected]))


def run_headless(artifact_dir: str | Path, *, min_disk_space_gb: float = 50.0,
                 skip_heavy: bool = False, on_event=None) -> dict:
    return run_setup(artifact_dir, min_disk_space_gb=min_disk_space_gb,
                     skip_heavy=skip_heavy, on_event=on_event)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--min-disk-space-gb", type=float, default=50.0)
    parser.add_argument("--skip-heavy", action="store_true")
    args = parser.parse_args(argv)
    summary = run_headless(args.artifact_dir, min_disk_space_gb=args.min_disk_space_gb,
                           skip_heavy=args.skip_heavy)
    print(json.dumps(summary, indent=2))
    return 0 if summary.get("overall_status") in {"PASSED", "DEGRADED_OPERATIONAL"} else 1


__all__ = ["DeploymentManifest", "ECOSYSTEM_REGISTRY", "SynapInstallerGUI", "run_headless", "main"]

if __name__ == "__main__":
    raise SystemExit(main())
