import os
import sys
from typing import Any, Dict, List, Optional, Union
import jinja2

# Ensure cochem_geom is accessible if running directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) + "/src")
from cochem_geom.engine.schemas import ORCAInputDeckSchema, CFOURInputDeckSchema, TaskType

ORCA_TEMPLATE = """{% if meta %}
{% for m in meta %}
# {{ m }}
{% endfor %}
{% endif %}
{{ output }}"""

CFOUR_TEMPLATE = """{% if meta %}
{% for m in meta %}
# {{ m }}
{% endfor %}
{% endif %}
{{ output }}"""

def generate_geom_block(
    engine: str, 
    method: str = "B3LYP", 
    basis: str = "cc-pVTZ", 
    geometry: str = "",
    topos_heuristic: str = "iMTD-GC", 
    topos_dedup: float = 0.05, 
    torq_dihedrals: str = "", 
    torq_resolution: int = 36, 
    torq_qrrho: bool = False
) -> str:
    """
    Generates an authentic input deck or geometry specification block based on user settings,
    abiding by the Anti-Spoofing and Zero-Mock directives.
    """
    engine = engine.upper()
    
    if engine == "ORCA":
        extra_kws = []
        if torq_qrrho:
            extra_kws.append("qRRHO")
            
        extra_blocks = {}
        if torq_dihedrals.strip():
            scan_tmpl = jinja2.Template("  Scan\n{% for d in dihedrals %}    dihedral {{ d }} = 0.0, 360.0, {{ torq_resolution }}\n{% endfor %}  end")
            dihedrals = [d.strip() for d in torq_dihedrals.split(',') if d.strip()]
            extra_blocks["geom"] = scan_tmpl.render(dihedrals=dihedrals, torq_resolution=torq_resolution)
            
        deck = ORCAInputDeckSchema(
            method=method,
            basis=basis,
            geometry_xyz=geometry if geometry.strip() else "O 0 0 0\nH 0 0.75 -0.5\nH 0 0.75 0.5",
            task=TaskType.OPT,
            extra_keywords=extra_kws,
            extra_blocks=extra_blocks
        )
        
        output = deck.format_deck_string()
        
        meta = [
            f"TOPOS Heuristic: {topos_heuristic}",
            f"TOPOS Deduplication Tolerance: {topos_dedup:.3f}"
        ]
        return jinja2.Template(ORCA_TEMPLATE).render(meta=meta, output=output)

    elif engine == "CFOUR":
        spec = {
            "method": method,
            "basis": basis,
            "geometry": geometry if geometry.strip() else "O 0.0 0.0 0.0\nH 0.0 0.757 -0.469\nH 0.0 -0.757 -0.469",
            "mult": 1,
            "ref": "RHF",
            "symmetry": "OFF",
            "vpt2": "OFF",
        }
        output = serialize_cfour_input(spec)
        
        meta = [
            "CFOUR Geometry Parameters (Cartesian SYMMETRY=OFF Frame Alignment) [M]",
            f"TOPOS Heuristic: {topos_heuristic}",
            f"TOPOS Deduplication Tolerance: {topos_dedup:.3f}"
        ]
        if torq_dihedrals.strip():
            meta.append(f"TORQ Active Dihedrals (Scan Resolution: {torq_resolution}): {torq_dihedrals}")
        if torq_qrrho:
            meta.append("qRRHO: Enabled")
            
        return jinja2.Template(CFOUR_TEMPLATE).render(meta=meta, output=output)

    return f"# Unsupported Engine: {engine}"


def serialize_cfour_input(spec: Union[Dict[str, Any], Any]) -> str:
    """Serializes a calculation spec into an authentic CFOUR input deck with coordinate frame alignment. [M]

    Enforces Method Matrix §9, §13, §14 requirements:
    - *CFOUR(CALC=...,BASIS=...,COORD=CARTESIAN,EXCITE=NONE,MULT=1,REF=RHF,SYMMETRY=OFF,VPT2=OFF)
    - SYMMETRY=OFF guarantees CFOUR will not reorient the Cartesian frame into a non-standard
      subgroup symmetry orientation, preserving principal-axis dipole moment components (mu_a, mu_b, mu_c).
    - Cartesian coordinates in standard 4-column format terminated by standard CFOUR blank lines.
    """
    if hasattr(spec, "model_dump"):
        data = spec.model_dump()
    elif isinstance(spec, dict):
        data = spec
    else:
        data = vars(spec)

    calc = str(data.get("calc") or data.get("method") or "CCSD(T)").upper()
    basis = str(data.get("basis") or data.get("basis_set") or "ANO0").upper()
    mult = int(data.get("mult") or data.get("multiplicity") or 1)
    ref = str(data.get("ref") or "RHF").upper()
    excite = str(data.get("excite") or "NONE").upper()
    vpt2 = str(data.get("vpt2") or "OFF").upper()
    title = str(data.get("title") or "CoChem CFOUR Deck Generation").strip()

    raw_geom = data.get("geometry") or data.get("geometry_xyz") or data.get("coordinates") or ""
    
    coord_rows: List[str] = []
    if isinstance(raw_geom, str):
        lines = [line.strip() for line in raw_geom.strip().splitlines() if line.strip()]
        start_idx = 0
        if len(lines) > 2 and lines[0].isdigit():
            start_idx = 2
        for line in lines[start_idx:]:
            parts = line.split()
            if len(parts) >= 4:
                elem = parts[0].capitalize()
                x = float(parts[1])
                y = float(parts[2])
                z = float(parts[3])
                coord_rows.append(f"{elem:<4} {x:14.8f} {y:14.8f} {z:14.8f}")
    elif isinstance(raw_geom, (list, tuple)):
        symbols = data.get("symbols") or []
        for i, row in enumerate(raw_geom):
            if len(row) == 4 and isinstance(row[0], str):
                elem = str(row[0]).capitalize()
                x, y, z = float(row[1]), float(row[2]), float(row[3])
            elif len(row) == 3 and i < len(symbols):
                elem = str(symbols[i]).capitalize()
                x, y, z = float(row[0]), float(row[1]), float(row[2])
            else:
                continue
            coord_rows.append(f"{elem:<4} {x:14.8f} {y:14.8f} {z:14.8f}")

    deck_lines = [
        title,
        f"*CFOUR(CALC={calc},BASIS={basis},COORD=CARTESIAN,EXCITE={excite}",
        f"MULT={mult},REF={ref},SYMMETRY=OFF,VPT2={vpt2})",
        "",
    ]
    deck_lines.extend(coord_rows)
    deck_lines.append("")
    deck_lines.append("")

    return "\n".join(deck_lines)

