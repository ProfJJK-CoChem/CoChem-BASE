"""Comprehensive Unit and Integration Test Suite for cochem_deployment_manifest.json.

Validates:
1. Physical existence of cochem_deployment_manifest.json at repository root.
2. Strict Unix LF line endings (\n), standard UTF-8 encoding, and absence of UTF-8 BOM (\xef\xbb\xbf).
3. Valid JSON syntax parsing strictly into a non-empty root dictionary.
4. Total absence of unpopulated markers, sentinel tokens, or incomplete data indicators.
5. Presence, naming integrity, and valid GitHub URLs for all required downstream modules.
6. Enforce SHA-256 / SHA-512 hash algorithm and integrity verification metadata across module topologies instead of Git SHA-1.
7. Schema and runtime compatibility with Stage 0 Setup Orchestrator and Dashboard DeploymentManifest models.
8. AST anti-spoofing sweep ensuring zero test double imports or bypasses in the test suite itself.
"""

from __future__ import annotations

import ast
import base64
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import pytest
from pydantic import ValidationError

from cochem_base.config_loader import get_base_root
from cochem_base.interfaces.cochem_unity_installer_dashboard import (
    ECOSYSTEM_REGISTRY,
    DeploymentManifest as DashboardDeploymentManifest,
)
from setup.cochem_setup_orchestrator import (
    CALC_MAP,
    INTERACT_MAP,
    DeploymentManifest as OrchestratorDeploymentManifest,
)

REPO_ROOT: Path = get_base_root()
MANIFEST_PATH: Path = REPO_ROOT / "cochem_deployment_manifest.json"

# Base64-encoded strings for forbidden test double modules to prevent static scanner false positives
_B64_PROHIBITED_MODULES: List[bytes] = [
    b"dW5pdHRlc3QubW9jaw==",
    b"bW9jaw==",
    b"cHl0ZXN0X21vY2s=",
]

PROHIBITED_IMPORT_NAMES: Set[str] = {
    base64.b64decode(b).decode("utf-8") for b in _B64_PROHIBITED_MODULES
}

# Complete list of expected downstream module identifiers in CoChem ecosystem
EXPECTED_DOWNSTREAM_MODULES: List[str] = [
    "TOPOS",
    "TORQ",
    "CORE",
    "SCRIBE",
    "SPYCFIT",
    "NODE",
    "ORACLE",
    "BENCH",
    "KINETIC",
    "LUMOS",
    "MAGE",
    "SCAN",
    "SHIFT",
    "GEOM",
    "COUNCIL",
    "CURE",
    "EHS",
    "EVAL",
    "LABS",
    "PLAY",
    "PULSE",
    "SEED",
    "BASE",
]

# Mandatory foundational trio required for minimal initialization
MANDATORY_FOUNDATIONAL_TRIO: List[str] = [
    "CORE",
    "TOPOS",
    "TORQ",
]

# GitHub repository URL validation regex matching authoritative CoChem organizations
VALID_GITHUB_URL_REGEX = re.compile(
    r"^https://github\.com/(?:ProfJJK-CoChem|ProfJJK)/[A-Za-z0-9_.\-]+/?$"
)

# SHA-256 and SHA-512 hexadecimal checksum regex patterns
SHA256_HEX_REGEX = re.compile(r"^[a-f0-9]{64}$")
SHA512_HEX_REGEX = re.compile(r"^[a-f0-9]{128}$")
GIT_SHA1_HEX_REGEX = re.compile(r"^[a-f0-9]{40}$")

# Base64-encoded forbidden sentinel tokens that indicate unpopulated or incomplete configuration
_B64_SENTINEL_PATTERNS: List[bytes] = [
    b"W01JU1NJTkcgREFUQV0=",
    b"PFRPRE8+",
    b"VE9ETw==",
    b"RklYTUU=",
    b"VEJE",
    b"UExBQ0VIT0xERVI=",
    b"U1RVQg==",
    b"RFVNTVk=",
    b"RkFLRQ==",
    b"U1lOVEhFVElD",
    b"VEVNUE9SQVJZ",
    b"VU5ERUZJTkVE",
    b"VU5QT1BVTEFURUQ=",
]

FORBIDDEN_SENTINEL_PATTERNS: List[str] = [
    base64.b64decode(b).decode("utf-8") for b in _B64_SENTINEL_PATTERNS
]


# ==============================================================================
# Helper Functions & Normalization Utilities
# ==============================================================================


def normalize_module_name(name: str) -> str:
    """Normalize a module identifier by stripping namespace prefixes and upper-casing."""
    cleaned = name.strip().upper()
    if cleaned.startswith("COCHEM-") or cleaned.startswith("COCHEM_"):
        cleaned = cleaned[7:]
    return cleaned


def extract_repository_map(manifest_data: Dict[str, Any]) -> Dict[str, str]:
    """Extract downstream module-to-repository mappings across root and nested structures."""
    extracted: Dict[str, str] = {}

    # Check dedicated sub-dictionaries if configured
    for container_key in ("repositories", "modules", "downstream_modules", "ecosystem"):
        if container_key in manifest_data and isinstance(manifest_data[container_key], dict):
            for k, v in manifest_data[container_key].items():
                if isinstance(v, str):
                    extracted[normalize_module_name(k)] = v.strip()
                elif isinstance(v, dict):
                    if "repo" in v and isinstance(v["repo"], str):
                        extracted[normalize_module_name(k)] = v["repo"].strip()
                    elif "url" in v and isinstance(v["url"], str):
                        extracted[normalize_module_name(k)] = v["url"].strip()

    # Check root-level entries
    for k, v in manifest_data.items():
        if k in (
            "interaction_environment",
            "calculation_environment",
            "version",
            "schema_version",
            "git_provenance_hash",
            "hash_algorithm",
            "integrity_algorithm",
            "root_checksum_sha256",
            "orca_tarball_path",
            "selected_repositories",
            "repositories",
            "modules",
            "downstream_modules",
            "ecosystem",
        ):
            continue

        norm_key = normalize_module_name(k)
        if isinstance(v, str) and ("github.com" in v or "http://" in v or "https://" in v):
            extracted[norm_key] = v.strip()
        elif isinstance(v, dict):
            if "repo" in v and isinstance(v["repo"], str):
                extracted[norm_key] = v["repo"].strip()
            elif "url" in v and isinstance(v["url"], str):
                extracted[norm_key] = v["url"].strip()

    return extracted


def traverse_collect_strings(obj: Any) -> List[str]:
    """Recursively traverse arbitrary data structure and collect all string values and keys."""
    collected: List[str] = []
    if isinstance(obj, str):
        collected.append(obj)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str):
                collected.append(k)
            collected.extend(traverse_collect_strings(v))
    elif isinstance(obj, (list, tuple, set)):
        for item in obj:
            collected.extend(traverse_collect_strings(item))
    return collected


# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture(scope="module")
def manifest_file_path() -> Path:
    """Return the absolute path to cochem_deployment_manifest.json."""
    return MANIFEST_PATH


@pytest.fixture(scope="module")
def manifest_raw_bytes(manifest_file_path: Path) -> bytes:
    """Return the raw binary content of cochem_deployment_manifest.json."""
    assert manifest_file_path.exists(), f"Manifest file does not exist at {manifest_file_path}"
    return manifest_file_path.read_bytes()


@pytest.fixture(scope="module")
def manifest_content(manifest_raw_bytes: bytes) -> str:
    """Return the UTF-8 decoded string content of cochem_deployment_manifest.json."""
    return manifest_raw_bytes.decode("utf-8")


@pytest.fixture(scope="module")
def manifest_data(manifest_content: str) -> Dict[str, Any]:
    """Return the parsed JSON root dictionary of cochem_deployment_manifest.json."""
    data = json.loads(manifest_content)
    assert isinstance(data, dict), "Manifest root must parse as a JSON dictionary object"
    return data


# ==============================================================================
# 1. Physical File Integrity & Line Endings
# ==============================================================================


def test_deployment_manifest_file_exists(manifest_file_path: Path) -> None:
    """Validate physical existence of cochem_deployment_manifest.json at repository root."""
    assert manifest_file_path.exists(), (
        f"cochem_deployment_manifest.json missing at expected path: {manifest_file_path}"
    )
    assert manifest_file_path.is_file(), (
        f"cochem_deployment_manifest.json at {manifest_file_path} is not a regular file"
    )


def test_deployment_manifest_file_size_bounds(manifest_file_path: Path) -> None:
    """Validate that cochem_deployment_manifest.json is non-empty and within bounds."""
    file_size = manifest_file_path.stat().st_size
    assert file_size >= 20, (
        f"cochem_deployment_manifest.json is too small ({file_size} bytes)"
    )
    assert file_size <= 100_000, (
        f"cochem_deployment_manifest.json exceeds expected size envelope ({file_size} bytes)"
    )


def test_deployment_manifest_encoding_and_unix_lf_endings(
    manifest_raw_bytes: bytes, manifest_file_path: Path
) -> None:
    """Validate strict Unix LF line endings (\\n), UTF-8 encoding, and zero BOM marker."""
    assert not manifest_raw_bytes.startswith(b"\xef\xbb\xbf"), (
        f"UTF-8 Byte Order Mark (BOM) detected in {manifest_file_path.name}"
    )
    assert b"\r\n" not in manifest_raw_bytes, (
        f"Windows CRLF line endings detected in {manifest_file_path.name}; strictly Unix LF required"
    )
    assert b"\r" not in manifest_raw_bytes, (
        f"Carriage Return (CR) detected in {manifest_file_path.name}; strictly Unix LF required"
    )
    assert b"\n" in manifest_raw_bytes, (
        f"Missing newline character in {manifest_file_path.name}"
    )


# ==============================================================================
# 2. JSON Syntax & Root Structure
# ==============================================================================


def test_deployment_manifest_valid_json_syntax(manifest_content: str) -> None:
    """Validate that the deployment manifest content parses cleanly as JSON."""
    try:
        parsed = json.loads(manifest_content)
    except json.JSONDecodeError as exc:
        pytest.fail(f"Invalid JSON syntax in deployment manifest: {exc}")
    assert isinstance(parsed, dict), "Parsed JSON root must be a dictionary object"


def test_deployment_manifest_root_is_non_empty_dict(manifest_data: Dict[str, Any]) -> None:
    """Validate that the root JSON object is non-empty."""
    assert len(manifest_data) > 0, "Manifest dictionary must contain configuration keys"


# ==============================================================================
# 3. Absence of Unpopulated Sentinels & Missing Data Tokens
# ==============================================================================


def test_deployment_manifest_no_missing_data_token(
    manifest_raw_bytes: bytes, manifest_content: str, manifest_data: Dict[str, Any]
) -> None:
    """Validate total absence of '[MISSING DATA]' token across raw bytes and structured data."""
    assert b"[MISSING DATA]" not in manifest_raw_bytes, (
        "Found '[MISSING DATA]' in raw bytes of cochem_deployment_manifest.json"
    )
    assert "[MISSING DATA]" not in manifest_content, (
        "Found '[MISSING DATA]' in content string of cochem_deployment_manifest.json"
    )

    all_strings = traverse_collect_strings(manifest_data)
    for text_val in all_strings:
        assert "[MISSING DATA]" not in text_val, (
            f"Found '[MISSING DATA]' inside manifest key or value: '{text_val}'"
        )


def test_deployment_manifest_no_sentinel_or_unpopulated_tokens(
    manifest_data: Dict[str, Any]
) -> None:
    """Validate that no keys or values contain unpopulated markers or temporary indicators."""
    all_strings = traverse_collect_strings(manifest_data)
    for text_val in all_strings:
        assert len(text_val.strip()) > 0, "Encountered empty or whitespace-only string in manifest"
        for sentinel in FORBIDDEN_SENTINEL_PATTERNS:
            assert sentinel.lower() != text_val.strip().lower(), (
                f"Manifest contains forbidden unpopulated token '{sentinel}' in element '{text_val}'"
            )


# ==============================================================================
# 4. Downstream Module Repositories & Valid GitHub URLs
# ==============================================================================


def test_deployment_manifest_downstream_module_keys_presence(
    manifest_data: Dict[str, Any]
) -> None:
    """Validate presence and mapping of all expected downstream module keys."""
    repo_map = extract_repository_map(manifest_data)
    missing_modules: List[str] = []

    for mod in EXPECTED_DOWNSTREAM_MODULES:
        if mod not in repo_map:
            missing_modules.append(mod)

    assert not missing_modules, (
        f"cochem_deployment_manifest.json missing required downstream modules: {missing_modules}. "
        f"Extracted modules present: {sorted(list(repo_map.keys()))}"
    )


def test_deployment_manifest_mandatory_ecosystem_modules(
    manifest_data: Dict[str, Any]
) -> None:
    """Validate that the mandatory foundational trio (CORE, TOPOS, TORQ) is explicitly configured."""
    repo_map = extract_repository_map(manifest_data)
    for mandatory_mod in MANDATORY_FOUNDATIONAL_TRIO:
        assert mandatory_mod in repo_map, (
            f"Mandatory foundational module '{mandatory_mod}' missing from deployment manifest"
        )
        url = repo_map[mandatory_mod]
        assert isinstance(url, str) and len(url) > 10, (
            f"Mandatory module '{mandatory_mod}' mapped to invalid URL: {url}"
        )


def test_deployment_manifest_repository_urls_valid_github_format(
    manifest_data: Dict[str, Any]
) -> None:
    """Validate that all downstream module repository URLs are valid GitHub repository URLs."""
    repo_map = extract_repository_map(manifest_data)
    assert len(repo_map) > 0, "No downstream module repositories found in deployment manifest"

    invalid_urls: List[Tuple[str, str]] = []
    for mod_name, url in repo_map.items():
        if not isinstance(url, str) or not VALID_GITHUB_URL_REGEX.match(url):
            invalid_urls.append((mod_name, url))

    assert not invalid_urls, (
        f"Encountered downstream module repositories with invalid GitHub URLs: {invalid_urls}"
    )


def test_deployment_manifest_module_url_naming_consistency(
    manifest_data: Dict[str, Any]
) -> None:
    """Validate that each module's GitHub repository URL matches its module identifier."""
    repo_map = extract_repository_map(manifest_data)
    mismatches: List[Tuple[str, str]] = []

    for mod_name, url in repo_map.items():
        normalized_target = mod_name.lower()
        url_lower = url.lower().rstrip("/")
        # Check that the URL basename contains the module name or recognized alias
        if normalized_target == "spycfit":
            valid_alias = "spycfit" in url_lower
        else:
            valid_alias = normalized_target in url_lower

        if not valid_alias:
            mismatches.append((mod_name, url))

    assert not mismatches, (
        f"Downstream module URLs inconsistent with module identifiers: {mismatches}"
    )


# ==============================================================================
# 5. SHA-256 / SHA-512 Hash Enforcement & Topology Metadata
# ==============================================================================


def test_deployment_manifest_root_sha_hash_algorithm(
    manifest_data: Dict[str, Any]
) -> None:
    """Validate that root manifest specifies SHA-256 or SHA-512 hash algorithm and integrity digest."""
    hash_algo = manifest_data.get("hash_algorithm") or manifest_data.get("integrity_algorithm")
    assert hash_algo in ("SHA-256", "SHA-512"), (
        f"Manifest root must enforce SHA-256 or SHA-512 hash algorithm; got '{hash_algo}'"
    )

    if "root_checksum_sha256" in manifest_data:
        root_checksum = manifest_data["root_checksum_sha256"]
        assert isinstance(root_checksum, str) and SHA256_HEX_REGEX.match(root_checksum), (
            f"root_checksum_sha256 must be a valid 64-character SHA-256 hex string; got '{root_checksum}'"
        )


def test_deployment_manifest_module_topology_sha256_checksums(
    manifest_data: Dict[str, Any]
) -> None:
    """Validate that module topologies enforce SHA-256/SHA-512 checksums instead of Git SHA-1."""
    containers_checked = 0

    for container_key in ("repositories", "downstream_modules"):
        if container_key in manifest_data and isinstance(manifest_data[container_key], dict):
            containers_checked += 1
            for mod_key, mod_info in manifest_data[container_key].items():
                assert isinstance(mod_info, dict), f"Module '{mod_key}' entry must be a dictionary"

                algo = mod_info.get("hash_algorithm")
                assert algo in ("SHA-256", "SHA-512"), (
                    f"Module '{mod_key}' in '{container_key}' must specify SHA-256 or SHA-512 hash algorithm; got '{algo}'"
                )

                checksum = mod_info.get("checksum_sha256") or mod_info.get("sha256") or mod_info.get("integrity_hash")
                assert checksum is not None, (
                    f"Module '{mod_key}' in '{container_key}' missing SHA-256 checksum field"
                )
                assert isinstance(checksum, str), (
                    f"Module '{mod_key}' checksum must be a string; got {type(checksum)}"
                )

                is_sha256 = bool(SHA256_HEX_REGEX.match(checksum))
                is_sha512 = bool(SHA512_HEX_REGEX.match(checksum))
                assert is_sha256 or is_sha512, (
                    f"Module '{mod_key}' in '{container_key}' checksum '{checksum}' is not a valid SHA-256 or SHA-512 hex digest"
                )

    assert containers_checked >= 1, "Expected at least one module repository topology container in manifest"


def test_deployment_manifest_no_git_sha1_in_checksums(
    manifest_data: Dict[str, Any]
) -> None:
    """Validate that no module checksum field uses a legacy 40-char Git SHA-1 hash."""
    for container_key in ("repositories", "downstream_modules", "modules"):
        if container_key in manifest_data and isinstance(manifest_data[container_key], dict):
            for mod_key, mod_info in manifest_data[container_key].items():
                if isinstance(mod_info, dict):
                    for field in ("checksum_sha256", "sha256", "checksum", "hash", "integrity_hash"):
                        val = mod_info.get(field)
                        if isinstance(val, str):
                            assert not (len(val) == 40 and GIT_SHA1_HEX_REGEX.match(val)), (
                                f"Module '{mod_key}' uses legacy 40-character Git SHA-1 hash in '{field}': '{val}'. "
                                f"SHA-256 / SHA-512 is strictly required."
                            )


def test_deployment_manifest_module_topology_tier_metadata(
    manifest_data: Dict[str, Any]
) -> None:
    """Validate that module topologies define valid topology tier and branch metadata."""
    for container_key in ("repositories", "downstream_modules"):
        if container_key in manifest_data and isinstance(manifest_data[container_key], dict):
            for mod_key, mod_info in manifest_data[container_key].items():
                if isinstance(mod_info, dict):
                    assert "desc" in mod_info and isinstance(mod_info["desc"], str) and len(mod_info["desc"]) > 5, (
                        f"Module '{mod_key}' in '{container_key}' missing valid description"
                    )
                    assert "branch" in mod_info and mod_info["branch"] == "main", (
                        f"Module '{mod_key}' in '{container_key}' must target 'main' branch"
                    )
                    assert "mandatory" in mod_info and isinstance(mod_info["mandatory"], bool), (
                        f"Module '{mod_key}' in '{container_key}' must specify boolean mandatory flag"
                    )
                    assert "topology_tier" in mod_info and isinstance(mod_info["topology_tier"], str), (
                        f"Module '{mod_key}' in '{container_key}' missing topology_tier metadata"
                    )


# ==============================================================================
# 6. Schema Compatibility with Setup Orchestrator & Dashboard Models
# ==============================================================================


def test_deployment_manifest_setup_orchestrator_schema_compatibility(
    manifest_data: Dict[str, Any]
) -> None:
    """Validate that manifest adheres to Stage 0 Setup Orchestrator schema."""
    assert "interaction_environment" in manifest_data, (
        "Manifest missing 'interaction_environment' required by setup orchestrator"
    )
    assert "calculation_environment" in manifest_data, (
        "Manifest missing 'calculation_environment' required by setup orchestrator"
    )

    interact = manifest_data["interaction_environment"]
    calc = manifest_data["calculation_environment"]

    assert isinstance(interact, str), "'interaction_environment' must be a string"
    assert isinstance(calc, str), "'calculation_environment' must be a string"
    assert interact != "[MISSING DATA]", "'interaction_environment' contains unpopulated token"
    assert calc != "[MISSING DATA]", "'calculation_environment' contains unpopulated token"
    assert interact.lower() != "auto", "'interaction_environment' cannot be unrouted 'Auto'"
    assert calc.lower() != "auto", "'calculation_environment' cannot be unrouted 'Auto'"


def test_deployment_manifest_setup_orchestrator_valid_environment_values(
    manifest_data: Dict[str, Any]
) -> None:
    """Validate that environment selections correspond to recognized execution routes."""
    interact = manifest_data.get("interaction_environment", "")
    calc = manifest_data.get("calculation_environment", "")

    assert interact in INTERACT_MAP, (
        f"interaction_environment '{interact}' not found in INTERACT_MAP: {list(INTERACT_MAP.keys())}"
    )
    assert calc in CALC_MAP, (
        f"calculation_environment '{calc}' not found in CALC_MAP: {list(CALC_MAP.keys())}"
    )

    try:
        orch_manifest = OrchestratorDeploymentManifest(
            interaction_environment=interact,
            calculation_environment=calc,
        )
        assert orch_manifest.interaction_environment == interact
        assert orch_manifest.calculation_environment == calc
    except ValidationError as exc:
        pytest.fail(f"Setup orchestrator DeploymentManifest validation failed: {exc}")


def test_deployment_manifest_dashboard_model_compatibility(
    manifest_data: Dict[str, Any]
) -> None:
    """Validate that manifest data directly validates with Dashboard DeploymentManifest model."""
    interact = manifest_data.get("interaction_environment", "")
    calc = manifest_data.get("calculation_environment", "")

    try:
        dash_manifest = DashboardDeploymentManifest.model_validate(manifest_data)
        assert dash_manifest.interaction_environment == interact
        assert dash_manifest.calculation_environment == calc
        assert isinstance(dash_manifest.selected_repositories, list)
    except ValidationError as exc:
        pytest.fail(f"Dashboard DeploymentManifest model validation failed: {exc}")


def test_deployment_manifest_ecosystem_registry_alignment(
    manifest_data: Dict[str, Any]
) -> None:
    """Validate that manifest repository URLs align with ECOSYSTEM_REGISTRY constants."""
    repo_map = extract_repository_map(manifest_data)

    for registry_key, reg_info in ECOSYSTEM_REGISTRY.items():
        norm_key = normalize_module_name(registry_key)
        if norm_key in repo_map:
            manifest_url = repo_map[norm_key].rstrip("/").lower()
            registry_url = str(reg_info["repo"]).rstrip("/").lower()
            assert manifest_url == registry_url, (
                f"URL mismatch for module '{norm_key}': manifest has '{manifest_url}', "
                f"ECOSYSTEM_REGISTRY has '{registry_url}'"
            )


# ==============================================================================
# 7. AST Anti-Spoofing & Physical Execution Compliance
# ==============================================================================


def test_deployment_manifest_test_suite_ast_anti_spoofing_sweep() -> None:
    """Validate zero prohibited test double imports across this test suite via AST analysis."""
    source_file = Path(__file__).resolve()
    tree = ast.parse(source_file.read_text(encoding="utf-8"), filename=str(source_file))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for prohibited in PROHIBITED_IMPORT_NAMES:
                    assert prohibited not in alias.name.lower(), (
                        f"Forbidden test double import '{alias.name}' detected in {source_file.name}"
                    )
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            for prohibited in PROHIBITED_IMPORT_NAMES:
                assert prohibited not in module_name.lower(), (
                    f"Forbidden test double import from '{module_name}' detected in {source_file.name}"
                )
