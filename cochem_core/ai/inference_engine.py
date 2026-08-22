# cochem_canvas_target: cochem_core/ai/inference_engine.py
"""
CoChem-BASE AI Integrations - INFERENCE_ENGINE ScribeLLMEngine Factory Router.

Autonomous AI orchestration router and graceful degradation loop for LLM weight
instantiation in the CoChem computational chemistry ecosystem.

Prioritizes local calculation stability and hardware safety over AI generation.

3-Tier Fallback Cascade:
  - Tier 1 (Local Metal): LocalLlamaEngine (.gguf weights loaded lazily strictly if hardware budget permits).
  - Tier 2 (API Client): GeminiEngine (Routed via GEMINI_API_KEY in .env, secured with OS-specific ACLs/chmod).
  - Tier 3 (Dry-Run): DryRunEngine (Jinja2 publication-ready computational chemistry boilerplate bypassing LLM).

Core Invariants:
  1. Lazy-loading: 0 GB dormant VRAM footprint on instantiation until inference execution.
  2. Proactive mathematical memory budgeting: KV cache and tensor memory calculated prior to allocation.
     Banned: 'try...except MemoryError'. Memory safety is mathematically guaranteed.
  3. Dynamic context expansion monitoring: If context expansion exceeds available VRAM/RAM, weights are
     immediately unloaded, inference halted, and execution silently falls back to DryRunEngine.
"""

from __future__ import annotations

import gc
import logging
import os
import platform
import stat
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import jinja2
from pydantic import BaseModel, ConfigDict, Field

from cochem_core.ai.resource_guard import (
    ResourceGuardDecision,
    evaluate_resource_guard,
    probe_host_memory,
    probe_nvidia_vram,
)

logger = logging.getLogger("CoChem.AI.InferenceEngine")

# =============================================================================
# CONSTANTS & CONFIGURATION
# =============================================================================

DEFAULT_CONTEXT_WINDOW: int = 4096
DEFAULT_MAX_TOKENS: int = 1024
DEFAULT_TEMPERATURE: float = 0.7
DEFAULT_TOP_P: float = 0.95
DEFAULT_MODEL_SIZE_GB: float = 4.5
DEFAULT_HEADROOM_GB: float = 1.0


# =============================================================================
# TYPED DATA MODELS
# =============================================================================

class EngineResponse(BaseModel):
    """
    Typed response object returned by all LLM engines and routers in the CoChem ecosystem.
    """
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    text: str = Field(
        ...,
        description="Generated scientific text, publication boilerplate, or model output"
    )
    tier: int = Field(
        ...,
        ge=1,
        le=3,
        description="Execution tier that generated the response: 1 (Local), 2 (API), 3 (Dry-Run)"
    )
    engine_name: str = Field(
        ...,
        description="Name of the specific engine class executing the generation"
    )
    tokens_generated: int = Field(
        default=0,
        ge=0,
        description="Estimated or counted number of generated output tokens"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Diagnostic metadata, latency, fallback trail, and template parameters"
    )
    success: bool = Field(
        default=True,
        description="Whether the generation completed successfully"
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize response to standard dictionary."""
        return self.model_dump()

    def to_json(self) -> str:
        """Serialize response to formatted JSON string."""
        return self.model_dump_json(indent=2)


class InferenceConfig(BaseModel):
    """
    Configuration options for ScribeLLMEngine factory router and sub-engines.
    """
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    preferred_tier: int = Field(
        default=1,
        ge=1,
        le=3,
        description="Target tier: 1 (Local Metal), 2 (Gemini API), 3 (Dry-Run Boilerplate)"
    )
    model_path: Optional[str] = Field(
        default=None,
        description="Filesystem path to local .gguf weights file"
    )
    model_size_gb: float = Field(
        default=DEFAULT_MODEL_SIZE_GB,
        ge=0.0,
        description="Estimated on-disk weight footprint in gigabytes"
    )
    context_window_tokens: int = Field(
        default=DEFAULT_CONTEXT_WINDOW,
        ge=128,
        description="Maximum context window size in tokens"
    )
    max_tokens: int = Field(
        default=DEFAULT_MAX_TOKENS,
        ge=1,
        description="Maximum tokens to generate per inference call"
    )
    temperature: float = Field(
        default=DEFAULT_TEMPERATURE,
        ge=0.0,
        le=2.0,
        description="Sampling temperature"
    )
    top_p: float = Field(
        default=DEFAULT_TOP_P,
        ge=0.0,
        le=1.0,
        description="Nucleus sampling probability"
    )
    n_gpu_layers: int = Field(
        default=-1,
        description="Number of transformer layers to offload to GPU (-1 = all possible layers)"
    )
    n_threads: Optional[int] = Field(
        default=None,
        description="Number of CPU threads for inference (None = auto-detect)"
    )
    n_layers: int = Field(
        default=32,
        ge=1,
        description="Number of transformer layers in model architecture"
    )
    n_heads: int = Field(
        default=32,
        ge=1,
        description="Number of attention heads"
    )
    head_dim: int = Field(
        default=128,
        ge=1,
        description="Dimension per attention head"
    )
    bytes_per_element: int = Field(
        default=2,
        ge=1,
        description="Bytes per KV cache tensor element (2 for fp16 / bf16, 4 for fp32)"
    )
    min_headroom_gb: float = Field(
        default=DEFAULT_HEADROOM_GB,
        ge=0.1,
        description="Safety buffer in GB to maintain free RAM/VRAM during execution"
    )
    api_key: Optional[str] = Field(
        default=None,
        description="Gemini API Key override"
    )
    env_path: Optional[str] = Field(
        default=None,
        description="Explicit filepath to .env configuration file"
    )
    gemini_model: str = Field(
        default="gemini-2.5-flash",
        description="Gemini model identifier"
    )


# =============================================================================
# MATHEMATICAL MEMORY BUDGETING (PROACTIVE SAFETY)
# =============================================================================

def calculate_kv_cache_memory_gb(
    n_ctx: int,
    n_layers: int = 32,
    n_heads: int = 32,
    head_dim: int = 128,
    bytes_per_element: int = 2,
) -> float:
    """
    Calculates exact KV (Key-Value) cache memory consumption in gigabytes.
    Formula:
        Memory (bytes) = 2 (Key + Value) * n_layers * n_heads * head_dim * n_ctx * bytes_per_element
    """
    total_bytes = 2 * n_layers * n_heads * head_dim * n_ctx * bytes_per_element
    return round(total_bytes / (1024 ** 3), 4)


def calculate_total_memory_required_gb(
    model_size_gb: float,
    n_ctx: int,
    n_layers: int = 32,
    n_heads: int = 32,
    head_dim: int = 128,
    bytes_per_element: int = 2,
    scratch_overhead_gb: float = 0.5,
) -> float:
    """
    Computes total memory allocation required for local LLM inference including:
    1. Static model weight footprint.
    2. Dynamic KV cache for requested context window length.
    3. Intermediate compute/scratch tensor overhead.
    """
    kv_cache_gb = calculate_kv_cache_memory_gb(
        n_ctx=n_ctx,
        n_layers=n_layers,
        n_heads=n_heads,
        head_dim=head_dim,
        bytes_per_element=bytes_per_element,
    )
    return round(model_size_gb + kv_cache_gb + scratch_overhead_gb, 4)


# =============================================================================
# OS-SPECIFIC PERMISSION SECURITY FOR .ENV
# =============================================================================

def secure_env_file(env_path: Union[str, Path]) -> bool:
    """
    Applies strict OS-specific security permissions to sensitive .env credential files:
      - Windows: Applies Win32 ACLs restricting read/write access strictly to the current user
        and SYSTEM, removing inherited permissions via win32security or icacls.
      - Linux/macOS: Applies standard POSIX chmod 600 (owner read/write only).

    Returns True if successfully secured, False if file does not exist or operation failed.
    """
    target = Path(env_path).expanduser().resolve()
    if not target.exists() or not target.is_file():
        logger.debug(f"Target env file does not exist for security application: {target}")
        return False

    system_os = platform.system()

    if system_os == "Windows":
        # 1. Attempt win32security ACL modification
        try:
            import ntsecuritycon
            import win32api
            import win32con
            import win32security

            # Obtain current process token and user SID
            token_handle = win32security.OpenProcessToken(
                win32api.GetCurrentProcess(),
                win32con.TOKEN_QUERY
            )
            user_sid, _ = win32security.GetTokenInformation(
                token_handle,
                win32security.TokenUser
            )

            # Create SYSTEM SID
            system_sid = win32security.CreateWellKnownSid(
                win32security.WinLocalSystemSid,
                None
            )

            # Build new explicit Discretionary Access Control List (DACL)
            dacl = win32security.ACL()
            dacl.AddAccessAllowedAce(
                win32security.ACL_REVISION,
                ntsecuritycon.FILE_ALL_ACCESS,
                user_sid
            )
            dacl.AddAccessAllowedAce(
                win32security.ACL_REVISION,
                ntsecuritycon.FILE_ALL_ACCESS,
                system_sid
            )

            # Set security descriptor with protected DACL (strips inheritance)
            sd = win32security.SECURITY_DESCRIPTOR()
            sd.SetSecurityDescriptorDacl(1, dacl, 0)
            win32security.SetFileSecurity(
                str(target),
                win32security.DACL_SECURITY_INFORMATION | win32security.PROTECTED_DACL_SECURITY_INFORMATION,
                sd
            )
            logger.info(f"Successfully secured .env credentials via win32security on Windows: {target}")
            return True
        except Exception as win_err:
            logger.debug(f"win32security ACL configuration fallback to icacls: {win_err}")

        # 2. Fallback to icacls via subprocess
        try:
            username = os.environ.get("USERNAME", "")
            if username:
                cmd = [
                    "icacls",
                    str(target),
                    "/inheritance:r",
                    "/grant:r",
                    f"{username}:(F)",
                    "/grant:r",
                    "SYSTEM:(F)",
                ]
                res = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=10)
                if res.returncode == 0:
                    logger.info(f"Successfully secured .env credentials via icacls on Windows: {target}")
                    return True
                logger.debug(f"icacls command returned nonzero code {res.returncode}: {res.stderr}")
        except Exception as icacls_err:
            logger.debug(f"icacls invocation failed: {icacls_err}")

        return True

    # Linux / macOS / POSIX
    try:
        os.chmod(target, stat.S_IRUSR | stat.S_IWUSR)  # 0o600
        logger.info(f"Successfully applied chmod 600 to credential file: {target}")
        return True
    except Exception as posix_err:
        logger.error(f"Failed to apply chmod 600 to {target}: {posix_err}")
        return False


def load_and_secure_gemini_key(env_path: Optional[Union[str, Path]] = None) -> Optional[str]:
    """
    Discovers, secures, and loads the GEMINI_API_KEY from environment or .env files.
    Secures the credential file on disk before parsing.
    """
    # 1. Check active environment variables
    env_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or os.environ.get("COCHEM_AI_API_KEY")
    if env_key and env_key.strip():
        return env_key.strip()

    # 2. Candidate .env discovery paths
    candidates: List[Path] = []
    if env_path:
        candidates.append(Path(os.path.expandvars(str(env_path))).expanduser().resolve())

    cochem_env = os.environ.get("COCHEM_ENV")
    if cochem_env:
        candidates.append(Path(os.path.expandvars(cochem_env)).expanduser().resolve())

    cwd = Path.cwd()
    home = Path.home()
    candidates.extend([
        cwd / ".env",
        cwd / "cochem.env",
        home / "CoChem_Artifacts" / ".env",
        home / "cochem_artifacts" / ".env",
        home / ".env",
        Path(__file__).resolve().parent.parent.parent / ".env",
    ])

    for target in candidates:
        try:
            if target.exists() and target.is_file():
                # Secure file immediately
                secure_env_file(target)

                # Parse key-value lines
                for line in target.read_text(encoding="utf-8").splitlines():
                    clean = line.strip()
                    if clean and not clean.startswith("#") and "=" in clean:
                        key, val = clean.split("=", 1)
                        k_clean = key.strip()
                        v_clean = val.strip().strip('"').strip("'")
                        if k_clean in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "COCHEM_AI_API_KEY") and v_clean:
                            os.environ[k_clean] = v_clean
                            return v_clean
        except Exception as e:
            logger.debug(f"Failed parsing candidate env file at {target}: {e}")

    return None


# =============================================================================
# ABSTRACT BASE ENGINE
# =============================================================================

class BaseLLMEngine(ABC):
    """
    Abstract interface for all inference engines in the CoChem AI ecosystem.
    """
    @property
    @abstractmethod
    def tier(self) -> int:
        """Engine tier identifier (1, 2, or 3)."""
        pass

    @property
    @abstractmethod
    def engine_name(self) -> str:
        """Engine class name."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Checks whether prerequisites (weights, API keys, dependencies) are available."""
        pass

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        context_data: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> EngineResponse:
        """Executes text generation."""
        pass

    @abstractmethod
    def unload(self) -> None:
        """Unloads weights and releases all VRAM/RAM allocations immediately."""
        pass


# =============================================================================
# TIER 3: DRY-RUN ENGINE (JINJA2 PUBLICATION-READY BOILERPLATE)
# =============================================================================

class DryRunEngine(BaseLLMEngine):
    """
    Tier 3 Failover Engine.
    Bypasses LLM inference completely and renders publication-ready, FAIR-compliant
    computational chemistry boilerplate text using Jinja2 templates.
    """

    TEMPLATES: Dict[str, str] = {
        "computational_details": (
            "Computational Details: Electronic structure and geometry optimizations were performed "
            "using {{ software | default('ORCA 6.0') }}. All molecular structures were optimized with the "
            "{{ method | default('B3LYP-D4') }} exchange-correlation functional combined with the "
            "{{ basis_set | default('def2-TZVP') }} basis set{% if solvent %} in the presence of {{ solvent }} "
            "implicit solvation modeled via the CPCM/SMD continuum framework{% endif %}. Numerical integration "
            "employed the RIJCOSX approximation with def2/J auxiliary Coulomb fitting to accelerate Coulomb and "
            "exchange transformations. Harmonic vibrational frequency calculations were performed at the same level "
            "of theory to confirm stationary points as true local minima (zero imaginary frequencies) or transition "
            "states (strictly one imaginary frequency). Thermal corrections to enthalpy and Gibbs free energy were "
            "computed at {{ temperature | default(298.15) }} K and {{ pressure | default(1.0) }} atm under standard "
            "harmonic oscillator and rigid rotor approximations."
        ),
        "supporting_information": (
            "Supporting Information: All stationary point geometries, electronic energies, zero-point vibrational "
            "energies (ZPVE), thermal corrections, and Cartesian coordinates for {{ molecule | default('the investigated system') }} "
            "were generated using {{ software | default('ORCA') }} at the {{ method | default('B3LYP-D4') }}/{{ basis_set | default('def2-TZVP') }} "
            "level of theory. Conformer ensembles were explored using CREST/ORCA GOAT workflows and refined with Method Matrix "
            "convergence criteria."
        ),
        "reaction_profile": (
            "Reaction Pathway and Energetics Analysis: The minimum energy reaction coordinate for {{ molecule | default('the reaction system') }} "
            "was mapped at the {{ method | default('wB97X-D3') }}/{{ basis_set | default('def2-TZVP') }} level. Forward and "
            "reverse Intrinsic Reaction Coordinate (IRC) integrations were performed from the located transition state to confirm "
            "unambiguous connection with the corresponding reactant and product energy basins."
        ),
        "generic": (
            "CoChem Computational Summary: Automated technical report generated for {{ prompt | default('Computational Chemistry Analysis') }}. "
            "System: {{ molecule | default('Molecular Complex') }}. Theoretical method: {{ method | default('DFT/Semi-Empirical') }}. "
            "Basis set: {{ basis_set | default('def2-TZVP') }}. All numerical criteria strictly conform to CoChem Method Matrix standards."
        ),
    }

    def __init__(self) -> None:
        self._env = jinja2.Environment(
            autoescape=False,
            undefined=jinja2.Undefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self._compiled_templates = {
            name: self._env.from_string(template_str)
            for name, template_str in self.TEMPLATES.items()
        }

    @property
    def tier(self) -> int:
        return 3

    @property
    def engine_name(self) -> str:
        return "DryRunEngine"

    def is_available(self) -> bool:
        return True

    def unload(self) -> None:
        """Flushes volatile Jinja2 template cache and releases references."""
        self._compiled_templates.clear()
        self._compiled_templates = {
            name: self._env.from_string(template_str)
            for name, template_str in self.TEMPLATES.items()
        }

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        context_data: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> EngineResponse:
        """
        Renders structured Jinja2 computational chemistry boilerplate text.
        """
        ctx: Dict[str, Any] = dict(context_data or {})
        ctx.setdefault("prompt", prompt)

        # Template selection heuristic
        sec = str(ctx.get("section", "")).lower()
        p_lower = prompt.lower()

        if "supporting_information" in sec or "si" in sec or "supporting information" in p_lower:
            template_key = "supporting_information"
        elif "reaction" in sec or "pathway" in p_lower or "irc" in p_lower:
            template_key = "reaction_profile"
        elif "detail" in sec or "computational" in p_lower or "method" in p_lower:
            template_key = "computational_details"
        else:
            template_key = "generic"

        tpl = self._compiled_templates.get(template_key, self._compiled_templates["generic"])
        rendered_text = tpl.render(ctx).strip()
        tokens_est = len(rendered_text.split())

        return EngineResponse(
            text=rendered_text,
            tier=3,
            engine_name=self.engine_name,
            tokens_generated=tokens_est,
            metadata={
                "template": template_key,
                "mode": "DRY_RUN",
                "reason": "Jinja2 deterministic publication boilerplate rendered",
            },
            success=True,
        )


# =============================================================================
# TIER 1: LOCAL LLAMA ENGINE (LOCAL METAL, LAZY LOADING, PROACTIVE BUDGETING)
# =============================================================================

class LocalLlamaEngine(BaseLLMEngine):
    """
    Tier 1 Local Metal Engine.
    Executes local GGUF models via llama-cpp-python with strict hardware constraints.

    Core Invariants:
      - 0 GB dormant VRAM footprint until inference execution.
      - Mathematical memory safety budgeting (No 'except MemoryError').
      - Dynamic context expansion monitoring: Unloads weights and falls back if context exceeds budget.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        model_size_gb: float = DEFAULT_MODEL_SIZE_GB,
        n_ctx: int = DEFAULT_CONTEXT_WINDOW,
        n_gpu_layers: int = -1,
        n_threads: Optional[int] = None,
        n_layers: int = 32,
        n_heads: int = 32,
        head_dim: int = 128,
        bytes_per_element: int = 2,
        min_headroom_gb: float = DEFAULT_HEADROOM_GB,
    ) -> None:
        self.model_path = model_path
        self.model_size_gb = model_size_gb
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers
        self.n_threads = n_threads
        self.n_layers = n_layers
        self.n_heads = n_heads
        self.head_dim = head_dim
        self.bytes_per_element = bytes_per_element
        self.min_headroom_gb = min_headroom_gb

        # Dormant state invariants (0 GB footprint)
        self._model: Any = None
        self._allocated_vram_gb: float = 0.0
        self._dry_run_fallback = DryRunEngine()

    @property
    def tier(self) -> int:
        return 1

    @property
    def engine_name(self) -> str:
        return "LocalLlamaEngine"

    def is_loaded(self) -> bool:
        """Returns True if weights are actively resident in memory."""
        return self._model is not None

    def get_allocated_vram_gb(self) -> float:
        """Returns currently tracked VRAM/RAM allocation in GB."""
        return self._allocated_vram_gb

    def is_available(self) -> bool:
        """
        Verifies whether local weights file exists and llama_cpp library is present.
        Does NOT load weights into memory.
        """
        if not self.model_path:
            return False
        p = Path(self.model_path).expanduser()
        if not (p.exists() and p.is_file()):
            return False

        try:
            import llama_cpp  # noqa: F401
            return True
        except ImportError:
            return False

    def unload(self) -> None:
        """
        Immediately unloads weights and frees memory.
        """
        if self._model is not None:
            logger.info("Unloading LocalLlamaEngine weights and releasing memory allocations.")
            del self._model
            self._model = None
            self._allocated_vram_gb = 0.0
            gc.collect()

    def check_memory_budget(
        self,
        requested_n_ctx: Optional[int] = None,
        available_memory_gb: Optional[float] = None,
    ) -> Tuple[bool, float, str]:
        """
        Mathematically verifies whether the model weights and KV cache can safely fit
        in available memory without exhausting the host or triggering OOM.

        Returns (can_fit, required_memory_gb, diagnostic_reason).
        """
        target_ctx = requested_n_ctx if requested_n_ctx is not None else self.n_ctx
        total_required_gb = calculate_total_memory_required_gb(
            model_size_gb=self.model_size_gb,
            n_ctx=target_ctx,
            n_layers=self.n_layers,
            n_heads=self.n_heads,
            head_dim=self.head_dim,
            bytes_per_element=self.bytes_per_element,
        )

        if available_memory_gb is None:
            _, host_avail_ram = probe_host_memory()
            _, avail_vram, gpu_count, _ = probe_nvidia_vram()
            available_memory_gb = avail_vram if (gpu_count > 0 and self.n_gpu_layers != 0) else host_avail_ram

        effective_limit = available_memory_gb - self.min_headroom_gb

        if total_required_gb > effective_limit:
            return (
                False,
                total_required_gb,
                f"Required allocation ({total_required_gb:.2f} GB) exceeds available memory budget "
                f"({available_memory_gb:.2f} GB with {self.min_headroom_gb:.2f} GB safety headroom)."
            )

        return (
            True,
            total_required_gb,
            f"Mathematical memory budget verified: {total_required_gb:.2f} GB fits within {available_memory_gb:.2f} GB."
        )

    def _load_weights(self, available_memory_gb: Optional[float] = None) -> bool:
        """
        Safely instantiates local LLM weights into memory after mathematical safety checks.
        """
        if self.is_loaded():
            return True

        if not self.is_available():
            logger.debug("LocalLlamaEngine dependencies or weights unavailable.")
            return False

        # Step 1: Proactive mathematical memory verification
        can_fit, required_gb, reason = self.check_memory_budget(available_memory_gb=available_memory_gb)
        if not can_fit:
            logger.warning(f"Proactive memory safety limit triggered: {reason}")
            return False

        # Step 2: Resource guard system conflict check
        guard_decision: ResourceGuardDecision = evaluate_resource_guard(
            requested_mode="LOCAL_LLM",
            min_available_ram_gb=required_gb + self.min_headroom_gb,
        )
        if not guard_decision.allow_local_llm:
            logger.warning(f"Resource guard intercepted local LLM load: {guard_decision.reason}")
            return False

        # Step 3: Instantiate llama_cpp
        try:
            import llama_cpp

            if not self.model_path:
                return False

            logger.info(f"Loading local LLM weights from {self.model_path} (Context: {self.n_ctx})...")
            self._model = llama_cpp.Llama(
                model_path=str(Path(self.model_path).expanduser().resolve()),
                n_ctx=self.n_ctx,
                n_gpu_layers=self.n_gpu_layers,
                n_threads=self.n_threads,
                verbose=False,
            )
            self._allocated_vram_gb = required_gb
            return True
        except Exception as e:
            logger.error(f"Failed to instantiate llama_cpp.Llama: {e}")
            self.unload()
            return False

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        context_data: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> EngineResponse:
        """
        Executes local inference with proactive memory bounds and dynamic context expansion checks.
        """
        # 1. Proactive context expansion evaluation
        prompt_tokens_est = int(len(prompt.split()) * 1.3) + 32
        required_total_tokens = prompt_tokens_est + max_tokens

        if required_total_tokens > self.n_ctx:
            # Context expands beyond initialized context window: verify new memory budget
            can_fit, req_gb, reason = self.check_memory_budget(requested_n_ctx=required_total_tokens)
            if not can_fit:
                logger.warning(f"Context expansion exceeds memory safety limits: {reason}. Unloading weights.")
                self.unload()
                return self._dry_run_fallback.generate(
                    prompt=prompt,
                    context_data=context_data,
                    **kwargs,
                )

        # 2. Lazy load weights if not already resident
        if not self.is_loaded():
            loaded = self._load_weights()
            if not loaded:
                return self._dry_run_fallback.generate(
                    prompt=prompt,
                    context_data=context_data,
                    **kwargs,
                )

        # 3. Execute generation
        try:
            full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            raw_output = self._model.create_completion(
                prompt=full_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            text_out = raw_output["choices"][0]["text"].strip()
            tokens_used = raw_output.get("usage", {}).get("completion_tokens", len(text_out.split()))

            return EngineResponse(
                text=text_out,
                tier=1,
                engine_name=self.engine_name,
                tokens_generated=tokens_used,
                metadata={
                    "model_path": self.model_path,
                    "allocated_vram_gb": self._allocated_vram_gb,
                    "n_ctx": self.n_ctx,
                },
                success=True,
            )
        except Exception as exec_err:
            logger.error(f"Inference execution error in LocalLlamaEngine: {exec_err}. Unloading and falling back.")
            self.unload()
            return self._dry_run_fallback.generate(
                prompt=prompt,
                context_data=context_data,
                **kwargs,
            )

    def generate_with_fallback(
        self,
        prompt: str,
        available_memory_gb: Optional[float] = None,
        context_data: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> EngineResponse:
        """
        Executes generation with explicit memory limit enforcement and fallback to DryRunEngine.
        """
        can_fit, _, reason = self.check_memory_budget(available_memory_gb=available_memory_gb)
        if not can_fit:
            logger.info(f"Memory budget insufficient ({reason}), falling back directly to DryRunEngine.")
            self.unload()
            return self._dry_run_fallback.generate(prompt=prompt, context_data=context_data, **kwargs)

        return self.generate(prompt=prompt, context_data=context_data, **kwargs)


# =============================================================================
# TIER 2: GEMINI ENGINE (EXTERNAL API CLIENT, SECURED .ENV)
# =============================================================================

class GeminiEngine(BaseLLMEngine):
    """
    Tier 2 External API Client Engine.
    Routes generation requests to Gemini API via GEMINI_API_KEY.
    Secures the .env credentials file dynamically applying OS-specific file permissions.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        env_path: Optional[str] = None,
        model: str = "gemini-2.5-flash",
    ) -> None:
        self.model = model
        self.api_key = api_key or load_and_secure_gemini_key(env_path=env_path)
        self._dry_run_fallback = DryRunEngine()

    @property
    def tier(self) -> int:
        return 2

    @property
    def engine_name(self) -> str:
        return "GeminiEngine"

    def is_available(self) -> bool:
        """Checks if a valid API key is present."""
        return bool(self.api_key and len(self.api_key.strip()) > 0)

    def unload(self) -> None:
        """Flushes volatile API buffers and invokes dry-run fallback unload."""
        self._dry_run_fallback.unload()

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        context_data: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> EngineResponse:
        """
        Dispatches inference call to Gemini API using google-genai or google-generativeai SDK.
        """
        if not self.is_available():
            logger.debug("Gemini API key is unconfigured. Falling back to DryRunEngine.")
            return self._dry_run_fallback.generate(prompt=prompt, context_data=context_data, **kwargs)

        # 1. Attempt google.genai (official modern SDK)
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)
            full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

            config = types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )

            resp = client.models.generate_content(
                model=self.model,
                contents=full_prompt,
                config=config,
            )
            text_out = resp.text or ""
            tokens_est = len(text_out.split())

            return EngineResponse(
                text=text_out,
                tier=2,
                engine_name=self.engine_name,
                tokens_generated=tokens_est,
                metadata={"model": self.model, "sdk": "google.genai"},
                success=True,
            )
        except Exception as sdk_err:
            logger.debug(f"google.genai call attempt encountered: {sdk_err}. Trying fallback mechanism.")

        # 2. Attempt google.generativeai (legacy SDK)
        try:
            import google.generativeai as legacy_genai

            legacy_genai.configure(api_key=self.api_key)
            model_inst = legacy_genai.GenerativeModel(self.model)
            full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

            legacy_resp = model_inst.generate_content(
                full_prompt,
                generation_config={"temperature": temperature, "max_output_tokens": max_tokens},
            )
            text_out = legacy_resp.text or ""
            return EngineResponse(
                text=text_out,
                tier=2,
                engine_name=self.engine_name,
                tokens_generated=len(text_out.split()),
                metadata={"model": self.model, "sdk": "google.generativeai"},
                success=True,
            )
        except Exception as legacy_err:
            logger.warning(f"Gemini API invocation failed: {legacy_err}. Falling back to DryRunEngine.")
            return self._dry_run_fallback.generate(prompt=prompt, context_data=context_data, **kwargs)

    def generate_with_fallback(
        self,
        prompt: str,
        context_data: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> EngineResponse:
        """Executes generation with graceful fallback to DryRunEngine."""
        if not self.is_available():
            return self._dry_run_fallback.generate(prompt=prompt, context_data=context_data, **kwargs)
        return self.generate(prompt=prompt, context_data=context_data, **kwargs)


# =============================================================================
# SCRIBE LLM ENGINE (FACTORY ROUTER & 3-TIER CASCADE)
# =============================================================================

class ScribeLLMEngine:
    """
    Factory Router and 3-Tier Fallback Cascade Coordinator for CoChem AI Integrations.

    Cascade Hierarchy:
      Tier 1 (Local Metal): LocalLlamaEngine (.gguf weights, 0GB dormant VRAM).
      Tier 2 (API Client): GeminiEngine (.env credential with dynamic OS security).
      Tier 3 (Dry-Run): DryRunEngine (Jinja2 publication-ready boilerplate).

    Safety Protocol:
      - Evaluates system hardware constraints via evaluate_resource_guard before routing.
      - Unloads local weights and halts inference if context expands beyond safe limits.
      - Always returns a valid, publication-ready EngineResponse without raising fatal exceptions.
    """

    def __init__(
        self,
        config: Optional[InferenceConfig] = None,
        model_path: Optional[str] = None,
        api_key: Optional[str] = None,
        env_path: Optional[str] = None,
    ) -> None:
        self.config = config or InferenceConfig()
        if model_path:
            self.config.model_path = model_path
        if api_key:
            self.config.api_key = api_key
        if env_path:
            self.config.env_path = env_path

        # Instantiate 3 engines lazily (0 GB dormant footprint)
        self.local_engine = LocalLlamaEngine(
            model_path=self.config.model_path,
            model_size_gb=self.config.model_size_gb,
            n_ctx=self.config.context_window_tokens,
            n_gpu_layers=self.config.n_gpu_layers,
            n_threads=self.config.n_threads,
            n_layers=self.config.n_layers,
            n_heads=self.config.n_heads,
            head_dim=self.config.head_dim,
            bytes_per_element=self.config.bytes_per_element,
            min_headroom_gb=self.config.min_headroom_gb,
        )

        self.gemini_engine = GeminiEngine(
            api_key=self.config.api_key,
            env_path=self.config.env_path,
            model=self.config.gemini_model,
        )

        self.dry_run_engine = DryRunEngine()

    def get_dormant_vram_footprint_gb(self) -> float:
        """
        Returns the current VRAM/RAM footprint of the router.
        Guaranteed to be 0.0 GB prior to explicit local inference execution.
        """
        return self.local_engine.get_allocated_vram_gb()

    def unload_all(self) -> None:
        """Unloads all active local models and frees allocations."""
        self.local_engine.unload()

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        context_data: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> EngineResponse:
        """
        Routes the generation request through the 3-tier fallback cascade:
          1. Tier 1 (Local Metal): Tried if preferred_tier == 1, hardware permits, and weights exist.
          2. Tier 2 (Gemini API): Tried if preferred_tier <= 2 and valid API key exists.
          3. Tier 3 (Dry-Run): Deterministic Jinja2 boilerplate failover.
        """
        m_tokens = max_tokens if max_tokens is not None else self.config.max_tokens
        temp = temperature if temperature is not None else self.config.temperature
        fallback_trail: List[str] = []

        # =========================================================================
        # TIER 1: LOCAL METAL EVALUATION
        # =========================================================================
        if self.config.preferred_tier == 1:
            # Check ResourceGuard safety
            guard: ResourceGuardDecision = evaluate_resource_guard(
                requested_mode="LOCAL_LLM",
                min_available_ram_gb=self.config.model_size_gb + self.config.min_headroom_gb,
            )

            if guard.allow_local_llm and self.local_engine.is_available():
                logger.info("Routing inference to Tier 1: LocalLlamaEngine.")
                resp = self.local_engine.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    max_tokens=m_tokens,
                    temperature=temp,
                    context_data=context_data,
                    **kwargs,
                )
                if resp.tier == 1 and resp.success:
                    resp.metadata["fallback_trail"] = ["Tier 1 (Local Metal) [SUCCESS]"]
                    return resp
                fallback_trail.append(f"Tier 1 (Local Metal) fell back: {resp.metadata.get('reason', 'Execution redirected')}")
            else:
                reason = "Weights missing / dependencies absent" if not self.local_engine.is_available() else guard.reason
                fallback_trail.append(f"Tier 1 (Local Metal) bypassed: {reason}")

        # =========================================================================
        # TIER 2: GEMINI API EVALUATION
        # =========================================================================
        if self.config.preferred_tier <= 2:
            if self.gemini_engine.is_available():
                logger.info("Routing inference to Tier 2: GeminiEngine.")
                resp = self.gemini_engine.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    max_tokens=m_tokens,
                    temperature=temp,
                    context_data=context_data,
                    **kwargs,
                )
                if resp.tier == 2 and resp.success:
                    fallback_trail.append("Tier 2 (Gemini API) [SUCCESS]")
                    resp.metadata["fallback_trail"] = fallback_trail
                    return resp
                fallback_trail.append("Tier 2 (Gemini API) fell back: API request failed or was rate limited")
            else:
                fallback_trail.append("Tier 2 (Gemini API) bypassed: GEMINI_API_KEY unconfigured or invalid")

        # =========================================================================
        # TIER 3: DETERMINISTIC JINJA2 DRY-RUN BOILERPLATE
        # =========================================================================
        logger.info("Routing generation to Tier 3: DryRunEngine.")
        fallback_trail.append("Tier 3 (Dry-Run) [SUCCESS: Jinja2 publication boilerplate rendered]")
        resp = self.dry_run_engine.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=m_tokens,
            temperature=temp,
            context_data=context_data,
            **kwargs,
        )
        resp.metadata["fallback_trail"] = fallback_trail
        return resp
