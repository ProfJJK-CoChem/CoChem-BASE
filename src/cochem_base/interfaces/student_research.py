"""Data-only research requests submitted through BASE, never student scripts.

The admission functions intentionally use only the standard library: hosted
workers can reject unsafe requests before installing modules or using secrets.
Provider availability is established separately in a verified isolated runtime.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
from threading import Event
from typing import Any

SCHEMA = "cochem.student-provider/1"
TOPOS_OPERATIONS = frozenset({"energy", "gradient", "optimize", "search", "frequency", "thermochemistry", "association", "matrix"})
TORQ_OPERATIONS = frozenset({"geometry_analysis", "research_scan", "wiberg_lowdin", "nbo_analysis", "wiberg_nao"})
ENGINES = frozenset({"xtb", "orca", "cfour", "pyscf", "mace", "aimnet2"})
MAX_INPUT_BYTES = 2_000_000
_ELEMENTS = ("H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr "
             "Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu "
             "Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og").split()
_ATOMIC_NUMBERS = {symbol: number for number, symbol in enumerate(_ELEMENTS, 1)}


def _molecular_state(molecule: dict) -> None:
    symbols, coordinates = molecule.get("symbols"), molecule.get("coordinates")
    if (not isinstance(symbols, list) or not 1 <= len(symbols) <= 2000
            or any(not isinstance(symbol, str) or symbol not in _ATOMIC_NUMBERS for symbol in symbols)
            or not isinstance(coordinates, list) or len(coordinates) != len(symbols)):
        raise ValueError("Research molecule requires complete ordered canonical elements and Cartesian coordinates")
    for row in coordinates:
        if not isinstance(row, list) or len(row) != 3 or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or abs(x) > 1e6 for x in row):
            raise ValueError("Research molecule requires finite bounded Cartesian coordinates")
    electrons = sum(_ATOMIC_NUMBERS[symbol] for symbol in symbols) - molecule["charge"]
    unpaired = molecule["multiplicity"] - 1
    if electrons < unpaired or (electrons - unpaired) % 2:
        raise ValueError("Electronic charge and multiplicity violate atom-count/spin parity")
    groups = molecule.get("fragments", [])
    states = molecule.get("fragment_states", [])
    if not isinstance(groups, list) or not isinstance(states, list):
        raise ValueError("Fragment partition and states must be explicit arrays")
    if groups:
        if any(not isinstance(group, list) or not group or any(type(i) is not int for i in group) for group in groups):
            raise ValueError("Fragment atom groups must contain explicit atom indices")
        if sorted(i for group in groups for i in group) != list(range(len(symbols))):
            raise ValueError("Fragments must partition the student geometry exactly once")
    if states:
        if len(states) != len(groups) or any(not isinstance(state, dict) or set(state) != {"atom_indices", "charge", "multiplicity"} for state in states):
            raise ValueError("Each fragment requires its matching explicit charge and multiplicity")
        declared = []
        spins = {0}
        for state in states:
            group = state["atom_indices"]
            if (not isinstance(group, list) or any(type(i) is not int or not 0 <= i < len(symbols) for i in group)
                    or type(state["charge"]) is not int or type(state["multiplicity"]) is not int or state["multiplicity"] < 1):
                raise ValueError("Fragment state contains invalid atom indices, charge or multiplicity")
            ne = sum(_ATOMIC_NUMBERS[symbols[i]] for i in group) - state["charge"]
            u = state["multiplicity"] - 1
            if ne < u or (ne - u) % 2:
                raise ValueError("Fragment electronic state violates electron/spin parity")
            spins = {total for previous in spins for total in range(abs(previous - u), previous + u + 1, 2)}
            declared.append(sorted(group))
        if (sorted(declared) != sorted(sorted(group) for group in groups)
                or sum(state["charge"] for state in states) != molecule["charge"] or unpaired not in spins):
            raise ValueError("Fragment states disagree with the partition, total charge or coupled molecular spin")


def _json_data(value: Any) -> None:
    """Reject commands, secrets, nonfinite values and non-JSON objects recursively."""
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                raise ValueError("Scientific request keys must be strings")
            word = key.lower().replace("-", "_")
            if (word in {"command", "shell", "script", "executable", "python_path", "environment", "env", "token"}
                    or any(term in word for term in ("password", "secret", "credential", "api_key", "authorization"))
                    or word.endswith("_token")):
                raise ValueError("Commands, environment overrides and credentials are forbidden in research requests")
            _json_data(child)
    elif isinstance(value, list):
        for child in value:
            _json_data(child)
    elif isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Scientific request numbers must be finite")
    elif value is not None and not isinstance(value, (str, int, float, bool)):
        raise ValueError("Scientific requests must contain JSON data only")


def _relative_artifact(value: Any) -> str:
    if not isinstance(value, str) or "\\" in value or not value or "\x00" in value:
        raise ValueError("Research artifact must be an explicit relative uploaded file")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {".", ".."} for part in path.parts) or str(path) != value:
        raise ValueError("Research artifact must remain inside the uploaded input bundle")
    return value


def validate_provider_request(provider: dict, files_metadata: Any = None) -> dict:
    """Validate transport authority; the installed provider validates chemistry.

    ``files_metadata`` may map relative filenames to SHA-256 strings or objects
    containing ``sha256``. It may also be a list of filename/path observations.
    """
    if not isinstance(provider, dict) or set(provider) != {"schema_version", "module", "operation", "artifact", "artifact_sha256", "options"}:
        raise ValueError("Research request requires exactly schema_version, module, operation, artifact, artifact_sha256 and options")
    _json_data(provider)
    if provider["schema_version"] != SCHEMA or not isinstance(provider["module"], str) or provider["module"] not in {"topos", "torq"}:
        raise ValueError("Unsupported BASE student research provider contract")
    operations = TOPOS_OPERATIONS if provider["module"] == "topos" else TORQ_OPERATIONS
    if not isinstance(provider["operation"], str) or provider["operation"] not in operations:
        raise ValueError("Research operation has no reviewed BASE provider adapter")
    name = _relative_artifact(provider["artifact"])
    digest = provider["artifact_sha256"]
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("Research artifact requires its exact SHA-256")
    options = provider["options"]
    if not isinstance(options, dict):
        raise ValueError("Research operation options must be a JSON object")
    if provider["module"] == "topos":
        if set(options) != {"topos_request"} or not isinstance(options["topos_request"], dict):
            raise ValueError("TOPOS research requires its complete typed topos_request")
        request = options["topos_request"]
        molecule = request.get("molecule")
        if not isinstance(molecule, dict) or not {"symbols", "coordinates", "charge", "multiplicity"}.issubset(molecule):
            raise ValueError("XYZ does not encode electronic state: charge and multiplicity must be explicit")
        if type(molecule["charge"]) is not int or type(molecule["multiplicity"]) is not int or molecule["multiplicity"] < 1:
            raise ValueError("Molecular charge and multiplicity must be explicit integers")
        _molecular_state(molecule)
        if request.get("purpose") != provider["operation"] or request.get("engine") not in ENGINES:
            raise ValueError("TOPOS purpose/engine differs from the requested operation")
        if provider["operation"] != "matrix" and request["engine"] not in {"xtb", "orca"}:
            raise ValueError("This TOPOS receiver exposes xTB/ORCA molecular workflows; other engines require an explicit reviewed matrix route")
        if provider["operation"] == "matrix" and (not isinstance(request.get("matrix_revision"), str)
                or not isinstance(request.get("matrix_row_id"), str) or request.get("matrix_product") not in {"A", "B", "C"}
                or not isinstance(request.get("matrix_inputs"), dict)):
            raise ValueError("Matrix execution requires its exact source revision, recipe row, product and typed input choices")
        if not isinstance(request.get("method"), str) or not request["method"].strip():
            raise ValueError("An explicit scientific method is required")
        for field, low in (("threads", 1), ("memory_mb", 64), ("budget_seconds", 0)):
            value = request.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < low or (field == "budget_seconds" and value == 0):
                raise ValueError("TOPOS requires positive explicit CPU, memory and time allocations")
        if type(request["threads"]) is not int or type(request["memory_mb"]) is not int:
            raise ValueError("TOPOS CPU and memory allocations must be integers")
        if request.get("calculation_environment", "local") != "local":
            raise ValueError("The hosted worker executes locally inside its audited allocation; nested remote dispatch is forbidden")
        if provider["operation"] == "association" and (len(molecule.get("fragments", [])) < 2 or len(molecule.get("fragment_states", [])) != len(molecule["fragments"])):
            raise ValueError("Association requires explicit monomer partitions and each monomer electronic state")
    elif provider["operation"] in {"nbo_analysis", "wiberg_nao"}:
        required = {"engine", "method", "charge", "multiplicity", "cores", "memory_mb"}
        if set(options) != required or not isinstance(options["engine"], str) or options["engine"] not in {"orca", "pyscf"}:
            raise ValueError("Orbital analysis requires an explicit supported backend and complete typed options")
        method = options["method"]
        if (not isinstance(method, dict) or set(method) != {"name", "basis"}
                or any(not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9+_.(),* -]{0,99}", value) for value in method.values())):
            raise ValueError("Orbital analysis requires explicit bounded method and basis names")
        if (type(options["charge"]) is not int or not -4 <= options["charge"] <= 4
                or type(options["multiplicity"]) is not int or not 1 <= options["multiplicity"] <= 5
                or type(options["cores"]) is not int or options["cores"] not in {1, 2}
                or type(options["memory_mb"]) is not int or not 256 <= options["memory_mb"] <= 2048):
            raise ValueError("Orbital analysis requires bounded explicit electronic state and resource settings")
    if files_metadata is not None:
        if isinstance(files_metadata, list):
            files_metadata = {item.get("filename", item.get("path")): item for item in files_metadata if isinstance(item, dict)}
        if not isinstance(files_metadata, dict) or name not in files_metadata:
            raise ValueError("Research input artifact is absent from its submitted bundle")
        actual = files_metadata[name]
        actual = actual.get("sha256") if isinstance(actual, dict) else actual
        if actual != digest:
            raise ValueError("Research artifact SHA-256 differs from the submitted bundle")
    json.dumps(provider, allow_nan=False)
    return deepcopy(provider)


def required_provider_modules(provider: dict) -> list[str]:
    request = validate_provider_request(provider)
    return ["torq", "topos"] if request["module"] == "topos" else ["torq"]


def required_provider_engines(provider: dict) -> list[str]:
    request = validate_provider_request(provider)
    if request["module"] == "topos":
        result = [request["options"]["topos_request"]["engine"]]
        sampler = request["options"]["topos_request"].get("search_algorithm", "jiggle-quench")
        if sampler in {"crest", "union"}:
            result.extend(["xtb", "crest"])
        if sampler == "union":
            result.append("orca")
        return list(dict.fromkeys(result))
    if request["operation"] in {"nbo_analysis", "wiberg_nao"}:
        # The selected engine is necessary but not sufficient. The installed
        # provider's separately verified metadata/runtime must admit all extra
        # dependencies (including separately licensed NBO when it is required).
        return [request["options"]["engine"]]
    return ["pyscf"] if request["operation"] in {"research_scan", "wiberg_lowdin"} else []


def validate_provider_resources(provider: dict, resources: dict) -> None:
    """Reject allocation mismatches before hosted installation or secret use."""
    request = validate_provider_request(provider)
    cores = resources.get("cores", resources.get("threads"))
    memory = resources.get("memory_mb")
    if memory is None and cores is not None and resources.get("maxcore_mb") is not None:
        memory = cores * resources["maxcore_mb"]
    budget = resources.get("budget_seconds", 1800)
    if request["module"] == "topos":
        actual = request["options"]["topos_request"]
        comparisons = (("threads", actual["threads"], cores), ("memory_mb", actual["memory_mb"], memory),
                       ("budget_seconds", actual["budget_seconds"], budget))
    elif request["operation"] in {"research_scan", "wiberg_lowdin", "nbo_analysis", "wiberg_nao"}:
        options = request["options"]
        if not {"cores", "memory_mb"}.issubset(options):
            raise ValueError("TORQ research requires explicit CPU and total memory allocations")
        comparisons = (("cores", options["cores"], cores), ("memory_mb", options["memory_mb"], memory))
    else:
        comparisons = ()
    for name, actual, limit in comparisons:
        if isinstance(actual, bool) or not isinstance(actual, (int, float)) or not math.isfinite(actual) or actual <= 0:
            raise ValueError("Provider request contains invalid " + name)
        if limit is not None and actual > limit:
            raise ValueError("Provider request exceeds the worker's allocated " + name)


def build_topos_request(geometry_xyz: str, *, operation: str, charge: int, multiplicity: int,
                        engine: str = "xtb", method: str = "GFN2-xTB", fragments: list | None = None,
                        fragment_states: list | None = None, options: dict | None = None) -> dict:
    """Build explicit provider chemistry from a student's uploaded XYZ bytes."""
    from cochem_base.geometry.nuclide_geometry import parse_geometry_identity

    if operation not in TOPOS_OPERATIONS:
        raise ValueError("Unsupported TOPOS scientific operation")
    raw = geometry_xyz.encode("utf-8")
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("Student XYZ exceeds the 2 MB input limit")
    parsing_text = geometry_xyz.removeprefix("\ufeff")
    lines = parsing_text.splitlines()
    if not lines or not lines[0].strip().isdigit():
        raise ValueError("Student upload must be one complete counted XYZ geometry")
    count = int(lines[0].strip())
    if not 1 <= count <= 2000 or len(lines) < count + 2 or any(line.strip() for line in lines[count + 2:]) or any(len(row.split()) != 4 for row in lines[2:count + 2]):
        raise ValueError("Student upload must be one complete counted XYZ geometry")
    identity = parse_geometry_identity(parsing_text)
    molecule = {"symbols": list(identity.elements), "coordinates": [list(row) for row in identity.coordinates_angstrom],
                "isotopes": list(identity.mass_numbers), "charge": charge, "multiplicity": multiplicity,
                "fragments": fragments or [], "fragment_states": fragment_states or []}
    request = {"molecule": molecule, "engine": engine, "method": method, "purpose": operation,
               "threads": 2, "memory_mb": 1024, "budget_seconds": 600,
               "n_candidates": 4 if operation in {"search", "association"} else 1,
               "profile_id": "screening-v1" if engine == "xtb" else "orca-mapping-v4.1",
               "presentation_environment": "base", "calculation_environment": "local"}
    if options:
        if set(options) & {"molecule", "purpose", "engine", "method"}:
            raise ValueError("Scientific options cannot replace input identity, engine, method or purpose")
        request.update(deepcopy(options))
    envelope = {"schema_version": SCHEMA, "module": "topos", "operation": operation,
                "artifact": "inputs/geometry.xyz", "artifact_sha256": hashlib.sha256(raw).hexdigest(),
                "options": {"topos_request": request}}
    validate_provider_request(envelope)
    return request


def assemble_monomers(monomers: list[dict], *, separation_angstrom: float = 5.0,
                      multiplicity: int = 1) -> dict:
    """Create a documented search seed from student monomers without changing them.

    Translation preserves each internal geometry. This packing is an initial
    seed, not an optimized complex or evidence of binding. Nuclear labels survive.
    """
    if not 2 <= len(monomers) <= 8 or not math.isfinite(separation_angstrom) or not 2 <= separation_angstrom <= 100:
        raise ValueError("Provide 2 to 8 monomers and an explicit separation of 2 to 100 angstrom")
    all_rows, groups, states, offset = [], [], [], 0
    for index, item in enumerate(monomers):
        if not isinstance(item, dict) or set(item) != {"xyz", "charge", "multiplicity"}:
            raise ValueError("Every student monomer requires XYZ, charge and multiplicity")
        request = build_topos_request(item["xyz"], operation="energy", charge=item["charge"], multiplicity=item["multiplicity"])
        coordinates = request["molecule"]["coordinates"]
        center = [sum(row[j] for row in coordinates) / len(coordinates) for j in range(3)]
        rows = item["xyz"].splitlines()[2:2 + len(coordinates)]
        for source, point in zip(rows, coordinates, strict=True):
            shifted = [point[j] - center[j] + (index * separation_angstrom if j == 0 else 0) for j in range(3)]
            all_rows.append(source.split()[0] + " " + " ".join(format(value, ".17g") for value in shifted))
        group = list(range(offset, offset + len(coordinates)))
        groups.append(group)
        states.append({"atom_indices": group, "charge": item["charge"], "multiplicity": item["multiplicity"]})
        offset += len(coordinates)
    xyz = str(offset) + "\nBASE assembled student monomer search seed; translation only; angstrom\n" + "\n".join(all_rows) + "\n"
    request = build_topos_request(xyz, operation="association", charge=sum(state["charge"] for state in states),
                                 multiplicity=multiplicity, fragments=groups, fragment_states=states)
    request["metadata"] = {"student_monomer_sources": [{"sha256": hashlib.sha256(item["xyz"].encode()).hexdigest(),
                            "charge": item["charge"], "multiplicity": item["multiplicity"]} for item in monomers],
                           "assembly": {"operation": "centroid translation", "separation_angstrom": separation_angstrom,
                                        "scope": "starting packing only; no calculated energy or binding claim"}}
    return {"xyz": xyz, "molecule": request["molecule"], "topos_request": request}


def get_student_capabilities(*, root: Path | None = None, manifest: Path | None = None) -> list[dict]:
    from .module_execution import installed_module_status
    return [item for item in installed_module_status(root, manifest) if item["module_id"] in {"topos", "torq"}]


def student_matrix_recipes(*, capabilities: list[dict] | None = None, root: Path | None = None,
                           manifest: Path | None = None) -> list[dict]:
    """Return simple optimization recipes from the actual sealed TOPOS catalog.

    These three rows need only the uploaded molecule. Association references,
    auxiliary electronic artifacts and expensive coupled-cluster routes require
    their own complete forms; they are not silently reduced to a single point.
    """
    observations = capabilities if capabilities is not None else get_student_capabilities(root=root, manifest=manifest)
    approved = {"T3O-10s", "T3O-30min", "T3O-1h"}
    for item in observations:
        if item.get("module_id") != "topos" or item.get("status") != "installed" or "matrix" not in item.get("operations", []):
            continue
        provider = item.get("provider_capabilities") or {}
        metadata = provider.get("provider_metadata") or {}
        result = []
        for recipe in metadata.get("student_matrix_recipes", []):
            if (not isinstance(recipe, dict) or recipe.get("row_id") not in approved
                    or recipe.get("engine") not in {"xtb", "orca"}
                    or not isinstance(recipe.get("matrix_revision"), str)
                    or not isinstance(recipe.get("catalog_source_sha256"), str)
                    or not re.fullmatch(r"[0-9a-f]{64}", recipe["catalog_source_sha256"])
                    or recipe.get("matrix_product") != "A" or recipe.get("matrix_inputs") != {}):
                continue
            result.append(deepcopy(recipe))
        return sorted(result, key=lambda recipe: (recipe["engine"] != "xtb", recipe["row_id"]))
    return []


def build_topos_matrix_request(geometry_xyz: str, *, row_id: str, charge: int, multiplicity: int,
                               options: dict | None = None, capabilities: list[dict] | None = None,
                               root: Path | None = None, manifest: Path | None = None) -> dict:
    """Build the selected compiled recipe without student JSON or code entry."""
    recipes = student_matrix_recipes(capabilities=capabilities, root=root, manifest=manifest)
    recipe = next((item for item in recipes if item["row_id"] == row_id), None)
    if recipe is None:
        raise ValueError("This simple matrix recipe is unavailable in the verified installed TOPOS provider")
    if options and set(options) - {"threads", "memory_mb", "budget_seconds", "presentation_environment"}:
        raise ValueError("Matrix form options may adjust resources, not replace the compiled scientific recipe")
    configured = {"matrix_revision": recipe["matrix_revision"], "matrix_row_id": row_id,
                  "matrix_product": recipe["matrix_product"], "matrix_inputs": {},
                  "basis": recipe["basis"], "auxiliary_basis": recipe["auxiliary_basis"],
                  "profile_id": recipe["profile_id"]}
    configured.update(options or {})
    return build_topos_request(geometry_xyz, operation="matrix", charge=charge, multiplicity=multiplicity,
                               engine=recipe["engine"], method=recipe["method"], options=configured)


def execute_provider_request(provider: dict, input_directory: str | Path, output: str | Path, *,
                             root: Path | None = None, manifest: Path | None = None,
                             registry: str | Path | None = None, resources: dict | None = None,
                             cancel_event: Event | None = None) -> dict:
    """Revalidate the uploaded bytes, freeze the handoff and invoke the provider."""
    from .artifact_handoff import prepare_module_handoff
    from .module_execution import execute_module_handoff

    request = validate_provider_request(provider)
    inputs = Path(input_directory).expanduser().resolve(strict=True)
    artifact = (inputs / request["artifact"]).resolve(strict=True)
    if not artifact.is_relative_to(inputs) or not artifact.is_file() or artifact.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("Research artifact is not a bounded file inside its input bundle")
    if hashlib.sha256(artifact.read_bytes()).hexdigest() != request["artifact_sha256"]:
        raise ValueError("Student uploaded geometry changed after submission")
    options = request["options"]
    if resources:
        validate_provider_resources(request, resources)
    if request["module"] == "topos":
        declared = options["topos_request"]
        verified = build_topos_request(artifact.read_text(encoding="utf-8"), operation=request["operation"],
                                      charge=declared["molecule"]["charge"], multiplicity=declared["molecule"]["multiplicity"],
                                      engine=declared["engine"], method=declared["method"],
                                      options={key: declared[key] for key in ("matrix_revision", "matrix_row_id", "matrix_product", "matrix_inputs")}
                                      if request["operation"] == "matrix" else None)
        for field in ("symbols", "coordinates", "isotopes"):
            if declared["molecule"].get(field, [None] * len(verified["molecule"]["symbols"]) if field == "isotopes" else None) != verified["molecule"][field]:
                raise ValueError("TOPOS molecular identity differs from the original student XYZ")
    target = Path(output).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=False)
    handoff = target / "input-handoff"
    prepare_module_handoff(request["module"], artifact, handoff, operation=request["operation"], options=options)
    budget = options.get("topos_request", {}).get("budget_seconds", 180)
    return execute_module_handoff(handoff / "handoff.json", target / "execution", root=root, manifest=manifest,
                                  timeout=float(budget) + 60, registry=registry, cancel_event=cancel_event)
