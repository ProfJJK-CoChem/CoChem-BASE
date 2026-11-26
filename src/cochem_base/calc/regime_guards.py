"""Chemical-regime auto-guards, coupled-cluster T1/D1 diagnostics, SCF retry, and imaginary-mode re-optimization.

Implements authentic physics-grounded safeguards for ORCA, CFOUR, PySCF, and GPU4PySCF:
1. Anion diffuse-basis auto-guard (`charge < 0`): upgrades non-diffuse basis sets to matching
   diffuse sets with explicit user-facing warnings and provenance (never silent).
2. Heavy-element scalar-relativistic / ECP & 3d transition-metal grid auto-guard using the
   complete IUPAC Z=1..118 periodic table (`21 <= Z <= 30` -> DEFGRID3; `Z > 36` ->
   engine-appropriate scalar-relativistic Hamiltonian/ECP + DEFGRID3).
3. Live coupled-cluster T1/D1 multireference diagnostics parser and warning gate for ORCA and
   CFOUR (`T1 > 0.020` closed-shell / `0.045` open-shell; `D1 > 0.050` / `0.070`; never fabricates
   missing values).
4. Bounded ORCA SCF retry remediation (`SlowConvInterceptor` + `RegexTrapEngine`, injecting
   `SlowConv`/`KDIIS`/`MaxIter 300`, capped at 2 retries) and authentic Hessian imaginary-mode
   eigenvector displacement + re-optimization helper (capped at 2 retries, failing closed).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import logging
import math
import re
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from cochem_base.exceptions import GeometryConvergenceError

logger = logging.getLogger(__name__)

# Complete IUPAC periodic table atomic numbers Z = 1..118 (integers only; zero static masses).
SYMBOL_TO_ATOMIC_NUMBER: dict[str, int] = {
    "H": 1, "He": 2,
    "Li": 3, "Be": 4, "B": 5, "C": 6, "N": 7, "O": 8, "F": 9, "Ne": 10,
    "Na": 11, "Mg": 12, "Al": 13, "Si": 14, "P": 15, "S": 16, "Cl": 17, "Ar": 18,
    "K": 19, "Ca": 20, "Sc": 21, "Ti": 22, "V": 23, "Cr": 24, "Mn": 25,
    "Fe": 26, "Co": 27, "Ni": 28, "Cu": 29, "Zn": 30,
    "Ga": 31, "Ge": 32, "As": 33, "Se": 34, "Br": 35, "Kr": 36,
    "Rb": 37, "Sr": 38, "Y": 39, "Zr": 40, "Nb": 41, "Mo": 42, "Tc": 43,
    "Ru": 44, "Rh": 45, "Pd": 46, "Ag": 47, "Cd": 48,
    "In": 49, "Sn": 50, "Sb": 51, "Te": 52, "I": 53, "Xe": 54,
    "Cs": 55, "Ba": 56,
    "La": 57, "Ce": 58, "Pr": 59, "Nd": 60, "Pm": 61, "Sm": 62, "Eu": 63,
    "Gd": 64, "Tb": 65, "Dy": 66, "Ho": 67, "Er": 68, "Tm": 69, "Yb": 70, "Lu": 71,
    "Hf": 72, "Ta": 73, "W": 74, "Re": 75, "Os": 76, "Ir": 77, "Pt": 78, "Au": 79, "Hg": 80,
    "Tl": 81, "Pb": 82, "Bi": 83, "Po": 84, "At": 85, "Rn": 86,
    "Fr": 87, "Ra": 88,
    "Ac": 89, "Th": 90, "Pa": 91, "U": 92, "Np": 93, "Pu": 94, "Am": 95,
    "Cm": 96, "Bk": 97, "Cf": 98, "Es": 99, "Fm": 100, "Md": 101, "No": 102, "Lr": 103,
    "Rf": 104, "Db": 105, "Sg": 106, "Bh": 107, "Hs": 108, "Mt": 109,
    "Ds": 110, "Rg": 111, "Cn": 112, "Nh": 113, "Fl": 114, "Mc": 115,
    "Lv": 116, "Ts": 117, "Og": 118,
}

ELEMENT_Z: dict[str, int] = dict(SYMBOL_TO_ATOMIC_NUMBER)

_COMPOSITE_METHODS = frozenset({"R2SCAN-3C", "B97-3C", "HF-3C", "PBEH-3C", "W97X-3C", "WB97X-3C"})
_RELATIVISTIC_KEYWORDS = frozenset({"DKH", "DKH2", "ZORA", "X2C", "IORA", "IORAMM"})
_NUMBER_RE = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][-+]?\d+)?"

# Coupled-cluster multireference thresholds (Lee & Taylor 1989; Janssen & Nielsen 1998;
# Jiang, DeYonker & Wilson 2012 for open-shell transition-metal / radical species).
T1_CLOSED_SHELL_THRESHOLD = 0.020
T1_OPEN_SHELL_THRESHOLD = 0.045
D1_CLOSED_SHELL_THRESHOLD = 0.050
D1_OPEN_SHELL_THRESHOLD = 0.070

MAX_SCF_RETRIES = 2
MAX_IMAGINARY_MODE_RETRIES = 2


class ImaginaryModePersistenceError(GeometryConvergenceError):
    """Raised fail-closed when genuine imaginary vibrational modes persist after bounded retries."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


def normalize_element_symbol(symbol: str) -> str:
    """Normalize an atom or nuclide token (e.g. '13C', 'D', 'T', 'I:', 'au') to its IUPAC symbol."""
    cleaned = symbol.strip().rstrip(":")
    if not cleaned:
        raise ValueError("Element symbol cannot be empty")
    match = re.fullmatch(r"(?:\d+)?([A-Za-z]{1,2})(?:[-_]?\d+)?", cleaned)
    if match is None:
        raise ValueError(f"Unrecognized chemical element token: {symbol!r}")
    token = match.group(1)
    if token.upper() in {"D", "T"}:
        return "H"
    canonical = token[0].upper() + token[1:].lower()
    if canonical not in SYMBOL_TO_ATOMIC_NUMBER:
        raise ValueError(f"Unknown IUPAC element symbol: {symbol!r} (normalized {canonical!r})")
    return canonical


def resolve_atomic_number(symbol: str) -> int:
    """Return the IUPAC atomic number Z (1..118) for any element or isotope token."""
    return SYMBOL_TO_ATOMIC_NUMBER[normalize_element_symbol(symbol)]


def is_composite_method(method_or_theory: str) -> bool:
    """Return True when the theory string names an ORCA composite method with a fixed basis."""
    tokens = {tok.upper() for tok in method_or_theory.split()}
    return bool(tokens & _COMPOSITE_METHODS)


def is_diffuse_basis(basis: str) -> bool:
    """Return True if the Gaussian basis label already includes diffuse functions."""
    cleaned = basis.strip()
    if not cleaned:
        return False
    lower = cleaned.lower()
    # Explicitly diffuse prefixes/families: ma-def2-*, aug-*, d-aug-*, jun-*, may-*, apr-*, jul-*, ano-rcc
    if lower.startswith((
        "ma-", "aug-", "d-aug-", "t-aug-", "maug-", "jun-", "may-", "apr-", "jul-",
        "dkh-ma-", "zora-ma-", "ano-rcc",
    )):
        return True
    # Minimally augmented or doubly-diffuse def2 sets: def2-SVPD, def2-TZVPD, def2-TZVPPD, def2-QZVPD, def2-QZVPPD
    if re.fullmatch(r"(?:(?:dkh|zora)-)?def2-(?:s|tz|qz)vp{1,2}d", lower):
        return True
    # Diffuse Pople sets: 6-31+G*, 6-31++G**, 6-311+G(d,p), 3-21+G, etc.
    if "+" in lower:
        return True
    # Diffuse Dunning/Jensen/Sapporo labels containing -aug- or diffuse
    if "-aug-" in lower or "diffuse" in lower or lower.endswith("-d"):
        return True
    return False


def _match_basis_token(theory_level: str) -> tuple[int, str] | None:
    """Locate the primary orbital basis token inside an ORCA theory_level string."""
    tokens = theory_level.split()
    basis_pattern = re.compile(
        r"^(?:(?:dkh|zora|ma|aug|d-aug|t-aug|maug|jun|may|apr|jul|old-dkh|old-zora|sarc-dkh|sarc-zora)-)*"
        r"(?:def2-(?:sv\(p\)|msvp|svpd|svp|tzvp\(-f\)|tzvppd|tzvpp|tzvpd|tzvp|qzvppd|qzvpp|qzvpd|qzvp)|"
        r"x2c-(?:sv\(p\)|svp|tzvpp|tzvp|qzvpp|qzvp)all(?:-2c)?(?:-s)?|"
        r"cc-p(?:w?c)?v[dtq56]z(?:-dk|-pp|-f12)?|"
        r"p(?:w?c)?v[dtq56]z|sto-[36]g|[346]-\d+\+{0,2}g(?:\*{0,2}|\([dfp,]+\))?|"
        r"pc(?:seg)?-[0-4]|ano[0-9a-z_-]*|mini|minix|midi|dz|dzp|d95\*?)$",
        re.IGNORECASE,
    )
    for idx, token in enumerate(tokens):
        if token.endswith(("/J", "/C", "/JK", "/j", "/c", "/jk")):
            continue
        if basis_pattern.fullmatch(token):
            return idx, token
    return None


def _basis_zeta(basis: str) -> int | None:
    """Return the cardinal zeta number (1=SZ, 2=DZ/SVP, 3=TZ, 4=QZ, 5=5Z, 6=6Z), or None if unknown."""
    lower = basis.strip().lower()
    if not lower:
        return None
    if re.search(r"(?:^|-)p?(?:w?c)?v6z(?:$|-)", lower):
        return 6
    if re.search(r"(?:^|-)p?(?:w?c)?v5z(?:$|-)", lower) or re.fullmatch(r"(?:aug-)?pc(?:seg)?-4", lower):
        return 5
    if (
        re.search(r"(?:^|-)p?(?:w?c)?vqz(?:$|-)", lower)
        or re.search(r"(?:^|-)qzvp{1,2}(?:d|all)?(?:$|[-_(])", lower)
        or re.fullmatch(r"(?:aug-)?pc(?:seg)?-3", lower)
        or lower in {"ano2", "ano-rcc-vqzp"}
    ):
        return 4
    if (
        re.search(r"(?:^|-)p?(?:w?c)?vtz(?:$|-)", lower)
        or re.search(r"(?:^|-)tzvp{1,2}(?:d|all)?(?:$|[-_(])", lower)
        or re.fullmatch(r"6-311\+{0,2}g(?:\*{0,2}|\([^)]+\))?", lower)
        or re.fullmatch(r"(?:aug-)?pc(?:seg)?-2", lower)
        or lower in {"ano1", "ano-rcc-vtzp"}
    ):
        return 3
    if (
        re.search(r"(?:^|-)p?(?:w?c)?vdz(?:$|-)", lower)
        or re.search(r"(?:^|-)(?:m?sv\(?p\)?d?|svp(?:d|all)?|sv\(p\)all)(?:$|[-_(])", lower)
        or re.fullmatch(r"[346]-[23]1\+{0,2}g(?:\*{0,2}|\([^)]+\))?", lower)
        or re.fullmatch(r"(?:aug-)?pc(?:seg)?-[01]", lower)
        or lower in {"dz", "dzp", "d95", "d95*", "ano0", "ano-rcc-vdzp"}
    ):
        return 2
    if lower in {"sto-3g", "sto-6g", "mini", "minix", "midi"}:
        return 1
    return None


def _basis_family_tags(basis: str) -> frozenset[str]:
    """Extract relativistic/pseudopotential family tags that must never be stripped."""
    lower = basis.strip().lower()
    tags: set[str] = set()
    if lower.startswith(("dkh-", "ma-dkh-", "dkh-ma-", "old-dkh-", "sarc-dkh-")) or lower.endswith("-dk"):
        tags.add("dkh")
    if lower.startswith(("zora-", "ma-zora-", "zora-ma-", "old-zora-", "sarc-zora-")):
        tags.add("zora")
    if lower.startswith(("x2c-", "ma-x2c-", "aug-x2c-")) or lower.endswith("-x2c"):
        tags.add("x2c")
    if lower.endswith("-pp"):
        tags.add("pp")
    return frozenset(tags)


def _assert_non_downgrading_diffuse_upgrade(original: str, upgraded: str, *, engine: str) -> str:
    """Enforce structural invariants: diffuse output, zeta monotonicity, and family preservation."""
    if not is_diffuse_basis(upgraded):
        raise ValueError(
            f"Internal regime-guard invariant violated on engine={engine!r}: mapped basis {upgraded!r} "
            f"for {original!r} is not diffuse."
        )
    orig_zeta = _basis_zeta(original)
    new_zeta = _basis_zeta(upgraded)
    if orig_zeta is not None and (new_zeta is None or new_zeta < orig_zeta):
        raise ValueError(
            f"Refusing silent basis zeta downgrade for anion on engine={engine!r}: "
            f"{original!r} (zeta={orig_zeta}) -> {upgraded!r} (zeta={new_zeta})."
        )
    orig_tags = _basis_family_tags(original)
    new_tags = _basis_family_tags(upgraded)
    if not orig_tags.issubset(new_tags):
        raise ValueError(
            f"Refusing relativistic/ECP family stripping for anion on engine={engine!r}: "
            f"{original!r} ({sorted(orig_tags)}) -> {upgraded!r} ({sorted(new_tags)})."
        )
    return upgraded


@dataclass(frozen=True)
class AnionDiffuseGuardDecision:
    """Explicit provenance record for the anion diffuse-basis auto-guard."""

    guard: str = "anion_diffuse_basis"
    triggered: bool = False
    charge: int = 0
    engine: str = "orca"
    original_basis: str | None = None
    effective_basis: str | None = None
    warning: str | None = None
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _map_diffuse_basis(basis: str, engine: str) -> str:
    """Map a non-diffuse basis set to an exact same-family, non-downgrading diffuse basis.

    Raises:
        ValueError: Fail closed when no verified same-zeta, same-family diffuse counterpart
            exists (including relativistic x2c-* bases or unrecognized exotic basis sets).
            Never silently falls back to ma-def2-SVP or aug-cc-pVDZ.
    """
    cleaned = basis.strip()
    lower = cleaned.lower()
    eng = engine.strip().lower()
    orig_zeta = _basis_zeta(cleaned)
    candidate: str | None = None

    # Karlsruhe def2 family (including ORCA DKH-def2-* and ZORA-def2-* scalar-relativistic sets)
    if eng == "cfour":
        cfour_def2 = {
            "def2-sv(p)": "def2-SVPD",
            "def2-svp": "def2-SVPD",
            "def2-tzvp": "def2-TZVPD",
            "def2-tzvpp": "def2-TZVPPD",
            "def2-qzvp": "def2-QZVPD",
            "def2-qzvpp": "def2-QZVPPD",
        }
        if lower in cfour_def2:
            candidate = cfour_def2[lower]
    else:
        orca_pyscf_def2 = {
            "def2-sv(p)": "ma-def2-SVP",
            "def2-svp": "ma-def2-SVP",
            "def2-tzvp": "ma-def2-TZVP",
            "def2-tzvpp": "def2-TZVPPD",
            "def2-qzvp": "ma-def2-QZVP",
            "def2-qzvpp": "def2-QZVPPD",
            # Verified live in ORCA 6.1.1: ma-DKH-def2-{SV(P),SVP,TZVP,TZVP(-f),TZVPP,QZVPP}
            # Note: ORCA 6 defines ma-DKH-def2-QZVPP (not ma-DKH-def2-QZVP)
            "dkh-def2-sv(p)": "ma-DKH-def2-SV(P)",
            "dkh-def2-svp": "ma-DKH-def2-SVP",
            "dkh-def2-tzvp": "ma-DKH-def2-TZVP",
            "dkh-def2-tzvp(-f)": "ma-DKH-def2-TZVP(-f)",
            "dkh-def2-tzvpp": "ma-DKH-def2-TZVPP",
            "dkh-def2-qzvp": "ma-DKH-def2-QZVPP",
            "dkh-def2-qzvpp": "ma-DKH-def2-QZVPP",
            # Verified live in ORCA 6.1.1: ma-ZORA-def2-{SV(P),SVP,TZVP,TZVP(-f),TZVPP,QZVPP}
            "zora-def2-sv(p)": "ma-ZORA-def2-SV(P)",
            "zora-def2-svp": "ma-ZORA-def2-SVP",
            "zora-def2-tzvp": "ma-ZORA-def2-TZVP",
            "zora-def2-tzvp(-f)": "ma-ZORA-def2-TZVP(-f)",
            "zora-def2-tzvpp": "ma-ZORA-def2-TZVPP",
            "zora-def2-qzvp": "ma-ZORA-def2-QZVPP",
            "zora-def2-qzvpp": "ma-ZORA-def2-QZVPP",
        }
        if lower in orca_pyscf_def2:
            candidate = orca_pyscf_def2[lower]

    # Dunning correlation-consistent family:
    # cc-pV(D|T|Q|5)Z-PP, cc-pV(D|T|Q|5)Z-DK, cc-p(w)CV(D|T|Q|5)Z(-DK|-PP)?, cc-pV(D|T|Q|5|6)Z(-F12)?
    if candidate is None:
        dunning_rel_pp = re.fullmatch(r"(cc-p(?:w?c)?v[dtq5]z-(?:dk|pp))", cleaned, re.IGNORECASE)
        if dunning_rel_pp:
            candidate = f"aug-{dunning_rel_pp.group(1)}"

    if candidate is None:
        dunning_std = re.fullmatch(r"(cc-p(?:w?c)?v[dtq56]z(?:-f12)?)", cleaned, re.IGNORECASE)
        if dunning_std:
            candidate = f"aug-{dunning_std.group(1)}"

    # CFOUR short Dunning keywords (PVDZ -> AUG-PVDZ, PWCVTZ -> AUG-PWCVTZ, etc.)
    if candidate is None:
        cfour_short = re.fullmatch(r"(p(?:w?c)?v[dtq56]z)", cleaned, re.IGNORECASE)
        if cfour_short:
            candidate = f"AUG-{cfour_short.group(1).upper()}"

    # Pople split-valence sets (6-31G*, 6-31G**, 6-311G(d,p), etc.)
    if candidate is None:
        pople = re.fullmatch(r"([346]-\d+)g(\*{0,2}|\([^)]+\))?", cleaned, re.IGNORECASE)
        if pople:
            stem, pol = pople.group(1), pople.group(2) or ""
            if stem == "3-21":
                candidate = "aug-cc-pVDZ" if eng == "cfour" else "ma-def2-SVP"
            else:
                diffuse_plus = "++" if ("**" in pol or "," in pol) else "+"
                candidate = f"{stem}{diffuse_plus}G{pol}"

    # Jensen polarization-consistent sets (pc-n, pcseg-n)
    if candidate is None:
        jensen = re.fullmatch(r"(pc(?:seg)?-[0-4])", cleaned, re.IGNORECASE)
        if jensen:
            candidate = f"aug-{jensen.group(1)}"

    # Explicitly recognized minimal / double-zeta non-relativistic basis sets (zeta <= 2 only)
    if candidate is None and lower in {"sto-3g", "sto-6g", "mini", "minix", "dz", "dzp", "d95", "d95*", "midi"}:
        candidate = "aug-cc-pVDZ" if eng == "cfour" else "ma-def2-SVP"

    if candidate is None:
        zeta_note = f" (zeta={orig_zeta})" if orig_zeta is not None else ""
        if lower.startswith("x2c-") or lower.endswith("-x2c"):
            raise ValueError(
                f"Anion diffuse-basis guard cannot auto-upgrade relativistic X2C basis {cleaned!r}{zeta_note} "
                f"on engine={eng!r}: ORCA 6 / standard libraries provide no exact same-zeta diffuse x2c-* "
                f"counterpart, and silent downgrade to ma-def2-SVP/aug-cc-pVDZ is prohibited. "
                f"Please specify an explicit diffuse basis of matching zeta (e.g., ma-DKH-def2-TZVP, "
                f"ma-ZORA-def2-TZVP, aug-cc-pVTZ-DK, or aug-cc-pVTZ-PP)."
            )
        raise ValueError(
            f"Anion diffuse-basis guard has no verified same-zeta, same-family diffuse counterpart "
            f"for basis {cleaned!r}{zeta_note} on engine={eng!r}; refusing silent fallback to "
            f"ma-def2-SVP/aug-cc-pVDZ. Please specify an explicit diffuse basis of matching zeta."
        )

    return _assert_non_downgrading_diffuse_upgrade(cleaned, candidate, engine=eng)


def upgrade_anion_diffuse_basis(
    basis: str | None,
    *,
    charge: int,
    engine: str = "orca",
    method_or_theory: str = "",
) -> AnionDiffuseGuardDecision:
    """Upgrade non-diffuse basis sets automatically for anionic systems (`charge < 0`)."""
    eng = engine.strip().lower()
    if charge >= 0:
        return AnionDiffuseGuardDecision(
            triggered=False,
            charge=charge,
            engine=eng,
            original_basis=basis,
            effective_basis=basis,
            reason="Non-anionic system (charge >= 0); no diffuse-basis upgrade required.",
        )

    if is_composite_method(method_or_theory):
        warning = (
            f"[REGIME_GUARD: ANION_COMPOSITE_BASIS] Anionic system (charge={charge}) requested with "
            f"fixed-basis composite method '{method_or_theory}'. Composite methods cannot append an "
            f"external diffuse basis; consider switching to a diffuse-augmented functional/basis "
            f"(e.g., wB97M-V ma-def2-TZVP or B3LYP D3BJ def2-TZVPPD)."
        )
        logger.warning(warning)
        return AnionDiffuseGuardDecision(
            triggered=True,
            charge=charge,
            engine=eng,
            original_basis=basis,
            effective_basis=basis,
            warning=warning,
            reason="Composite method has built-in non-overridable basis; emitted anion diffuse advisory.",
        )

    if not basis or not basis.strip():
        return AnionDiffuseGuardDecision(
            triggered=False,
            charge=charge,
            engine=eng,
            original_basis=basis,
            effective_basis=basis,
            reason="No explicit orbital basis supplied.",
        )

    cleaned = basis.strip()
    if is_diffuse_basis(cleaned):
        return AnionDiffuseGuardDecision(
            triggered=False,
            charge=charge,
            engine=eng,
            original_basis=cleaned,
            effective_basis=cleaned,
            reason=f"Requested basis '{cleaned}' already contains diffuse functions.",
        )

    upgraded = _map_diffuse_basis(cleaned, eng)
    warning = (
        f"[REGIME_GUARD: ANION_DIFFUSE_UPGRADE] Anionic system (charge={charge}) on engine={eng}: "
        f"automatically upgraded non-diffuse basis '{cleaned}' -> '{upgraded}' to prevent "
        f"artificial electron confinement and unreliable electron affinities."
    )
    logger.warning(warning)
    return AnionDiffuseGuardDecision(
        triggered=True,
        charge=charge,
        engine=eng,
        original_basis=cleaned,
        effective_basis=upgraded,
        warning=warning,
        reason=f"Anion (charge={charge}) requires diffuse functions; upgraded '{cleaned}' -> '{upgraded}'.",
    )


@dataclass(frozen=True)
class HeavyElementGuardDecision:
    """Explicit provenance record for heavy-element relativistic/ECP and 3d-TM grid auto-guard."""

    guard: str = "heavy_element_and_tm_regime"
    triggered: bool = False
    engine: str = "orca"
    max_atomic_number: int = 0
    transition_metals_3d: tuple[str, ...] = ()
    heavy_elements: tuple[str, ...] = ()
    superheavy_elements: tuple[str, ...] = ()
    require_defgrid3: bool = False
    relativistic_mode: str | None = None
    injected_keywords: tuple[str, ...] = ()
    orca_basis_block_lines: tuple[str, ...] = ()
    cfour_keywords: tuple[str, ...] = ()
    pyscf_ecp: dict[str, str] | None = None
    pyscf_sfx2c1e: bool = False
    effective_basis: str | None = None
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in (
            "transition_metals_3d",
            "heavy_elements",
            "superheavy_elements",
            "injected_keywords",
            "orca_basis_block_lines",
            "cfour_keywords",
            "warnings",
        ):
            data[key] = list(data[key])
        return data


def _is_def2_ecp_basis(basis: str | None) -> bool:
    if not basis:
        return False
    return bool(
        re.fullmatch(
            r"(?:ma-)?def2-(?:sv\(p\)|msvp|svpd|svp|tzvppd|tzvpp|tzvpd|tzvp|qzvppd|qzvpp|qzvpd|qzvp)",
            basis.strip(),
            re.IGNORECASE,
        )
    )


def _is_pp_ecp_basis(basis: str | None) -> bool:
    if not basis:
        return False
    return bool(
        re.fullmatch(
            r"(?:(?:d-|t-)?aug-|jun-|may-|apr-|jul-)?cc-p(?:w?c)?v[dtq5]z-pp",
            basis.strip(),
            re.IGNORECASE,
        )
    )


def _to_dkh_or_zora_base_basis(basis: str | None, hamiltonian: str) -> str:
    """Convert a standard def2/light basis to a valid ORCA DKH2/ZORA light-atom basis without zeta downgrade."""
    prefix = "ZORA" if hamiltonian.upper() == "ZORA" else "DKH"
    if not basis:
        return f"{prefix}-def2-TZVP"
    cleaned = basis.strip()
    lower = cleaned.lower()
    if lower.startswith((f"{prefix.lower()}-", f"ma-{prefix.lower()}-", f"sarc-{prefix.lower()}-", f"old-{prefix.lower()}-")):
        if lower == f"{prefix.lower()}-def2-qzvp":
            return f"{prefix}-def2-QZVPP"
        if lower == f"ma-{prefix.lower()}-def2-qzvp":
            return f"ma-{prefix}-def2-QZVPP"
        return cleaned
    if prefix == "DKH" and lower.endswith("-dk"):
        return cleaned
    if lower.startswith("ma-def2-"):
        suffix = cleaned[8:]
        if suffix.lower() == "qzvp":
            suffix = "QZVPP"
        return f"ma-{prefix}-def2-{suffix}"
    if lower in {"def2-svpd", "def2-tzvpd", "def2-tzvppd", "def2-qzvpd", "def2-qzvppd"}:
        mapped_d = {
            "def2-svpd": f"ma-{prefix}-def2-SVP",
            "def2-tzvpd": f"ma-{prefix}-def2-TZVP",
            "def2-tzvppd": f"ma-{prefix}-def2-TZVPP",
            "def2-qzvpd": f"ma-{prefix}-def2-QZVPP",
            "def2-qzvppd": f"ma-{prefix}-def2-QZVPP",
        }
        return mapped_d[lower]
    if lower.startswith("def2-"):
        suffix = cleaned[5:]
        if suffix.lower() == "qzvp":
            suffix = "QZVPP"
        return f"{prefix}-def2-{suffix}"
    if re.fullmatch(r"(?:aug-)?cc-p(?:w?c)?v[dtq5]z", lower):
        if prefix == "DKH":
            return f"{cleaned}-DK"
        zeta = _basis_zeta(cleaned) or 3
        stem = {2: "SVP", 3: "TZVP", 4: "QZVPP", 5: "QZVPP"}.get(zeta, "TZVP")
        return f"ma-ZORA-def2-{stem}" if is_diffuse_basis(cleaned) else f"ZORA-def2-{stem}"
    return f"{prefix}-def2-TZVP"


def evaluate_heavy_element_and_tm_guard(
    elements: Sequence[str],
    *,
    method_or_theory: str = "",
    basis: str | None = None,
    engine: str = "orca",
) -> HeavyElementGuardDecision:
    """Inspect atomic numbers Z=1..118 and enforce 3d-TM DEFGRID3 and Z>36 relativistic/ECP rules."""
    eng = engine.strip().lower()
    normalized = [normalize_element_symbol(sym) for sym in elements]
    z_values = [(sym, SYMBOL_TO_ATOMIC_NUMBER[sym]) for sym in normalized]
    max_z = max((z for _, z in z_values), default=0)

    tm_3d = tuple(dict.fromkeys(sym for sym, z in z_values if 21 <= z <= 30))
    heavy = tuple(dict.fromkeys(sym for sym, z in z_values if z > 36))
    heavy_37_86 = tuple(dict.fromkeys(sym for sym, z in z_values if 37 <= z <= 86))
    superheavy = tuple(dict.fromkeys(sym for sym, z in z_values if z > 86))

    warnings_list: list[str] = []
    injected_keywords: list[str] = []
    orca_basis_block_lines: list[str] = []
    cfour_keywords: list[str] = []
    pyscf_ecp: dict[str, str] | None = None
    pyscf_sfx2c1e = False
    relativistic_mode: str | None = None
    effective_basis = basis.strip() if basis else None
    require_defgrid3 = bool(tm_3d or heavy)

    if not tm_3d and not heavy:
        return HeavyElementGuardDecision(
            triggered=False,
            engine=eng,
            max_atomic_number=max_z,
            effective_basis=effective_basis,
        )

    if tm_3d and not heavy:
        w = (
            f"[REGIME_GUARD: 3D_TM_GRID] Detected 3d transition metal(s) {', '.join(tm_3d)} "
            f"(Z in 21..30) on engine={eng}: enforcing tight quadrature grid (DEFGRID3 / fine XC grid) "
            f"to eliminate d-shell angular integration noise."
        )
        logger.warning(w)
        warnings_list.append(w)
        return HeavyElementGuardDecision(
            triggered=True,
            engine=eng,
            max_atomic_number=max_z,
            transition_metals_3d=tm_3d,
            require_defgrid3=True,
            effective_basis=effective_basis,
            warnings=tuple(warnings_list),
        )

    # Z > 36 heavy elements present
    if tm_3d:
        w_tm = (
            f"[REGIME_GUARD: 3D_TM_GRID] Detected 3d transition metal(s) {', '.join(tm_3d)} alongside "
            f"heavy element(s) {', '.join(heavy)}; enforcing DEFGRID3."
        )
        logger.warning(w_tm)
        warnings_list.append(w_tm)

    theory_tokens = {tok.upper() for tok in method_or_theory.split()}
    existing_rel = next((tok for tok in ("DKH2", "DKH", "ZORA", "X2C") if tok in theory_tokens), None)

    if eng == "orca":
        if is_composite_method(method_or_theory):
            relativistic_mode = "def2-ECP (built-in composite)" if not superheavy else "ADVISORY_SUPERHEAVY"
            w = (
                f"[REGIME_GUARD: HEAVY_ELEMENT_RELATIVISTIC] Heavy element(s) {', '.join(heavy)} "
                f"(max Z={max_z}) with composite method '{method_or_theory}': enforcing DEFGRID3. "
                + (
                    "Built-in def2-ECP provides scalar-relativistic core potentials for Z=37..86."
                    if not superheavy
                    else f"Elements {', '.join(superheavy)} (Z>86) exceed def2-ECP coverage; switch to DKH2 + SARC-DKH-TZVP."
                )
            )
            logger.warning(w)
            warnings_list.append(w)
        elif existing_rel is None and not superheavy and _is_def2_ecp_basis(effective_basis):
            # ORCA 6 automatically assigns scalar-relativistic Karlsruhe def2-ECP for Rb..Rn (37..86)
            relativistic_mode = "def2-ECP"
            w = (
                f"[REGIME_GUARD: HEAVY_ELEMENT_ECP] Heavy element(s) {', '.join(heavy)} (max Z={max_z}, Z in 37..86) "
                f"on ORCA with Karlsruhe basis '{effective_basis}': scalar-relativistic Def2-ECP is active "
                f"and DEFGRID3 is enforced."
            )
            logger.warning(w)
            warnings_list.append(w)
        elif existing_rel is None and not superheavy and _is_pp_ecp_basis(effective_basis):
            # ORCA 6 automatically assigns scalar-relativistic SK-MCDHF-RSC ECPs for -PP bases
            # on heavy atoms (Z=37..86). For mixed molecules containing light atoms (Z <= 28)
            # lacking -PP definitions in ORCA, assign the matching same-zeta non-PP Dunning
            # basis via %basis NewGTO while keeping the global -PP basis and ECP intact.
            relativistic_mode = "PP-ECP (SK-MCDHF-RSC)"
            non_pp_basis = effective_basis[:-3]
            light_for_pp = tuple(dict.fromkeys(sym for sym, z in z_values if z <= 28))
            for sym in light_for_pp:
                orca_basis_block_lines.append(f'  NewGTO {sym} "{non_pp_basis}" end')
            w = (
                f"[REGIME_GUARD: HEAVY_ELEMENT_ECP] Heavy element(s) {', '.join(heavy)} (max Z={max_z}, Z in 37..86) "
                f"on ORCA with pseudopotential basis '{effective_basis}': scalar-relativistic SK-MCDHF-RSC ECP "
                f"is active and DEFGRID3 is enforced."
            )
            logger.warning(w)
            warnings_list.append(w)
        else:
            # All-electron basis (e.g., cc-pVXZ, STO-3G, 6-31G*), explicit DKH2/ZORA, or Z > 86:
            # Inject DKH2 (or preserve explicit ZORA/X2C) with valid ORCA 6 scalar-relativistic basis sets.
            ham = "ZORA" if existing_rel == "ZORA" else "DKH2"
            relativistic_mode = ham
            if existing_rel is None:
                injected_keywords.append(ham)
            effective_basis = _to_dkh_or_zora_base_basis(effective_basis, ham)
            # ORCA's DKH-def2-* / ZORA-def2-* cover Z=1..36; Z=37..54 use old-DKH-TZVP / old-ZORA-TZVP;
            # Z=55..103 use SARC-DKH-TZVP / SARC-ZORA-TZVP (SARC-DKH-TZVP covers Cs..Lr).
            for sym in heavy:
                z = SYMBOL_TO_ATOMIC_NUMBER[sym]
                if 37 <= z <= 54:
                    rel_atom_basis = f"old-{ham[:3]}-TZVP" if ham == "DKH2" else "old-ZORA-TZVP"
                else:
                    rel_atom_basis = "SARC-ZORA-TZVP" if ham == "ZORA" else "SARC-DKH-TZVP"
                orca_basis_block_lines.append(f'  NewGTO {sym} "{rel_atom_basis}" end')
            if "AUTOAUX" not in theory_tokens and not any(tok.endswith("/J") for tok in theory_tokens):
                injected_keywords.append("AutoAux")
            w = (
                f"[REGIME_GUARD: HEAVY_ELEMENT_RELATIVISTIC] Heavy element(s) {', '.join(heavy)} "
                f"(max Z={max_z} > 36) on ORCA: injected scalar-relativistic '{ham}', basis '{effective_basis}', "
                f"per-element relativistic GTOs ({'; '.join(line.strip() for line in orca_basis_block_lines)}), "
                f"and enforced DEFGRID3."
            )
            logger.warning(w)
            warnings_list.append(w)

    elif eng == "cfour":
        relativistic_mode = "X2C1E"
        cfour_keywords.append("RELATIVISTIC=X2C1E")
        w = (
            f"[REGIME_GUARD: HEAVY_ELEMENT_RELATIVISTIC] Heavy element(s) {', '.join(heavy)} "
            f"(max Z={max_z} > 36) on CFOUR: automatically injected scalar-relativistic "
            f"RELATIVISTIC=X2C1E."
        )
        logger.warning(w)
        warnings_list.append(w)

    elif eng in {"pyscf", "gpu4pyscf"}:
        if not superheavy and (_is_def2_ecp_basis(effective_basis) or _is_pp_ecp_basis(effective_basis)):
            # In PySCF, ECPs are NOT loaded unless gto.M(..., ecp=...) is passed explicitly!
            ecp_basis_name = effective_basis
            if ecp_basis_name and ecp_basis_name.lower().startswith("ma-"):
                ecp_basis_name = ecp_basis_name[3:]
            pyscf_ecp = {sym: ecp_basis_name for sym in heavy_37_86}
            relativistic_mode = (
                f"PP-ECP ({ecp_basis_name})"
                if _is_pp_ecp_basis(effective_basis)
                else f"def2-ECP ({ecp_basis_name})"
            )
            w = (
                f"[REGIME_GUARD: HEAVY_ELEMENT_ECP] Heavy element(s) {', '.join(heavy_37_86)} "
                f"(max Z={max_z}) on {eng}: explicitly attached scalar-relativistic ECP "
                f"{pyscf_ecp} and enforced fine XC grid (99, 590)."
            )
            logger.warning(w)
            warnings_list.append(w)
        else:
            pyscf_sfx2c1e = True
            relativistic_mode = "sfX2C1e"
            w = (
                f"[REGIME_GUARD: HEAVY_ELEMENT_RELATIVISTIC] Heavy element(s) {', '.join(heavy)} "
                f"(max Z={max_z} > 36) on {eng} with all-electron/superheavy basis '{effective_basis}': "
                f"enabled spin-free exact two-component scalar relativity (.sfx2c1e()) and fine XC grid."
            )
            logger.warning(w)
            warnings_list.append(w)

    else:
        relativistic_mode = "ADVISORY"
        w = (
            f"[REGIME_GUARD: HEAVY_ELEMENT_RELATIVISTIC] Heavy element(s) {', '.join(heavy)} "
            f"(max Z={max_z} > 36) detected on engine={eng}; scalar-relativistic treatment recommended."
        )
        logger.warning(w)
        warnings_list.append(w)

    return HeavyElementGuardDecision(
        triggered=True,
        engine=eng,
        max_atomic_number=max_z,
        transition_metals_3d=tm_3d,
        heavy_elements=heavy,
        superheavy_elements=superheavy,
        require_defgrid3=require_defgrid3,
        relativistic_mode=relativistic_mode,
        injected_keywords=tuple(injected_keywords),
        orca_basis_block_lines=tuple(orca_basis_block_lines),
        cfour_keywords=tuple(cfour_keywords),
        pyscf_ecp=pyscf_ecp,
        pyscf_sfx2c1e=pyscf_sfx2c1e,
        effective_basis=effective_basis,
        warnings=tuple(warnings_list),
    )


@dataclass(frozen=True)
class RegimeGuardReport:
    """Combined chemical-regime auto-guard evaluation (anion diffuse + heavy/3d-TM)."""

    engine: str
    charge: int
    original_theory_level: str
    effective_theory_level: str
    original_basis: str | None
    effective_basis: str | None
    anion_guard: AnionDiffuseGuardDecision
    heavy_element_guard: HeavyElementGuardDecision
    require_defgrid3: bool
    orca_basis_block_lines: tuple[str, ...]
    cfour_keywords: tuple[str, ...]
    pyscf_ecp: dict[str, str] | None
    pyscf_sfx2c1e: bool
    warnings: tuple[str, ...]

    @property
    def any_triggered(self) -> bool:
        return self.anion_guard.triggered or self.heavy_element_guard.triggered

    def to_provenance_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "charge": self.charge,
            "any_triggered": self.any_triggered,
            "original_theory_level": self.original_theory_level,
            "effective_theory_level": self.effective_theory_level,
            "original_basis": self.original_basis,
            "effective_basis": self.effective_basis,
            "require_defgrid3": self.require_defgrid3,
            "anion_diffuse_guard": self.anion_guard.to_dict(),
            "heavy_element_guard": self.heavy_element_guard.to_dict(),
            "warnings": list(self.warnings),
        }


def apply_chemical_regime_guards(
    elements: Sequence[str],
    *,
    charge: int,
    method_or_theory: str,
    basis: str | None = None,
    engine: str = "orca",
) -> RegimeGuardReport:
    """Apply both Guard 1 (anion diffuse basis) and Guard 2 (heavy-element / 3d-TM) consistently."""
    eng = engine.strip().lower()
    theory = method_or_theory.strip()
    tokens = theory.split()

    basis_idx: int | None = None
    detected_basis: str | None = basis.strip() if basis and basis.strip() else None
    if detected_basis is None and not is_composite_method(theory):
        matched = _match_basis_token(theory)
        if matched is not None:
            basis_idx, detected_basis = matched
    elif detected_basis is not None:
        for idx, tok in enumerate(tokens):
            if tok.lower() == detected_basis.lower():
                basis_idx = idx
                break

    # Guard 1: Anion diffuse-basis upgrade
    anion_dec = upgrade_anion_diffuse_basis(
        detected_basis,
        charge=charge,
        engine=eng,
        method_or_theory=theory,
    )
    eff_basis = anion_dec.effective_basis
    if anion_dec.triggered and eff_basis and basis_idx is not None:
        tokens[basis_idx] = eff_basis
    eff_theory = " ".join(tokens)

    # Guard 2: Heavy-element scalar-relativistic/ECP and 3d-TM DEFGRID3
    heavy_dec = evaluate_heavy_element_and_tm_guard(
        elements,
        method_or_theory=eff_theory,
        basis=eff_basis,
        engine=eng,
    )
    if heavy_dec.effective_basis and heavy_dec.effective_basis != eff_basis:
        eff_basis = heavy_dec.effective_basis
        if basis_idx is not None:
            tokens[basis_idx] = eff_basis
    for kw in heavy_dec.injected_keywords:
        if kw.upper() not in {t.upper() for t in tokens}:
            tokens.append(kw)
    eff_theory = " ".join(tokens)

    warnings: list[str] = []
    if anion_dec.warning:
        warnings.append(anion_dec.warning)
    warnings.extend(heavy_dec.warnings)

    return RegimeGuardReport(
        engine=eng,
        charge=charge,
        original_theory_level=theory,
        effective_theory_level=eff_theory,
        original_basis=detected_basis,
        effective_basis=eff_basis,
        anion_guard=anion_dec,
        heavy_element_guard=heavy_dec,
        require_defgrid3=heavy_dec.require_defgrid3,
        orca_basis_block_lines=heavy_dec.orca_basis_block_lines,
        cfour_keywords=heavy_dec.cfour_keywords,
        pyscf_ecp=heavy_dec.pyscf_ecp,
        pyscf_sfx2c1e=heavy_dec.pyscf_sfx2c1e,
        warnings=tuple(warnings),
    )


# =============================================================================
# Guard 3: Live Coupled-Cluster T1 / D1 Multireference Diagnostics Gate
# =============================================================================

def _parse_finite_float(token: str) -> float | None:
    try:
        value = float(token.replace("D", "E").replace("d", "e"))
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def is_coupled_cluster_method(method: str) -> bool:
    """Return True if the method string denotes a coupled-cluster calculation."""
    return bool(re.search(r"(?:DLPNO-)?CCSD(?:\(T\d?\)|\[T\])?|CC2|CC3|CCSDT", method, re.IGNORECASE))


def parse_cc_multireference_diagnostics(
    output_text: str,
    *,
    engine: str = "orca",
    method: str = "",
    multiplicity: int = 1,
) -> dict[str, Any]:
    """Parse real T1 and D1 diagnostics from ORCA or CFOUR output without fabricating values.

    Thresholds:
    - Closed-shell (`multiplicity == 1`): T1 > 0.020 or D1 > 0.050
    - Open-shell (`multiplicity > 1`):    T1 > 0.045 or D1 > 0.070
    """
    eng = engine.strip().lower()
    is_open_shell = int(multiplicity) > 1
    t1_thresh = T1_OPEN_SHELL_THRESHOLD if is_open_shell else T1_CLOSED_SHELL_THRESHOLD
    d1_thresh = D1_OPEN_SHELL_THRESHOLD if is_open_shell else D1_CLOSED_SHELL_THRESHOLD

    t1_val: float | None = None
    d1_val: float | None = None
    t1_source: str | None = None
    d1_source: str | None = None

    # Explicit T1 diagnostic patterns (ORCA mdci/DLPNO-CCSD(T) and CFOUR)
    t1_patterns = (
        re.compile(rf"T1\s+diagnostic\s*(?:\.{{2,}}|:|=|is)\s*({_NUMBER_RE})", re.IGNORECASE),
        re.compile(rf"The\s+T1\s+diagnostic\s+is\s+({_NUMBER_RE})", re.IGNORECASE),
        re.compile(rf"\bT1\s*=\s*({_NUMBER_RE})\b"),
    )
    for pat in t1_patterns:
        matches = pat.findall(output_text)
        if matches:
            parsed = _parse_finite_float(matches[-1])
            if parsed is not None:
                t1_val = parsed
                t1_source = "explicit_engine_diagnostic"
                break

    # CFOUR xvcc fallback: compute exact Lee-Taylor T1 = ||T1AA|| / sqrt(N_corr_elec)
    # ONLY when genuine CFOUR T1 amplitude norm and correlated electron count are both present.
    if t1_val is None and eng == "cfour":
        norm_aa = re.findall(rf"Norm\s+of\s+T1AA\s+vector[^:]*:\s*({_NUMBER_RE})", output_text, re.IGNORECASE)
        norm_bb = re.findall(rf"Norm\s+of\s+T1BB\s+vector[^:]*:\s*({_NUMBER_RE})", output_text, re.IGNORECASE)
        n_corr = _extract_cfour_correlated_electrons(output_text)
        if norm_aa and n_corr is not None and n_corr > 0:
            aa = _parse_finite_float(norm_aa[-1])
            bb = _parse_finite_float(norm_bb[-1]) if norm_bb else None
            if aa is not None:
                if bb is not None and is_open_shell:
                    # Open-shell Lee-Taylor norm: sqrt((||T1_a||^2 + ||T1_b||^2) / (2 * N_corr))
                    t1_val = math.sqrt((aa * aa + bb * bb) / (2.0 * n_corr))
                else:
                    # Closed-shell Lee-Taylor: ||T1_alpha||_2 / sqrt(N_corr)
                    t1_val = aa / math.sqrt(float(n_corr))
                t1_source = "cfour_t1_amplitude_norm"

    # Explicit D1 diagnostic patterns (never fabricated when absent)
    d1_patterns = (
        re.compile(rf"D1\s+diagnostic\s*(?:\.{{2,}}|:|=|is)\s*({_NUMBER_RE})", re.IGNORECASE),
        re.compile(rf"The\s+D1\s+diagnostic\s+is\s+({_NUMBER_RE})", re.IGNORECASE),
        re.compile(rf"D1\s*\(\s*CCSD\s*\)\s*(?:\.{{2,}}|:|=)\s*({_NUMBER_RE})", re.IGNORECASE),
    )
    for pat in d1_patterns:
        matches = pat.findall(output_text)
        if matches:
            parsed = _parse_finite_float(matches[-1])
            if parsed is not None:
                d1_val = parsed
                d1_source = "explicit_engine_diagnostic"
                break

    t1_exceeded = bool(t1_val is not None and t1_val > t1_thresh)
    d1_exceeded = bool(d1_val is not None and d1_val > d1_thresh)
    mr_warning = t1_exceeded or d1_exceeded

    warnings: list[str] = []
    if t1_exceeded:
        w = (
            f"[REGIME_GUARD: MULTIREFERENCE_T1] Coupled-cluster T1 diagnostic = {t1_val:.5f} exceeds "
            f"{'open-shell' if is_open_shell else 'closed-shell'} threshold {t1_thresh:.3f} "
            f"(engine={eng}, method={method or 'CC'}). Single-reference coupled-cluster amplitudes "
            f"indicate significant static correlation; validate with T9 CASSCF/NEVPT2."
        )
        logger.warning(w)
        warnings.append(w)
    if d1_exceeded:
        w = (
            f"[REGIME_GUARD: MULTIREFERENCE_D1] Coupled-cluster D1 diagnostic = {d1_val:.5f} exceeds "
            f"{'open-shell' if is_open_shell else 'closed-shell'} threshold {d1_thresh:.3f} "
            f"(engine={eng}, method={method or 'CC'}). Strong orbital relaxation / multireference "
            f"character detected; validate with T9 CASSCF/NEVPT2."
        )
        logger.warning(w)
        warnings.append(w)

    return {
        "engine": eng,
        "method": method,
        "is_coupled_cluster": is_coupled_cluster_method(method) or t1_val is not None or d1_val is not None,
        "is_open_shell": is_open_shell,
        "t1_diagnostic": t1_val,
        "t1_source": t1_source,
        "t1_threshold": t1_thresh,
        "t1_exceeded": t1_exceeded,
        "d1_diagnostic": d1_val,
        "d1_source": d1_source,
        "d1_threshold": d1_thresh,
        "d1_exceeded": d1_exceeded,
        "multireference_warning": mr_warning,
        "warnings": warnings,
        "recommendation": (
            "Escalate to T9 multireference CASSCF/NEVPT2"
            if mr_warning
            else "Single-reference coupled-cluster diagnostics within threshold"
            if (t1_val is not None or d1_val is not None)
            else "No coupled-cluster T1/D1 diagnostics reported in engine output"
        ),
    }


def _extract_cfour_correlated_electrons(output_text: str) -> int | None:
    """Extract correlated electron count from genuine CFOUR output when reported."""
    # Look for explicit correlated/active occupied counts printed by xvmol2ja/xvcc
    m_occ = re.search(
        r"Number\s+of\s+(?:correlated|active)\s+electrons\s*[:=]\s*(\d+)",
        output_text,
        re.IGNORECASE,
    )
    if m_occ:
        return int(m_occ.group(1))
    # CFOUR prints: "Alpha occupied orbitals ...  4" / "Beta occupied orbitals ...  4" (after dropping core)
    # or "There are   4 active alpha occupied orbitals" / "DROPMO" counts
    alpha_occ = re.findall(r"(?:active\s+)?alpha\s+occupied\s+orbitals[^0-9]*(\d+)", output_text, re.IGNORECASE)
    beta_occ = re.findall(r"(?:active\s+)?beta\s+occupied\s+orbitals[^0-9]*(\d+)", output_text, re.IGNORECASE)
    if alpha_occ and beta_occ:
        return int(alpha_occ[-1]) + int(beta_occ[-1])
    # CFOUR xscf/xvtran/xvcc summary: "total electron number: 10.000..." or "Number of electrons: 10"
    # minus dropped core orbitals * 2 ("The following 1 MOs will be dropped:" / "There is 1 frozen-core orbital.")
    m_elec = re.search(r"Number\s+of\s+electrons\s*[:=]?\s*(\d+)", output_text, re.IGNORECASE)
    total_elec: int | None = int(m_elec.group(1)) if m_elec else None
    if total_elec is None:
        m_tot = re.findall(rf"total\s+electron\s+number\s*:\s*({_NUMBER_RE})", output_text, re.IGNORECASE)
        if m_tot:
            val = _parse_finite_float(m_tot[-1])
            if val is not None and val >= 1.0:
                total_elec = int(round(val))
    m_drop = (
        re.search(r"dropped\s+core\s+orbitals\s*[:=]?\s*(\d+)", output_text, re.IGNORECASE)
        or re.search(r"The\s+following\s+(\d+)\s+MOs?\s+will\s+be\s+dropped", output_text, re.IGNORECASE)
        or re.search(r"There\s+(?:is|are)\s+(\d+)\s+frozen[- ]core\s+orbitals?", output_text, re.IGNORECASE)
    )
    if total_elec is not None:
        dropped = int(m_drop.group(1)) if m_drop else 0
        corr = total_elec - 2 * dropped
        return corr if corr > 0 else total_elec
    # CFOUR xfillfc / xscf occupation lines: "Occupation of alpha orbitals:  5" and "frozen core orbitals: 1"
    m_a = re.search(r"Alpha\s+electrons\s*[:=]\s*(\d+)", output_text, re.IGNORECASE)
    m_b = re.search(r"Beta\s+electrons\s*[:=]\s*(\d+)", output_text, re.IGNORECASE)
    if m_a and m_b:
        return int(m_a.group(1)) + int(m_b.group(1))
    return None


# =============================================================================
# Guard 4a: Live ORCA SCF Convergence Retry (SlowConvInterceptor + RegexTrapEngine)
# =============================================================================

@dataclass(frozen=True)
class SCFRetryDecision:
    """Structured provenance for one ORCA SCF convergence retry evaluation."""

    should_retry: bool
    retry_number: int
    max_retries: int
    failure_detected: bool
    terminal_collapse: bool
    trap_flag: str
    matched_signature: str
    injected_keywords: tuple[str, ...] = ()
    remediated_deck: str = ""
    warnings: tuple[str, ...] = ()
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["injected_keywords"] = list(data["injected_keywords"])
        data["warnings"] = list(data["warnings"])
        # Omit full deck text from compact JSON summaries
        data.pop("remediated_deck", None)
        return data


def _inject_orca_scf_retry_directives(
    deck_text: str,
    *,
    keywords_to_add: Sequence[str],
    max_iter: int = 300,
    extra_scf_lines: Sequence[str] = (),
) -> tuple[str, list[str]]:
    """Inject valid ORCA 6 SCF convergence keywords and `%scf MaxIter` into an ORCA deck."""
    lines = deck_text.splitlines()
    injected: list[str] = []
    new_lines: list[str] = []

    # 1. Update first '!' keyword line
    header_done = False
    for line in lines:
        if not header_done and line.strip().startswith("!"):
            toks = line.strip().split()
            existing_upper = {t.upper() for t in toks}
            for kw in keywords_to_add:
                if kw.upper() not in existing_upper:
                    toks.append(kw)
                    existing_upper.add(kw.upper())
                    injected.append(kw)
            new_lines.append(" ".join(toks))
            header_done = True
        else:
            new_lines.append(line)
    if not header_done:
        new_lines.insert(0, "! " + " ".join(keywords_to_add))
        injected.extend(keywords_to_add)

    # 2. Update or insert %scf block with MaxIter >= max_iter and extra directives
    updated_lines: list[str] = []
    in_scf = False
    found_scf = False
    maxiter_written = False
    extra_written: set[str] = set()
    extra_keys = {entry.split()[0].lower(): entry for entry in extra_scf_lines if entry.strip()}

    for line in new_lines:
        stripped = line.strip()
        if not in_scf and stripped.lower() == "%scf":
            in_scf = True
            found_scf = True
            updated_lines.append(line)
            continue
        if in_scf:
            if stripped.lower() == "end":
                if not maxiter_written:
                    updated_lines.append(f" MaxIter {max_iter}")
                    injected.append(f"MaxIter {max_iter}")
                for key, entry in extra_keys.items():
                    if key not in extra_written:
                        updated_lines.append(f" {entry}")
                        injected.append(entry)
                in_scf = False
                updated_lines.append(line)
                continue
            if stripped.lower().startswith("maxiter"):
                updated_lines.append(f" MaxIter {max_iter}")
                maxiter_written = True
                if f"MaxIter {max_iter}" not in injected:
                    injected.append(f"MaxIter {max_iter}")
                continue
            first_tok = stripped.split()[0].lower() if stripped else ""
            if first_tok in extra_keys:
                updated_lines.append(f" {extra_keys[first_tok]}")
                extra_written.add(first_tok)
                injected.append(extra_keys[first_tok])
                continue
        updated_lines.append(line)

    if not found_scf:
        scf_block = ["%scf", f" MaxIter {max_iter}"]
        injected.append(f"MaxIter {max_iter}")
        for entry in extra_scf_lines:
            if entry.strip():
                scf_block.append(f" {entry.strip()}")
                injected.append(entry.strip())
        scf_block.append("end")
        # Insert right before '* xyz' if present, else append
        insert_at = next(
            (i for i, ln in enumerate(updated_lines) if ln.strip().lower().startswith("* xyz")),
            len(updated_lines),
        )
        updated_lines = updated_lines[:insert_at] + scf_block + [""] + updated_lines[insert_at:]

    return "\n".join(updated_lines) + "\n", injected


def prepare_orca_scf_retry(
    deck_text: str,
    stdout_text: str,
    *,
    retry_index: int,
    max_retries: int = MAX_SCF_RETRIES,
) -> SCFRetryDecision:
    """Analyze ORCA stdout via `SlowConvInterceptor` + `RegexTrapEngine` and synthesize bounded SCF retry."""
    from cochem_base.bench_engine.cochem_bench_cbs import SlowConvInterceptor
    from cochem_base.core_engine.cochem_regex_traps import EngineDialect, RegexTrapEngine, TrapFlag

    capped_max = min(int(max_retries), MAX_SCF_RETRIES)

    # 1. Stream-scan output through RegexTrapEngine
    trap_engine = RegexTrapEngine(dialect=EngineDialect.ORCA)
    for line in stdout_text.splitlines(keepends=True):
        trap_engine.feed_line(line)
    trap_report = trap_engine.finalize()

    if trap_report.primary_flag == TrapFlag.NUMERICAL_COLLAPSE:
        return SCFRetryDecision(
            should_retry=False,
            retry_number=retry_index,
            max_retries=capped_max,
            failure_detected=True,
            terminal_collapse=True,
            trap_flag=trap_report.primary_flag.value,
            matched_signature=trap_report.numerical_collapse.token if trap_report.numerical_collapse else "NaN/Inf",
            warnings=(
                f"[REGIME_GUARD: SCF_NUMERICAL_COLLAPSE] Terminal NaN/Inf numerical collapse detected "
                f"({trap_report.numerical_collapse.token if trap_report.numerical_collapse else 'NaN/Inf'}); "
                f"failing closed without SCF retry.",
            ),
            reason="Terminal numerical collapse detected by RegexTrapEngine; refusing unsafe retry.",
        )

    # 2. Check SlowConvInterceptor + RegexTrapEngine ping-pong / linear dependence
    interceptor = SlowConvInterceptor(max_retries=capped_max)
    has_slowconv_fail, matched_sig = interceptor.detect_scf_failure(stdout_text)
    has_ping_pong = trap_report.primary_flag == TrapFlag.SCF_PING_PONG_DETECTED
    has_lin_dep = trap_report.primary_flag == TrapFlag.LINEAR_DEPENDENCE_DETECTED
    has_extra_scf_fail = bool(
        re.search(
            r"SCF\s+DID\s+NOT\s+CONVERGE|Maximum\s+number\s+of\s+SCF\s+cycles\s+reached|"
            r"ERROR.*SCF\s+not\s+converged",
            stdout_text,
            re.IGNORECASE,
        )
    )

    failure_detected = has_slowconv_fail or has_ping_pong or has_extra_scf_fail
    if not failure_detected:
        return SCFRetryDecision(
            should_retry=False,
            retry_number=retry_index,
            max_retries=capped_max,
            failure_detected=False,
            terminal_collapse=False,
            trap_flag=trap_report.primary_flag.value,
            matched_signature="",
            remediated_deck=deck_text,
            reason="No ORCA SCF convergence failure detected.",
        )

    sig_desc = matched_sig or (
        "SCF_PING_PONG_DETECTED" if has_ping_pong else "SCF_NON_CONVERGENCE"
    )
    if retry_index >= capped_max:
        w = (
            f"[REGIME_GUARD: SCF_RETRY_EXHAUSTED] ORCA SCF convergence failure ({sig_desc}) persisted "
            f"after {capped_max} automatic retry attempt(s); failing closed."
        )
        logger.warning(w)
        return SCFRetryDecision(
            should_retry=False,
            retry_number=retry_index,
            max_retries=capped_max,
            failure_detected=True,
            terminal_collapse=False,
            trap_flag=trap_report.primary_flag.value,
            matched_signature=sig_desc,
            remediated_deck=deck_text,
            warnings=(w,),
            reason=f"SCF retry budget exhausted ({retry_index}/{capped_max}) for '{sig_desc}'.",
        )

    # Tiered remediation:
    # Retry 1 (retry_index == 0): SlowConv + KDIIS + MaxIter 300 (+ SOSCF on ping-pong, AutoAux/SThresh on lin-dep)
    # Retry 2 (retry_index == 1): VerySlowConv + SlowConv + KDIIS + SOSCF + MaxIter 300 + Shift 0.25 + DampFac 0.7
    keywords: list[str] = ["SlowConv", "KDIIS"]
    extra_scf: list[str] = []
    if has_ping_pong or retry_index >= 1:
        keywords.append("SOSCF")
    if retry_index >= 1:
        keywords.append("VerySlowConv")
        extra_scf.extend(["Shift 0.25", "DampFac 0.7"])
    if has_lin_dep:
        keywords.append("AutoAux")
        extra_scf.append("SThresh 1e-5")

    remediated, injected = _inject_orca_scf_retry_directives(
        deck_text,
        keywords_to_add=keywords,
        max_iter=300,
        extra_scf_lines=extra_scf,
    )
    next_retry = retry_index + 1
    w = (
        f"[REGIME_GUARD: SCF_AUTO_RETRY] Detected ORCA SCF failure ({sig_desc}, trap={trap_report.primary_flag.value}). "
        f"Retrying ({next_retry}/{capped_max}) with injected directives: {', '.join(injected)}."
    )
    logger.warning(w)
    return SCFRetryDecision(
        should_retry=True,
        retry_number=next_retry,
        max_retries=capped_max,
        failure_detected=True,
        terminal_collapse=False,
        trap_flag=trap_report.primary_flag.value,
        matched_signature=sig_desc,
        injected_keywords=tuple(injected),
        remediated_deck=remediated,
        warnings=(w,),
        reason=f"Remediated SCF failure '{sig_desc}' for retry {next_retry}/{capped_max}.",
    )


# =============================================================================
# Guard 4b: Authentic Imaginary-Mode Eigenvector Displacement & Re-Optimization
# =============================================================================

def _projected_vibrational_modes(
    cartesian_hessian: np.ndarray,
    coordinates_angstrom: np.ndarray,
    masses_u: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, int]:
    """Project out rigid translations/rotations and diagonalize mass-weighted Hessian.

    Returns:
        (frequencies_cm1, cartesian_modes_3N_by_nvib, rigid_mode_count)
        where each column `cartesian_modes[:, k]` is an un-mass-weighted Cartesian
        displacement vector in Angstrom-scaled direction (`q_k / sqrt(m)`), normalized
        to unit Euclidean norm, sorted ascending by frequency (`cm^-1`, negative = imaginary).
    """
    from cochem_base.core.cochem_constants import (
        ATOMIC_MASS_UNIT_KG,
        BOHR_TO_METER,
        HARTREE_TO_JOULE,
        SPEED_OF_LIGHT_CM_S,
    )

    hess = np.asarray(cartesian_hessian, dtype=np.float64)
    coords = np.asarray(coordinates_angstrom, dtype=np.float64)
    masses = np.asarray(masses_u, dtype=np.float64)

    n_atoms = len(masses)
    dim = 3 * n_atoms
    if hess.shape != (dim, dim) or not np.isfinite(hess).all():
        raise ValueError("Cartesian Hessian must be a finite 3N x 3N matrix")
    if coords.shape != (n_atoms, 3) or not np.isfinite(coords).all():
        raise ValueError("Coordinates must be a finite N x 3 array")
    if masses.shape != (n_atoms,) or np.any(masses <= 0) or not np.isfinite(masses).all():
        raise ValueError("Atomic masses must be positive finite values")

    # Mass-weight Hessian: H_mw = M^{-1/2} H M^{-1/2}
    sqrt_m3 = np.repeat(np.sqrt(masses), 3)
    inv_sqrt_m3 = 1.0 / sqrt_m3
    h_mw = 0.5 * (hess + hess.T) * np.outer(inv_sqrt_m3, inv_sqrt_m3)

    # Center of mass shift
    com = np.sum(coords * masses[:, None], axis=0) / np.sum(masses)
    shifted = coords - com

    # Build translational and rotational basis in mass-weighted coordinates (Eckart frame)
    rigid_vectors: list[np.ndarray] = []
    for axis in range(3):
        vec = np.zeros((n_atoms, 3), dtype=np.float64)
        vec[:, axis] = np.sqrt(masses)
        rigid_vectors.append(vec.ravel())

    # Principal moments of inertia for rotation generators
    inertia = np.zeros((3, 3), dtype=np.float64)
    for m, r in zip(masses, shifted):
        inertia += m * (np.dot(r, r) * np.eye(3) - np.outer(r, r))
    _, principal_axes = np.linalg.eigh(inertia)

    for col in range(3):
        axis_vec = principal_axes[:, col]
        rot = np.cross(shifted, axis_vec) * np.sqrt(masses)[:, None]
        norm = float(np.linalg.norm(rot))
        if norm > 1e-8:
            rigid_vectors.append((rot / norm).ravel())

    basis = np.column_stack(rigid_vectors)
    u_rigid, singular, _ = np.linalg.svd(basis, full_matrices=True)
    rigid_count = int(np.count_nonzero(singular > 1e-8 * singular[0]))
    vib_basis = u_rigid[:, rigid_count:]  # (3N, 3N - rigid_count)

    # Diagonalize vibrational subspace
    h_vib = vib_basis.T @ h_mw @ vib_basis
    h_vib = 0.5 * (h_vib + h_vib.T)
    evals, evecs_vib = np.linalg.eigh(h_vib)

    eig_to_cm1 = math.sqrt(
        HARTREE_TO_JOULE / (BOHR_TO_METER**2 * ATOMIC_MASS_UNIT_KG)
    ) / (2.0 * math.pi * SPEED_OF_LIGHT_CM_S)

    freqs = np.array(
        [math.sqrt(v) * eig_to_cm1 if v >= 0.0 else -math.sqrt(-v) * eig_to_cm1 for v in evals],
        dtype=np.float64,
    )
    mw_modes = vib_basis @ evecs_vib  # (3N, n_vib)
    cart_modes = mw_modes * inv_sqrt_m3[:, None]
    for k in range(cart_modes.shape[1]):
        col_norm = float(np.linalg.norm(cart_modes[:, k]))
        if col_norm > 0.0:
            cart_modes[:, k] /= col_norm

    order = np.argsort(freqs)
    return freqs[order], cart_modes[:, order], rigid_count


def extract_imaginary_vibrational_modes(
    cartesian_hessian: np.ndarray,
    elements: Sequence[str],
    coordinates_angstrom: Sequence[Sequence[float]],
    *,
    masses_u: Sequence[float] | None = None,
    imag_threshold_cm1: float = 10.0,
) -> dict[str, Any]:
    """Compute projected vibrational frequencies and extract imaginary normal modes from a real Hessian."""
    if imag_threshold_cm1 < 0 or not math.isfinite(imag_threshold_cm1):
        raise ValueError("imag_threshold_cm1 must be finite and non-negative")
    coords = np.asarray(coordinates_angstrom, dtype=np.float64)
    if masses_u is None:
        from cochem_base.spectroscopy.isotopologue import get_nuclide_mass
        masses = np.asarray([get_nuclide_mass(sym) for sym in elements], dtype=np.float64)
    else:
        masses = np.asarray(masses_u, dtype=np.float64)

    freqs, cart_modes, rigid_count = _projected_vibrational_modes(
        np.asarray(cartesian_hessian, dtype=np.float64), coords, masses
    )
    imag_indices = [int(i) for i, w in enumerate(freqs) if w < -imag_threshold_cm1]
    return {
        "n_imag": len(imag_indices),
        "imag_threshold_cm1": float(imag_threshold_cm1),
        "rigid_mode_count": rigid_count,
        "vibrational_frequencies_cm1": [float(w) for w in freqs],
        "imaginary_frequencies_cm1": [float(freqs[i]) for i in imag_indices],
        "imaginary_mode_indices": imag_indices,
        "cartesian_modes": cart_modes,
        "masses_u": masses,
    }


def displace_along_imaginary_mode(
    coordinates_angstrom: Sequence[Sequence[float]],
    cartesian_hessian: np.ndarray,
    elements: Sequence[str],
    *,
    mode_rank: int = 0,
    step_angstrom: float = 0.05,
    direction: float = 1.0,
    masses_u: Sequence[float] | None = None,
    imag_threshold_cm1: float = 10.0,
) -> dict[str, Any]:
    """Displace Cartesian coordinates along an authentic Hessian imaginary vibrational eigenvector.

    Normalizes the Cartesian normal mode so the maximum single-atom displacement equals
    `|step_angstrom|`, removes center-of-mass translation drift, and returns both the displaced
    geometry and complete provenance.
    """
    if not math.isfinite(step_angstrom) or step_angstrom <= 0.0 or step_angstrom > 1.0:
        raise ValueError("step_angstrom must be finite in (0, 1.0] Angstrom")
    if direction not in (-1.0, 1.0) and direction not in (-1, 1):
        raise ValueError("direction must be +1.0 or -1.0")

    coords = np.asarray(coordinates_angstrom, dtype=np.float64)
    analysis = extract_imaginary_vibrational_modes(
        cartesian_hessian,
        elements,
        coords,
        masses_u=masses_u,
        imag_threshold_cm1=imag_threshold_cm1,
    )
    if analysis["n_imag"] == 0:
        raise ValueError("No imaginary vibrational modes exceed threshold; displacement not required")
    if mode_rank < 0 or mode_rank >= analysis["n_imag"]:
        raise IndexError(f"mode_rank {mode_rank} out of range for {analysis['n_imag']} imaginary mode(s)")

    mode_idx = analysis["imaginary_mode_indices"][mode_rank]
    imag_freq = analysis["imaginary_frequencies_cm1"][mode_rank]
    vec = analysis["cartesian_modes"][:, mode_idx].reshape(len(elements), 3)

    # Remove any residual mass-weighted COM drift from the displacement vector
    masses = analysis["masses_u"]
    com_shift = np.sum(vec * masses[:, None], axis=0) / np.sum(masses)
    vec = vec - com_shift

    atom_norms = np.linalg.norm(vec, axis=1)
    max_atom_norm = float(np.max(atom_norms))
    if not math.isfinite(max_atom_norm) or max_atom_norm <= 1e-12:
        raise ValueError("Selected imaginary normal mode has degenerate zero Cartesian displacement")

    delta = (float(direction) * float(step_angstrom) / max_atom_norm) * vec
    displaced = coords + delta
    if not np.isfinite(displaced).all():
        raise ValueError("Computed displaced coordinates contain non-finite values")

    return {
        "mode_index": mode_idx,
        "imaginary_frequency_cm1": float(imag_freq),
        "step_angstrom": float(step_angstrom),
        "direction": float(direction),
        "max_atomic_displacement_angstrom": float(np.max(np.linalg.norm(delta, axis=1))),
        "displacement_vector_angstrom": delta.tolist(),
        "displaced_coordinates_angstrom": displaced.tolist(),
        "n_imag_before": analysis["n_imag"],
        "imaginary_frequencies_before_cm1": analysis["imaginary_frequencies_cm1"],
    }


def reoptimize_imaginary_modes(
    elements: Sequence[str],
    initial_result: dict[str, Any],
    *,
    initial_hessian: np.ndarray,
    reopt_runner: Callable[[list[list[float]], int], tuple[dict[str, Any], np.ndarray]],
    max_retries: int = MAX_IMAGINARY_MODE_RETRIES,
    step_schedule_angstrom: Sequence[float] = (0.05, 0.08),
    imag_threshold_cm1: float = 10.0,
    masses_u: Sequence[float] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Iteratively displace along imaginary Hessian eigenvectors and re-optimize (capped at 2 retries).

    Args:
        elements: Ordered element symbols.
        initial_result: Result dict from the initial optimization+frequency run (must contain
            `coordinates_angstrom`).
        initial_hessian: Real 3N x 3N Cartesian Hessian (Hartree/Bohr^2) at `initial_result`.
        reopt_runner: Callable `(displaced_coords_angstrom, attempt_number) -> (new_result, new_hessian)`.
        max_retries: Maximum displacement+reoptimization attempts (hard-capped at 2).
        step_schedule_angstrom: Step sizes (Angstrom) for retry 1 and retry 2.
        imag_threshold_cm1: Minimum |imaginary frequency| (cm^-1) treated as a genuine saddle mode.
        masses_u: Optional atomic masses (amu); defaults to dynamic Mendeleev principal isotope masses.

    Returns:
        (accepted_result, provenance_dict) when `n_imag == 0`.

    Raises:
        ImaginaryModePersistenceError: Fail closed if `n_imag > 0` after `max_retries`.
    """
    capped_max = min(int(max_retries), MAX_IMAGINARY_MODE_RETRIES)
    current_result = initial_result
    current_hessian = np.asarray(initial_hessian, dtype=np.float64)
    current_coords = np.asarray(current_result["coordinates_angstrom"], dtype=np.float64)

    initial_analysis = extract_imaginary_vibrational_modes(
        current_hessian,
        elements,
        current_coords,
        masses_u=masses_u,
        imag_threshold_cm1=imag_threshold_cm1,
    )
    if initial_analysis["n_imag"] == 0:
        provenance = {
            "guard": "imaginary_mode_reoptimization",
            "initial_n_imag": 0,
            "initial_imaginary_frequencies_cm1": [],
            "retries_used": 0,
            "max_retries": capped_max,
            "attempts": [],
            "final_n_imag": 0,
            "final_imaginary_frequencies_cm1": [],
            "resolved": True,
            "warnings": [],
        }
        return current_result, provenance

    attempts: list[dict[str, Any]] = []
    warnings_list: list[str] = []
    directions = (1.0, -1.0)
    current_analysis = initial_analysis

    for attempt_idx in range(capped_max):
        step = float(step_schedule_angstrom[min(attempt_idx, len(step_schedule_angstrom) - 1)])
        direction = directions[attempt_idx % len(directions)]
        disp = displace_along_imaginary_mode(
            current_coords,
            current_hessian,
            elements,
            mode_rank=0,
            step_angstrom=step,
            direction=direction,
            masses_u=masses_u,
            imag_threshold_cm1=imag_threshold_cm1,
        )
        attempt_num = attempt_idx + 1
        w = (
            f"[REGIME_GUARD: IMAGINARY_MODE_RETRY] Minimum optimization landed on a stationary point "
            f"with {current_analysis['n_imag']} imaginary mode(s) "
            f"({[round(x, 2) for x in current_analysis['imaginary_frequencies_cm1']]} cm^-1). "
            f"Displacing along lowest imaginary eigenvector (step={step:.3f} A, dir={direction:+.0f}) "
            f"and re-optimizing (attempt {attempt_num}/{capped_max})."
        )
        logger.warning(w)
        warnings_list.append(w)

        new_result, new_hessian = reopt_runner(disp["displaced_coordinates_angstrom"], attempt_num)
        new_coords = np.asarray(new_result["coordinates_angstrom"], dtype=np.float64)
        new_analysis = extract_imaginary_vibrational_modes(
            np.asarray(new_hessian, dtype=np.float64),
            elements,
            new_coords,
            masses_u=masses_u,
            imag_threshold_cm1=imag_threshold_cm1,
        )
        attempts.append({
            "attempt": attempt_num,
            "mode_index": disp["mode_index"],
            "imaginary_frequency_before_cm1": disp["imaginary_frequency_cm1"],
            "step_angstrom": step,
            "direction": direction,
            "max_atomic_displacement_angstrom": disp["max_atomic_displacement_angstrom"],
            "n_imag_after": new_analysis["n_imag"],
            "imaginary_frequencies_after_cm1": new_analysis["imaginary_frequencies_cm1"],
        })
        current_result = new_result
        current_hessian = np.asarray(new_hessian, dtype=np.float64)
        current_coords = new_coords
        current_analysis = new_analysis

        if current_analysis["n_imag"] == 0:
            provenance = {
                "guard": "imaginary_mode_reoptimization",
                "initial_n_imag": initial_analysis["n_imag"],
                "initial_imaginary_frequencies_cm1": initial_analysis["imaginary_frequencies_cm1"],
                "retries_used": attempt_num,
                "max_retries": capped_max,
                "attempts": attempts,
                "final_n_imag": 0,
                "final_imaginary_frequencies_cm1": [],
                "resolved": True,
                "warnings": warnings_list,
            }
            return current_result, provenance

    fail_msg = (
        f"[IMAGINARY_MODE_PERSISTENCE] Structure still exhibits {current_analysis['n_imag']} "
        f"imaginary vibrational mode(s) ({[round(x, 2) for x in current_analysis['imaginary_frequencies_cm1']]} cm^-1) "
        f"after {capped_max} eigenvector-displacement re-optimization attempt(s). "
        f"Refusing to accept a saddle point as a true minimum."
    )
    warnings_list.append(fail_msg)
    provenance = {
        "guard": "imaginary_mode_reoptimization",
        "initial_n_imag": initial_analysis["n_imag"],
        "initial_imaginary_frequencies_cm1": initial_analysis["imaginary_frequencies_cm1"],
        "retries_used": capped_max,
        "max_retries": capped_max,
        "attempts": attempts,
        "final_n_imag": current_analysis["n_imag"],
        "final_imaginary_frequencies_cm1": current_analysis["imaginary_frequencies_cm1"],
        "resolved": False,
        "warnings": warnings_list,
    }
    raise ImaginaryModePersistenceError(fail_msg, details=provenance)


__all__ = [
    "D1_CLOSED_SHELL_THRESHOLD",
    "D1_OPEN_SHELL_THRESHOLD",
    "ELEMENT_Z",
    "MAX_IMAGINARY_MODE_RETRIES",
    "MAX_SCF_RETRIES",
    "SYMBOL_TO_ATOMIC_NUMBER",
    "T1_CLOSED_SHELL_THRESHOLD",
    "T1_OPEN_SHELL_THRESHOLD",
    "AnionDiffuseGuardDecision",
    "HeavyElementGuardDecision",
    "ImaginaryModePersistenceError",
    "RegimeGuardReport",
    "SCFRetryDecision",
    "apply_chemical_regime_guards",
    "displace_along_imaginary_mode",
    "evaluate_heavy_element_and_tm_guard",
    "extract_imaginary_vibrational_modes",
    "is_composite_method",
    "is_coupled_cluster_method",
    "is_diffuse_basis",
    "normalize_element_symbol",
    "parse_cc_multireference_diagnostics",
    "prepare_orca_scf_retry",
    "reoptimize_imaginary_modes",
    "resolve_atomic_number",
    "upgrade_anion_diffuse_basis",
]
