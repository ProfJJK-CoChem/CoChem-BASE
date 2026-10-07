"""Legacy TOPOS interface backed by the actual native BASE conformer controller."""
from __future__ import annotations

import math
import os

from ui.voila_layout.cochem_gui import CoChemGUI


class CochemToposUI(CoChemGUI):
    """Open the connected search panel without a second execution implementation."""

    def __init__(self) -> None:
        super().__init__()
        self.state.active_view = "matrix"
        self.config_tabs.selected_index = 2

    def render(self):
        return self.display()


def clamp_vram_ceiling(vram_free_gb: float) -> float:
    """Limit a prospective allocation to 80% of observed free VRAM and 16 GB."""
    if isinstance(vram_free_gb, bool) or not math.isfinite(vram_free_gb) or vram_free_gb < 0:
        raise ValueError("Free VRAM must be finite and nonnegative")
    return min(16.0, 0.8 * vram_free_gb)


def discover_cuda_devices() -> list[dict]:
    """Return only hardware actually discovered and visible to this process."""
    visibility = os.environ.get("CUDA_VISIBLE_DEVICES")
    if visibility is not None and visibility.strip() in {"", "-1"}:
        return []
    from cochem_base.orchestrator.cochem_setup_phase_2 import probe_nvidia_gpus

    devices = probe_nvidia_gpus()
    if visibility is not None:
        selected = {value.strip() for value in visibility.split(",")}
        devices = [device for device in devices if str(device.index) in selected or device.uuid in selected]
    return [device.model_dump(mode="json") for device in devices]


def get_conformer_search_protocol(name: str) -> dict:
    """Describe the engine inputs actually used by the native conformer broker."""
    if name == "GOAT":
        return {"name": "ORCA GOAT", "orca_keyword": "! GOAT XTB2", "scope": "conformer screening"}
    if name == "CREST_NCI":
        return {"name": "CREST NCI", "crest_flags": ["--gfn2", "--nci", "--noreftopo"], "scope": "conformer screening"}
    if name == "CREST_GOAT":
        return {"name": "Parallel CREST + GOAT union", "engines": [get_conformer_search_protocol("CREST_NCI"), get_conformer_search_protocol("GOAT")]}
    raise ValueError(f"Unsupported physical conformer protocol: {name}")
