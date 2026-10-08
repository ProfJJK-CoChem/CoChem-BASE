"""BASE job capability and immutable handoff contracts.

An installed module or quantum executable is not an accepted scientific result.
Only the native adapters listed here have a connected result-validation path.
Future consumers receive complete input jobs with explicit required evidence;
entry-point discovery never imports or executes their code automatically.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from typing import Any, Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .artifact_handoff import ModuleHandoff, load_module_handoff, prepare_module_handoff


Operation = Literal["single_point", "optimization", "harmonic_frequencies", "vpt2"]


class CalculationCapability(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    module_id: Literal["base"] = "base"
    engine: Literal["orca", "xtb", "pyscf", "qe", "cfour"]
    operation: Operation
    adapter_status: Literal["connected", "pending_integration"]
    executable_authorization: Literal["required_at_execution"] = "required_at_execution"
    reason: str
    scientific_execution_performed: Literal[False] = False


def calculation_capability(config: Any) -> CalculationCapability:
    """Describe a request's adapter, separately from audited binary availability."""
    operation: Operation = ("vpt2" if config.is_vpt2 else "harmonic_frequencies" if config.is_freq
                            else "optimization" if config.is_opt else "single_point")
    native = {"orca": {"single_point", "optimization", "harmonic_frequencies"}, "xtb": {"single_point", "optimization"},
              "pyscf": {"single_point"}, "qe": {"single_point"}, "cfour": set()}
    connected = operation in native[config.engine]
    if config.engine == "cfour":
        from cochem_base.calc.cfour_execution import supported_cfour_request
        connected = supported_cfour_request(config)
    return CalculationCapability(
        engine=config.engine, operation=operation,
        adapter_status="connected" if connected else "pending_integration",
        reason=("Native execution and operation-specific result validation are connected; audited engine authorization is still required."
                if connected else "This scientific operation requires integration of its execution adapter and domain result validator; BASE can preserve and hand off the validated input job."),
    )


def required_scientific_evidence(config: Any) -> tuple[str, ...]:
    requirements = ["input_geometry_and_config_sha256", "audited_engine_identity_and_version",
                    "normal_process_termination", "electronic_convergence", "finite_requested_method_energy_hartree"]
    if config.multiplicity > 1:
        requirements.append("live_and_final_spin_contamination_validation")
    if config.is_opt:
        requirements.extend(("stationary_geometry_convergence", "final_coordinates_angstrom", "complete_optimization_trajectory"))
    if config.is_freq or config.is_vpt2:
        requirements.extend(("geometry_bound_cartesian_hessian_hartree_per_bohr_squared",
                             "principal_isotope_masses_u", "harmonic_frequencies_cm_inverse"))
    if config.is_vpt2:
        requirements.extend(("cubic_and_semidiagonal_quartic_force_field_with_units",
                             "vibration_rotation_interaction_constants_MHz",
                             "resonance_treatment_and_anharmonic_validity_evidence"))
    if config.recipe:
        requirements.append("frozen_monomer_full_trajectory_integrity")
    if config.recipe == "R2":
        requirements.extend(("CCSD_T_CBS_reference_provenance", "five_leg_counterpoise_energies_hartree",
                             "residual_gradient_validation"))
    return tuple(requirements)


def _config_digest(data: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def validate_job_configuration(config: Any) -> None:
    """Reject malformed electronic states and unsupported CFOUR method requests."""
    from cochem_base.calc.calculation_service import parse_run_geometry
    from cochem_base.physics.isotopes import get_element_mass_and_abundance

    elements, _ = parse_run_geometry(config.geometry)
    electrons = sum(get_element_mass_and_abundance(symbol)[2] for symbol in elements) - config.charge
    unpaired = config.multiplicity - 1
    if electrons <= 0 or unpaired > electrons or (electrons - unpaired) % 2:
        raise ValueError("Molecular charge and spin multiplicity are incompatible with the electron count")
    for label, value in (("method", config.method), ("basis_set", config.basis_set)):
        if value is not None and (not value.strip() or "\n" in value or "\r" in value):
            raise ValueError(f"{label} must be a nonempty single-line specification")
    if config.engine == "cfour":
        from cochem_base.core_engine.cochem_core_cfour_bridge import CFOURCalcLevel
        CFOURCalcLevel(config.method)
        if not config.basis_set or config.basis_set.lower() in {"default", "built-in"}:
            raise ValueError("CFOUR jobs require an explicit orbital basis")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9+_.()*-]*", config.basis_set):
            raise ValueError("CFOUR basis must be a plain basis label without injected input keywords")
        if config.recipe or config.implicit_solvation or config.frozen_monomer_indices is not None:
            raise ValueError("CFOUR handoff does not define ORCA recipe, solvation or frozen-index keyword translations")
    if config.initial_hessian.upper() == "READ" and config.hessian_file is None:
        raise ValueError("A READ Hessian job requires its actual input checkpoint")
    if config.engine == "qe":
        from cochem_base.calc.periodic_execution import PeriodicCalculationConfig
        from cochem_base.theory_matrix import ProductClass
        PeriodicCalculationConfig.model_validate(config.periodic)
        if config.product_class not in {"B", ProductClass.PRODUCT_B.value} or config.method.upper() != "PBE" or config.basis_set not in {None, "PAW", "plane_wave", "built-in"}:
            raise ValueError("Periodic scientific jobs require Product B, PBE and a plane-wave PAW basis")
        if config.charge != 0 or config.multiplicity != 1:
            raise ValueError("The periodic job contract requires a neutral closed-shell singlet")


class ScientificJobRequest(BaseModel):
    """Structure/integrity acceptance for a future consumer, never science acceptance."""
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["cochem.scientific-job/1"] = "cochem.scientific-job/1"
    module_id: Literal["base"] = "base"
    capability: CalculationCapability
    calculation_config: dict[str, Any]
    configuration_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    geometry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    coordinates_unit: Literal["angstrom"] = "angstrom"
    required_evidence: tuple[str, ...]
    provider_options: dict[str, Any] = Field(default_factory=dict)
    dependencies: dict[str, dict[str, Any]] = Field(default_factory=dict)
    input_bindings: dict[str, str] = Field(default_factory=dict)
    acceptance_scope: Literal["input_validation_only"] = "input_validation_only"

    @model_validator(mode="after")
    def verify_request(self) -> "ScientificJobRequest":
        from cochem_base.calc.calculation_service import CalculationMatrixConfig
        config = CalculationMatrixConfig.model_validate(self.calculation_config)
        json.dumps(self.provider_options, allow_nan=False)
        for name, dependency in self.dependencies.items():
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name):
                raise ValueError("Dependency names must be safe filename components")
            if set(dependency) != {"sha256", "size_bytes"} or not re.fullmatch(r"[0-9a-f]{64}", str(dependency["sha256"])):
                raise ValueError("Dependency requires its exact digest and size")
            if isinstance(dependency["size_bytes"], bool) or not isinstance(dependency["size_bytes"], int) or dependency["size_bytes"] <= 0:
                raise ValueError("Scientific job dependencies must be nonempty files")
        expected_inputs = {field for field in ("hessian_file", "r2_reference_manifest") if getattr(config, field) is not None}
        if config.engine == "qe":
            expected_inputs.update("pseudopotential." + symbol for symbol in config.periodic["pseudopotentials"])
        if set(self.input_bindings) != expected_inputs or any(name not in self.dependencies for name in self.input_bindings.values()):
            raise ValueError("Every declared scientific input file must bind to a copied dependency")
        if config.engine == "qe":
            for symbol, potential in config.periodic["pseudopotentials"].items():
                if self.dependencies[self.input_bindings["pseudopotential." + symbol]]["sha256"] != potential["sha256"]:
                    raise ValueError("Periodic pseudopotential snapshot contradicts its pinned digest")
        validate_job_configuration(config)
        if _config_digest(self.calculation_config) != self.configuration_sha256:
            raise ValueError("Scientific job configuration digest differs from the requested input")
        if calculation_capability(config) != self.capability:
            raise ValueError("Scientific job capability does not match its requested operation")
        if required_scientific_evidence(config) != self.required_evidence:
            raise ValueError("Scientific job acceptance requirements were altered or omitted")
        return self


def prepare_calculation_handoff(config: Any, artifact_path: str | Path, destination: str | Path,
                                *, provider_options: dict[str, Any] | None = None,
                                dependency_files: dict[str, str | Path] | None = None) -> ModuleHandoff:
    """Bind a real single-frame XYZ and complete validated configuration for BASE."""
    validate_job_configuration(config)
    from cochem_base.calc.calculation_service import parse_run_geometry
    source = Path(artifact_path).expanduser().resolve(strict=True)
    if parse_run_geometry(source.read_text()) != parse_run_geometry(config.geometry):
        raise ValueError("Handoff geometry must exactly match its calculation configuration")
    data = config.model_dump(mode="json")
    source_inputs = dict(dependency_files or {})
    bindings = {}
    for field in ("hessian_file", "r2_reference_manifest"):
        path = getattr(config, field)
        if path is not None:
            name = field + path.suffix
            source_inputs.setdefault(name, path)
            bindings[field] = name
    if config.engine == "qe":
        for symbol, potential in config.periodic["pseudopotentials"].items():
            name = f"pseudopotential_{symbol}.UPF"
            source_inputs.setdefault(name, potential["path"])
            bindings["pseudopotential." + symbol] = name
    sources = {name: Path(path).expanduser().resolve(strict=True) for name, path in source_inputs.items()}
    dependencies = {name: {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "size_bytes": path.stat().st_size}
                    for name, path in sources.items()}
    request = ScientificJobRequest(
        capability=calculation_capability(config), calculation_config=data,
        configuration_sha256=_config_digest(data), geometry_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        required_evidence=required_scientific_evidence(config),
        provider_options=provider_options or {},
        dependencies=dependencies,
        input_bindings=bindings,
    )
    from filelock import FileLock
    from cochem.core.context import assert_writable_path
    target = Path(destination).expanduser().resolve()
    assert_writable_path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(str(target) + ".lock", timeout=10):
        if target.exists():
            raise FileExistsError(f"Handoff destination already exists: {target}")
        staging = target.parent / f".{target.name}.{uuid.uuid4().hex}.partial"
        try:
            handoff = prepare_module_handoff("base", source, staging,
                                             operation=request.capability.operation,
                                             options={"scientific_job": request.model_dump(mode="json")})
            if sources:
                (staging / "dependencies").mkdir()
            for name, path in sources.items():
                snapshot = staging / "dependencies" / name
                shutil.copyfile(path, snapshot)
                if hashlib.sha256(snapshot.read_bytes()).hexdigest() != dependencies[name]["sha256"]:
                    raise ValueError("Checkpoint bytes changed while preparing the scientific job")
            load_calculation_handoff(staging / "handoff.json")
            os.replace(staging, target)
            return handoff
        finally:
            if staging.exists():
                shutil.rmtree(staging)


def load_calculation_handoff(manifest_path: str | Path) -> ScientificJobRequest:
    """Revalidate the receiving boundary without loading any installed module code."""
    from cochem_base.calc.calculation_service import parse_run_geometry
    path = Path(manifest_path).expanduser().resolve(strict=True)
    manifest = load_module_handoff(path)
    if manifest.module_id != "base" or manifest.artifact.kind != "geometry_xyz":
        raise ValueError("Scientific job handoff requires BASE and a real XYZ input artifact")
    request = ScientificJobRequest.model_validate(manifest.options["scientific_job"])
    if request.geometry_sha256 != manifest.artifact.sha256 or request.capability.operation != manifest.operation:
        raise ValueError("Scientific job input binding or operation is inconsistent")
    if parse_run_geometry((path.parent / manifest.artifact.filename).read_text()) != parse_run_geometry(request.calculation_config["geometry"]):
        raise ValueError("Scientific job geometry differs from its copied artifact")
    for name, expected in request.dependencies.items():
        checkpoint = (path.parent / "dependencies" / name).resolve(strict=True)
        if checkpoint.parent != path.parent / "dependencies" or not checkpoint.is_file():
            raise ValueError("Checkpoint must remain inside its immutable job package")
        if checkpoint.stat().st_size != expected["size_bytes"] or hashlib.sha256(checkpoint.read_bytes()).hexdigest() != expected["sha256"]:
            raise ValueError("Scientific job checkpoint integrity verification failed")
    if request.capability.engine == "qe":
        from cochem_base.calc.periodic_execution import PeriodicCalculationConfig, _validate_inputs
        periodic = json.loads(json.dumps(request.calculation_config["periodic"]))
        for symbol, potential in periodic["pseudopotentials"].items():
            potential["path"] = str(path.parent / "dependencies" / request.input_bindings["pseudopotential." + symbol])
        elements, coordinates = parse_run_geometry(request.calculation_config["geometry"])
        _validate_inputs(elements, coordinates, PeriodicCalculationConfig.model_validate(periodic),
                         request.calculation_config["charge"], request.calculation_config["multiplicity"])
    return request
