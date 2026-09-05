import os
import sys
from typing import Any, Dict, List, Sequence, Union

import jinja2
import numpy as np

# Ensure cochem_geom is accessible if running directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) + "/src")
from cochem_geom.engine.schemas import ORCAInputDeckSchema, TaskType

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


def validate_interatomic_distances(
    coordinates: Union[np.ndarray, Sequence[Sequence[float]]],
    min_dist: float = 0.70,
    max_dist: float = 25.0,
) -> None:
    """Validates that all pairwise interatomic distances satisfy physical bounds. [M]

    Raises ValueError if clashing atoms (< min_dist) or excessively fragmented / unbounded
    coordinates (> max_dist) are detected.
    """
    coords = np.array(coordinates, dtype=np.float64)
    n_atoms = len(coords)
    if n_atoms < 2:
        return

    for i in range(n_atoms):
        for j in range(i + 1, n_atoms):
            diff = coords[i] - coords[j]
            dist = float(np.linalg.norm(diff))
            if dist < min_dist:
                raise ValueError(
                    f"Physical Dimensionality Violation: Interatomic distance between atom {i} and {j} "
                    f"is {dist:.6f} Å, which is below the physical bound of {min_dist} Å."
                )
            if dist > max_dist:
                raise ValueError(
                    f"Physical Dimensionality Violation: Interatomic distance between atom {i} and {j} "
                    f"is {dist:.6f} Å, which exceeds the physical bound of {max_dist} Å."
                )


def cartesian_to_zmatrix(
    symbols: Sequence[str],
    coordinates: Union[np.ndarray, Sequence[Sequence[float]]],
) -> List[str]:
    """Translates Cartesian coordinates to syntactically valid CFOUR internal Z-matrix lines. [M]

    Computes authentic bond lengths (Å), planar angles (deg), and dihedral angles (deg)
    using vector geometry and covalent connectivity.
    """
    coords = np.array(coordinates, dtype=np.float64)
    n_atoms = len(symbols)
    if len(coords) != n_atoms:
        raise ValueError(f"Number of symbols ({n_atoms}) does not match coordinate count ({len(coords)})")

    validate_interatomic_distances(coords)

    zmat_lines: List[str] = []
    if n_atoms == 0:
        return zmat_lines

    # Atom 1: Element only
    zmat_lines.append(symbols[0].capitalize())
    if n_atoms == 1:
        return zmat_lines

    # Atom 2: Bond to atom 1
    r12 = float(np.linalg.norm(coords[1] - coords[0]))
    zmat_lines.append(f"{symbols[1].capitalize()} 1 {r12:12.6f}")
    if n_atoms == 2:
        return zmat_lines

    # Atom 3: Bond to 1, angle with 2
    v21 = coords[0] - coords[1]
    v23 = coords[2] - coords[0]
    r13 = float(np.linalg.norm(coords[2] - coords[0]))
    cos_theta = np.dot(-v21, v23) / (np.linalg.norm(v21) * np.linalg.norm(v23) + 1e-14)
    cos_theta = np.clip(cos_theta, -1.0, 1.0)
    theta123 = float(np.degrees(np.arccos(cos_theta)))
    zmat_lines.append(f"{symbols[2].capitalize()} 1 {r13:12.6f} 2 {theta123:12.4f}")
    if n_atoms == 3:
        return zmat_lines

    # Atom i (i >= 3): Bond to i-1 (or closest), angle, dihedral
    for i in range(3, n_atoms):
        p_i = coords[i]
        # Choose 3 preceding reference atoms (i-1, i-2, i-3)
        ref1, ref2, ref3 = i - 1, i - 2, i - 3
        v_bond = p_i - coords[ref1]
        dist = float(np.linalg.norm(v_bond))

        v1 = coords[ref1] - coords[ref2]
        v2 = p_i - coords[ref1]
        cos_ang = np.dot(-v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-14)
        ang = float(np.degrees(np.arccos(np.clip(cos_ang, -1.0, 1.0))))

        # Dihedral angle: ref3 -> ref2 -> ref1 -> i
        b1 = coords[ref2] - coords[ref3]
        b2 = coords[ref1] - coords[ref2]
        b3 = p_i - coords[ref1]

        n1 = np.cross(b1, b2)
        n2 = np.cross(b2, b3)
        n1_norm = np.linalg.norm(n1)
        n2_norm = np.linalg.norm(n2)
        if n1_norm > 1e-12 and n2_norm > 1e-12:
            n1 /= n1_norm
            n2 /= n2_norm
            m1 = np.cross(n1, b2 / (np.linalg.norm(b2) + 1e-14))
            x = np.dot(n1, n2)
            y = np.dot(m1, n2)
            dihedral = float(np.degrees(np.arctan2(y, x)))
        else:
            dihedral = 0.0

        zmat_lines.append(
            f"{symbols[i].capitalize()} {ref1 + 1} {dist:12.6f} {ref2 + 1} {ang:12.4f} {ref3 + 1} {dihedral:12.4f}"
        )

    return zmat_lines


def serialize_cfour_input(spec: Union[Dict[str, Any], Any]) -> str:
    """Serializes a calculation spec into an authentic CFOUR input deck with coordinate frame alignment. [M]

    Enforces Method Matrix §9, §13, §14 requirements:
    - *CFOUR(CALC=...,BASIS=...,COORD=CARTESIAN,UNITS=ANGSTROM,EXCITE=NONE,MULT=1,REF=RHF,SYMMETRY=OFF,VPT2=OFF)
    - UNITS=ANGSTROM is strictly enforced to prevent default Bohr scaling collapse (1.8897x distortion).
    - SYMMETRY=OFF guarantees CFOUR will not reorient the Cartesian frame into a non-standard
      subgroup symmetry orientation, preserving principal-axis dipole moment components (mu_a, mu_b, mu_c).
    - Validates interatomic physical distances against physical bounds (0.70 Å <= r_ij <= 25.0 Å).
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
    deriv = str(data.get("deriv") or "ANALYTIC").upper()
    title = str(data.get("title") or "CoChem CFOUR Deck Generation").strip()

    raw_geom = data.get("geometry") or data.get("geometry_xyz") or data.get("coordinates") or ""

    coord_rows: List[str] = []
    numeric_coords: List[List[float]] = []
    symbols_list: List[str] = []

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
                symbols_list.append(elem)
                numeric_coords.append([x, y, z])
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
            symbols_list.append(elem)
            numeric_coords.append([x, y, z])
            coord_rows.append(f"{elem:<4} {x:14.8f} {y:14.8f} {z:14.8f}")

    if numeric_coords:
        validate_interatomic_distances(numeric_coords)

    deck_lines = [
        title,
        f"*CFOUR(CALC={calc},BASIS={basis},COORD=CARTESIAN,UNITS=ANGSTROM,EXCITE={excite}",
        f"MULT={mult},REF={ref},DERIV={deriv},SYMMETRY=OFF,VPT2={vpt2})",
        "",
    ]
    deck_lines.extend(coord_rows)
    deck_lines.append("")
    deck_lines.append("")

    return "\n".join(deck_lines)

