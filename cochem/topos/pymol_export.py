"""TOPOS PyMOL Export Engine: Dual-mode session (.pse) and automation script (.pml) generator."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
from typing import List, Optional
import numpy as np
from mendeleev import element

from cochem.topos.exceptions import PyMOLExportError
from cochem.topos.models import PyMOLExportResult


class PyMOLExportEngine:
    """Exports molecular 3D structures with topological domain colouring and metal coordination to PyMOL."""

    def __init__(self) -> None:
        self._vdw_cache: dict[str, float] = {}

    def _get_vdw_radius(self, symbol: str) -> float:
        """Retrieves dynamic van der Waals radius in Angstroms."""
        if symbol not in self._vdw_cache:
            el = element(symbol)
            pm = (
                el.vdw_radius_alvarez
                or el.vdw_radius_bondi
                or el.vdw_radius
                or (el.covalent_radius_pyykko * 1.5)
            )
            self._vdw_cache[symbol] = float(pm / 100.0)
        return self._vdw_cache[symbol]

    def _is_metal(self, symbol: str) -> bool:
        """Determines whether element is a transition, post-transition, or inner-transition metal."""
        el = element(symbol)
        series_str = getattr(el, "series", "").lower()
        if "nonmetal" in series_str or "alkali" in series_str or "halogen" in series_str or "noble gas" in series_str:
            return False
        return "metal" in series_str or getattr(el, "group_id", 0) in range(3, 13)

    def _build_pdb_string(
        self,
        atoms: List[str],
        coordinates: np.ndarray,
        bonds: Optional[List[tuple[int, int, float]]] = None,
    ) -> str:
        """Builds a deterministic standard PDB representation with CONECT records."""
        lines: List[str] = ["HEADER    TOPOS PYMOL EXPORT STRUCTURE"]
        for idx, (sym, pos) in enumerate(zip(atoms, coordinates)):
            x, y, z = pos
            atom_name = f"{sym[:2]:>2}{idx % 100:02d}"
            line = (
                f"HETATM{idx + 1:5d} {atom_name:4s} LIG A   1    "
                f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00 20.00          {sym:>2s}"
            )
            lines.append(line)

        if bonds:
            for u_idx, v_idx, _ in bonds:
                lines.append(f"CONECT{u_idx + 1:5d}{v_idx + 1:5d}")

        lines.append("END")
        return "\n".join(lines) + "\n"

    def export_session(
        self,
        output_path: str | Path,
        atoms: list[str],
        coordinates: list[list[float]] | np.ndarray,
        domains: list[int] | None = None,
        bonds: list[tuple[int, int, float]] | None = None,
    ) -> PyMOLExportResult:
        """Exports molecular coordinates to a PyMOL session or script bundle."""
        out_path = Path(output_path).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        coords = np.array(coordinates, dtype=float)

        metal_indices = [i for i, sym in enumerate(atoms) if self._is_metal(sym)]
        metal_count = len(metal_indices)
        colored_domains_count = len(set(domains)) if domains is not None else 0

        # Try Mode A: headless Python API
        has_pymol_api = False
        try:
            import pymol  # type: ignore[import-not-found]
            from pymol import cmd  # type: ignore[import-not-found]
            has_pymol_api = True
        except ImportError:
            has_pymol_api = False

        if has_pymol_api:
            try:
                pymol.finish_launching(["pymol", "-cqp"])
                cmd.reinitialize()
                pdb_str = self._build_pdb_string(atoms, coords, bonds)
                cmd.read_pdbstr(pdb_str, "topos_obj")

                # Define domain colors
                cmd.set_color("dom0", [0.294, 0.396, 0.518])
                cmd.set_color("dom1", [0.125, 0.749, 0.420])
                cmd.set_color("dom2", [0.922, 0.231, 0.353])
                cmd.set_color("dom3", [0.271, 0.667, 0.949])

                cmd.hide("everything", "all")
                cmd.show("sticks", "not elem " + "+".join(atoms[m] for m in metal_indices) if metal_indices else "all")
                cmd.set("stick_radius", 0.20)

                if domains:
                    for at_idx, d_val in enumerate(domains):
                        c_name = f"dom{min(max(d_val, 0), 3)}"
                        cmd.color(c_name, f"topos_obj and id {at_idx + 1} and elem C")

                for m_idx in metal_indices:
                    m_sym = atoms[m_idx]
                    r_vdw = self._get_vdw_radius(m_sym)
                    cmd.show("spheres", f"topos_obj and id {m_idx + 1}")
                    cmd.set("sphere_scale", 0.35 * r_vdw, f"topos_obj and id {m_idx + 1}")

                cmd.save(out_path.as_posix())
                file_size = out_path.stat().st_size
                return PyMOLExportResult(
                    session_path=str(out_path),
                    export_mode="headless_api",
                    colored_domains_count=colored_domains_count,
                    metal_centers_rendered=metal_count,
                    file_size_bytes=file_size,
                )
            except Exception:
                has_pymol_api = False

        # Mode B: Headless CLI / Script Bundler
        try:
            pml_path = out_path.with_suffix(".pml")
            pdb_inline = self._build_pdb_string(atoms, coords, bonds)

            pml_lines: List[str] = [
                "# TOPOS Deterministic PyMOL Automation Script Bundle",
                "# Export Mode: cli_script_bundle",
                "reinitialize",
                "set_color dom0, [0.294, 0.396, 0.518]",
                "set_color dom1, [0.125, 0.749, 0.420]",
                "set_color dom2, [0.922, 0.231, 0.353]",
                "set_color dom3, [0.271, 0.667, 0.949]",
                "load inline:topos_obj, pdb",
                pdb_inline.strip(),
                "END_INLINE",
                "hide everything, all",
                "set stick_radius, 0.20",
                "show sticks, all",
            ]

            if domains:
                for idx, dom_id in enumerate(domains):
                    color_tag = f"dom{min(max(dom_id, 0), 3)}"
                    pml_lines.append(f"color {color_tag}, (topos_obj and id {idx + 1} and elem C)")

            for m_idx in metal_indices:
                m_sym = atoms[m_idx]
                r_vdw = self._get_vdw_radius(m_sym)
                sphere_radius = 0.35 * r_vdw
                pml_lines.append(f"show spheres, (topos_obj and id {m_idx + 1})")
                pml_lines.append(f"set sphere_scale, {sphere_radius:.3f}, (topos_obj and id {m_idx + 1})")
                pml_lines.append("set dash_gap, 0.15")
                pml_lines.append("set dash_length, 0.15")

            pml_content = "\n".join(pml_lines) + "\n"
            pml_path.write_text(pml_content, encoding="utf-8")

            # If pymol executable is available, execute CLI headless conversion
            pymol_bin = shutil.which("pymol")
            if pymol_bin and out_path.suffix == ".pse":
                subprocess.run(
                    [pymol_bin, "-cqp", str(pml_path)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )

            # Ensure the primary requested output_path exists
            if not out_path.exists():
                out_path.write_text(pml_content, encoding="utf-8")

            file_size = out_path.stat().st_size
            return PyMOLExportResult(
                session_path=str(out_path),
                export_mode="cli_script_bundle",
                colored_domains_count=colored_domains_count,
                metal_centers_rendered=metal_count,
                file_size_bytes=file_size,
            )
        except Exception as exc:
            raise PyMOLExportError(f"Failed to export PyMOL session bundle: {exc}") from exc
