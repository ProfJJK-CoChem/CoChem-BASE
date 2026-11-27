"""Authentic CFOUR 2.1 execution with spherical basis, open-shell, opt/freq, and VPT2 support.

Emits SPHERICAL=ON for Dunning/ANO/def2 spherical basis sets, defaults to
FROZEN_CORE=ON (configurable), supports closed- and open-shell (RHF/UHF/ROHF),
correlated optimization/frequencies (VIB=EXACT / VIB=FINDIF), and real
ANHARM=VPT2 execution with measured derivative and spectroscopic acceptance.
"""
from __future__ import annotations

from cochem_base.core_engine.scientific_writer import scientific_producer

import hashlib
import json
import math
import os
from pathlib import Path
import re
import time
from typing import Any, Callable

import numpy as np

from cochem_base.core.cochem_constants import BOHR_TO_ANGSTROM


NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][-+]?\d+)?"
BOHR_ANGSTROM = BOHR_TO_ANGSTROM
GEOMETRY_TOLERANCE_ANGSTROM = 2e-7
ENERGY_TOLERANCE_HARTREE = 2e-8
FREQUENCY_TOLERANCE_CM1 = 0.25
OPTIMIZATION_FORCE_TOLERANCE = 1e-5  # largest atomic norm, hartree/bohr
SUPPORTED_CFOUR_BASIS_LABELS = (
    "STO-3G", "3-21G", "4-31G", "6-31G", "6-31G*", "6-31G**", "6-31+G", "6-31+G*", "6-31+G**", "6-31++G**",
    "6-311G", "6-311G*", "6-311G**", "6-311+G*", "6-311++G**", "DZ", "DZP", "D95", "D95*", "MIDI",
    "cc-pVDZ", "cc-pVTZ", "cc-pVQZ", "cc-pV5Z", "cc-pV6Z",
    "aug-cc-pVDZ", "aug-cc-pVTZ", "aug-cc-pVQZ", "aug-cc-pV5Z",
    "cc-pCVDZ", "cc-pCVTZ", "cc-pCVQZ", "cc-pCV5Z",
    "aug-cc-pCVDZ", "aug-cc-pCVTZ", "aug-cc-pCVQZ", "aug-cc-pCV5Z",
    "cc-pwCVDZ", "cc-pwCVTZ", "cc-pwCVQZ", "cc-pwCV5Z",
    "PVDZ", "PVTZ", "PVQZ", "PV5Z", "PV6Z",
    "AUG-PVDZ", "AUG-PVTZ", "AUG-PVQZ", "AUG-PV5Z",
    "PCVDZ", "PCVTZ", "PCVQZ", "PCV5Z",
    "AUG-PCVDZ", "AUG-PCVTZ", "AUG-PCVQZ", "AUG-PCV5Z",
    "PWCVDZ", "PWCVTZ", "PWCVQZ", "PWCV5Z",
    "ANO0", "ANO1", "ANO2", "ANO-RCC",
    "def2-SVP", "def2-SVPD", "def2-TZVP", "def2-TZVPD",
    "def2-TZVPP", "def2-TZVPPD", "def2-QZVP", "def2-QZVPD",
    "def2-QZVPP", "def2-QZVPPD",
)

_SPHERICAL_BASIS_PATTERNS = (
    re.compile(r"^(?:aug-|jun-|may-|d-aug-)?cc-p(?:w?c)?v[dtq56]z$", re.I),
    re.compile(r"^(?:aug-)?p(?:w?c)?v[dtq56]z$", re.I),
    re.compile(r"^ano[0-9a-z_-]*$", re.I),
    re.compile(r"^def2-[a-z0-9]+$", re.I),
)

_CARTESIAN_BASIS_PATTERNS = (
    re.compile(r"^sto-3g$", re.I),
    re.compile(r"^[346]-\d+\+{0,2}g\*{0,2}$", re.I),
    re.compile(r"^(?:dz|dzp|d95\*?|midi)$", re.I),
)


def uses_spherical_basis(basis: str) -> bool:
    """Return True when the CFOUR basis requires spherical harmonics (SPHERICAL=ON)."""
    cleaned = basis.strip()
    return any(pat.fullmatch(cleaned) for pat in _SPHERICAL_BASIS_PATTERNS)


def normalize_cfour_basis_keyword(basis: str) -> str:
    """Translate standard Dunning basis names to CFOUR 2.1 native BASIS= keywords."""
    cleaned = basis.strip()
    for pattern, repl in (
        (r"^d-aug-cc-pv([dtq56])z$", r"D-AUG-PV\1Z"),
        (r"^aug-cc-pwcv([dtq56])z$", r"AUG-PWCV\1Z"),
        (r"^aug-cc-pcv([dtq56])z$", r"AUG-PCV\1Z"),
        (r"^aug-cc-pv([dtq56])z$", r"AUG-PV\1Z"),
        (r"^cc-pwcv([dtq56])z$", r"PWCV\1Z"),
        (r"^cc-pcv([dtq56])z$", r"PCV\1Z"),
        (r"^cc-pv([dtq56])z$", r"PV\1Z"),
    ):
        match = re.fullmatch(pattern, cleaned, flags=re.I)
        if match:
            return re.sub(pattern, repl, cleaned, flags=re.I).upper()
    return cleaned


def is_supported_cfour_basis(value: str | None) -> bool:
    """Validate plain CFOUR basis labels across Pople, Dunning, ANO, and def2 families."""
    if not isinstance(value, str) or not value.strip():
        return False
    cleaned = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9+_.()*-]*", cleaned):
        return False
    if cleaned.lower() in {basis.lower() for basis in SUPPORTED_CFOUR_BASIS_LABELS}:
        return True
    return (
        any(pat.fullmatch(cleaned) for pat in _SPHERICAL_BASIS_PATTERNS)
        or any(pat.fullmatch(cleaned) for pat in _CARTESIAN_BASIS_PATTERNS)
    )


def supported_cfour_request(config: Any) -> bool:
    """Return True for connected native CFOUR 2.1 operations (RHF/UHF/ROHF, opt, freq, VPT2)."""
    return (config.multiplicity >= 1 and config.product_class is None
            and is_supported_cfour_basis(config.basis_set)
            and config.method in {"HF", "MP2", "CCSD", "CCSD(T)"}
            and config.initial_hessian.upper() in ({"BFGS"} if config.is_opt else {"XTB2", "BFGS"})
            and config.hessian_file is None
            and config.grid_stage is None and config.cbs_cardinal_pair is None
            and config.theory_tier is None and config.r2_reference_manifest is None)


def _require_authorized_runtime_seal(authorized_seal: str | None, observed_seal: str) -> None:
    """Every observation must match Stage 0, including the first observation."""
    from cochem_base.core_engine.execution_authority import RegistryAuthorityViolationError
    if (not isinstance(authorized_seal, str) or not re.fullmatch(r"[0-9a-f]{64}", authorized_seal)
            or observed_seal != authorized_seal):
        raise RegistryAuthorityViolationError("CFOUR runtime does not match its authorized Stage 0 integrity seal")


def _raise_if_cancelled(cancellation_event: Any) -> None:
    from cochem_base.core_engine.cochem_core_subprocess_broker import SubprocessCancelledError
    if cancellation_event is not None and cancellation_event.is_set():
        raise SubprocessCancelledError("CFOUR calculation cancelled before its next operation")


def _float(value: str) -> float:
    number = float(value.replace("D", "E").replace("d", "e"))
    if not math.isfinite(number):
        raise ValueError("CFOUR scientific values must be finite")
    return number


def _record(path: Path, root: Path, unit: str | None = None) -> dict[str, Any]:
    result = {"filename": str(path.relative_to(root)),
              "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    if unit:
        result["unit"] = unit
    return result


def _has_core_electrons(elements: list[str]) -> bool:
    """Return True when at least one atom has Z > 2 (nonempty core orbital space)."""
    from cochem_base.physics.isotopes import get_element_mass_and_abundance
    return any(get_element_mass_and_abundance(sym)[2] > 2 for sym in elements)


def _resolve_cfour_options(
    config: Any,
    elements: list[str],
    *,
    gradient: bool = False,
    harmonic: bool = False,
    anharmonic: bool | None = None,
    frozen_core: bool | None = None,
    reference: str | None = None,
    vib_mode: str | None = None,
    spherical: bool | None = None,
) -> dict[str, Any]:
    """Resolve authentic CFOUR 2.1 keyword settings from validated job parameters."""
    basis = config.basis_set
    use_spherical = uses_spherical_basis(basis) if spherical is None else bool(spherical)
    do_vpt2 = bool(config.is_vpt2 if anharmonic is None else anharmonic)
    do_harmonic = bool(harmonic and not do_vpt2)

    mult = int(config.multiplicity)
    if reference is not None:
        ref = reference.strip().upper()
        if mult > 1 and ref not in {"UHF", "ROHF"}:
            raise ValueError("Open-shell CFOUR calculations require REF=UHF or REF=ROHF")
        if mult == 1 and ref not in {"RHF", "UHF"}:
            raise ValueError("Closed-shell singlet CFOUR calculations require REF=RHF or REF=UHF")
    else:
        ref = "UHF" if mult > 1 else "RHF"

    requested_fc = (
        bool(getattr(config, "frozen_core", True))
        if frozen_core is None
        else bool(frozen_core)
    )
    # CFOUR 2.1 xfillfc expects a FRZINF record on correlated derivatives when
    # FROZEN_CORE=ON; species with only H/He (Z<=2) have zero core orbitals, so
    # FROZEN_CORE=OFF is physically identical and avoids the empty-core crash.
    needs_corr_deriv = config.method != "HF" and (gradient or do_harmonic or do_vpt2)
    eff_frozen_core = requested_fc and (not needs_corr_deriv or _has_core_electrons(elements))

    resolved_vib: str | None = None
    if do_vpt2 or do_harmonic:
        if vib_mode is not None:
            resolved_vib = vib_mode.strip().upper()
            if resolved_vib not in {"EXACT", "FINDIF"}:
                raise ValueError("CFOUR vib_mode must be 'EXACT' or 'FINDIF'")
        else:
            resolved_vib = "EXACT" if (config.method in {"HF", "MP2"} and ref != "ROHF") else "FINDIF"

    cc_prog: str | None = None
    if config.method in {"CCSD", "CCSD(T)"}:
        if ref == "RHF" and not (gradient or do_harmonic or do_vpt2):
            cc_prog = "NCC"
        else:
            cc_prog = "VCC"

    return {
        "spherical": use_spherical,
        "frozen_core": eff_frozen_core,
        "requested_frozen_core": requested_fc,
        "reference": ref,
        "multiplicity": mult,
        "do_vpt2": do_vpt2,
        "do_harmonic": do_harmonic,
        "vib_mode": resolved_vib,
        "cc_prog": cc_prog,
    }


def write_cfour_input(directory: Path, config: Any, elements: list[str], coordinates: Any,
                      *, memory_mb: int = 1024, gradient: bool = False,
                      harmonic: bool = False, anharmonic: bool | None = None,
                      frozen_core: bool | None = None, reference: str | None = None,
                      vib_mode: str | None = None, spherical: bool | None = None) -> Path:
    """Write fixed Cartesian ZMAT with spherical, frozen-core, open-shell, freq, and VPT2 support."""
    basis = config.basis_set
    if not basis or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9+_.()*-]*", basis):
        raise ValueError("CFOUR basis must be a plain supported basis label without input keywords")
    if not is_supported_cfour_basis(basis):
        raise ValueError("CFOUR basis has no reviewed native keyword mapping in BASE")
    if not supported_cfour_request(config):
        raise ValueError("The requested CFOUR operation lacks a connected native result validator")
    xyz = np.asarray(coordinates, dtype=float)
    if xyz.shape != (len(elements), 3) or not np.isfinite(xyz).all():
        raise ValueError("CFOUR requires complete finite Cartesian coordinates")
    if isinstance(memory_mb, bool) or not isinstance(memory_mb, int) or memory_mb < 1:
        raise ValueError("CFOUR global memory must be a positive integer MB")

    from cochem_base.calc.regime_guards import apply_chemical_regime_guards

    regime = apply_chemical_regime_guards(
        elements,
        charge=int(config.charge),
        method_or_theory=str(config.method),
        basis=basis,
        engine="cfour",
    )
    effective_basis = regime.effective_basis or basis
    effective_config = (
        config.model_copy(update={"basis_set": effective_basis})
        if hasattr(config, "model_copy") and effective_basis != basis
        else config
    )

    opts = _resolve_cfour_options(
        effective_config,
        elements,
        gradient=gradient,
        harmonic=harmonic,
        anharmonic=anharmonic,
        frozen_core=frozen_core,
        reference=reference,
        vib_mode=vib_mode,
        spherical=spherical,
    )

    cfour_basis_kw = normalize_cfour_basis_keyword(effective_basis)
    keywords = [
        f"CALC={config.method}",
        f"BASIS={cfour_basis_kw}",
        "COORD=CARTESIAN",
        "UNITS=BOHR",
        "SYMMETRY=OFF",
        f"REFERENCE={opts['reference']}",
        f"CHARGE={config.charge}",
        f"MULTIPLICITY={opts['multiplicity']}",
        f"SPHERICAL={'ON' if opts['spherical'] else 'OFF'}",
        f"FROZEN_CORE={'ON' if opts['frozen_core'] else 'OFF'}",
        "SCF_CONV=10",
        "CC_CONV=10",
        f"MEMORY_SIZE={memory_mb}",
        "MEM_UNIT=MB",
    ]
    for rel_kw in regime.cfour_keywords:
        if rel_kw not in keywords:
            keywords.append(rel_kw)
    if opts["cc_prog"] is not None:
        keywords.append(f"CC_PROG={opts['cc_prog']}")
    if opts["do_vpt2"]:
        keywords.append(f"VIB={opts['vib_mode']}")
        keywords.append("ANHARM=VPT2")
        # CFOUR 2.1 defaults CPHF_CONVER to 10^-16 (ICPHFT=16), which hits the
        # IEEE-754 FP64 roundoff floor (~10^-26 squared norm) in xcphf for
        # correlated analytic Hessians (e.g. MP2 VIB=EXACT) and aborts after
        # 64 cycles. CPHF_CONVER=12 (10^-12) avoids the xcphf FP64 roundoff
        # stall cleanly above machine roundoff while keeping LINEQ_CONV=10.
        keywords.append("LINEQ_CONV=10")
        keywords.append("CPHF_CONVER=12")
        keywords.append("CPHF_MAXCYC=128")
    elif opts["do_harmonic"]:
        keywords.append(f"VIB={opts['vib_mode']}")
        if opts["vib_mode"] == "EXACT":
            keywords.append("CPHF_CONVER=12")
            keywords.append("CPHF_MAXCYC=128")
    elif gradient:
        keywords.append("DERIV_LEVEL=FIRST")

    text = "CoChem BASE measured CFOUR Cartesian job\n"
    # CFOUR 2.1's legacy ANGSTROM conversion uses a rounded bohr constant.
    # Serialize CODATA-converted bohr coordinates so the measured derivative
    # frame binds to BASE's Angstrom input without size-dependent unit drift.
    text += "\n".join(symbol + " " + " ".join(format(float(v) / BOHR_ANGSTROM, ".17g") for v in row)
                       for symbol, row in zip(elements, xyz, strict=True))
    text += "\n\n*CFOUR(" + "\n".join(keywords) + ")\n\n"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "ZMAT"
    path.write_text(text, encoding="utf-8")
    return path


def _accept_output(
    text: str,
    method: str,
    requested_threads: int,
    *,
    anharmonic: bool = False,
    multiplicity: int = 1,
) -> dict[str, Any]:
    """Check every native module status and the specifically requested energy."""
    from cochem_base.exceptions import ConvergenceError
    if re.search(r"NOT CONVERGED|DID NOT CONVERGE|FAILED TO CONVERGE|FATAL ERROR|ABNORMAL TERMINATION", text, re.I):
        raise ConvergenceError("CFOUR reported failed scientific convergence")
    statuses = re.findall(r"--executable\s+(\S+)\s+finished with status\s+(-?\d+)\b", text)
    if not statuses or any(int(status) != 0 for _, status in statuses):
        raise ConvergenceError("CFOUR must report successful completion of every native module")
    invocations = re.findall(r"--invoking executable--\s*\n([^\n]+)", text)
    if [Path(path.strip()).name for path in invocations] != [name for name, _ in statuses]:
        raise ConvergenceError("CFOUR native module invocations and completion records differ")
    if not re.search(r"\bSCF\b[^\n]*\bconverged\b", text, re.I):
        raise ConvergenceError("CFOUR lacks explicit SCF convergence")
    final = re.findall(rf"The final electronic energy is\s+({NUMBER})\s+a\.u\.", text)
    if len(final) != 1:
        raise ValueError("CFOUR requires one finite final electronic energy and normal driver completion")
    patterns = {
        "HF": rf"E\(SCF\)\s*=\s*({NUMBER})",
        "MP2": rf"(?:Total MP2 energy|Total MBPT\(2\)\s+energy|E\(MP2\))\s*[:=]?\s*({NUMBER})",
        "CCSD": rf"(?:Total CCSD energy|E\(CCSD\)|(?<![A-Za-z0-9_(])CCSD energy)\s*[:=]?\s*({NUMBER})",
        "CCSD(T)": rf"(?:Total CCSD\(T\) energy|E\(CCSD\(T\)\)|(?<![A-Za-z0-9_(])CCSD\(T\) energy)\s*[:=]?\s*({NUMBER})",
    }
    measured = re.findall(patterns[method], text, re.I)
    if not measured and method == "CCSD":
        # CFOUR 2.1 xvcc for CALC=CCSD reports "The total energy is <E> a.u."
        # inside the converged xvcc section rather than "E(CCSD) = <E>".
        vcc_sections = re.findall(
            r"--invoking executable--\s*[^\n]*[/\\]xvcc\s*\n(.*?)(?=--executable xvcc finished)",
            text,
            re.S,
        )
        for sec in vcc_sections:
            if re.search(r"CCSD energy will be calculated", sec, re.I) and re.search(
                r"The CC iterations have converged", sec, re.I
            ):
                measured.extend(re.findall(rf"The total energy is\s+({NUMBER})\s+a\.u\.", sec, re.I))
    if not measured:
        raise ValueError(f"CFOUR has no measured total energy for requested {method}")
    energy = _float(final[0])
    # In VPT2 / FINDIF displacement jobs, the final electronic energy corresponds
    # to the reference geometry (first evaluation), while later evaluations are displaced.
    candidates = [_float(item) for item in measured]
    if not any(math.isclose(energy, cand, abs_tol=ENERGY_TOLERANCE_HARTREE, rel_tol=0) for cand in (candidates[0], candidates[-1])):
        raise ValueError("CFOUR final energy does not match the explicitly requested method")
    if method in {"CCSD", "CCSD(T)"}:
        has_cc_conv = bool(
            re.search(
                r"(?:CCSD iterations converged in\s+\d+\s+cycles|"
                r"Amplitude equations converged in\s+\d+\s*iterations|"
                r"The CC iterations have converged)",
                text,
                re.I,
            )
        )
        if not has_cc_conv:
            raise ConvergenceError("The coupled-cluster calculation lacks measured convergence")
        ncc_sections = re.findall(
            r"--invoking executable--\s*[^\n]*[/\\]xncc\s*\n(.*?)(?=--executable xncc finished)",
            text,
            re.S,
        )
        if ncc_sections:
            if any(re.findall(r"Running with (\d+) threads/proc", sec) != [str(requested_threads)] for sec in ncc_sections):
                raise ValueError("NCC did not confirm the requested OpenMP thread count")
    if anharmonic and not re.search(r"HARMONIC AND FUNDAMENTAL FREQUENCIES|VPT2 vibrational analysis", text, re.I):
        raise ValueError("CFOUR VPT2 output lacks anharmonic vibrational analysis results")
    accepted_payload: dict[str, Any] = {
        "energy_hartree": energy,
        "reference_energy_hartree": candidates[0],
        "native_modules_completed": [name for name, _ in statuses],
        "electronic_convergence_verified": True,
    }
    if method in {"CCSD", "CCSD(T)"}:
        from cochem_base.calc.regime_guards import parse_cc_multireference_diagnostics

        accepted_payload["multireference_diagnostics"] = parse_cc_multireference_diagnostics(
            text, engine="cfour", method=method, multiplicity=multiplicity,
        )
    return accepted_payload


def _rigid_alignment(native: np.ndarray, target: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Find the proper rigid transform without permitting reordered atoms."""
    native_center, target_center = np.mean(native, axis=0), np.mean(target, axis=0)
    u, _, vt = np.linalg.svd((native - native_center).T @ (target - target_center))
    correction = np.diag([1., 1., float(np.linalg.det(u @ vt))])
    rotation = u @ correction @ vt
    aligned = (native - native_center) @ rotation + target_center
    if not np.allclose(aligned, target, atol=GEOMETRY_TOLERANCE_ANGSTROM, rtol=0):
        raise ValueError("CFOUR derivative geometry differs from its submitted ordered nuclear geometry")
    return rotation, aligned


def read_cfour_gradient(path: Path, elements: list[str], target_coordinates: Any) -> dict[str, Any]:
    """Read the actual GRD checkpoint and rotate its measured derivatives."""
    from cochem_base.physics.isotopes import get_element_mass_and_abundance
    lines = [line.split() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    count = len(elements)
    if not lines or int(lines[0][0]) != count or len(lines) != 1 + 2 * count:
        raise ValueError("CFOUR GRD must contain its complete ordered geometry and 3N gradient")
    expected = [get_element_mass_and_abundance(symbol)[2] for symbol in elements]
    native_coordinates, gradients = [], []
    for row, nuclear_charge in zip(lines[1:1 + count], expected, strict=True):
        if len(row) != 4 or _float(row[0]) != nuclear_charge:
            raise ValueError("CFOUR GRD atomic identities/order changed")
        native_coordinates.append([_float(v) * BOHR_ANGSTROM for v in row[1:]])
    for row, nuclear_charge in zip(lines[1 + count:], expected, strict=True):
        if len(row) != 4 or _float(row[0]) != nuclear_charge:
            raise ValueError("CFOUR GRD contains an incomplete Cartesian gradient")
        gradients.append([_float(v) for v in row[1:]])
    native, gradient = np.asarray(native_coordinates), np.asarray(gradients)
    rotation, _ = _rigid_alignment(native, np.asarray(target_coordinates, dtype=float))
    return {"native_coordinates_angstrom": native.tolist(), "native_gradients_hartree_per_bohr": gradient.tolist(),
            "gradients_hartree_per_bohr": (gradient @ rotation).tolist(), "native_to_submitted_rotation": rotation.tolist()}


def _accept_hessian(directory: Path, elements: list[str], coordinates: Any,
                    text: str, root: Path, runtime: dict[str, Any] | None = None,
                    *, nuclides: list[str] | None = None, method: str = "HF") -> dict[str, Any]:
    from cochem_base.spectroscopy.isotopologue import IsotopologueSpectroscopyEngine, projected_harmonic_frequencies
    from cochem_base.geometry.nuclide_geometry import resolve_nuclear_identity
    identity = resolve_nuclear_identity(nuclides if nuclides is not None else elements)
    if list(identity.elements) != elements:
        raise ValueError("CFOUR harmonic nuclide assignments differ from the submitted electronic elements")
    path = directory / "FCMFINAL"
    tokens = path.read_text(encoding="utf-8").split()
    n, dimension = len(elements), 3 * len(elements)
    if len(tokens) != 2 + dimension * dimension or [int(v) for v in tokens[:2]] != [n, dimension]:
        raise ValueError("CFOUR FCMFINAL must be a complete 3N Cartesian Hessian")
    matrix = np.asarray([_float(v) for v in tokens[2:]]).reshape(dimension, dimension)
    if not np.allclose(matrix, matrix.T, atol=1e-8, rtol=0):
        raise ValueError("CFOUR Cartesian Hessian is not symmetric")
    if (directory / "GRD").is_file():
        gradient = read_cfour_gradient(directory / "GRD", elements, coordinates)
        native_coordinates = np.asarray(gradient["native_coordinates_angstrom"])
    else:
        native_coordinates = np.asarray(coordinates, dtype=float)
    masses_blocks = re.findall(r"masses used \(in AMU\) in vibrational analysis:\s*\n(.*?)Normal Coordinate Analysis", text, re.S)
    if not masses_blocks:
        raise ValueError("CFOUR harmonic output lacks its actual vibrational masses")
    masses = np.asarray([_float(v) for v in masses_blocks[0].split()])
    if masses.shape != (n,) or np.any(masses <= 0):
        raise ValueError("CFOUR native masses must be positive and complete")
    rows = re.findall(rf"^\s*\S+\s+({NUMBER})(i?)\s+{NUMBER}\s+(VIBRATION|ROTATION|TRANSLATION)\s*$", text, re.M)
    if len(rows) < dimension:
        raise ValueError("CFOUR harmonic output lacks a complete classified 3N spectrum")
    first_spectrum = rows[:dimension]
    vibration = sorted((-1 if imaginary else 1) * _float(value) for value, imaginary, kind in first_spectrum if kind == "VIBRATION")
    recalculated, rigid = projected_harmonic_frequencies(matrix, native_coordinates, masses)
    if len(vibration) != dimension - rigid or not np.allclose(vibration, recalculated, atol=FREQUENCY_TOLERANCE_CM1, rtol=0):
        raise ValueError("CFOUR native frequencies disagree with its geometry-bound mass-weighted Hessian")
    if "--executable xcphf finished" in text and not re.search(r"CPHF converged after\s+\d+\s+iterations", text):
        raise ValueError("CFOUR analytic Hessian lacks response-equation convergence")
    principal = IsotopologueSpectroscopyEngine(elements, native_coordinates, matrix).compute_observables()
    selected = IsotopologueSpectroscopyEngine(list(identity.nuclides), native_coordinates, matrix).compute_observables()
    bundle = directory / "harmonic-hessian.npz"
    raw_names = [name for name in ("ZMAT", "GRD", "FCMFINAL", "output.dat") if (directory / name).is_file()]
    source = {"engine": "cfour", "method": method, "coordinates_frame": "Native GRD/FCMFINAL Cartesian frame",
              "raw_artifacts": {name: _record(directory / name, root) for name in raw_names},
              "runtime_seal_sha256": runtime.get("runtime_seal_sha256") if runtime else None,
              "nuclear_identity": identity.metadata}
    np.savez_compressed(bundle, symbols=np.asarray(identity.nuclides), coordinates_angstrom=native_coordinates,
                        hessian_hartree_bohr2=matrix, source=np.asarray(json.dumps(source, sort_keys=True)))
    from cochem_base.spectroscopy.artifacts import load_hessian_artifact
    canonical = load_hessian_artifact(bundle)
    if canonical.symbols != identity.nuclides or not np.array_equal(canonical.hessian_hartree_bohr2, matrix):
        raise ValueError("The published CFOUR harmonic bundle differs from its measured native Hessian")
    evidence = {**_record(path, root, "hartree/bohr^2"), "shape": list(matrix.shape),
                "coordinates_angstrom": native_coordinates.tolist(), "native_masses_u": masses.tolist(),
                "native_vibrational_frequencies_cm1": vibration,
                "rediagonalized_native_mass_frequencies_cm1": list(recalculated), "rigid_mode_count": rigid,
                "frequency_consistency_tolerance_cm1": FREQUENCY_TOLERANCE_CM1,
                "native_spectrum_max_difference_cm1": float(np.max(np.abs(np.asarray(vibration) - recalculated))) if vibration else 0.0,
                "scientific_accuracy_established": False}
    return {"hessian_artifact": evidence,
            "hessian_bundle_artifact": {**_record(bundle, root, "hartree/bohr^2"), "coordinates_unit": "angstrom",
                                         "scope": "Geometry-bound measured harmonic Hessian; no anharmonic force field"},
            "harmonic_frequencies_cm1": selected.harmonic_frequencies_cm1,
            "harmonic_nuclides": list(identity.nuclides),
            "harmonic_isotope_masses_u": selected.masses,
            "principal_isotope_masses_u": principal.masses,
            "harmonic_frequency_provenance": "Input-nuclide mass reweighting and geometric rigid-motion projection of measured CFOUR FCMFINAL; bare elements select their principal isotope"}


def _reconcile_post_opt_vibrational_energy(
    previous_energy: float,
    final: dict[str, Any],
    *,
    vib_mode: str | None,
    is_vpt2: bool,
) -> float:
    """Cross-check post-optimization vibrational energy against the optimized equilibrium minimum."""
    if vib_mode == "EXACT" and not is_vpt2:
        if not math.isclose(final["energy_hartree"], previous_energy, abs_tol=ENERGY_TOLERANCE_HARTREE, rel_tol=0):
            raise ValueError("CFOUR vibrational evaluation changed the optimized electronic energy")
        return final["energy_hartree"]
    # In ANY multi-displacement job (VPT2 with VIB=EXACT or VIB=FINDIF, or
    # harmonic VIB=FINDIF), CFOUR's last evaluated energy is a displaced
    # geometry; cross-check the first undisplaced reference evaluation energy
    # against the optimized minimum and retain `previous_energy`.
    reference_energy = final.get("reference_energy_hartree")
    if (
        not isinstance(reference_energy, (int, float))
        or isinstance(reference_energy, bool)
        or not math.isclose(reference_energy, previous_energy, abs_tol=ENERGY_TOLERANCE_HARTREE, rel_tol=0)
    ):
        raise ValueError("CFOUR vibrational evaluation reference geometry changed the optimized electronic energy")
    return previous_energy


@scientific_producer
def execute_cfour(config: Any, elements: list[str], coordinates: Any, *, directory: Path,
                  authority: Any, environment: dict[str, str], cancellation_event: Any = None,
                  on_event: Callable[[dict[str, Any]], None] | None = None,
                  telemetry_job_id: str | None = None,
                  frozen_core: bool | None = None,
                  reference: str | None = None,
                  vib_mode: str | None = None,
                  spherical: bool | None = None) -> dict[str, Any]:
    """Execute native checkpoints, preserving every process and optimizer step."""
    from cochem_base.core_engine.cochem_core_subprocess_broker import safe_subprocess_run
    from cochem_base.geometry.nuclide_geometry import parse_geometry_identity
    nuclear_identity = parse_geometry_identity(config.geometry)
    if list(nuclear_identity.elements) != elements:
        raise ValueError("CFOUR input nuclear assignments differ from the submitted ordered electronic elements")
    from cochem_base.core_engine.cfour_runtime import verify_cfour_runtime
    from cochem_base.core_engine.scientific_telemetry import append_scientific_result
    if not supported_cfour_request(config):
        raise ValueError("CFOUR requested operation remains pending integration")
    _raise_if_cancelled(cancellation_event)
    authorized_seal = getattr(authority, "runtime_seal_sha256", None)
    runtime = verify_cfour_runtime(authority.executable, environment=environment)
    _require_authorized_runtime_seal(authorized_seal, runtime["runtime_seal_sha256"])
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "runtime_provenance.json").write_text(json.dumps(runtime, indent=2, allow_nan=False), encoding="utf-8")
    child_environment = {key: value for key, value in environment.items()
                         if not any(marker in key.upper() for marker in ("TOKEN", "SECRET", "PASSWORD", "CREDENTIAL", "API_KEY"))}
    child_environment["PATH"] = os.pathsep.join([*runtime["path_entries"], child_environment.get("PATH", os.defpath)])
    if runtime.get("ld_library_path"):
        child_environment["LD_LIBRARY_PATH"] = runtime["ld_library_path"]
    started = time.monotonic()
    runs: list[dict[str, Any]] = []
    trajectory: list[dict[str, Any]] = []

    def native(xyz: Any, *, gradient: bool = False, harmonic: bool = False, anharmonic: bool = False) -> dict[str, Any]:
        _raise_if_cancelled(cancellation_event)
        remaining = config.timeout_seconds - (time.monotonic() - started)
        if remaining <= 0:
            raise TimeoutError("CFOUR operation exceeded its total wall-clock budget")
        work = directory / f"evaluation-{len(runs):04d}"
        current_runtime = verify_cfour_runtime(authority.executable, environment=environment)
        _require_authorized_runtime_seal(authorized_seal, current_runtime["runtime_seal_sha256"])
        _raise_if_cancelled(cancellation_event)
        deck = write_cfour_input(
            work, config, elements, xyz, memory_mb=authority.total_memory_mb,
            gradient=gradient, harmonic=harmonic, anharmonic=anharmonic,
            frozen_core=frozen_core, reference=reference, vib_mode=vib_mode, spherical=spherical,
        )
        for name, field in (("GENBAS", "genbas"), ("ECPDATA", "ecpdata")):
            source = current_runtime.get(field)
            if source:
                os.symlink(Path(source).resolve(strict=True), work / name)
        proc = safe_subprocess_run(authority.command(), cwd=work, timeout=remaining, check=False,
                                   capture_output=True, text=True, env=child_environment,
                                   required_disk_gb=0.1, load_full_stdout=True,
                                   sanitize_mpi=False,
                                   cpu_affinity=list(authority.cpu_affinity) or None,
                                   cancellation_event=cancellation_event,
                                   on_stdout_line=(lambda line: on_event({"kind": "log", "stream": "stdout", "message": line})) if on_event else None)
        stdout, stderr = work / "output.dat", work / "stderr.log"
        stdout.write_text(proc.stdout or "", encoding="utf-8")
        stderr.write_text(proc.stderr or "", encoding="utf-8")
        completed_runtime = verify_cfour_runtime(authority.executable, environment=environment)
        _require_authorized_runtime_seal(authorized_seal, completed_runtime["runtime_seal_sha256"])
        _raise_if_cancelled(cancellation_event)
        if proc.returncode != 0:
            raise RuntimeError(f"CFOUR process exited {proc.returncode}; diagnostics retained in {work}")
        accepted = _accept_output(
            proc.stdout or "", config.method, authority.cores,
            anharmonic=anharmonic, multiplicity=int(config.multiplicity),
        )
        accepted.update(input_artifact=_record(deck, directory.parent), output_artifact=_record(stdout, directory.parent))
        accepted["directory"] = str(work.relative_to(directory.parent))
        if (gradient or harmonic) and (work / "GRD").is_file():
            derivatives = read_cfour_gradient(work / "GRD", elements, xyz)
            accepted.update(gradients_hartree_per_bohr=derivatives["gradients_hartree_per_bohr"],
                            gradient_artifact={**_record(work / "GRD", directory.parent, "hartree/bohr"),
                                               "native_to_submitted_rotation": derivatives["native_to_submitted_rotation"]})
        if harmonic and (work / "FCMFINAL").is_file():
            accepted.update(_accept_hessian(work, elements, xyz, proc.stdout or "", directory.parent, runtime,
                                           nuclides=list(nuclear_identity.nuclides), method=config.method))
        if anharmonic:
            from cochem_base.core_engine.cochem_core_cfour_bridge import CFOUROutputParser
            obs = CFOUROutputParser.parse_cfour_stdout(
                proc.stdout or "", symbols_fallback=elements, coordinates_fallback=np.asarray(xyz, dtype=float)
            )
            accepted.update({
                "vpt2_observables": obs.model_dump(mode="json"),
                "harmonic_frequencies_cm1": list(obs.harmonic_force_field.frequencies_cm_inv),
                "fundamental_frequencies_cm1": list(obs.fundamental_frequencies_cm_inv),
                "anharmonic_contributions_cm1": list(obs.anharmonic_contributions_cm_inv),
                "rotational_constants_be_mhz": [obs.Ae_MHz, obs.Be_MHz, obs.Ce_MHz],
                "rotational_constants_b0_mhz": [obs.A0_MHz, obs.B0_MHz, obs.C0_MHz],
                "quartic_distortion_khz": obs.quartic_distortion.model_dump(mode="json") if obs.quartic_distortion else None,
                "vpt2_zpe_cm1": obs.vpt2_zpe_cm_inv,
            })
        runs.append(accepted)
        (directory / "native_evaluations.json").write_text(json.dumps(runs, indent=2, allow_nan=False), encoding="utf-8")
        return accepted

    final_coordinates = np.asarray(coordinates, dtype=float)
    optimization = None
    if config.is_opt:
        from scipy.optimize import minimize
        accepted_steps: list[dict[str, Any]] = []

        def energy_and_gradient(flat_coordinates: np.ndarray) -> tuple[float, np.ndarray]:
            positions = flat_coordinates.reshape(len(elements), 3)
            result = native(positions, gradient=True)
            gradient = np.asarray(result["gradients_hartree_per_bohr"])
            frame = {"coordinates_angstrom": positions.tolist(), "energy_hartree": result["energy_hartree"],
                     "gradients_hartree_per_bohr": gradient.tolist(), "evaluation": result["directory"]}
            trajectory.append(frame)
            (directory / "optimization_trajectory.json").write_text(json.dumps(trajectory, indent=2, allow_nan=False), encoding="utf-8")
            if telemetry_job_id is not None:
                append_scientific_result(telemetry_job_id, nuclear_identity.nuclides, positions, result["energy_hartree"],
                                         gradients=gradient, metadata={"engine": "cfour", "method": config.method,
                                            "record_kind": "optimization_gradient_evaluation", "optimizer": "SciPy BFGS"})
            # SciPy's variables are Angstrom, whereas native GRD is Eh/bohr.
            return result["energy_hartree"], gradient.ravel() / BOHR_ANGSTROM

        def record_step(flat_coordinates: np.ndarray) -> None:
            accepted_steps.append({"coordinates_angstrom": flat_coordinates.reshape(len(elements), 3).tolist()})
            (directory / "optimizer_steps.json").write_text(json.dumps(accepted_steps, indent=2, allow_nan=False), encoding="utf-8")

        optimized = minimize(energy_and_gradient, final_coordinates.ravel(), method="BFGS", jac=True,
                             callback=record_step,
                             options={"gtol": OPTIMIZATION_FORCE_TOLERANCE / (BOHR_ANGSTROM * math.sqrt(3)),
                                      "maxiter": 100})
        final_coordinates = optimized.x.reshape(len(elements), 3)
        final = native(final_coordinates, gradient=True)
        if not optimized.success:
            raise ValueError(f"CFOUR-backed BFGS did not reach declared convergence: {optimized.message}")
        force = float(np.max(np.linalg.norm(np.asarray(final["gradients_hartree_per_bohr"]), axis=1)))
        if force > OPTIMIZATION_FORCE_TOLERANCE:
            raise ValueError("CFOUR final measured Cartesian gradient exceeds optimization tolerance")
        optimization = {"optimizer": "SciPy BFGS with native CFOUR analytic gradients", "converged": True,
                        "evaluations": len(trajectory), "maximum_atomic_gradient_hartree_per_bohr": force,
                        "tolerance_hartree_per_bohr": OPTIMIZATION_FORCE_TOLERANCE,
                        "trajectory_artifact": _record(directory / "optimization_trajectory.json", directory.parent),
                        "trajectory_scope": "Every actual gradient evaluation, including line-search evaluations",
                        "accepted_steps": accepted_steps, "optimizer_message": str(optimized.message)}
    else:
        final = native(
            final_coordinates,
            gradient=(config.method == "HF" and not config.is_freq and not config.is_vpt2),
            harmonic=(config.is_freq and not config.is_vpt2),
            anharmonic=config.is_vpt2,
        )
    equilibrium_energy_hartree = final["energy_hartree"]
    if config.is_opt and (config.is_freq or config.is_vpt2):
        previous_energy = final["energy_hartree"]
        vib_opts = _resolve_cfour_options(
            config,
            elements,
            harmonic=(config.is_freq and not config.is_vpt2),
            anharmonic=config.is_vpt2,
            frozen_core=frozen_core,
            reference=reference,
            vib_mode=vib_mode,
            spherical=spherical,
        )
        final = native(
            final_coordinates,
            harmonic=(config.is_freq and not config.is_vpt2),
            anharmonic=config.is_vpt2,
        )
        equilibrium_energy_hartree = _reconcile_post_opt_vibrational_energy(
            previous_energy,
            final,
            vib_mode=vib_opts["vib_mode"],
            is_vpt2=bool(config.is_vpt2),
        )

    from cochem_base.calc.regime_guards import apply_chemical_regime_guards

    regime = apply_chemical_regime_guards(
        elements,
        charge=int(config.charge),
        method_or_theory=str(config.method),
        basis=config.basis_set,
        engine="cfour",
    )
    resolved_opts = _resolve_cfour_options(
        config.model_copy(update={"basis_set": regime.effective_basis or config.basis_set})
        if hasattr(config, "model_copy") and regime.effective_basis
        else config,
        elements,
        gradient=config.is_opt, harmonic=(config.is_freq and not config.is_vpt2),
        anharmonic=config.is_vpt2, frozen_core=frozen_core, reference=reference,
        vib_mode=vib_mode, spherical=spherical,
    )
    operation = (
        "vpt2" if config.is_vpt2
        else "harmonic_frequencies" if config.is_freq
        else "optimization" if config.is_opt
        else "single_point"
    )
    result = {"engine": "cfour", "method": config.method, "basis_set": regime.effective_basis or config.basis_set,
              "requested_basis_set": config.basis_set,
              "converged": True, "energy_hartree": equilibrium_energy_hartree, "elements": elements,
              "coordinates_angstrom": final_coordinates.tolist(), "operation": operation,
              "optimization_performed": config.is_opt, "native_evaluations": runs,
              "reference": resolved_opts["reference"], "multiplicity": resolved_opts["multiplicity"],
              "spherical_basis": resolved_opts["spherical"], "frozen_core": resolved_opts["frozen_core"],
              "vib_mode": resolved_opts["vib_mode"],
              "anharmonic_mode": "VPT2" if config.is_vpt2 else "NONE",
              "parallel_model": "OpenMP; no MPI launcher", "requested_threads": authority.cores,
              "runtime_provenance": runtime,
              "regime_guards": regime.to_provenance_dict(),
              "scientific_accuracy_established": False}
    result.update({
        key: final[key]
        for key in (
            "gradients_hartree_per_bohr", "gradient_artifact", "hessian_artifact",
            "hessian_bundle_artifact", "harmonic_frequencies_cm1", "harmonic_nuclides",
            "harmonic_isotope_masses_u", "principal_isotope_masses_u",
            "harmonic_frequency_provenance", "fundamental_frequencies_cm1",
            "anharmonic_contributions_cm1", "rotational_constants_be_mhz",
            "rotational_constants_b0_mhz", "quartic_distortion_khz",
            "vpt2_zpe_cm1", "vpt2_observables", "multireference_diagnostics",
        )
        if key in final
    })
    if optimization:
        result["optimization_evidence"] = optimization
    result["metadata"] = {
        key: result[key]
        for key in (
            "gradient_artifact", "hessian_artifact", "hessian_bundle_artifact",
            "optimization_evidence", "harmonic_frequencies_cm1", "fundamental_frequencies_cm1",
            "harmonic_nuclides", "harmonic_isotope_masses_u", "principal_isotope_masses_u",
            "rotational_constants_be_mhz", "rotational_constants_b0_mhz",
            "quartic_distortion_khz", "vpt2_zpe_cm1", "parallel_model",
            "regime_guards", "multireference_diagnostics",
        )
        if key in result
    }
    result.update(nuclides=list(nuclear_identity.nuclides), nuclear_identity=nuclear_identity.metadata)
    _raise_if_cancelled(cancellation_event)
    return result
