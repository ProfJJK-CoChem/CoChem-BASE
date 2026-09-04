from __future__ import annotations

import os; os.environ["JAX_ENABLE_X64"] = "True"

# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
CoChem-BASE: Dynamic Computational MLFF Fallback Router & Precision Governor
Stage 0 / Method Matrix v4 (§8, §8A, §8B, §8C, §8D) Implementation.

Authoritative Implementation for Graceful Degradation:
1. Dynamic VRAM-Governed MLFF Routing Cascade:
   Polls the Golden Registry ($SCRATCH/CoChem_Artifacts/Registry/cochem_system_config.json,
   $COCHEM_CONFIG, etc.) via Pydantic HardwareSchema.
   Enforces cascade order: MACE-OFF24m -> MACE-ONNX (CPU) -> AIMNet2 -> g-xTB -> xTB2.
2. Anti-Silent Downgrade Guard:
   Prohibits silent Hamiltonian and method downgrades. Emits StrategyPivotException
   (in strict mode) or PivotWarning (in permissive mode), attaches the '[Reduced Fidelity]'
   provenance tag, and streams cryptographically signed structured telemetry events.
3. Precision Downgrade Protocol:
   Guarantees canonical FP64 precision for quantum chemical tensors (JAX_ENABLE_X64=True
   pre-initialization), while providing cpu_mlff_precision_fence() to force FP32 on CPU MLFF
   inference engines, preventing CPU RAM swapping, accelerating inference, and restoring FP64 on exit.
4. Comprehensive Pydantic v2 Models:
   MLFFMethod, PrecisionMode, ExecutionDevice, MLFFRoutingRequest, MLFFRoutingDecision.
5. Zero-Mock validation compliance and real hardware telemetry introspection.
"""

import contextlib
import json
import logging
import platform
from pathlib import Path
import sys
import threading
import uuid
import warnings
from datetime import datetime, timezone
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    Optional,
    Tuple,
    TypeVar,
    Union,
)

import psutil
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

# Safe conditional imports for tensor frameworks
try:
    import torch
    HAS_TORCH = True
except ImportError:
    torch = None  # type: ignore[assignment]
    HAS_TORCH = False

try:
    import jax
    import jax.numpy as jnp
    HAS_JAX = True
except ImportError:
    jax = None  # type: ignore[assignment]
    jnp = None  # type: ignore[assignment]
    HAS_JAX = False

from cochem_base.config_loader import (
    get_artifact_dir,
    get_scratch_dir,
    resolve_config_path,
)
from core_engine.cochem_core_registry_schema import (
    GPUComputeSchema,
    HardwareSchema,
)

try:
    from core_engine.cochem_core_telemetry_logger import (
        RotatingJsonlSink,
        sign_provenance_block,
    )
    HAS_TELEMETRY_LOGGER = True
except ImportError:
    HAS_TELEMETRY_LOGGER = False
    RotatingJsonlSink = None  # type: ignore[assignment,misc]
    sign_provenance_block = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------
logger = logging.getLogger("CoChem-MLFFRouter")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(
        logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s")
    )
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)

T = TypeVar("T")

# =============================================================================
# CONSTANTS AND PROVENANCE TAGS
# =============================================================================

REDUCED_FIDELITY_TAG: str = "[Reduced Fidelity]"
FP64_CANONICAL_TAG: str = "[FP64 Canonical]"
FP32_CPU_FENCED_TAG: str = "[FP32 CPU Fenced]"
PRECISION_DOWNGRADE_TAG: str = "[Precision Downgrade FP32]"
CASCADE_STEPPED_TAG: str = "[Cascade Stepped]"
DEFAULT_MIN_MACE_VRAM_GB: float = 2.0
DEFAULT_MIN_AIMNET_VRAM_GB: float = 1.0


# =============================================================================
# ENUMERATIONS
# =============================================================================

class MLFFMethod(str, Enum):
    """
    Authoritative Machine Learning Force Field (MLFF) and Semi-Empirical
    Methods registered in the CoChem-BASE Method Matrix.
    Cascade Hierarchy: MACE-OFF24m -> MACE-ONNX (CPU) -> AIMNet2 -> g-xTB -> xTB2
    """
    MACE_OFF24M = "MACE-OFF24m"
    MACE_ONNX = "MACE-ONNX (CPU)"
    AIMNET2 = "AIMNet2"
    G_XTB = "g-xTB"
    XTB2 = "xTB2"

    @classmethod
    def from_string(cls, value: Union[str, 'MLFFMethod']) -> 'MLFFMethod':
        """Coerce string or alias to a canonical MLFFMethod enum value."""
        if isinstance(value, MLFFMethod):
            return value
        if not isinstance(value, str):
            raise ValueError(f"Expected string or MLFFMethod, got {type(value)}")

        val = value.strip()
        v_lower = val.lower().replace("_", "-").replace(" ", "")

        # Exact enum string matches
        for member in cls:
            if member.value.lower().replace("_", "-").replace(" ", "") == v_lower:
                return member

        # Alias resolution map
        if v_lower in {"mace", "mace-off24m", "mace-off23", "mace-mp-0", "mace-gpu", "maceoff24m"}:
            return cls.MACE_OFF24M
        if v_lower in {"mace-onnx", "mace-onnx(cpu)", "mace-cpu", "maceonnx", "maceonnxcpu"}:
            return cls.MACE_ONNX
        if v_lower in {"aimnet", "aimnet2", "aim-net2", "aimnet-2"}:
            return cls.AIMNET2
        if v_lower in {"g-xtb", "gxtb", "gfn-xtb-ml", "g_xtb"}:
            return cls.G_XTB
        if v_lower in {"xtb", "xtb2", "gfn2-xtb", "gfn2_xtb", "gfn2", "xtb-2"}:
            return cls.XTB2

        raise ValueError(
            f"Unknown or unregistered MLFFMethod '{value}'. "
            f"Allowed canonical methods: {[m.value for m in cls]}"
        )


class ExecutionDevice(str, Enum):
    """Execution hardware target device."""
    CUDA = "cuda"
    CPU = "cpu"
    MPS = "mps"
    AUTO = "auto"

    @classmethod
    def from_string(cls, value: Union[str, 'ExecutionDevice']) -> 'ExecutionDevice':
        """Coerce string to canonical ExecutionDevice enum value."""
        if isinstance(value, ExecutionDevice):
            return value
        if not isinstance(value, str):
            raise ValueError(f"Expected string or ExecutionDevice, got {type(value)}")

        val = value.strip().lower()
        if val in {"cuda", "gpu", "nvidia", "cuda:0"}:
            return cls.CUDA
        if val in {"cpu", "host"}:
            return cls.CPU
        if val in {"mps", "apple", "metal"}:
            return cls.MPS
        if val in {"auto", "default", "dynamic"}:
            return cls.AUTO

        raise ValueError(
            f"Unknown ExecutionDevice '{value}'. Allowed: {[d.value for d in cls]}"
        )


class PrecisionMode(str, Enum):
    """Floating-point tensor execution precision mode."""
    FP64 = "FP64"
    FP32 = "FP32"
    FP16 = "FP16"
    BF16 = "BF16"
    MIXED = "MIXED"

    @classmethod
    def from_string(cls, value: Union[str, 'PrecisionMode']) -> 'PrecisionMode':
        """Coerce string to canonical PrecisionMode enum value."""
        if isinstance(value, PrecisionMode):
            return value
        if not isinstance(value, str):
            raise ValueError(f"Expected string or PrecisionMode, got {type(value)}")

        val = value.strip().upper()
        if val in {"FP64", "FLOAT64", "DOUBLE"}:
            return cls.FP64
        if val in {"FP32", "FLOAT32", "SINGLE"}:
            return cls.FP32
        if val in {"FP16", "FLOAT16", "HALF"}:
            return cls.FP16
        if val in {"BF16", "BFLOAT16"}:
            return cls.BF16
        if val in {"MIXED", "AUTO_PRECISION"}:
            return cls.MIXED

        raise ValueError(
            f"Unknown PrecisionMode '{value}'. Allowed: {[p.value for p in cls]}"
        )


# Canonical 5-stage fallback cascade order
CASCADE_ORDER: Tuple[MLFFMethod, ...] = (
    MLFFMethod.MACE_OFF24M,
    MLFFMethod.MACE_ONNX,
    MLFFMethod.AIMNET2,
    MLFFMethod.G_XTB,
    MLFFMethod.XTB2,
)


# =============================================================================
# METHOD PROFILES
# =============================================================================

class MLFFMethodProfile(BaseModel):
    """Static metadata and operational requirements for an MLFF method."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    method: MLFFMethod
    requires_gpu: bool
    min_vram_gb: float
    min_ram_gb: float = 2.0
    default_device: ExecutionDevice
    default_precision: PrecisionMode
    fenced_on_cpu: bool
    fidelity_rank: int
    description: str


METHOD_PROFILES: Dict[MLFFMethod, MLFFMethodProfile] = {
    MLFFMethod.MACE_OFF24M: MLFFMethodProfile(
        method=MLFFMethod.MACE_OFF24M,
        requires_gpu=True,
        min_vram_gb=DEFAULT_MIN_MACE_VRAM_GB,
        min_ram_gb=4.0,
        default_device=ExecutionDevice.CUDA,
        default_precision=PrecisionMode.FP32,
        fenced_on_cpu=False,
        fidelity_rank=1,
        description="MACE Foundation Model (MACE-OFF24m) GPU-accelerated higher-fidelity MLFF."
    ),
    MLFFMethod.MACE_ONNX: MLFFMethodProfile(
        method=MLFFMethod.MACE_ONNX,
        requires_gpu=False,
        min_vram_gb=0.0,
        min_ram_gb=2.0,
        default_device=ExecutionDevice.CPU,
        default_precision=PrecisionMode.FP32,
        fenced_on_cpu=True,
        fidelity_rank=2,
        description="MACE-ONNX CPU-optimized execution engine with FP32 precision fence."
    ),
    MLFFMethod.AIMNET2: MLFFMethodProfile(
        method=MLFFMethod.AIMNET2,
        requires_gpu=False,
        min_vram_gb=DEFAULT_MIN_AIMNET_VRAM_GB,
        min_ram_gb=2.0,
        default_device=ExecutionDevice.AUTO,
        default_precision=PrecisionMode.FP32,
        fenced_on_cpu=True,
        fidelity_rank=3,
        description="AIMNet2 Neural Network Potential for organic molecules and conformational sampling."
    ),
    MLFFMethod.G_XTB: MLFFMethodProfile(
        method=MLFFMethod.G_XTB,
        requires_gpu=False,
        min_vram_gb=0.0,
        min_ram_gb=1.0,
        default_device=ExecutionDevice.CPU,
        default_precision=PrecisionMode.FP32,
        fenced_on_cpu=True,
        fidelity_rank=4,
        description="g-xTB semi-empirical tight-binding gradient acceleration layer."
    ),
    MLFFMethod.XTB2: MLFFMethodProfile(
        method=MLFFMethod.XTB2,
        requires_gpu=False,
        min_vram_gb=0.0,
        min_ram_gb=1.0,
        default_device=ExecutionDevice.CPU,
        default_precision=PrecisionMode.FP64,
        fenced_on_cpu=False,
        fidelity_rank=5,
        description="GFN2-xTB semi-empirical quantum mechanical baseline engine."
    ),
}


# =============================================================================
# EXCEPTIONS AND WARNINGS
# =============================================================================

class MLFFRoutingError(Exception):
    """Base exception for all MLFF routing, hardware gating, and precision errors."""
    pass


class StrategyPivotException(MLFFRoutingError):
    """
    Raised when an MLFF Hamiltonian / method downgrade is triggered in strict mode,
    or when no viable method can be resolved in the cascade.
    """
    def __init__(
        self,
        message: str,
        requested_method: Union[str, MLFFMethod],
        fallback_method: Optional[Union[str, MLFFMethod]] = None,
        reason: Optional[str] = None,
        hardware_snapshot: Optional[Dict[str, Any]] = None,
        provenance_tags: Optional[List[str]] = None,
    ) -> None:
        super().__init__(message)
        self.requested_method = str(getattr(requested_method, "value", requested_method))
        self.fallback_method = str(getattr(fallback_method, "value", fallback_method)) if fallback_method is not None else None
        self.reason = reason or message
        self.hardware_snapshot = hardware_snapshot or {}
        self.provenance_tags = provenance_tags or []


class PivotWarning(UserWarning):
    """Warning emitted when an MLFF strategy pivot / Hamiltonian downgrade occurs in permissive mode."""
    pass


# =============================================================================
# PYDANTIC ROUTING MODELS (Pydantic v2)
# =============================================================================

class MLFFRoutingRequest(BaseModel):
    """
    Input request for MLFF method resolution and dynamic fallback routing.
    Strictly forbids extra fields to maintain schema air-gap integrity.
    """
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    requested_method: MLFFMethod = Field(
        default=MLFFMethod.MACE_OFF24M,
        description="Desired MLFF or semi-empirical method."
    )
    requested_device: ExecutionDevice = Field(
        default=ExecutionDevice.AUTO,
        description="Target compute device (auto, cuda, cpu, mps)."
    )
    requested_precision: Optional[PrecisionMode] = Field(
        default=None,
        description="Requested tensor precision mode. If None, resolves to method canonical precision."
    )
    atom_count: Optional[int] = Field(
        default=None,
        ge=1,
        description="Number of atoms in the molecular system (used for VRAM scaling estimation)."
    )
    required_vram_gb: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Explicitly required VRAM in GB. If omitted, estimated dynamically."
    )
    strict: bool = Field(
        default=False,
        description="If True, raises StrategyPivotException on any method or device downgrade."
    )
    allow_downgrade: bool = Field(
        default=True,
        description="If True, allows stepping down the cascade when hardware constraints fail."
    )
    hardware_override: Optional[HardwareSchema] = Field(
        default=None,
        description="Explicit HardwareSchema override for deterministic testing and dry runs."
    )
    config_path: Optional[Union[str, Path]] = Field(
        default=None,
        description="Explicit path to cochem_system_config.json registry file."
    )
    provenance_tags: List[str] = Field(
        default_factory=list,
        description="User-supplied provenance tags to append to the calculation trace."
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional contextual metadata (job_id, molecule_name, etc.)."
    )

    @field_validator("requested_method", mode="before")
    @classmethod
    def _validate_requested_method(cls, v: Any) -> MLFFMethod:
        return MLFFMethod.from_string(v)

    @field_validator("requested_device", mode="before")
    @classmethod
    def _validate_requested_device(cls, v: Any) -> ExecutionDevice:
        return ExecutionDevice.from_string(v)

    @field_validator("requested_precision", mode="before")
    @classmethod
    def _validate_requested_precision(cls, v: Any) -> Optional[PrecisionMode]:
        if v is None:
            return None
        return PrecisionMode.from_string(v)

    @field_validator("config_path", mode="before")
    @classmethod
    def _validate_config_path(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        return str(Path(str(v)).resolve())


class MLFFRoutingDecision(BaseModel):
    """
    Resulting decision payload produced by the MLFF Fallback Router.
    Contains the authoritative execution contract, active precision, and provenance trace.
    """
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    requested_method: MLFFMethod = Field(..., description="Originally requested MLFF method.")
    selected_method: MLFFMethod = Field(..., description="Authoritatively selected method for execution.")
    execution_device: ExecutionDevice = Field(..., description="Target device assigned for execution.")
    precision_mode: PrecisionMode = Field(..., description="Tensor precision assigned for execution.")
    is_pivoted: bool = Field(..., description="True if a method or hardware downgrade occurred.")
    pivot_reason: Optional[str] = Field(default=None, description="Detailed diagnostic reason for pivot.")
    cascade_trace: List[MLFFMethod] = Field(
        default_factory=list,
        description="Full cascade trace of evaluated methods during routing."
    )
    provenance_tags: List[str] = Field(
        default_factory=list,
        description="Complete list of provenance tags attached to this routing decision."
    )
    hardware_snapshot: Dict[str, Any] = Field(
        default_factory=dict,
        description="Snapshot of the hardware profile used during routing decision."
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="UTC ISO 8601 timestamp of routing decision."
    )
    telemetry_event_id: Optional[str] = Field(
        default=None,
        description="Unique ID of the structured telemetry event emitted for this pivot."
    )
    fenced_execution: bool = Field(
        default=False,
        description="True if execution must be wrapped in cpu_mlff_precision_fence()."
    )


# =============================================================================
# PRECISION DOWNGRADE FENCE CONTEXT MANAGER
# =============================================================================

@contextlib.contextmanager
def cpu_mlff_precision_fence(
    target_precision: Union[PrecisionMode, str] = PrecisionMode.FP32
) -> Iterator[PrecisionMode]:
    """
    Precision Downgrade Fence Context Manager.

    Forces CPU MLFF inference operations into FP32 (or specified target_precision)
    to prevent CPU RAM swapping and accelerate inference times, while guaranteeing
    strict restoration of FP64 / previous default precision on context exit.

    Usage:
        with cpu_mlff_precision_fence():
            # CPU MLFF inference runs in FP32
            output = model(inputs)
        # FP64 precision is restored for PySCF / quantum tensors
    """
    target_mode = PrecisionMode.from_string(target_precision)
    prev_torch_dtype = None

    if HAS_TORCH and torch is not None:
        try:
            prev_torch_dtype = torch.get_default_dtype()
            if target_mode in (PrecisionMode.FP32, PrecisionMode.MIXED):
                torch.set_default_dtype(torch.float32)
            elif target_mode == PrecisionMode.FP64:
                torch.set_default_dtype(torch.float64)
            elif target_mode == PrecisionMode.FP16:
                torch.set_default_dtype(torch.float16)
            elif target_mode == PrecisionMode.BF16 and hasattr(torch, "bfloat16"):
                torch.set_default_dtype(torch.bfloat16)
        except Exception as exc:
            logger.warning(f"Precision fence could not set torch default dtype: {exc}")

    try:
        yield target_mode
    finally:
        if HAS_TORCH and torch is not None and prev_torch_dtype is not None:
            try:
                torch.set_default_dtype(prev_torch_dtype)
            except Exception as exc:
                logger.warning(f"Precision fence failed to restore torch default dtype: {exc}")


def execute_fenced_mlff(
    func: Callable[..., T],
    *args: Any,
    target_precision: Union[PrecisionMode, str] = PrecisionMode.FP32,
    **kwargs: Any,
) -> T:
    """
    Executes a callable inside the CPU MLFF precision fence, ensuring clean
    entry and exit precision transitions.
    """
    with cpu_mlff_precision_fence(target_precision):
        return func(*args, **kwargs)


# =============================================================================
# REGISTRY POLLING & HARDWARE RESOLUTION
# =============================================================================

def resolve_golden_registry_path(
    explicit_path: Optional[Union[str, Path]] = None,
    scratch_dir: Optional[Union[str, Path]] = None,
) -> Optional[Path]:
    """
    Resolves the authoritative Golden Registry path following the 5-tier discovery hierarchy:
    1. Explicit path parameter.
    2. $SCRATCH/CoChem_Artifacts/Registry/cochem_system_config.json or $COCHEM_SCRATCH/...
    3. $COCHEM_CONFIG environment variable.
    4. $COCHEM_ARTIFACT_DIR/Registry/cochem_system_config.json or $COCHEM_ARTIFACT_DIR/cochem_system_config.json.
    5. Standard config loader discovery hierarchy via resolve_config_path().
    """
    if explicit_path is not None:
        p = Path(os.path.expandvars(str(explicit_path))).expanduser().resolve()
        if p.exists():
            return p

    # Tier 2: Scratch Registry
    candidate_scratches = []
    if scratch_dir is not None:
        candidate_scratches.append(Path(scratch_dir))
    env_scratch = os.environ.get("SCRATCH") or os.environ.get("COCHEM_SCRATCH") or os.environ.get("COCHEM_SCRATCH_DIR")
    if env_scratch:
        candidate_scratches.append(Path(os.path.expandvars(env_scratch)).expanduser())
    try:
        candidate_scratches.append(get_scratch_dir())
    except Exception as _e:
        logger.debug(f"Ignored exception: {_e}")

    for s_dir in candidate_scratches:
        candidates = [
            s_dir / "CoChem_Artifacts" / "Registry" / "cochem_system_config.json",
            s_dir / "Registry" / "cochem_system_config.json",
            s_dir / "cochem_system_config.json",
        ]
        for cand in candidates:
            if cand.exists():
                return cand.resolve()

    # Tier 3: COCHEM_CONFIG environment variable
    env_cfg = os.environ.get("COCHEM_CONFIG")
    if env_cfg:
        p = Path(os.path.expandvars(env_cfg)).expanduser().resolve()
        if p.exists():
            return p

    # Tier 4: Artifact directory registry
    try:
        art_dir = get_artifact_dir()
        candidates = [
            art_dir / "Registry" / "cochem_system_config.json",
            art_dir / "cochem_system_config.json",
        ]
        for cand in candidates:
            if cand.exists():
                return cand.resolve()
    except Exception as _e:
        logger.debug(f"Ignored exception: {_e}")

    # Tier 5: Standard config loader resolution
    try:
        resolved = resolve_config_path()
        if resolved.exists():
            return resolved
    except Exception as _e:
        logger.debug(f"Ignored exception: {_e}")

    return None


def probe_live_hardware() -> HardwareSchema:
    """
    Performs real, zero-mock physical hardware introspection of CPU, RAM, and GPU resources.
    Returns a Pydantic HardwareSchema instance.
    """
    # 1. CPU & RAM Discovery
    try:
        total_ram_gb = round(psutil.virtual_memory().total / (1024**3), 2)
        phys_cores = psutil.cpu_count(logical=False) or os.cpu_count() or 1
        log_cores = psutil.cpu_count(logical=True) or os.cpu_count() or 1
    except Exception:
        total_ram_gb = 16.0
        phys_cores = os.cpu_count() or 1
        log_cores = os.cpu_count() or 1

    # 2. GPU Discovery via PyTorch (if available)
    vram_gb: float = 0.0
    device_count: int = 0
    gpu_profile: str = "None"
    compute_cap: Optional[str] = None
    fp64_capable: bool = False

    if HAS_TORCH and torch is not None:
        try:
            if torch.cuda.is_available():
                device_count = torch.cuda.device_count()
                if device_count > 0:
                    gpu_profile = torch.cuda.get_device_name(0)
                    props = torch.cuda.get_device_properties(0)
                    vram_gb = round(props.total_memory / (1024**3), 2)
                    compute_cap = f"{props.major}.{props.minor}"
                    fp64_capable = True
        except Exception as exc:
            logger.debug(f"Live CUDA hardware probe encountered non-fatal error: {exc}")

    # OS Target
    sys_name = platform.system().lower()
    if "windows" in sys_name:
        os_target = "Local-Windows"
    elif "darwin" in sys_name:
        os_target = "Local-MacOS"
    else:
        os_target = "Local-Linux"

    gpu_metrics = GPUComputeSchema(
        gpu_profile=gpu_profile,
        vram_gb=vram_gb,
        device_count=device_count,
        compute_capability=compute_cap,
        fp64_capable=fp64_capable,
        mps_enabled=False,
    )

    return HardwareSchema(
        ram_gb=total_ram_gb,
        cpu_physical_cores=phys_cores,
        physical_cpu_cores=phys_cores,
        logical_cpu_cores=log_cores,
        allocatable_compute_cores=phys_cores,
        vram_gb=vram_gb,
        gpu_compute_metrics=gpu_metrics,
        gpu_fp64_capable=fp64_capable,
        mps_enabled=False,
        avx_512_capable=False,
        gpu_profile=gpu_profile,
        os_target=os_target,
    )


def poll_hardware_registry(
    config_path: Optional[Union[str, Path]] = None,
    scratch_dir: Optional[Union[str, Path]] = None,
) -> HardwareSchema:
    """
    Polls the Golden Registry to retrieve the validated HardwareSchema.
    If the registry file does not exist or fails parsing, transparently falls back
    to live host hardware introspection.
    """
    resolved_path = resolve_golden_registry_path(config_path, scratch_dir=scratch_dir)
    if resolved_path is not None and resolved_path.exists():
        try:
            with open(resolved_path, "r", encoding="utf-8") as f:
                raw_json = json.loads(f.read())

            # Check nested system config structure
            if "hardware" in raw_json and isinstance(raw_json["hardware"], dict):
                return HardwareSchema.model_validate(raw_json["hardware"])
            return HardwareSchema.model_validate(raw_json)
        except Exception as exc:
            logger.warning(
                f"Failed to load hardware configuration from registry at '{resolved_path}': {exc}. "
                "Falling back to live physical hardware discovery."
            )

    return probe_live_hardware()


# =============================================================================
# TELEMETRY EVENT STREAMING
# =============================================================================

def emit_mlff_pivot_telemetry(
    decision: MLFFRoutingDecision,
    telemetry_log_path: Optional[Union[str, Path]] = None,
    secret_key: Optional[Union[str, bytes]] = None,
) -> Dict[str, Any]:
    """
    Constructs and records a cryptographically signed, structured JSON-LD telemetry event
    recording the MLFF strategy pivot and provenance metadata.
    """
    event_id = decision.telemetry_event_id or f"mlff-pivot-{uuid.uuid4().hex[:12]}"
    now_utc = datetime.now(timezone.utc).isoformat()

    event_payload: Dict[str, Any] = {
        "@context": "https://w3id.org/ro/qcschema",
        "@type": "MLFFRoutingPivotEvent",
        "event_id": event_id,
        "timestamp": now_utc,
        "requested_method": decision.requested_method.value,
        "selected_method": decision.selected_method.value,
        "execution_device": decision.execution_device.value,
        "precision_mode": decision.precision_mode.value,
        "is_pivoted": decision.is_pivoted,
        "pivot_reason": decision.pivot_reason,
        "cascade_trace": [m.value for m in decision.cascade_trace],
        "provenance_tags": list(decision.provenance_tags),
        "fenced_execution": decision.fenced_execution,
        "hardware_snapshot": decision.hardware_snapshot,
    }

    # Resolve log path
    target_log_path: Optional[Path] = None
    if telemetry_log_path is not None:
        target_log_path = Path(telemetry_log_path).resolve()
    else:
        try:
            art_dir = get_artifact_dir()
            target_log_path = art_dir / "Logs" / "cochem_telemetry_stream.jsonl"
        except Exception:
            target_log_path = Path("Logs") / "cochem_telemetry_stream.jsonl"

    try:
        target_log_path.parent.mkdir(parents=True, exist_ok=True)
        if HAS_TELEMETRY_LOGGER and RotatingJsonlSink is not None:
            sink = RotatingJsonlSink(target_log_path, secret_key=secret_key)
            signed_entry = sink.write_entry(event_payload, sign=True)
            sink.close()
            return signed_entry
        else:
            with open(target_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event_payload, ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.debug(f"Non-fatal error writing MLFF pivot telemetry log: {exc}")

    return event_payload


# =============================================================================
# MLFF ROUTER ENGINE
# =============================================================================

class MLFFRouter:
    """
    Authoritative Dynamic Computational MLFF Fallback Router for CoChem-BASE.

    Responsibilities:
    1. Polling Golden Registry for hardware boundaries (RAM, VRAM, GPU presence).
    2. Dynamic VRAM estimation and capability verification.
    3. Cascade evaluation: MACE-OFF24m -> MACE-ONNX (CPU) -> AIMNet2 -> g-xTB -> xTB2.
    4. Anti-Silent Downgrade Guard: StrategyPivotException (strict) or PivotWarning (permissive)
       with [Reduced Fidelity] provenance tagging.
    5. CPU MLFF precision downgrade fencing to FP32, preserving canonical FP64 on exit.
    """

    def __init__(
        self,
        default_config_path: Optional[Union[str, Path]] = None,
        telemetry_log_path: Optional[Union[str, Path]] = None,
    ) -> None:
        self.default_config_path = default_config_path
        self.telemetry_log_path = telemetry_log_path

    def poll_hardware(self, custom_path: Optional[Union[str, Path]] = None) -> HardwareSchema:
        """Polls the Golden Registry or live hardware."""
        path = custom_path or self.default_config_path
        return poll_hardware_registry(config_path=path)

    def estimate_required_vram(
        self,
        method: MLFFMethod,
        atom_count: Optional[int] = None,
    ) -> float:
        """
        Dynamically estimates required VRAM (in GB) based on method and molecular size.
        """
        profile = METHOD_PROFILES[method]
        base_vram = profile.min_vram_gb

        if not profile.requires_gpu:
            return 0.0

        if atom_count is None or atom_count <= 0:
            return base_vram

        # Empirical quadratic/linear scaling buffer: base + (atoms * per_atom_mb)
        # e.g. MACE: 2.0 GB base + ~10 MB per atom for high angular momentum representations
        scaling_gb = (atom_count * 0.010)
        return round(base_vram + scaling_gb, 2)

    def evaluate_method_viability(
        self,
        candidate_method: MLFFMethod,
        requested_device: ExecutionDevice,
        hardware: HardwareSchema,
        required_vram_gb: float,
    ) -> Tuple[bool, Optional[str], ExecutionDevice]:
        """
        Evaluates whether candidate_method can execute on the detected hardware.
        Returns: (is_viable, rejection_reason, assigned_device)
        """
        profile = METHOD_PROFILES[candidate_method]

        # Extract hardware parameters
        detected_vram = hardware.vram_gb
        device_count = hardware.gpu_compute_metrics.device_count if hardware.gpu_compute_metrics else 0
        has_cuda = (device_count > 0 and detected_vram > 0.0) or (
            HAS_TORCH and torch is not None and torch.cuda.is_available() and detected_vram > 0.0
        )

        # 1. Check GPU-Bound Methods (e.g. MACE-OFF24m)
        if profile.requires_gpu:
            if requested_device == ExecutionDevice.CPU:
                return False, f"Method '{candidate_method.value}' is GPU-bound but CPU device was explicitly requested.", ExecutionDevice.CPU

            if not has_cuda or detected_vram <= 0.0:
                return False, (
                    f"Method '{candidate_method.value}' requires CUDA GPU with VRAM >= {profile.min_vram_gb} GB, "
                    f"but detected VRAM is {detected_vram} GB (CUDA unavailable or no devices)."
                ), ExecutionDevice.CUDA

            if detected_vram < required_vram_gb:
                return False, (
                    f"Method '{candidate_method.value}' requires {required_vram_gb} GB VRAM for this molecular system, "
                    f"but detected device only provides {detected_vram} GB VRAM."
                ), ExecutionDevice.CUDA

            return True, None, ExecutionDevice.CUDA

        # 2. Check Flexible or CPU-bound methods (MACE-ONNX, AIMNet2, g-xTB, xTB2)
        if candidate_method == MLFFMethod.AIMNET2:
            # AIMNet2 can run on GPU if requested & available, or CPU
            if requested_device in (ExecutionDevice.CUDA, ExecutionDevice.AUTO) and has_cuda and detected_vram >= profile.min_vram_gb:
                return True, None, ExecutionDevice.CUDA
            return True, None, ExecutionDevice.CPU

        # MACE-ONNX, g-xTB, xTB2
        return True, None, ExecutionDevice.CPU

    def route(
        self,
        request: Union[MLFFRoutingRequest, Dict[str, Any]],
    ) -> MLFFRoutingDecision:
        """
        Authoritative routing entry point. Evaluates request against Golden Registry hardware
        and executes the Graceful Degradation Cascade when constraints trigger a pivot.
        """
        # 1. Normalize and validate input request
        if isinstance(request, dict):
            req_model = MLFFRoutingRequest.model_validate(request)
        elif isinstance(request, MLFFRoutingRequest):
            req_model = request
        else:
            raise TypeError(f"Expected MLFFRoutingRequest or dict, got {type(request)}")

        # 2. Hardware resolution
        hardware = req_model.hardware_override or self.poll_hardware(req_model.config_path)

        # 3. Calculate VRAM requirement
        required_vram = (
            req_model.required_vram_gb
            if req_model.required_vram_gb is not None
            else self.estimate_required_vram(req_model.requested_method, req_model.atom_count)
        )

        cascade_trace: List[MLFFMethod] = []
        provenance_tags: List[str] = list(req_model.provenance_tags)
        selected_method: Optional[MLFFMethod] = None
        selected_device: Optional[ExecutionDevice] = None
        primary_rejection_reason: Optional[str] = None
        pivot_reason: Optional[str] = None
        is_pivoted: bool = False

        # Find starting index in CASCADE_ORDER
        try:
            start_idx = CASCADE_ORDER.index(req_model.requested_method)
        except ValueError:
            start_idx = 0

        # If downgrading is disabled, only evaluate the requested method
        candidates = CASCADE_ORDER[start_idx:] if req_model.allow_downgrade else (req_model.requested_method,)

        for candidate in candidates:
            cascade_trace.append(candidate)
            viable, rejection_msg, assigned_dev = self.evaluate_method_viability(
                candidate_method=candidate,
                requested_device=req_model.requested_device,
                hardware=hardware,
                required_vram_gb=required_vram,
            )

            if viable:
                selected_method = candidate
                selected_device = assigned_dev
                if candidate != req_model.requested_method:
                    is_pivoted = True
                    pivot_reason = primary_rejection_reason or rejection_msg or (
                        f"Hardware constraints triggered pivot from requested method "
                        f"'{req_model.requested_method.value}' to fallback '{candidate.value}'."
                    )
                elif req_model.requested_device == ExecutionDevice.CUDA and assigned_dev == ExecutionDevice.CPU:
                    is_pivoted = True
                    pivot_reason = (
                        f"Requested CUDA execution for '{req_model.requested_method.value}', "
                        f"but GPU is unavailable or has 0.0 GB VRAM. Routed to CPU."
                    )
                break
            else:
                if candidate == req_model.requested_method and not primary_rejection_reason:
                    primary_rejection_reason = rejection_msg

        # If no viable method could be found in cascade
        if selected_method is None or selected_device is None:
            exhaust_reason = pivot_reason or primary_rejection_reason or "All candidate methods failed hardware verification."
            err_msg = (
                f"MLFF Fallback Cascade Exhausted: No viable method found for request "
                f"'{req_model.requested_method.value}'. Reason: {exhaust_reason}"
            )
            hardware_snap = hardware.model_dump()
            raise StrategyPivotException(
                message=err_msg,
                requested_method=req_model.requested_method,
                fallback_method=None,
                reason=exhaust_reason,
                hardware_snapshot=hardware_snap,
                provenance_tags=provenance_tags,
            )

        # 4. Precision Resolution
        selected_profile = METHOD_PROFILES[selected_method]
        fenced_execution = (selected_device == ExecutionDevice.CPU and selected_profile.fenced_on_cpu)

        if req_model.requested_precision is not None:
            active_precision = req_model.requested_precision
        elif fenced_execution:
            active_precision = PrecisionMode.FP32
        else:
            active_precision = selected_profile.default_precision

        # 5. Provenance Tag Management
        if is_pivoted:
            if REDUCED_FIDELITY_TAG not in provenance_tags:
                provenance_tags.append(REDUCED_FIDELITY_TAG)
            if CASCADE_STEPPED_TAG not in provenance_tags:
                provenance_tags.append(CASCADE_STEPPED_TAG)

        if fenced_execution:
            if FP32_CPU_FENCED_TAG not in provenance_tags:
                provenance_tags.append(FP32_CPU_FENCED_TAG)
        elif active_precision == PrecisionMode.FP64:
            if FP64_CANONICAL_TAG not in provenance_tags:
                provenance_tags.append(FP64_CANONICAL_TAG)

        hardware_snapshot = hardware.model_dump()

        # 6. Anti-Silent Downgrade Guard Handling
        telemetry_event_id: Optional[str] = None
        if is_pivoted:
            telemetry_event_id = f"mlff-pivot-{uuid.uuid4().hex[:12]}"
            if req_model.strict:
                pivot_err = (
                    f"Strict MLFF Strategy Pivot Trap: Requested method '{req_model.requested_method.value}' "
                    f"failed hardware verification. Downgrade to '{selected_method.value}' prohibited by strict=True. "
                    f"Reason: {pivot_reason}"
                )
                raise StrategyPivotException(
                    message=pivot_err,
                    requested_method=req_model.requested_method,
                    fallback_method=selected_method,
                    reason=pivot_reason or pivot_err,
                    hardware_snapshot=hardware_snapshot,
                    provenance_tags=provenance_tags,
                )
            else:
                # Emit formal warning in permissive mode
                warning_msg = (
                    f"CoChem MLFF Router Strategy Pivot: Requested '{req_model.requested_method.value}' -> "
                    f"Fell back to '{selected_method.value}' on {selected_device.value.upper()} ({active_precision.value}). "
                    f"Reason: {pivot_reason}"
                )
                warnings.warn(warning_msg, PivotWarning, stacklevel=2)
                logger.warning(warning_msg)

        decision = MLFFRoutingDecision(
            requested_method=req_model.requested_method,
            selected_method=selected_method,
            execution_device=selected_device,
            precision_mode=active_precision,
            is_pivoted=is_pivoted,
            pivot_reason=pivot_reason,
            cascade_trace=cascade_trace,
            provenance_tags=provenance_tags,
            hardware_snapshot=hardware_snapshot,
            telemetry_event_id=telemetry_event_id,
            fenced_execution=fenced_execution,
        )

        # Log structured telemetry event if pivot occurred
        if is_pivoted:
            emit_mlff_pivot_telemetry(decision, telemetry_log_path=self.telemetry_log_path)

        return decision

    def execute(
        self,
        request: Union[MLFFRoutingRequest, Dict[str, Any]],
        compute_fn: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> Tuple[MLFFRoutingDecision, T]:
        """
        Routes the MLFF request and immediately executes compute_fn under the
        appropriate precision fence and hardware environment.
        Returns: (routing_decision, computation_result)
        """
        decision = self.route(request)

        if decision.fenced_execution:
            with cpu_mlff_precision_fence(decision.precision_mode):
                result = compute_fn(*args, **kwargs)
        else:
            result = compute_fn(*args, **kwargs)

        return decision, result


# =============================================================================
# CONVENIENCE FUNCTIONAL APIS
# =============================================================================

_DEFAULT_ROUTER: Optional[MLFFRouter] = None
_ROUTER_LOCK = threading.Lock()


def get_default_mlff_router() -> MLFFRouter:
    """Returns the singleton default MLFFRouter instance."""
    global _DEFAULT_ROUTER
    with _ROUTER_LOCK:
        if _DEFAULT_ROUTER is None:
            _DEFAULT_ROUTER = MLFFRouter()
        return _DEFAULT_ROUTER


def route_mlff(
    requested_method: Union[str, MLFFMethod] = MLFFMethod.MACE_OFF24M,
    requested_device: Union[str, ExecutionDevice] = ExecutionDevice.AUTO,
    requested_precision: Optional[Union[str, PrecisionMode]] = None,
    atom_count: Optional[int] = None,
    required_vram_gb: Optional[float] = None,
    strict: bool = False,
    allow_downgrade: bool = True,
    hardware_override: Optional[HardwareSchema] = None,
    config_path: Optional[Union[str, Path]] = None,
    provenance_tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> MLFFRoutingDecision:
    """
    Direct functional entrypoint to route an MLFF computational job through the fallback cascade.
    """
    method = MLFFMethod.from_string(requested_method)
    device = ExecutionDevice.from_string(requested_device)
    precision = PrecisionMode.from_string(requested_precision) if requested_precision is not None else None

    req = MLFFRoutingRequest(
        requested_method=method,
        requested_device=device,
        requested_precision=precision,
        atom_count=atom_count,
        required_vram_gb=required_vram_gb,
        strict=strict,
        allow_downgrade=allow_downgrade,
        hardware_override=hardware_override,
        config_path=config_path,
        provenance_tags=provenance_tags or [],
        metadata=metadata or {},
    )
    router = get_default_mlff_router()
    return router.route(req)


def execute_mlff_cascade(
    compute_fn: Callable[..., T],
    *args: Any,
    requested_method: Union[str, MLFFMethod] = MLFFMethod.MACE_OFF24M,
    requested_device: Union[str, ExecutionDevice] = ExecutionDevice.AUTO,
    strict: bool = False,
    hardware_override: Optional[HardwareSchema] = None,
    config_path: Optional[Union[str, Path]] = None,
    **kwargs: Any,
) -> Tuple[MLFFRoutingDecision, T]:
    """
    Routes and executes a calculation payload with automatic CPU precision fencing.
    """
    method = MLFFMethod.from_string(requested_method)
    device = ExecutionDevice.from_string(requested_device)

    req = MLFFRoutingRequest(
        requested_method=method,
        requested_device=device,
        strict=strict,
        hardware_override=hardware_override,
        config_path=config_path,
    )
    router = get_default_mlff_router()
    return router.execute(req, compute_fn, *args, **kwargs)
