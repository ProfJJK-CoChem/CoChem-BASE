"""Real HTTP and CLI-process protocol controls; no live GitHub/engine claims."""
import json
import os
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from scripts.configure_lab_project import (
    SELECTOR_VARIABLES,
    GitHubCLI,
    ProjectConfigurationError,
    configure_project,
    main,
)

REPOSITORY = "student/chemistry-project"
CREDENTIAL = "STUDENT_ARCHIVE_READ"
_SERVICES = []


@pytest.fixture(autouse=True)
def close_protocol_services():
    start = len(_SERVICES)
    yield
    for control in _SERVICES[start:]:
        control.close()
    del _SERVICES[start:]


class APIControl:
    """A local HTTP protocol service contacted by actual isolated CLI processes."""

    def __init__(self):
        self.calls = []
        self.account = {"login": "student"}
        self.project = {"private": True, "visibility": "private", "full_name": REPOSITORY,
                        "owner": {"login": "student", "type": "User"}}
        self.permissions = {"enabled": True}
        self.secret_pages = [{"secrets": [{"name": CREDENTIAL}]}]
        self.variables = {}
        self.failure = None
        self.variable_reads = 0
        self.bad_readback = False
        self.separator = "\n"
        self.raw_response = None
        self._directory = tempfile.TemporaryDirectory(prefix="cochem-project-api-control-")
        self._program = Path(self._directory.name) / "protocol_cli.py"
        self._program.write_text('''import json,sys,urllib.error,urllib.request
base=sys.argv[1]; arguments=sys.argv[2:]
assert arguments[:4]==['api','--hostname','github.com','--method']
method,endpoint=arguments[4:6]
data=sys.stdin.buffer.read() if '--input' in arguments else None
request=urllib.request.Request(base+'/'+endpoint,data=data,method=method,
    headers={'Content-Type':'application/json'})
try:
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request,timeout=5) as response:
        sys.stdout.buffer.write(response.read())
except urllib.error.HTTPError as error:
    sys.stderr.buffer.write(error.read()); raise SystemExit(1)
''', encoding="utf-8")
        control = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                return None

            def do_GET(self):
                self.respond("GET")

            def do_POST(self):
                self.respond("POST")

            def do_PATCH(self):
                self.respond("PATCH")

            def respond(self, method):
                endpoint = self.path.removeprefix("/")
                if control.failure and control.failure(method, endpoint):
                    self.send_response(403)
                    self.end_headers()
                    self.wfile.write(("Protocol denial diagnostic: " + CREDENTIAL).encode())
                    return
                if method != "GET":
                    body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                    control.variables[body["name"]] = body["value"]
                    raw = ""
                elif control.raw_response is not None:
                    raw = control.raw_response
                elif endpoint == "user":
                    raw = json.dumps(control.account)
                elif endpoint == "repos/" + REPOSITORY:
                    raw = json.dumps(control.project)
                elif endpoint.endswith("/actions/permissions"):
                    raw = json.dumps(control.permissions)
                elif endpoint.endswith("/actions/secrets"):
                    raw = control.separator.join(json.dumps(page, indent=2) for page in control.secret_pages)
                elif endpoint.endswith("/actions/variables"):
                    control.variable_reads += 1
                    values = control.variables.copy()
                    if control.bad_readback and control.variable_reads > 1:
                        values[SELECTOR_VARIABLES[0]] = "UNEXPECTED_PRIVATE_IDENTIFIER"
                    raw = json.dumps({"variables": [{"name": name, "value": value}
                                                    for name, value in values.items()]})
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.end_headers()
                self.wfile.write(raw.encode("utf-8"))

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever,
                                        kwargs={"poll_interval": 0.01}, daemon=True)
        self._thread.start()
        _SERVICES.append(self)

    def close(self):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=3)
        assert not self._thread.is_alive()
        self._directory.cleanup()

    def run(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        assert kwargs["capture_output"] is True
        assert kwargs["check"] is False
        assert kwargs["timeout"] == 60
        assert "shell" not in kwargs
        assert argv[:6] == ["gh", "api", "--hostname", "github.com", "--method", argv[5]]
        if argv[5] != "GET":
            assert argv[7:] == ["--input", "-"]
            assert CREDENTIAL not in argv
        else:
            assert kwargs["input"] is None
        environment = {key: value for key, value in os.environ.items()
                       if key.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TMP", "TEMP"}}
        return subprocess.run([sys.executable, "-I", "-B", str(self._program),
                               f"http://127.0.0.1:{self._server.server_port}", *argv[1:]],
                              env=environment, **kwargs)

    def client(self):
        return GitHubCLI(run=self.run)


def test_personal_owner_creates_two_selectors_via_json_stdin():
    control = APIControl()
    result = configure_project(REPOSITORY, CREDENTIAL.lower(), client=control.client())
    writes = [(argv[5], json.loads(kwargs["input"])) for argv, kwargs in control.calls if argv[5] != "GET"]
    assert writes == [("POST", {"name": name, "value": CREDENTIAL}) for name in SELECTOR_VARIABLES]
    assert control.variable_reads == 2
    assert result["configuration_status"] == "configured"
    assert result["variable_writes_completed"] == list(SELECTOR_VARIABLES)
    assert result["archive_access_verified"] is False
    assert result["scientific_acceptance"] == "not-run"
    assert CREDENTIAL not in json.dumps(result)


def test_existing_selectors_are_updated_and_matching_selectors_are_not_rewritten():
    control = APIControl()
    control.variables = {SELECTOR_VARIABLES[0]: CREDENTIAL, SELECTOR_VARIABLES[1]: "OTHER_PRIVATE_CREDENTIAL"}
    result = configure_project(REPOSITORY, CREDENTIAL, client=control.client())
    writes = [(argv, kwargs) for argv, kwargs in control.calls if argv[5] != "GET"]
    assert len(writes) == 1
    assert writes[0][0][5:7] == ["PATCH", f"repos/{REPOSITORY}/actions/variables/{SELECTOR_VARIABLES[1]}"]
    assert result["variable_writes_completed"] == [SELECTOR_VARIABLES[1]]


@pytest.mark.parametrize("repository", ["student", "student/a/b", "student/proj;echo", "--student/project", "student../project"])
def test_malformed_repositories_make_no_api_requests(repository):
    control = APIControl()
    with pytest.raises(ProjectConfigurationError):
        configure_project(repository, CREDENTIAL, client=control.client())
    assert control.calls == []


@pytest.mark.parametrize("name", ["3PRIVATE_NAME", "BAD-NAME", "GITHUB_RESERVED", "PRIVATE\nNAME", "$(printf bad)"])
def test_malformed_selectors_are_never_echoed_or_submitted(name):
    control = APIControl()
    with pytest.raises(ProjectConfigurationError) as captured:
        configure_project(REPOSITORY, name, client=control.client())
    assert name not in str(captured.value)
    assert control.calls == []


@pytest.mark.parametrize("mutation", [
    lambda c: c.project.update(private=False, visibility="public"),
    lambda c: c.project["owner"].update(type="Organization"),
    lambda c: c.project["owner"].update(login="other-student"),
    lambda c: c.account.update(login="instructor"),
    lambda c: c.project.update(full_name="student/other-project"),
    lambda c: c.project.update(archived=True),
    lambda c: c.permissions.update(enabled=False),
])
def test_privacy_ownership_and_actions_preflight_refuse_before_writes(mutation):
    control = APIControl()
    mutation(control)
    with pytest.raises(ProjectConfigurationError) as captured:
        configure_project(REPOSITORY, CREDENTIAL, client=control.client())
    assert captured.value.phase == "preflight"
    assert all(argv[5] == "GET" for argv, _ in control.calls)


def test_missing_selected_secret_refuses_before_variable_writes():
    control = APIControl()
    control.secret_pages = [{"secrets": []}]
    with pytest.raises(ProjectConfigurationError, match="does not exist"):
        configure_project(REPOSITORY, CREDENTIAL, client=control.client())
    assert all(argv[5] == "GET" for argv, _ in control.calls)


def test_secret_inventory_uses_all_pages():
    control = APIControl()
    control.secret_pages = [{"secrets": []}, {"secrets": [{"name": CREDENTIAL}]}]
    assert configure_project(REPOSITORY, CREDENTIAL, client=control.client())["configuration_status"] == "configured"


@pytest.mark.parametrize("separator", ["", "\n", " \n\t "])
def test_paginated_cli_decodes_multiple_formatted_json_documents_without_slurp(separator):
    pages = [{"secrets": []}, {"secrets": [{"name": CREDENTIAL}]}]
    control = APIControl()
    control.secret_pages = pages
    control.separator = separator
    result = control.client().request(f"repos/{REPOSITORY}/actions/secrets", paginate=True)
    assert result == pages
    assert [argv for argv, _ in control.calls] == [["gh", "api", "--hostname", "github.com", "--method", "GET",
                                                  f"repos/{REPOSITORY}/actions/secrets", "--paginate"]]
    assert CREDENTIAL not in control.calls[0][0]


@pytest.mark.parametrize("malformed", [
    '{"secrets": []}\ntrailing-private-diagnostic',
    '{"secrets": []}\n{"secrets": [',
    'private-diagnostic\n{"secrets": []}',
])
def test_paginated_cli_rejects_partial_or_malformed_output_without_echo(malformed):
    control = APIControl()
    control.raw_response = malformed
    with pytest.raises(ProjectConfigurationError) as captured:
        control.client().request(f"repos/{REPOSITORY}/actions/secrets", paginate=True)
    assert "private-diagnostic" not in str(captured.value)
    assert CREDENTIAL not in str(captured.value)


def test_actions_authorization_error_is_sanitized_and_precedes_any_writes():
    control = APIControl()
    control.failure = lambda method, endpoint: endpoint.endswith("/actions/secrets")
    with pytest.raises(ProjectConfigurationError) as captured:
        configure_project(REPOSITORY, CREDENTIAL, client=control.client())
    assert CREDENTIAL not in json.dumps(captured.value.report())
    assert all(argv[5] == "GET" for argv, _ in control.calls)


@pytest.mark.parametrize("failed_write,completed", [(1, []), (2, [SELECTOR_VARIABLES[0]])])
def test_failed_writes_report_completed_and_attempted_variables_without_rollback_claim(failed_write, completed):
    control = APIControl()
    writes = 0

    def failure(method, endpoint):
        nonlocal writes
        if method != "GET":
            writes += 1
            return writes == failed_write
        return False

    control.failure = failure
    with pytest.raises(ProjectConfigurationError) as captured:
        configure_project(REPOSITORY, CREDENTIAL, client=control.client())
    report = captured.value.report()
    assert report["configuration_status"] == "incomplete"
    assert report["phase"] == "variable-write"
    assert report["variable_writes_completed"] == completed
    assert report["variables_attempted"] == list(SELECTOR_VARIABLES[:failed_write])
    assert report["changes_may_have_occurred"] is True
    assert CREDENTIAL not in json.dumps(report)


@pytest.mark.parametrize("unavailable", [False, True])
def test_readback_failure_retains_successful_write_status_without_claiming_configuration(unavailable):
    control = APIControl()
    control.bad_readback = not unavailable
    if unavailable:
        control.failure = lambda method, endpoint: method == "GET" and endpoint.endswith("/actions/variables") and control.variable_reads == 1
    with pytest.raises(ProjectConfigurationError) as captured:
        configure_project(REPOSITORY, CREDENTIAL, client=control.client())
    report = captured.value.report()
    assert report["phase"] == "readback"
    assert report["variable_writes_completed"] == list(SELECTOR_VARIABLES)
    assert CREDENTIAL not in json.dumps(report)


def test_check_only_accepts_different_existing_engine_credentials_without_writes():
    control = APIControl()
    second = "STUDENT_SECOND_ARCHIVE_READ"
    control.secret_pages[0]["secrets"].append({"name": second})
    control.variables = dict(zip(SELECTOR_VARIABLES, [CREDENTIAL, second], strict=True))
    result = configure_project(REPOSITORY, check_only=True, client=control.client())
    assert result["configuration_status"] == "checked"
    assert result["variable_writes_completed"] == []
    assert all(argv[5] == "GET" for argv, _ in control.calls)
    assert CREDENTIAL not in json.dumps(result)
    assert second not in json.dumps(result)


@pytest.mark.parametrize("variables", [
    {},
    dict.fromkeys(SELECTOR_VARIABLES, "MISSING_PRIVATE_CREDENTIAL"),
    dict.fromkeys(SELECTOR_VARIABLES, "NOT-A-SECRET-NAME"),
])
def test_check_only_refuses_missing_or_invalid_selectors_without_writes(variables):
    control = APIControl()
    control.variables = variables
    with pytest.raises(ProjectConfigurationError):
        configure_project(REPOSITORY, check_only=True, client=control.client())
    assert all(argv[5] == "GET" for argv, _ in control.calls)


def test_check_only_expected_credential_must_match_existing_selectors():
    control = APIControl()
    control.secret_pages[0]["secrets"].append({"name": "OTHER_PRIVATE_CREDENTIAL"})
    control.variables = dict.fromkeys(SELECTOR_VARIABLES, "OTHER_PRIVATE_CREDENTIAL")
    with pytest.raises(ProjectConfigurationError, match="do not match"):
        configure_project(REPOSITORY, CREDENTIAL, check_only=True, client=control.client())
    assert all(argv[5] == "GET" for argv, _ in control.calls)


def test_configure_requires_explicit_existing_secret_name_before_api_reads():
    control = APIControl()
    with pytest.raises(ProjectConfigurationError, match="requires"):
        configure_project(REPOSITORY, client=control.client())
    assert control.calls == []


@pytest.mark.parametrize("failure", ["missing-program", "real-timeout"])
def test_unavailable_gh_is_sanitized(failure):
    def unavailable(*args, **kwargs):
        command = ([str(Path(tempfile.gettempdir()) / (CREDENTIAL + "-absent-program"))]
                   if failure == "missing-program" else
                   [sys.executable, "-I", "-c", "import time; time.sleep(5)"])
        return subprocess.run(command, capture_output=True, text=True, check=False, timeout=0.05)

    with pytest.raises(ProjectConfigurationError) as captured:
        configure_project(REPOSITORY, CREDENTIAL, client=GitHubCLI(run=unavailable))
    assert CREDENTIAL not in str(captured.value)
    assert "private diagnostic" not in str(captured.value)


def test_cli_success_and_failure_never_print_private_identifier(capsys):
    control = APIControl()
    assert main(["--repository", REPOSITORY, "--credential-name", CREDENTIAL], client=control.client()) == 0
    output = capsys.readouterr()
    assert json.loads(output.out)["configuration_status"] == "configured"
    assert CREDENTIAL not in output.out + output.err
    control.failure = lambda method, endpoint: endpoint.endswith("/actions/secrets")
    assert main(["--repository", REPOSITORY, "--check-only"], client=control.client()) == 2
    output = capsys.readouterr()
    assert json.loads(output.err)["configuration_status"] == "incomplete"
    assert CREDENTIAL not in output.out + output.err


def test_cli_argument_errors_do_not_echo_private_identifiers(capsys):
    with pytest.raises(SystemExit) as captured:
        main(["--repository", REPOSITORY, "--unexpected", CREDENTIAL])
    assert captured.value.code == 2
    assert CREDENTIAL not in capsys.readouterr().err
