"""
CoChem-TORQ: Phase 1 Hardware Schema & 5-Whys Gatekeeper
========================================================
Enforces strict Pydantic validation on master system configuration
and produces traceable 5-Whys root cause analysis traces upon failure.

Authoritative Standards:
- Method Matrix: Stage 0.0 Hardware Schema & Golden Registry Validation
- 5 Whys Root Cause Analysis Protocol
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator

from cochem_base.exceptions import ConfigError, ProvenanceErrorCode

logger = logging.getLogger("CoChem-TORQ.Schema")


class TorqSchemaValidationError(ConfigError):
    """Raised when hardware or runtime configuration fails schema validation."""

    def __init__(
        self,
        message: str,
        five_whys_trace: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code=ProvenanceErrorCode.CONFIG_VALIDATION_FAILED,
            details=details,
        )
        self.five_whys_trace = five_whys_trace


class TorqHardwareSchema(BaseModel):
    """
    Master hardware & runtime configuration schema for CoChem-TORQ workflows.
    Enforces strict mathematical bounds on MPI threads, GPU memory, and resolved paths.
    """

    mpi_threads: int = Field(
        default=1,
        ge=1,
        le=1024,
        description="Number of OpenMPI / execution threads allocated (1 <= threads <= 1024)",
    )
    gpu_vram_gb: float = Field(
        default=0.0,
        ge=0.0,
        description="Allocated GPU VRAM in gigabytes (must be >= 0.0)",
    )
    gpu_device_ids: List[int] = Field(
        default_factory=list,
        description="List of CUDA device indices available for MACE / GPU acceleration",
    )
    maxcore_mb: int = Field(
        default=1024,
        ge=256,
        description="Per-core memory ceiling in megabytes for electronic structure packages (>= 256 MB)",
    )
    scratch_dir: Path = Field(
        description="Absolute resolved path to volatile scratch directory",
    )
    artifacts_dir: Path = Field(
        description="Absolute resolved path to long-term artifacts repository",
    )
    torq_lib_dir: Path = Field(
        description="Absolute resolved path to TORQ reference library directory",
    )
    cuda_enabled: bool = Field(
        default=False,
        description="Whether CUDA acceleration is activated for tensor kernels",
    )
    strict_airgap: bool = Field(
        default=True,
        description="Whether to enforce strict air-gap boundary checks between scratch and artifacts",
    )

    model_config = {
        "arbitrary_types_allowed": True,
        "validate_assignment": True,
        "extra": "forbid",
    }

    @field_validator("scratch_dir", "artifacts_dir", "torq_lib_dir", mode="before")
    @classmethod
    def resolve_and_validate_path(cls, v: Any) -> Path:
        if v is None:
            raise ValueError("Path field cannot be None")
        p = Path(v).resolve()
        return p

    @model_validator(mode="after")
    def validate_hardware_consistency(self) -> "TorqHardwareSchema":
        # Check GPU consistency
        if self.cuda_enabled and self.gpu_vram_gb <= 0.0:
            if not self.gpu_device_ids:
                logger.warning(
                    "CUDA enabled but gpu_vram_gb=0.0 and no device IDs specified; fallback expected."
                )

        # Check path separation if airgap is enforced
        if self.strict_airgap:
            if self.scratch_dir == self.artifacts_dir:
                raise ValueError(
                    f"Air-gap violation: scratch_dir ({self.scratch_dir}) and artifacts_dir ({self.artifacts_dir}) must be distinct."
                )
            try:
                self.scratch_dir.relative_to(self.artifacts_dir)
                raise ValueError(
                    f"Air-gap violation: scratch_dir ({self.scratch_dir}) cannot be nested inside artifacts_dir ({self.artifacts_dir})."
                )
            except ValueError as err:
                if "Air-gap violation" in str(err):
                    raise
            try:
                self.artifacts_dir.relative_to(self.scratch_dir)
                raise ValueError(
                    f"Air-gap violation: artifacts_dir ({self.artifacts_dir}) cannot be nested inside scratch_dir ({self.scratch_dir})."
                )
            except ValueError as err:
                if "Air-gap violation" in str(err):
                    raise

        return self


def format_5_whys_error(error: Exception, context: Dict[str, Any]) -> str:
    """
    Constructs a structured 5-Whys Root Cause Trace for configuration and schema failures.
    """
    field_name = context.get("field", "unknown_field")
    invalid_value = context.get("value", "unknown_value")
    rule = context.get("rule", "Schema contract specification")
    origin = context.get("origin", "cochem_system_config.json / runtime input")
    remediation = context.get("remediation", "Correct configuration parameter within valid bounds.")

    trace_lines = [
        "=== 5-WHYS ROOT CAUSE ANALYSIS TRACE ===",
        f"Why 1 (Symptom): Configuration validation failed for field '{field_name}' with error: {error}",
        f"Why 2 (Trigger): Supplied value '{invalid_value}' violated active schema constraint.",
        f"Why 3 (Boundary): Physical / mathematical requirement violated: {rule}.",
        f"Why 4 (Origin): Input source '{origin}' provided inconsistent parameters.",
        f"Why 5 (Architectural Resolution): {remediation}",
        "=========================================",
    ]
    return "\n".join(trace_lines)


def validate_registry_state(
    config_data: Union[str, Path, Dict[str, Any]],
) -> TorqHardwareSchema:
    """
    Validates configuration state against TorqHardwareSchema.
    Accepts JSON file path or dictionary. On error, formats 5-Whys trace and raises TorqSchemaValidationError.
    """
    raw_dict: Dict[str, Any] = {}

    if isinstance(config_data, (str, Path)):
        cfg_path = Path(config_data).resolve()
        if not cfg_path.exists():
            context = {
                "field": "config_path",
                "value": str(cfg_path),
                "rule": "Configuration file must exist on filesystem",
                "origin": "validate_registry_state() file lookup",
                "remediation": f"Ensure configuration file exists at {cfg_path}",
            }
            trace = format_5_whys_error(FileNotFoundError(f"Config not found: {cfg_path}"), context)
            raise TorqSchemaValidationError(
                message=f"Configuration file not found: {cfg_path}",
                five_whys_trace=trace,
                details=context,
            )
        try:
            with open(cfg_path, "r", encoding="utf-8") as fp:
                raw_dict = json.load(fp)
        except json.JSONDecodeError as err:
            context = {
                "field": "json_syntax",
                "value": str(cfg_path),
                "rule": "Configuration must be valid JSON syntax",
                "origin": "validate_registry_state() json parser",
                "remediation": "Fix syntax errors in JSON file",
            }
            trace = format_5_whys_error(err, context)
            raise TorqSchemaValidationError(
                message=f"Invalid JSON in config file {cfg_path}: {err}",
                five_whys_trace=trace,
                details=context,
            ) from err
    elif isinstance(config_data, dict):
        raw_dict = config_data
    else:
        context = {
            "field": "config_data_type",
            "value": str(type(config_data)),
            "rule": "Input must be a valid path (str/Path) or Dict[str, Any]",
            "origin": "validate_registry_state() type check",
            "remediation": "Pass a dictionary or file path to validate_registry_state()",
        }
        trace = format_5_whys_error(TypeError("Unsupported config_data type"), context)
        raise TorqSchemaValidationError(
            message=f"Unsupported configuration type: {type(config_data)}",
            five_whys_trace=trace,
            details=context,
        )

    try:
        schema = TorqHardwareSchema(**raw_dict)
        logger.info(
            "Hardware schema validated successfully: threads=%d, maxcore=%d MB, vram=%.1f GB",
            schema.mpi_threads,
            schema.maxcore_mb,
            schema.gpu_vram_gb,
        )
        return schema
    except Exception as err:
        context = {
            "field": "hardware_schema",
            "value": str(raw_dict),
            "rule": "All fields must conform to TorqHardwareSchema mathematical limits",
            "origin": "Pydantic TorqHardwareSchema.__init__",
            "remediation": "Adjust hardware configuration variables to satisfy limits (threads >= 1, maxcore >= 256, vram >= 0.0)",
        }
        trace = format_5_whys_error(err, context)
        raise TorqSchemaValidationError(
            message=f"TorqHardwareSchema validation failed: {err}",
            five_whys_trace=trace,
            details=context,
        ) from err
