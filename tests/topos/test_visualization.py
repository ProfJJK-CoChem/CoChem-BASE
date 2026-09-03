"""Physical Unit Tests for CoChem-TOPOS py3Dmol Jupyter Visualizer Widget.

Strictly adheres to Zero-Mock mandate.
Validates:
- Headless CI/terminal detection.
- Graceful HTML fallback rendering without display exceptions.
- Export of self-contained standalone HTML documents.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

from cochem.topos.graph import TopologyGraph
from cochem.topos.visualization import TOPOSpy3DmolWidget


class TestVisualizationWidget:
    """Verifies py3Dmol widget headless safety and HTML export."""

    def test_widget_initialization(self) -> None:
        """Verify default dimensions and configuration."""
        widget = TOPOSpy3DmolWidget(width=800, height=600)
        assert widget.width == 800
        assert widget.height == 600

    def test_headless_detection(self) -> None:
        """Verify deterministic headless detection in CLI / test environment."""
        # In pytest execution, environment is headless (no active Jupyter frontend)
        assert TOPOSpy3DmolWidget.is_headless() is True

    def test_headless_render_graceful_html_fallback(self) -> None:
        """Verify headless render generates HTML representation without GUI crashes."""
        graph = TopologyGraph()
        graph.add_chemical_node(0, "C", formal_charge=0, hybridization="sp2", in_ring=True)
        graph.add_chemical_node(1, "C", formal_charge=0, hybridization="sp2", in_ring=True)
        graph.add_chemical_edge(0, 1, bond_order=1.5, aromatic=True, in_ring=True)

        coords = np.array([
            [0.0, 0.0, 0.0],
            [1.4, 0.0, 0.0],
        ], dtype=float)

        widget = TOPOSpy3DmolWidget()
        output = widget.render(graph, coords=coords, style="stick")

        # Headless output must be a valid HTML string containing topology summary
        assert isinstance(output, str)
        assert "cochem-topos-headless" in output
        assert "data-nodes='2'" in output
        assert "data-edges='1'" in output

    def test_export_html_to_disk(self, tmp_path: Path) -> None:
        """Verify export_html writes a self-contained HTML file with 3Dmol JS payload."""
        graph = TopologyGraph()
        graph.add_chemical_node(0, "O", formal_charge=0, hybridization="sp3")
        graph.add_chemical_node(1, "H", formal_charge=0, hybridization="sp3")
        graph.add_chemical_node(2, "H", formal_charge=0, hybridization="sp3")
        graph.add_chemical_edge(0, 1, bond_order=1.0)
        graph.add_chemical_edge(0, 2, bond_order=1.0)

        coords = np.array([
            [0.0, 0.0, 0.1173],
            [0.0, 0.7572, -0.4692],
            [0.0, -0.7572, -0.4692],
        ], dtype=float)

        widget = TOPOSpy3DmolWidget(width=640, height=480)
        out_file = tmp_path / "molecule_view.html"

        html_content = widget.export_html(graph, coords=coords, output_path=out_file)

        assert out_file.exists()
        assert len(html_content) > 100
        assert "<html" in html_content
        assert "3Dmol" in html_content

        # Verify file content matches returned string
        saved_text = out_file.read_text(encoding="utf-8")
        assert saved_text == html_content
