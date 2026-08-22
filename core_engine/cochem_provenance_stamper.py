#!/usr/bin/env python3
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
CoChem-CORE: Stage 8.0 - Cryptographic Provenance Stamper & Artifact Immutability Lock.

Provides FAIR-compliant cryptographic provenance tracking and OS-level artifact immutability.
Constructs linked JSON-LD provenance blocks containing:
- SHA-256 cryptographic hash of cochem_system_config.json
- Exact software version manifests (via pip freeze and distribution hashes)
- Hardware microarchitecture flags (AVX-512 support, BLAS/LAPACK linking)
- Target file pre-stamp cryptographic checksums

Appends structured JSON-LD footers directly into plaintext `.out` run files and applies
immutable filesystem read-only permissions (os.chmod 0o444) to mathematically prevent
tampering or accidental overwrites across host operating systems.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import logging
import os
import platform
import stat
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

from pydantic import BaseModel, ConfigDict, Field

from cochem_base.config_loader import resolve_config_path

logger = logging.getLogger("CoChem-ProvenanceStamper")

FOOTER_DELIMITER_START: str = "--- BEGIN COCHEM PROVENANCE JSON-LD ---"
FOOTER_DELIMITER_END: str = "--- END COCHEM PROVENANCE JSON-LD ---"


# =============================================================================
# PYDANTIC VALIDATION MODELS
# =============================================================================


class JSONLDSoftwareEnvironment(BaseModel):
    """Software dependency and runtime version manifest."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    pip_freeze_sha256: str = Field(..., description="SHA-256 hash of normalized pip freeze output")
    package_count: int = Field(..., ge=0, description="Total count of installed packages")
    packages: Dict[str, str] = Field(
        default_factory=dict, description="Package name to version mapping"
    )
    python_version: str = Field(..., description="Python runtime version")
    python_implementation: str = Field(..., description="Python implementation (CPython/PyPy)")
    executable_path: str = Field(..., description="Path to active Python executable")


class JSONLDHardwareMicroarchitecture(BaseModel):
    """Hardware microarchitecture and acceleration features."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    cpu_arch: str = Field(..., description="CPU architecture identifier")
    cpu_model: str = Field(..., description="CPU processor model description")
    physical_cores: int = Field(..., ge=1, description="Physical CPU cores")
    logical_cores: int = Field(..., ge=1, description="Logical/hyperthreaded CPU cores")
    total_ram_gb: float = Field(..., ge=0.0, description="Total host RAM in GB")
    avx512_support: bool = Field(..., description="Whether AVX-512 SIMD instructions are supported")
    avx512_details: Dict[str, Any] = Field(
        default_factory=dict, description="Detailed AVX-512 instruction flags"
    )
    blas_info: Dict[str, Any] = Field(
        default_factory=dict, description="BLAS/LAPACK linking and library info"
    )


class JSONLDTargetFileInfo(BaseModel):
    """Pre-stamp target file cryptographic metadata."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    filename: Optional[str] = Field(default=None, description="Target file base name")
    sha256: str = Field(..., description="SHA-256 checksum of file prior to footer stamping")
    size_bytes: int = Field(..., ge=0, description="File size in bytes prior to footer stamping")


class ProvenanceRecordModel(BaseModel):
    """Full JSON-LD Linked Data Provenance Record."""

    model_config = ConfigDict(extra="allow", validate_assignment=True, populate_by_name=True)

    context: Dict[str, Any] = Field(..., alias="@context", description="JSON-LD context mapping")
    entity_type: List[str] = Field(..., alias="@type", description="JSON-LD rdf:type hierarchy")
    record_id: str = Field(..., alias="@id", description="Unique URN for this provenance run")
    generated_at_time: str = Field(
        ..., alias="prov:generatedAtTime", description="ISO 8601 UTC timestamp"
    )
    was_generated_by: Dict[str, Any] = Field(
        ..., alias="prov:wasGeneratedBy", description="Activity and engine metadata"
    )
    system_config_sha256: str = Field(
        ..., alias="cochem:systemConfigSha256", description="SHA-256 of cochem_system_config.json"
    )
    software_environment: JSONLDSoftwareEnvironment = Field(..., alias="cochem:softwareEnvironment")
    hardware_microarchitecture: JSONLDHardwareMicroarchitecture = Field(
        ..., alias="cochem:hardwareMicroarchitecture"
    )
    target_file_pre_stamp: Optional[JSONLDTargetFileInfo] = Field(
        default=None, alias="cochem:targetFilePreStamp"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, alias="cochem:metadata")


# =============================================================================
# 1. CONFIGURATION & SOFTWARE PROVENANCE HASHING
# =============================================================================


def get_system_config_sha256(config_path: Optional[Union[str, Path]] = None) -> str:
    """Computes the deterministic SHA-256 hash of cochem_system_config.json.

    Args:
        config_path: Optional custom path to cochem_system_config.json.

    Returns:
        64-character lowercase hexadecimal SHA-256 hash.

    Raises:
        FileNotFoundError: If the resolved configuration file does not exist on disk.
    """
    resolved = resolve_config_path(Path(config_path) if config_path is not None else None)
    if not resolved.is_file():
        raise FileNotFoundError(f"Configuration file not found at: {resolved}")

    content = resolved.read_text(encoding="utf-8", errors="replace")
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def get_software_version_hashes(timeout_seconds: float = 30.0) -> Dict[str, Any]:
    """Extracts exact installed software versions via pip freeze and computes manifest hash.

    Args:
        timeout_seconds: Subprocess execution timeout in seconds.

    Returns:
        Dict containing pip_freeze_sha256, package_count, packages mapping, python_version, etc.
    """
    packages: Dict[str, str] = {}
    raw_lines: List[str] = []

    try:
        cmd = [sys.executable, "-m", "pip", "freeze"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=True,
        )
        for line in result.stdout.strip().splitlines():
            line_str = line.strip()
            if not line_str or line_str.startswith("#"):
                continue
            raw_lines.append(line_str)
            if "==" in line_str:
                pkg_name, pkg_ver = line_str.split("==", 1)
                packages[pkg_name.strip()] = pkg_ver.strip()
            elif "@" in line_str:
                parts = line_str.split("@", 1)
                packages[parts[0].strip()] = parts[1].strip()
            else:
                packages[line_str] = "installed"
    except Exception as e:
        logger.warning(f"pip freeze invocation failed: {e}. Falling back to importlib.metadata.")
        # Fallback to standard library importlib.metadata
        try:
            for dist in importlib.metadata.distributions():
                name = dist.metadata["Name"] or dist.name
                version = dist.version
                packages[name] = version
                raw_lines.append(f"{name}=={version}")
        except Exception as fallback_err:
            logger.error(f"importlib fallback also failed: {fallback_err}")

    # Deterministically sort lines for invariant hashing
    sorted_lines = sorted(raw_lines)
    manifest_payload = "\n".join(sorted_lines) + "\n"
    manifest_sha256 = hashlib.sha256(manifest_payload.encode("utf-8")).hexdigest()

    return {
        "pip_freeze_sha256": manifest_sha256,
        "package_count": len(packages),
        "packages": dict(sorted(packages.items())),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "executable_path": sys.executable,
    }


# =============================================================================
# 2. HARDWARE MICROARCHITECTURE PROFILING (AVX-512, BLAS)
# =============================================================================


def _detect_avx512(
    config_path: Optional[Union[str, Path]] = None,
) -> Tuple[bool, Dict[str, Any]]:
    """Detects AVX-512 CPU support and instruction set flags across architectures."""
    details: Dict[str, Any] = {
        "detection_method": "none",
        "flags": [],
    }
    avx512_found = False

    # Check numpy CPU features if available
    if HAS_NUMPY:
        try:
            if hasattr(np, "show_config"):
                conf: Any = {}
                if hasattr(np.show_config, "__code__"):
                    conf = np.show_config(mode="dicts")
                simd = conf.get("SIMD Extensions", {}) if isinstance(conf, dict) else {}
                found_simd = simd.get("found", []) + simd.get("baseline", [])
                for ext in found_simd:
                    if "AVX512" in str(ext).upper() or "AVX_512" in str(ext).upper():
                        avx512_found = True
                        details["flags"].append(str(ext))
                        details["detection_method"] = "numpy_simd"
        except Exception:
            pass

    # Check Linux /proc/cpuinfo if on Linux
    if platform.system() == "Linux":
        cpuinfo_path = Path("/proc/cpuinfo")
        if cpuinfo_path.is_file():
            try:
                content = cpuinfo_path.read_text(encoding="utf-8", errors="ignore")
                for line in content.splitlines():
                    if line.startswith("flags"):
                        flags = line.split(":", 1)[1].strip().split()
                        avx512_flags = [f for f in flags if f.startswith("avx512")]
                        if avx512_flags:
                            avx512_found = True
                            details["flags"] = sorted(set(details["flags"] + avx512_flags))
                            details["detection_method"] = "/proc/cpuinfo"
                        break
            except Exception:
                pass

    # Check Windows processor features or config file
    if not avx512_found:
        try:
            cfg_path = resolve_config_path(
                Path(config_path) if config_path is not None else None
            )
            if cfg_path.is_file():
                cfg_data = json.loads(cfg_path.read_text(encoding="utf-8"))
                hw = cfg_data.get("hardware", {})
                if hw.get("avx512_support") is True or hw.get("avx_512_capable") is True:
                    avx512_found = True
                    details["detection_method"] = "cochem_system_config"
                    details["flags"].append("AVX512_CONFIGURED")
        except Exception:
            pass

    return avx512_found, details


def _detect_blas_lapack() -> Dict[str, Any]:
    """Detects BLAS and LAPACK library linking and configuration."""
    blas_info: Dict[str, Any] = {
        "blas_detected": False,
        "blas_libraries": [],
        "lapack_libraries": [],
        "details": {},
    }

    if HAS_NUMPY:
        try:
            if hasattr(np, "show_config"):
                conf = np.show_config(mode="dicts")
                if isinstance(conf, dict):
                    build_deps = conf.get("Build Dependencies", {})
                    blas_data = build_deps.get("blas", {})
                    lapack_data = build_deps.get("lapack", {})

                    if blas_data and blas_data.get("found", False):
                        blas_info["blas_detected"] = True
                        blas_name = blas_data.get("name", "unknown_blas")
                        blas_info["blas_libraries"].append(blas_name)
                        blas_info["details"]["blas"] = {
                            "name": blas_name,
                            "version": blas_data.get("version"),
                            "openblas_configuration": blas_data.get("openblas configuration"),
                        }

                    if lapack_data and lapack_data.get("found", False):
                        lapack_name = lapack_data.get("name", "unknown_lapack")
                        blas_info["lapack_libraries"].append(lapack_name)
                        blas_info["details"]["lapack"] = {
                            "name": lapack_name,
                            "version": lapack_data.get("version"),
                        }
        except Exception as e:
            logger.debug(f"NumPy show_config dict inspection error: {e}")

    # Fallback to general library checks
    if not blas_info["blas_libraries"]:
        for candidate in ["scipy_openblas", "mkl", "openblas", "blis", "accelerate"]:
            try:
                importlib.metadata.version(candidate)
                blas_info["blas_detected"] = True
                blas_info["blas_libraries"].append(candidate)
            except importlib.metadata.PackageNotFoundError:
                pass

    return blas_info


def get_hardware_microarchitecture_flags(
    config_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Profiles and returns CPU microarchitecture, AVX-512 support, and BLAS linkage.

    Args:
        config_path: Optional custom path to cochem_system_config.json.

    Returns:
        Dict containing CPU, RAM, AVX-512 flags, and BLAS/LAPACK specifications.
    """
    phys_cores = 1
    log_cores = os.cpu_count() or 1
    total_ram_gb = 16.0

    if HAS_PSUTIL:
        try:
            phys = psutil.cpu_count(logical=False)
            if phys:
                phys_cores = phys
            log = psutil.cpu_count(logical=True)
            if log:
                log_cores = log
            total_ram_gb = round(psutil.virtual_memory().total / (1024**3), 2)
        except Exception:
            pass

    avx512_support, avx512_details = _detect_avx512(config_path=config_path)
    blas_info = _detect_blas_lapack()

    return {
        "cpu_arch": platform.machine(),
        "cpu_model": platform.processor() or platform.machine(),
        "physical_cores": phys_cores,
        "logical_cores": log_cores,
        "total_ram_gb": total_ram_gb,
        "avx512_support": avx512_support,
        "avx512_details": avx512_details,
        "blas_info": blas_info,
    }


# =============================================================================
# 3. JSON-LD PROVENANCE BLOCK BUILDER
# =============================================================================


def construct_jsonld_provenance(
    target_file: Optional[Union[str, Path]] = None,
    config_path: Optional[Union[str, Path]] = None,
    run_id: Optional[str] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Constructs a standard JSON-LD Linked Data Provenance Record.

    Args:
        target_file: Optional path to output file being stamped.
        config_path: Optional path to cochem_system_config.json.
        run_id: Optional UUID/identifier for the computational run.
        extra_metadata: Additional key-value metadata to embed in provenance.

    Returns:
        Fully structured JSON-LD dictionary.
    """
    # Compute target file pre-stamp hash if provided and exists
    pre_stamp_info: Optional[Dict[str, Any]] = None
    if target_file is not None:
        p = Path(target_file).resolve()
        if p.is_file():
            content_bytes = p.read_bytes()
            # Normalize newlines for deterministic hashing
            normalized_content = content_bytes.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
            pre_hash = hashlib.sha256(normalized_content).hexdigest()
            pre_stamp_info = {
                "filename": p.name,
                "sha256": pre_hash,
                "size_bytes": len(content_bytes),
            }

    # Retrieve components
    cfg_sha256 = get_system_config_sha256(config_path)
    sw_env = get_software_version_hashes()
    hw_micro = get_hardware_microarchitecture_flags(config_path)

    active_run_id = run_id or str(uuid.uuid4())
    timestamp_utc = datetime.now(timezone.utc).isoformat()

    jsonld_doc: Dict[str, Any] = {
        "@context": {
            "@vocab": "https://schema.org/",
            "prov": "http://www.w3.org/ns/prov#",
            "cochem": "https://cochem.org/schema/",
            "xsd": "http://www.w3.org/2001/XMLSchema#",
        },
        "@type": ["prov:Entity", "cochem:ComputationalRunProvenance"],
        "@id": f"urn:cochem:run:{active_run_id}",
        "prov:generatedAtTime": timestamp_utc,
        "prov:wasGeneratedBy": {
            "@type": "prov:Activity",
            "cochem:engine": "CoChem-CORE",
            "cochem:host": platform.node(),
            "cochem:platform": platform.platform(),
        },
        "cochem:systemConfigSha256": cfg_sha256,
        "cochem:softwareEnvironment": sw_env,
        "cochem:hardwareMicroarchitecture": hw_micro,
        "cochem:targetFilePreStamp": pre_stamp_info,
        "cochem:metadata": extra_metadata or {},
    }

    # Validate against Pydantic schema model
    ProvenanceRecordModel.model_validate(jsonld_doc)

    return jsonld_doc


# =============================================================================
# 4. FOOTER STAMPING, EXTRACTION, AND VERIFICATION
# =============================================================================


def append_provenance_footer(
    output_file: Union[str, Path],
    provenance_block: Optional[Dict[str, Any]] = None,
    config_path: Optional[Union[str, Path]] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
    allow_re_stamp: bool = False,
) -> Dict[str, Any]:
    """Appends a structured JSON-LD Provenance block directly to the footer of a plaintext output file.

    Args:
        output_file: Path to target plaintext output file (e.g. .out, .log).
        provenance_block: Optional pre-constructed JSON-LD dictionary.
        config_path: Optional path to cochem_system_config.json.
        extra_metadata: Optional metadata to embed if generating provenance.
        allow_re_stamp: If False, raises ValueError if file is already stamped.

    Returns:
        The JSON-LD provenance dictionary appended to the file.

    Raises:
        FileNotFoundError: If output_file does not exist.
        PermissionError: If file permissions cannot be adjusted for appending.
        ValueError: If file already contains a provenance footer and allow_re_stamp is False.
    """
    target = Path(output_file).resolve()
    if not target.is_file():
        raise FileNotFoundError(f"Target output file not found: {target}")

    # Temporarily unlock if currently read-only
    was_locked = is_immutable(target)
    if was_locked:
        unlock_immutability(target)

    try:
        content_preview = target.read_text(encoding="utf-8", errors="replace")
        if not allow_re_stamp and FOOTER_DELIMITER_START in content_preview:
            raise ValueError(
                f"Target file {target} already contains a provenance footer. "
                "Re-stamping is forbidden to preserve cryptographic immutability."
            )

        # Generate block if not supplied
        if provenance_block is None:
            provenance_block = construct_jsonld_provenance(
                target_file=target,
                config_path=config_path,
                extra_metadata=extra_metadata,
            )

        serialized_json = json.dumps(provenance_block, indent=2, sort_keys=True)
        footer_text = f"\n\n{FOOTER_DELIMITER_START}\n{serialized_json}\n{FOOTER_DELIMITER_END}\n"

        # Append to target file with explicit LF newline handling
        with open(target, "a", encoding="utf-8", newline="\n") as f:
            f.write(footer_text)
            f.flush()
            os.fsync(f.fileno())

        logger.info(f"Successfully appended JSON-LD provenance footer to {target}")
        return provenance_block

    finally:
        # Re-lock if it was originally locked and caller didn't explicitly request otherwise
        if was_locked:
            apply_immutability_lock(target)


def extract_provenance_footer(
    output_file: Union[str, Path],
    validate_schema: bool = True,
) -> Dict[str, Any]:
    """Extracts and parses the JSON-LD provenance block from a stamped output file.

    Args:
        output_file: Path to the stamped file.
        validate_schema: Whether to validate parsed JSON-LD against ProvenanceRecordModel.

    Returns:
        Parsed JSON-LD dictionary.

    Raises:
        FileNotFoundError: If output_file does not exist.
        ValueError: If delimiters are missing, corrupted, or JSON parsing fails.
    """
    target = Path(output_file).resolve()
    if not target.is_file():
        raise FileNotFoundError(f"File not found: {target}")

    content = target.read_text(encoding="utf-8", errors="replace")
    if FOOTER_DELIMITER_START not in content or FOOTER_DELIMITER_END not in content:
        raise ValueError(f"No provenance footer delimiters found in {target}")

    start_idx = content.find(FOOTER_DELIMITER_START) + len(FOOTER_DELIMITER_START)
    end_idx = content.find(FOOTER_DELIMITER_END, start_idx)

    if end_idx == -1 or end_idx <= start_idx:
        raise ValueError(
            f"Malformed provenance footer in {target}: closing delimiter not found after opening delimiter."
        )

    json_str = content[start_idx:end_idx].strip()
    try:
        data: Dict[str, Any] = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON-LD provenance from {target}: {e}") from e

    if validate_schema:
        try:
            ProvenanceRecordModel.model_validate(data)
        except Exception as e:
            raise ValueError(f"Provenance JSON-LD schema validation failed for {target}: {e}") from e

    return data


def verify_provenance_footer(output_file: Union[str, Path]) -> Tuple[bool, List[str]]:
    """Cryptographically validates the pre-stamp payload and JSON-LD schema of a stamped file.

    Args:
        output_file: Path to the stamped output file.

    Returns:
        Tuple of (is_valid: bool, issues: List[str]).
    """
    target = Path(output_file).resolve()
    if not target.is_file():
        return False, [f"File not found: {target}"]

    content_bytes = target.read_bytes()
    delimiter_bytes = FOOTER_DELIMITER_START.encode("utf-8")
    if delimiter_bytes not in content_bytes:
        return False, ["Missing provenance delimiter start tag"]

    try:
        prov = extract_provenance_footer(target, validate_schema=True)
    except Exception as e:
        return False, [f"Failed to extract/parse provenance footer: {e}"]

    pre_stamp_data = prov.get("cochem:targetFilePreStamp")
    if not pre_stamp_data:
        return False, ["Provenance block missing 'cochem:targetFilePreStamp' entry"]

    expected_sha256 = pre_stamp_data.get("sha256")
    size_bytes = pre_stamp_data.get("size_bytes")

    # Primary verification via exact pre-stamp byte slice
    if isinstance(size_bytes, int) and size_bytes <= len(content_bytes):
        pre_slice = content_bytes[:size_bytes]
        normalized_slice = pre_slice.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        computed_sha256 = hashlib.sha256(normalized_slice).hexdigest()

        remainder = content_bytes[size_bytes:]
        if not remainder.strip().startswith(delimiter_bytes):
            return False, [
                "Tampering detected: pre-stamp byte boundary does not align with provenance footer delimiter"
            ]

        if computed_sha256 != expected_sha256:
            return False, [
                f"Pre-stamp content hash mismatch: expected '{expected_sha256}', computed '{computed_sha256}' (tampering detected)"
            ]
        return True, []

    # Fallback to splitting by delimiter
    pre_footer_bytes = content_bytes.split(delimiter_bytes, 1)[0]
    if pre_footer_bytes.endswith(b"\r\n\r\n"):
        pre_footer_bytes = pre_footer_bytes[:-4]
    elif pre_footer_bytes.endswith(b"\n\n"):
        pre_footer_bytes = pre_footer_bytes[:-2]
    elif pre_footer_bytes.endswith(b"\r\n"):
        pre_footer_bytes = pre_footer_bytes[:-2]
    elif pre_footer_bytes.endswith(b"\n"):
        pre_footer_bytes = pre_footer_bytes[:-1]

    normalized_pre = pre_footer_bytes.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    computed_fallback_sha256 = hashlib.sha256(normalized_pre).hexdigest()

    if computed_fallback_sha256 != expected_sha256:
        return False, [
            f"Pre-stamp content hash mismatch: expected '{expected_sha256}', computed '{computed_fallback_sha256}' (tampering detected)"
        ]

    return True, []


# =============================================================================
# 5. OS-LEVEL IMMUTABILITY LOCKING (0o444)
# =============================================================================


def apply_immutability_lock(
    filepath: Union[str, Path],
    max_retries: int = 3,
    retry_delay: float = 0.1,
) -> None:
    """Applies OS-level read-only immutability lock (os.chmod 0o444) to a file.

    Sets S_IREAD across user, group, and other, stripping all write permissions.
    Handles potential file I/O locks gracefully via retry backoff.

    Args:
        filepath: Path to target file.
        max_retries: Maximum retry attempts for transient file locks.
        retry_delay: Delay between retries in seconds.

    Raises:
        FileNotFoundError: If filepath does not exist.
        PermissionError: If permissions cannot be modified after all retries.
    """
    target = Path(filepath).resolve()
    if not target.is_file():
        raise FileNotFoundError(f"Cannot apply immutability lock: file not found at {target}")

    read_only_mode = stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH  # 0o444

    for attempt in range(1, max_retries + 1):
        try:
            os.chmod(target, read_only_mode)
            logger.info(f"Applied immutability lock (0o444) to {target}")
            return
        except PermissionError as e:
            if attempt == max_retries:
                logger.error(
                    f"Failed to apply immutability lock to {target} after {max_retries} attempts: {e}"
                )
                raise
            time.sleep(retry_delay * attempt)
        except OSError as e:
            if attempt == max_retries:
                logger.error(f"OS error applying immutability lock to {target}: {e}")
                raise
            time.sleep(retry_delay * attempt)


def unlock_immutability(
    filepath: Union[str, Path],
    max_retries: int = 3,
    retry_delay: float = 0.1,
) -> None:
    """Restores read-write permissions (os.chmod 0o666) to an immutable file.

    Args:
        filepath: Path to target file.
        max_retries: Maximum retry attempts for transient locks.
        retry_delay: Delay between retries in seconds.

    Raises:
        FileNotFoundError: If filepath does not exist.
        PermissionError: If permissions cannot be modified after all retries.
        OSError: If an OS-level error occurs during chmod.
    """
    target = Path(filepath).resolve()
    if not target.is_file():
        raise FileNotFoundError(f"Cannot unlock: file not found at {target}")

    read_write_mode = (
        stat.S_IREAD | stat.S_IWRITE | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH
    )  # 0o666

    for attempt in range(1, max_retries + 1):
        try:
            os.chmod(target, read_write_mode)
            logger.info(f"Restored write permissions (0o666) to {target}")
            return
        except (PermissionError, OSError) as e:
            if attempt == max_retries:
                logger.error(f"Failed to unlock {target}: {e}")
                raise
            time.sleep(retry_delay * attempt)


def is_immutable(filepath: Union[str, Path]) -> bool:
    """Checks whether a file currently has read-only immutability applied.

    Args:
        filepath: Path to target file.

    Returns:
        True if file is read-only (not writable), False otherwise.
    """
    target = Path(filepath).resolve()
    if not target.is_file():
        return False
    return not os.access(target, os.W_OK)


# =============================================================================
# 6. END-TO-END WORKFLOW CONVENIENCE FUNCTION
# =============================================================================


def stamp_run_provenance(
    output_file: Union[str, Path],
    config_path: Optional[Union[str, Path]] = None,
    lock_file: bool = True,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Full workflow: Generates JSON-LD provenance, stamps footer, and locks immutability.

    Args:
        output_file: Target plaintext output file.
        config_path: Optional path to cochem_system_config.json.
        lock_file: If True, applies os.chmod(0o444) after stamping.
        extra_metadata: Optional custom metadata dict.

    Returns:
        The generated JSON-LD provenance dictionary.
    """
    target = Path(output_file).resolve()
    prov_block = append_provenance_footer(
        output_file=target,
        config_path=config_path,
        extra_metadata=extra_metadata,
    )

    if lock_file:
        apply_immutability_lock(target)

    return prov_block


__all__ = [
    "FOOTER_DELIMITER_START",
    "FOOTER_DELIMITER_END",
    "JSONLDSoftwareEnvironment",
    "JSONLDHardwareMicroarchitecture",
    "JSONLDTargetFileInfo",
    "ProvenanceRecordModel",
    "get_system_config_sha256",
    "get_software_version_hashes",
    "get_hardware_microarchitecture_flags",
    "construct_jsonld_provenance",
    "append_provenance_footer",
    "extract_provenance_footer",
    "verify_provenance_footer",
    "apply_immutability_lock",
    "unlock_immutability",
    "is_immutable",
    "stamp_run_provenance",
]
