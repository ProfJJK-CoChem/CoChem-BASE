import os
import sys
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
        deck = CFOURInputDeckSchema(
            method=method,
            basis=basis,
            geometry_zmat=geometry if geometry.strip() else "O\nH 1 0.96\nH 1 0.96 2 104.5",
        )
        output = deck.format_zmat_string()
        
        meta = [
            "CFOUR Geometry Parameters",
            f"TOPOS Heuristic: {topos_heuristic}",
            f"TOPOS Deduplication Tolerance: {topos_dedup:.3f}"
        ]
        if torq_dihedrals.strip():
            meta.append(f"TORQ Active Dihedrals (Scan Resolution: {torq_resolution}): {torq_dihedrals}")
        if torq_qrrho:
            meta.append("qRRHO: Enabled")
            
        return jinja2.Template(CFOUR_TEMPLATE).render(meta=meta, output=output)

    return f"# Unsupported Engine: {engine}"
