"""Student Google Colab request packaging and advisory local CU accounting.

Provides credential-isolated dispatch token resolution (`COLAB_OFFLOAD_DISPATCH_TOKEN`
bound via `COCHEM_COLAB_ACCESS_SECRET`), HMAC-SHA256 request signing so the
instructor's raw Google Colab OAuth token (`~/.config/colab-cli/token.json`)
never leaves the instructor workstation, GitHub issue relay submission/polling,
and the dynamic monthly Compute Unit (CU) quota ledger (`1,750.0 CUs / max(N_students, 1)`
per `YYYY-MM` calendar month) for student repositories enrolled through
`ProfJJK-CoChem/CoChem-Project-Access`.

The local ledger is advisory accounting; authoritative admission and resource
enforcement require a separately verified receiver. Packaging is not proof of
engine availability, licensing, GPU execution or a scientific result.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import re
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

if __package__:
    from .course_access import BINDING_VARIABLES, CourseAccessError, GitHubAPI, repository_name
    from .student_request import validate_xyz
    from .student_research import _ATOMIC_NUMBERS
else:
    # The metadata-only CLI runs before BASE/scientific dependencies are installed.
    # Load the same contracts beside this file without executing interfaces/__init__.
    import importlib.util
    import sys

    def _source_local_contract(name: str):
        path = Path(__file__).resolve().with_name(name + ".py")
        key = "_cochem_colab_source_" + hashlib.sha256(str(path).encode()).hexdigest()
        cached = sys.modules.get(key)
        if cached is not None:
            if Path(cached.__file__).resolve() != path:
                raise ImportError("The Colab contract cache belongs to another source")
            return cached
        spec = importlib.util.spec_from_file_location(key, path)
        if spec is None or spec.loader is None:
            raise ImportError("The source-local Colab contract is unavailable")
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            sys.modules.pop(key, None)
            raise
        return module

    _course_access = _source_local_contract("course_access")
    BINDING_VARIABLES = _course_access.BINDING_VARIABLES
    CourseAccessError = _course_access.CourseAccessError
    GitHubAPI = _course_access.GitHubAPI
    repository_name = _course_access.repository_name
    validate_xyz = _source_local_contract("student_request").validate_xyz
    _ATOMIC_NUMBERS = _source_local_contract("student_research")._ATOMIC_NUMBERS

SCHEMA_LEDGER = "cochem.student-colab-cu-ledger.v1"
SCHEMA_REQUEST = "cochem.student-colab-request.v1"
SCHEMA_RESULT = "cochem.student-colab-result.v1"
DEFAULT_MONTHLY_POOL_CU = 1750.0
_STUDENT_ID_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\Z")
_JOB_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{3,63}\Z")
_MONTH_RE = re.compile(r"\d{4}-(?:0[1-9]|1[0-2])\Z")
_FORBIDDEN_CREDENTIALS = (
    "token.json",
    ".config/colab-cli",
    "colab auth",
    "colab pay",
    "colab drivemount",
    "drive.mount",
    "/content/drive",
    "google.colab",
)


class ColabQuotaExceededError(CourseAccessError):
    """The student's monthly Google Colab Compute Unit cap has been reached."""


def resolve_colab_dispatch_token(environ: Mapping[str, str] | None = None) -> str:
    """Resolve the scoped Colab offload dispatch token from Codespaces or Actions env.

    Students never receive the instructor's raw `~/.config/colab-cli/token.json`.
    Instead, the controller binds `COCHEM_COLAB_ACCESS_SECRET` (defaulting to
    `COLAB_OFFLOAD_DISPATCH_TOKEN`) on enrolled repositories.
    """
    env = os.environ if environ is None else environ
    secret_name = env.get(BINDING_VARIABLES["colab"], "COLAB_OFFLOAD_DISPATCH_TOKEN").strip()
    if not secret_name:
        secret_name = "COLAB_OFFLOAD_DISPATCH_TOKEN"
    token = (env.get(secret_name) or env.get("COLAB_OFFLOAD_DISPATCH_TOKEN") or "").strip()
    if not token:
        raise CourseAccessError(
            "Google Colab dispatch token is not configured in this environment. "
            "Confirm project enrollment in Connect using an instructor invitation."
        )
    lowered = token.lower()
    if any(marker in lowered for marker in _FORBIDDEN_CREDENTIALS):
        raise CourseAccessError("Refusing raw Colab CLI credential path in student dispatch token.")
    return token


def _canonical_signing_bytes(payload: Mapping[str, Any]) -> bytes:
    """Return canonical UTF-8 JSON bytes for HMAC signing (excluding `hmac_sha256` and `quota`)."""
    signable = {
        key: value
        for key, value in payload.items()
        if key not in {"hmac_sha256", "quota"}
    }
    return json.dumps(signable, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sign_student_colab_request(payload: Mapping[str, Any], dispatch_token: str) -> str:
    """Compute HMAC-SHA256 signature proving possession of `COLAB_OFFLOAD_DISPATCH_TOKEN`."""
    clean_token = dispatch_token.strip()
    if not clean_token:
        raise CourseAccessError("Cannot sign student Colab request with an empty dispatch token.")
    return hmac.new(
        clean_token.encode("utf-8"),
        _canonical_signing_bytes(payload),
        hashlib.sha256,
    ).hexdigest()


def verify_student_colab_request_signature(payload: Mapping[str, Any], dispatch_token: str) -> bool:
    """Constant-time verification of a student Colab request's HMAC-SHA256 signature."""
    provided = str(payload.get("hmac_sha256", "")).strip()
    if not provided or not dispatch_token or not dispatch_token.strip():
        return False
    expected = sign_student_colab_request(payload, dispatch_token)
    return hmac.compare_digest(provided, expected)


@dataclass(frozen=True)
class StudentCuAllowance:
    """Computed monthly Google Colab CU allowance for a single student."""

    student_id: str
    month_key: str
    monthly_pool_cu: float
    active_student_count: int
    per_student_cap_cu: float
    used_cu: float
    remaining_cu: float
    requested_cu: float
    allowed: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "student_id": self.student_id,
            "month_key": self.month_key,
            "monthly_pool_cu": self.monthly_pool_cu,
            "active_student_count": self.active_student_count,
            "per_student_cap_cu": self.per_student_cap_cu,
            "used_cu": self.used_cu,
            "remaining_cu": self.remaining_cu,
            "requested_cu": self.requested_cu,
            "allowed": self.allowed,
            "reason": self.reason,
        }


class MonthlyStudentCuQuotaManager:
    """Enforces `monthly_pool_cu / max(N_students, 1)` per calendar month (`YYYY-MM`)."""

    def __init__(
        self,
        ledger_path: Path,
        *,
        monthly_pool_cu: float = DEFAULT_MONTHLY_POOL_CU,
        org: str = "ProfJJK-CoChem",
        team_slug: str = "students",
        allow_live_gh: bool = False,
    ) -> None:
        if not math.isfinite(monthly_pool_cu) or monthly_pool_cu <= 0:
            raise ValueError("monthly_pool_cu must be a positive finite float.")
        self.ledger_path = Path(ledger_path)
        self.monthly_pool_cu = float(monthly_pool_cu)
        self.org = org
        self.team_slug = team_slug
        self.allow_live_gh = allow_live_gh

    @staticmethod
    def current_month_key(now: datetime | None = None) -> str:
        ts = now or datetime.now(timezone.utc)
        return ts.strftime("%Y-%m")

    def compute_per_student_cap(self, n_students: int) -> float:
        effective = max(int(n_students), 1)
        return round(self.monthly_pool_cu / effective, 4)

    def fetch_live_students_team_members(self) -> list[str]:
        if not self.allow_live_gh:
            return []
        try:
            kwargs: dict[str, Any] = {
                "capture_output": True,
                "text": True,
                "timeout": 15,
                "check": False,
            }
            if os.name == "nt":
                kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            proc = subprocess.run(
                ["gh", "api", f"orgs/{self.org}/teams/{self.team_slug}/members", "--paginate"],
                **kwargs,
            )
            if proc.returncode != 0 or not proc.stdout.strip():
                return []
            payload = json.loads(proc.stdout)
            if not isinstance(payload, list):
                return []
            return sorted(
                {
                    str(item["login"]).strip()
                    for item in payload
                    if isinstance(item, dict) and isinstance(item.get("login"), str) and item["login"].strip()
                }
            )
        except (OSError, ValueError, subprocess.SubprocessError):
            return []

    def _load_or_init(self, month_key: str, *, n_students_override: int | None = None) -> dict[str, Any]:
        if not _MONTH_RE.fullmatch(month_key):
            raise ValueError("month_key must be YYYY-MM.")
        data: dict[str, Any] = {
            "schema": SCHEMA_LEDGER,
            "org": self.org,
            "team_slug": self.team_slug,
            "monthly_pool_cu": self.monthly_pool_cu,
            "active_month": month_key,
            "months": {},
        }
        if self.ledger_path.is_file():
            try:
                loaded = json.loads(self.ledger_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict) and loaded.get("schema") == SCHEMA_LEDGER:
                    data = loaded
            except (OSError, ValueError):
                pass
        data["active_month"] = month_key
        data["monthly_pool_cu"] = self.monthly_pool_cu
        months = data.setdefault("months", {})
        if month_key not in months or not isinstance(months[month_key], dict):
            members = self.fetch_live_students_team_members()
            count = n_students_override if n_students_override is not None else max(len(members), 1)
            months[month_key] = {
                "month_key": month_key,
                "monthly_pool_cu": self.monthly_pool_cu,
                "students_team_count": max(int(count), 1),
                "students_team_members": members,
                "per_student_monthly_cap_cu": self.compute_per_student_cap(max(int(count), 1)),
                "total_used_cu": 0.0,
                "students": {},
            }
        elif n_students_override is not None:
            bucket = months[month_key]
            bucket["students_team_count"] = max(int(n_students_override), 1)
            bucket["per_student_monthly_cap_cu"] = self.compute_per_student_cap(max(int(n_students_override), 1))
        return data

    def _save(self, data: dict[str, Any]) -> None:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.ledger_path.parent / f".{self.ledger_path.name}.{uuid.uuid4().hex}.tmp"
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(self.ledger_path)

    def check_student_allowance(
        self,
        student_id: str,
        requested_cu: float = 0.0,
        *,
        month_key: str | None = None,
        n_students_override: int | None = None,
    ) -> StudentCuAllowance:
        clean_id = student_id.strip()
        if not _STUDENT_ID_RE.fullmatch(clean_id):
            raise ValueError("Invalid student GitHub login.")
        if not math.isfinite(requested_cu) or requested_cu < 0:
            raise ValueError("requested_cu must be a non-negative finite number.")
        m_key = month_key or self.current_month_key()
        data = self._load_or_init(m_key, n_students_override=n_students_override)
        bucket = data["months"][m_key]
        cap = float(bucket["per_student_monthly_cap_cu"])
        count = int(bucket["students_team_count"])
        student_row = bucket.setdefault("students", {}).get(clean_id, {})
        used = round(float(student_row.get("used_cu", 0.0)), 4)
        remaining = round(max(0.0, cap - used), 4)
        allowed = (used + requested_cu) <= (cap + 1e-9)
        reason = (
            f"Approved within {m_key} student cap ({used + requested_cu:.2f}/{cap:.2f} CU)."
            if allowed
            else f"Monthly student CU cap exceeded for {clean_id} in {m_key} ({used + requested_cu:.2f} > {cap:.2f} CU)."
        )
        self._save(data)
        return StudentCuAllowance(
            student_id=clean_id,
            month_key=m_key,
            monthly_pool_cu=self.monthly_pool_cu,
            active_student_count=count,
            per_student_cap_cu=cap,
            used_cu=used,
            remaining_cu=remaining,
            requested_cu=round(float(requested_cu), 4),
            allowed=allowed,
            reason=reason,
        )

    def record_student_cu_usage(
        self,
        student_id: str,
        job_id: str,
        cu_spent: float,
        *,
        month_key: str | None = None,
        n_students_override: int | None = None,
        enforce_cap: bool = True,
    ) -> StudentCuAllowance:
        clean_id = student_id.strip()
        clean_job = job_id.strip()
        if not _STUDENT_ID_RE.fullmatch(clean_id):
            raise ValueError("Invalid student GitHub login.")
        if not _JOB_ID_RE.fullmatch(clean_job):
            raise ValueError("Invalid calculation job_id.")
        if not math.isfinite(cu_spent) or cu_spent < 0:
            raise ValueError("cu_spent must be a non-negative finite number.")
        m_key = month_key or self.current_month_key()
        allowance = self.check_student_allowance(
            clean_id,
            cu_spent,
            month_key=m_key,
            n_students_override=n_students_override,
        )
        if enforce_cap and not allowance.allowed:
            raise ColabQuotaExceededError(allowance.reason)
        data = self._load_or_init(m_key, n_students_override=n_students_override)
        bucket = data["months"][m_key]
        students = bucket.setdefault("students", {})
        entry = students.setdefault(clean_id, {"student_id": clean_id, "used_cu": 0.0, "jobs": []})
        if not any(isinstance(j, dict) and j.get("job_id") == clean_job for j in entry.get("jobs", [])):
            entry["used_cu"] = round(float(entry.get("used_cu", 0.0)) + float(cu_spent), 4)
            entry.setdefault("jobs", []).append(
                {
                    "job_id": clean_job,
                    "cu_spent": round(float(cu_spent), 4),
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                }
            )
            bucket["total_used_cu"] = round(
                sum(float(s.get("used_cu", 0.0)) for s in students.values()),
                4,
            )
        self._save(data)
        return self.check_student_allowance(
            clean_id,
            0.0,
            month_key=m_key,
            n_students_override=n_students_override,
        )


def _validate_colab_scientific_inputs(
    *, geometry_xyz: str, method: str, basis_set: str | None,
    charge: int, multiplicity: int, is_opt: bool, is_freq: bool,
    estimated_cu: float,
) -> tuple[str, str, str | None, float]:
    """Validate data before credential access or advisory ledger mutation.

    This stdlib-only sender accepts canonical plain elements, not nuclear
    isotope/ghost labels. It performs no mass resolution or engine-capability
    inference. Electronic-state rules match the existing scientific job gate.
    """
    if type(charge) is not int:
        raise CourseAccessError("Molecular charge must be an explicit integer, not a boolean or coerced value.")
    if type(multiplicity) is not int or multiplicity < 1:
        raise CourseAccessError("Spin multiplicity must be an explicit positive integer, not a boolean or coerced value.")
    if type(is_opt) is not bool or type(is_freq) is not bool:
        raise CourseAccessError("Optimization and frequency flags must be explicit booleans.")
    specifications: list[str | None] = []
    for label, value in (("method", method), ("basis_set", basis_set)):
        if label == "basis_set" and value is None:
            specifications.append(None)
            continue
        if (not isinstance(value, str) or not value.strip()
                or not value.isprintable()):
            raise CourseAccessError(f"{label} must be a nonempty single-line specification without control characters.")
        specifications.append(value.strip())
    if type(estimated_cu) not in (int, float):
        raise CourseAccessError("Estimated CU must be a finite nonnegative number, not a boolean or coerced value.")
    try:
        clean_estimate = float(estimated_cu)
    except (OverflowError, ValueError):
        raise CourseAccessError("Estimated CU must be a finite nonnegative number.") from None
    if not math.isfinite(clean_estimate) or clean_estimate < 0:
        raise CourseAccessError("Estimated CU must be a finite nonnegative number.")
    if not isinstance(geometry_xyz, str) or not geometry_xyz.strip():
        raise CourseAccessError("A complete plain-element XYZ geometry is required for Colab offload.")
    clean_xyz = geometry_xyz.strip()
    try:
        validate_xyz(clean_xyz.encode("utf-8"))
    except (ValueError, OverflowError) as error:
        raise CourseAccessError("Invalid Colab XYZ geometry: " + str(error)) from error
    labels = [line.split()[0] for line in clean_xyz.removeprefix("\ufeff").splitlines()[2:]]
    if any(label not in _ATOMIC_NUMBERS for label in labels):
        raise CourseAccessError(
            "Colab offload requires canonical plain element symbols; isotope, ghost and unknown labels "
            "are unsupported by this route. Use the existing nuclear-identity calculation route for isotopes."
        )
    electrons = sum(_ATOMIC_NUMBERS[label] for label in labels) - charge
    unpaired = multiplicity - 1
    if electrons <= 0 or unpaired > electrons or (electrons - unpaired) % 2:
        raise CourseAccessError("Molecular charge and spin multiplicity are incompatible with the electron count.")
    return clean_xyz, specifications[0], specifications[1], clean_estimate


def package_student_colab_request(
    *,
    student_id: str,
    job_id: str,
    engine: str,
    method: str,
    geometry_xyz: str,
    basis_set: str | None = None,
    repository: str | None = None,
    estimated_cu: float = 2.5,
    charge: int = 0,
    multiplicity: int = 1,
    is_opt: bool = True,
    is_freq: bool = True,
    quota_manager: MonthlyStudentCuQuotaManager | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Validate, HMAC-sign, and package a student Colab GPU calculation request."""
    if not isinstance(student_id, str) or not isinstance(job_id, str):
        raise CourseAccessError("Student username and job_id must be strings.")
    clean_student = student_id.strip()
    clean_job = job_id.strip()
    if not _STUDENT_ID_RE.fullmatch(clean_student):
        raise CourseAccessError("Invalid student GitHub username for Colab offload.")
    if not _JOB_ID_RE.fullmatch(clean_job):
        raise CourseAccessError("Invalid job_id for Colab offload.")
    if not isinstance(engine, str):
        raise CourseAccessError("Calculation engine must be a string.")
    clean_engine = engine.strip().upper()
    if clean_engine not in {"ORCA", "CFOUR", "XTB", "PYSCF"}:
        raise CourseAccessError("Unsupported calculation engine for student Colab offload.")
    clean_xyz, clean_method, clean_basis, clean_estimate = _validate_colab_scientific_inputs(
        geometry_xyz=geometry_xyz, method=method, basis_set=basis_set,
        charge=charge, multiplicity=multiplicity, is_opt=is_opt, is_freq=is_freq,
        estimated_cu=estimated_cu,
    )
    if repository is not None and not isinstance(repository, str):
        raise CourseAccessError("Repository must be a repository-name string or None.")
    clean_repo = repository_name(repository) if repository else None
    lowered = f"{clean_job}\n{method}\n{basis_set or ''}\n{geometry_xyz}".lower()
    if any(marker in lowered for marker in _FORBIDDEN_CREDENTIALS):
        raise CourseAccessError("Credential isolation check refused forbidden path or Drive reference.")

    token = resolve_colab_dispatch_token(environ)
    token_fingerprint = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]

    allowance_dict: dict[str, Any] | None = None
    if quota_manager is not None:
        allowance = quota_manager.record_student_cu_usage(
            clean_student,
            clean_job,
            clean_estimate,
            enforce_cap=True,
        )
        allowance_dict = allowance.to_dict()

    payload: dict[str, Any] = {
        "schema": SCHEMA_REQUEST,
        "job_id": clean_job,
        "student_id": clean_student,
        "repository": clean_repo,
        "engine": clean_engine,
        "method": clean_method,
        "basis_set": clean_basis,
        "charge": charge,
        "multiplicity": multiplicity,
        "is_opt": is_opt,
        "is_freq": is_freq,
        "estimated_cu": round(clean_estimate, 4),
        "geometry_xyz": clean_xyz,
        "geometry_sha256": hashlib.sha256(clean_xyz.encode("utf-8")).hexdigest(),
        "dispatch_token_fingerprint": token_fingerprint,
        "binding_variable": BINDING_VARIABLES["colab"],
    }
    payload["hmac_sha256"] = sign_student_colab_request(payload, token)
    payload["quota"] = allowance_dict
    return payload


def parse_student_colab_request(text: str) -> dict[str, Any]:
    """Parse a `cochem.student-colab-request.v1` JSON block from a GitHub issue body."""
    if not isinstance(text, str) or not text.strip():
        raise CourseAccessError("Empty student Colab request body.")
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, flags=re.DOTALL)
    raw_json = fence.group(1) if fence else cleaned
    try:
        data = json.loads(raw_json)
    except ValueError as exc:
        raise CourseAccessError("Student Colab request body is not valid JSON.") from exc
    if not isinstance(data, dict) or data.get("schema") != SCHEMA_REQUEST:
        raise CourseAccessError("Issue body is not a cochem.student-colab-request.v1 payload.")
    return data


def submit_student_colab_issue(
    api: GitHubAPI,
    controller_repository: str,
    packaged_request: Mapping[str, Any],
) -> dict[str, Any]:
    """Submit a signed `cochem.student-colab-request.v1` job to the controller repository's issue queue."""
    ctrl = repository_name(controller_repository)
    if packaged_request.get("schema") != SCHEMA_REQUEST or not packaged_request.get("hmac_sha256"):
        raise CourseAccessError("Only a signed cochem.student-colab-request.v1 payload may be submitted.")
    job_id = str(packaged_request["job_id"])
    student_id = str(packaged_request["student_id"])
    engine = str(packaged_request["engine"])
    method = str(packaged_request["method"])
    body = (
        f"### CoChem Student Google Colab GPU Request (`{job_id}`)\n\n"
        f"- **Student:** `{student_id}`\n"
        f"- **Engine / Method:** `{engine}` / `{method}`\n\n"
        f"```json\n{json.dumps(dict(packaged_request), indent=2, sort_keys=True)}\n```\n"
    )
    owner, repo = ctrl.split("/", 1)
    issue = api.request_json(
        "POST",
        f"/repos/{owner}/{repo}/issues",
        {
            "title": f"CoChem Colab GPU job: {job_id} ({student_id})",
            "body": body,
        },
    )
    return {
        "controller_repository": ctrl,
        "issue_number": int(issue["number"]),
        "html_url": str(issue.get("html_url", "")),
        "job_id": job_id,
        "status": "submitted",
    }
