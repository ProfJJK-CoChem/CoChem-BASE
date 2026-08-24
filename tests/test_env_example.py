"""Zero-Mock Physical Unit Tests for CoChem-BASE .env.example.

Phase 1, Task 1 - Prompt 4: .env.example Environment Template Verification.
Validates Bipartite Workspace Air-Gap Security Notice, Template Keys,
Empty Key Value Enforcement, Zero Dummy/Mock Values, and Identifier Validity.
"""

from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_EXAMPLE_PATH = REPO_ROOT / ".env.example"
GITIGNORE_PATH = REPO_ROOT / ".gitignore"

EXPECTED_KEYS = [
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "LOCAL_LLAMA_URL",
    "COCHEM_ARTIFACTS_DIR",
    "COCHEM_DATA_DIR",
    "COCHEM_OFFLINE",
    "RESOURCE_GUARD",
    "PUBCHEM_ENDPOINT",
    "COCHEM_EMAIL",
]

EXPECTED_SECTIONS = [
    "1. LLM API Providers & Local Inference Endpoints",
    "2. Data Tier & Artifact Storage Paths",
    "3. Execution Guardrails & Offline Operational Mode",
    "4. Harvester Endpoints & API Contact Information",
]

BANNED_PLACEHOLDERS = [
    "[add keys here]",
    "[insert",
    "[todo",
    "[placeholder",
    "<your_",
    "<api_",
    "your_key",
    "your-key",
    "mock",
    "stub",
    "dummy",
    "fake",
    "sample",
    "todo",
    "fixme",
]


def _get_raw_lines() -> list[str]:
    """Return raw lines from physical .env.example file."""
    return ENV_EXAMPLE_PATH.read_text(encoding="utf-8").splitlines()


def _get_parsed_key_value_pairs() -> dict[str, str]:
    """Parse active (non-comment, non-empty) lines into key-value pairs."""
    pairs: dict[str, str] = {}
    for line in _get_raw_lines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        assert "=" in stripped, f"Invalid environment line syntax (missing '='): {stripped}"
        key, value = stripped.split("=", 1)
        pairs[key.strip()] = value.strip()
    return pairs


def test_env_example_file_exists() -> None:
    """Verify that .env.example exists physically at the root of the repository."""
    assert ENV_EXAMPLE_PATH.exists(), f".env.example must exist at {ENV_EXAMPLE_PATH}"
    assert ENV_EXAMPLE_PATH.is_file(), f"{ENV_EXAMPLE_PATH} must be a regular file"
    assert ENV_EXAMPLE_PATH.stat().st_size > 0, ".env.example must not be empty"


def test_env_example_encoding_no_bom() -> None:
    """Verify that .env.example is UTF-8 encoded without BOM."""
    raw_bytes = ENV_EXAMPLE_PATH.read_bytes()
    assert not raw_bytes.startswith(b"\xef\xbb\xbf"), ".env.example must not contain UTF-8 BOM"
    content = raw_bytes.decode("utf-8")
    assert len(content.strip()) > 0, ".env.example must contain readable text"
    assert "\n" in content, ".env.example must have multi-line formatting"


def test_security_notice_and_data_tier_comment() -> None:
    """Verify that .env.example contains explicit security notices and Data Tier path."""
    content = ENV_EXAMPLE_PATH.read_text(encoding="utf-8")
    assert "SECURITY NOTICE:" in content, "Must contain SECURITY NOTICE header"
    assert "$HOME/CoChem_Artifacts/.env" in content, (
        "Must explicitly specify actual .env location in Data Tier ($HOME/CoChem_Artifacts/.env)"
    )
    assert "template" in content.lower(), "Must state that this file is an empty configuration template"
    assert "never" in content.lower(), "Must state that real keys must never be committed"
    assert "Data Tier" in content, "Must reference the Data Tier architecture"
    assert "Bipartite Workspace Air-Gap" in content, (
        "Must reference the CoChem Bipartite Workspace Air-Gap Architecture"
    )


def test_all_expected_keys_present() -> None:
    """Verify that all 10 required environment template keys exist in .env.example."""
    parsed_pairs = _get_parsed_key_value_pairs()
    active_keys = list(parsed_pairs.keys())

    for expected_key in EXPECTED_KEYS:
        assert (
            expected_key in active_keys
        ), f"Required template key '{expected_key}' missing from .env.example"

    assert len(active_keys) == len(
        EXPECTED_KEYS
    ), f"Expected exactly {len(EXPECTED_KEYS)} active keys, found {len(active_keys)}: {active_keys}"


def test_keys_have_empty_values() -> None:
    """Verify that all template keys have empty values without placeholder text."""
    parsed_pairs = _get_parsed_key_value_pairs()
    for key, value in parsed_pairs.items():
        assert (
            value == ""
        ), f"Template key '{key}' must have an empty value, but has: '{value}'"


def test_no_banned_placeholders_or_dummy_text() -> None:
    """Verify that .env.example contains no banned placeholder strings or dummy markers."""
    content = ENV_EXAMPLE_PATH.read_text(encoding="utf-8").lower()
    for placeholder in BANNED_PLACEHOLDERS:
        assert (
            placeholder not in content
        ), f"Banned placeholder or dummy marker '{placeholder}' found in .env.example"


def test_line_format_and_identifier_validity() -> None:
    """Verify that each active line matches KEY= format with valid uppercase shell/python identifiers."""
    raw_lines = _get_raw_lines()
    active_lines = [
        line.strip()
        for line in raw_lines
        if line.strip() and not line.strip().startswith("#")
    ]

    key_regex = re.compile(r"^[A-Z][A-Z0-9_]*=$")
    seen_keys: set[str] = set()

    for line in active_lines:
        assert key_regex.match(line), f"Line does not match standard 'KEY=' format: '{line}'"
        key_name = line[:-1]
        assert key_name.isidentifier(), f"Key name '{key_name}' is not a valid identifier"
        assert key_name.isupper(), f"Key name '{key_name}' must be uppercase"
        assert key_name not in seen_keys, f"Duplicate key '{key_name}' found in .env.example"
        seen_keys.add(key_name)


def test_comment_sections_structured() -> None:
    """Verify that .env.example contains organized structural section comments."""
    content = ENV_EXAMPLE_PATH.read_text(encoding="utf-8")
    for section in EXPECTED_SECTIONS:
        assert section in content, f"Missing section heading: '{section}'"


def test_airgap_gitignore_enforcement() -> None:
    """Verify that repository .gitignore properly protects artifacts workspace and blocks .env while allowing .env.example."""
    assert GITIGNORE_PATH.exists(), f".gitignore must exist at {GITIGNORE_PATH}"
    gitignore_content = GITIGNORE_PATH.read_text(encoding="utf-8")
    assert "CoChem_Artifacts" in gitignore_content, ".gitignore must block CoChem_Artifacts"
    assert ".env" in gitignore_content, ".gitignore must block .env"
    assert ".env.*" in gitignore_content, ".gitignore must block .env.*"
    assert "!.env.example" in gitignore_content, ".gitignore must explicitly allow .env.example"
