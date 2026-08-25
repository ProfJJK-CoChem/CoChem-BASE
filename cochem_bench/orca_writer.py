"""
CoChem-BENCH ORCA Input Generator & Counterpoise Engine
Generates DLPNO-CCSD(T)-F12 inputs, Boys-Bernardi counterpoise inputs, and relativistic specifications.
"""
from typing import Any

def inspect_basis_set_cp_capability(basis: str) -> dict[str, Any]:
    """
    Inspects basis set augmentation for CP-OPT safety and BSSE accuracy.
    """
    is_aug = "aug-" in basis.lower()
    is_cbs = ("/" in basis) or ("cbs" in basis.lower())
    return {
        "is_augmented": is_aug,
        "is_cbs": is_cbs,
        "cp_opt_permitted": is_aug and not is_cbs
    }

def generate_dlpno_ccsd_f12(
    coords: list[tuple[str, float, float, float] | list[Any]],
    basis: str = "aug-cc-pVTZ",
    is_opt: bool = False,
    in_hess: str = "XTB2",
    rel_mode: str = "auto",
    tight_scf: bool = False,
    charge: int = 0,
    mult: int = 1,
    nprocs: int = 1
) -> str:
    """
    Generates Method Matrix v4 compliant ORCA DLPNO-CCSD(T)-F12 input string.
    """
    # Detect heavy elements (Z >= 36, e.g. I, Br, Xe, etc.)
    has_heavy = any(str(c[0]).rstrip(':').capitalize() in ["I", "Br", "Xe", "Kr", "Rb", "Sr", "Y", "Zr", "Nb", "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd", "In", "Sn", "Sb", "Te"] for c in coords)
    
    effective_rel = rel_mode
    if rel_mode == "auto":
        effective_rel = "DKH2" if has_heavy else "none"

    effective_basis = basis
    if effective_rel.upper() == "DKH2":
        if "aug-cc-p" in basis:
            effective_basis = basis.replace("aug-cc-p", "aug-cc-pwC").replace("VTZ", "VTZ-DK").replace("VQZ", "VQZ-DK")
        elif not basis.endswith("-DK"):
            effective_basis = f"{basis}-DK"

    # Header composition
    keywords = ["!"]
    keywords.append("DLPNO-CCSD(T)-F12")
    keywords.append(effective_basis)
    keywords.append("CABS")
    
    # Method Matrix Quick Start Recipe R2 dictates DefGrid3 and TightOpt for geometries
    # DLPNO-CCSD(T) lacks analytic gradients. Using DefGrid1 with numerical gradients
    # produces catastrophic numerical noise. Enforcing TightOpt + DefGrid3.
    if is_opt:
        keywords.append("TightOpt")
        keywords.append("DefGrid3")
    else:
        keywords.append("DefGrid3")
    
    if tight_scf:
        keywords.append("TightSCF")
        
    if is_opt:
        keywords.append("Opt")
        
    if effective_rel.upper() == "DKH2":
        keywords.append("Relativistic DKH2")
    elif effective_rel.upper() == "ZORA":
        keywords.append("ZORA")

    lines = [" ".join(keywords)]

    if nprocs > 1:
        lines.append(f"%pal nprocs {nprocs} end")

    if is_opt:
        lines.append("%geom")
        lines.append("  TolE     1e-7")
        lines.append("  TolRMSG  3e-6")
        lines.append("  TolMaxG  1e-5")
        lines.append("  TolRMSD  5e-5")
        lines.append("  TolMaxD  1e-4")
        lines.append(f"  InHess   {in_hess}")
        lines.append("end")

    lines.append(f"* xyz {charge} {mult}")
    for c in coords:
        lines.append(f"  {c[0]}  {c[1]:12.8f}  {c[2]:12.8f}  {c[3]:12.8f}")
    lines.append("*")

    return "\n".join(lines) + "\n"

def generate_counterpoise_input(
    frag_a: list[tuple[str, float, float, float] | list[Any]],
    frag_b: list[tuple[str, float, float, float] | list[Any]],
    basis: str = "aug-cc-pVTZ",
    is_opt: bool = False,
    in_hess: str = "XTB2",
    rel_mode: str = "auto",
    charge: int = 0,
    mult: int = 1,
    nprocs: int = 1
) -> dict[str, Any]:
    """
    Generates Boys-Bernardi counterpoise ORCA inputs for complex, monomer A, and monomer B.
    """
    if is_opt and (("/" in basis) or ("cbs" in basis.lower())):
        raise ValueError("CP-OPT is strictly prohibited on CBS extrapolation basis set sequences")

    is_aug = "aug-" in basis.lower()
    
    # Complex (all real atoms, no ghost colon)
    complex_coords = list(frag_a) + list(frag_b)
    complex_inp = generate_dlpno_ccsd_f12(
        complex_coords, basis=basis, is_opt=is_opt, in_hess=in_hess,
        rel_mode=rel_mode, charge=charge, mult=mult, nprocs=nprocs
    )

    # Monomer A (frag_a real, frag_b ghost)
    monomer_a_coords = [(str(c[0]), c[1], c[2], c[3]) for c in frag_a] + \
                       [(f"{str(c[0]).rstrip(':')}:", c[1], c[2], c[3]) for c in frag_b]
    monomer_a_inp = generate_dlpno_ccsd_f12(
        monomer_a_coords, basis=basis, is_opt=False, in_hess=in_hess,
        rel_mode=rel_mode, charge=charge, mult=mult, nprocs=nprocs
    )

    # Monomer B (frag_b real, frag_a ghost)
    monomer_b_coords = [(f"{str(c[0]).rstrip(':')}:", c[1], c[2], c[3]) for c in frag_a] + \
                       [(str(c[0]), c[1], c[2], c[3]) for c in frag_b]
    monomer_b_inp = generate_dlpno_ccsd_f12(
        monomer_b_coords, basis=basis, is_opt=False, in_hess=in_hess,
        rel_mode=rel_mode, charge=charge, mult=mult, nprocs=nprocs
    )

    result = {
        "complex_input": complex_inp,
        "monomer_a_input": monomer_a_inp,
        "monomer_b_input": monomer_b_inp,
    }
    
    if is_opt:
        result["cp_opt_enforced"] = not is_aug
    else:
        result["bsse_accuracy_capped_3pct"] = not is_aug

    return result

def compute_counterpoise_corrected_energy(
    e_complex: float,
    e_monomer_a_cp: float,
    e_monomer_b_cp: float,
    e_monomer_a_raw: float,
    e_monomer_b_raw: float
) -> dict[str, float]:
    """
    Computes CP-corrected interaction energy and BSSE correction in Hartree.
    """
    delta_e_cp = e_complex - e_monomer_a_cp - e_monomer_b_cp
    e_bsse = (e_monomer_a_raw + e_monomer_b_raw) - (e_monomer_a_cp + e_monomer_b_cp)
    return {
        "delta_e_cp_hartree": delta_e_cp,
        "e_bsse_hartree": e_bsse,
        "delta_e_raw_hartree": e_complex - e_monomer_a_raw - e_monomer_b_raw
    }

def generate_isotopologue_freq_input(
    parent_hess_path: str,
    coords: list[tuple[str, float, float, float] | list[Any]],
    mass_substitutions: dict[int, float],
    charge: int = 0,
    mult: int = 1,
    nprocs: int = 1
) -> str:
    """
    Implements the 'Zero-Cost' Electronic Structure shortcut for isotopologues
    (Method Matrix Row 9). By reading an existing .hess file and substituting 
    atomic masses, vibrational frequencies and rotational constants (Product B/C)
    are re-computed without any new SCF or gradient evaluations.
    This delivers a 6-15x efficiency gain on isotopologue campaigns.
    
    mass_substitutions: Dict mapping 0-indexed atom index to new atomic mass.
    """
    lines = ["! Freq"]
    
    if nprocs > 1:
        lines.append(f"%pal nprocs {nprocs} end")
        
    lines.append("%freq")
    lines.append(f'  InHessName "{parent_hess_path}"')
    if mass_substitutions:
        lines.append("  Mass")
        for idx, new_mass in mass_substitutions.items():
            lines.append(f"    {idx} {new_mass:.5f}")
        lines.append("  end")
    lines.append("end")
    
    lines.append(f"* xyz {charge} {mult}")
    for c in coords:
        lines.append(f"  {c[0]}  {c[1]:12.8f}  {c[2]:12.8f}  {c[3]:12.8f}")
    lines.append("*")
    
    return "\n".join(lines) + "\n"
