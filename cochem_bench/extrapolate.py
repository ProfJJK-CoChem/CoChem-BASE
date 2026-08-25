"""
CoChem-BENCH Extrapolation Algorithms
Complete Basis Set (CBS) Extrapolations (Halkier, F12, Karton-Martin, Feller).
"""
import math
def calculate_halkier(corr_x3: float, corr_x4: float) -> float:
    """
    Halkier 1/X^3 two-point correlation energy CBS extrapolation for T/Q zeta.
    E_corr(CBS) = (4^3 * E(4) - 3^3 * E(3)) / (4^3 - 3^3) = (64*E(4) - 27*E(3)) / 37
    """
    return (64.0 * corr_x4 - 27.0 * corr_x3) / 37.0

def calculate_f12_cbs(corr_x3: float, corr_x4: float, beta: float = 7.0) -> float:
    """
    F12 1/X^beta CBS correlation energy extrapolation.
    Default beta = 7.0 for explicit correlation F12 convergence.
    """
    c3 = 3.0 ** beta
    c4 = 4.0 ** beta
    return (c4 * corr_x4 - c3 * corr_x3) / (c4 - c3)

def calculate_karton_martin(hf_x3: float, hf_x4: float, family: str = "aug-cc-pVXZ") -> float:
    """
    Karton-Martin exponential two-point HF CBS extrapolation.
    E_HF(X) = E_HF(CBS) + A * exp(-alpha * sqrt(X))
    """
    if "aug" in family.lower():
        alpha = 5.46
    else:
        alpha = 5.70
    
    exp3 = math.exp(-alpha * math.sqrt(3.0))
    exp4 = math.exp(-alpha * math.sqrt(4.0))
    
    # E_HF(CBS) = (hf_x4 * exp3 - hf_x3 * exp4) / (exp3 - exp4)
    # If hf_x3 is higher (less negative) than hf_x4:
    cbs = (hf_x4 * exp3 - hf_x3 * exp4) / (exp3 - exp4)
    return cbs

def compute_total_cbs_energy(
    hf_x3: float,
    hf_x4: float,
    corr_x3: float,
    corr_x4: float,
    is_f12: bool = True,
    basis_family: str = "aug-cc-pVXZ"
) -> dict[str, float]:
    """
    Computes total CBS energy combining HF and correlation components.
    """
    hf_cbs = calculate_karton_martin(hf_x3, hf_x4, family=basis_family)
    if is_f12:
        corr_cbs = calculate_f12_cbs(corr_x3, corr_x4, beta=7.0)
    else:
        corr_cbs = calculate_halkier(corr_x3, corr_x4)
    
    total_cbs = hf_cbs + corr_cbs
    return {
        "hf_cbs": hf_cbs,
        "corr_cbs": corr_cbs,
        "total_cbs": total_cbs
    }
