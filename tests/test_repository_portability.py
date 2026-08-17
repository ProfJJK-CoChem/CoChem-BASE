import ast
import re
from pathlib import Path
from typing import Iterator

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EXTERNAL_COMMANDS = {
    "apt-get",
    "bash",
    "conda",
    "curl",
    "git",
    "mpiexec",
    "mpirun",
    "nvidia-smi",
    "powershell",
    "pwsh",
    "qcxms",
    "sbatch",
    "sudo",
    "tar",
    "wsl",
    "wsl.exe",
}
FORBIDDEN_POSIX_PREFIXES = tuple(
    "/" + "/".join(parts) + suffix
    for parts, suffix in (
        (("dev", "shm"), ""),
        (("home",), "/"),
        (("mnt",), "/"),
        (("opt",), "/"),
        (("proc",), "/"),
        (("tmp",), "/"),
        (("usr", "local"), "/"),
        (("workspaces",), ""),
    )
)


def python_files() -> Iterator[Path]:
    for path in REPOSITORY_ROOT.rglob("*.py"):
        if "__pycache__" not in path.parts and ".egg-info" not in path.as_posix():
            yield path


def call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        owner = node.func.value
        if isinstance(owner, ast.Name):
            return f"{owner.id}.{node.func.attr}"
        return node.func.attr
    return ""


def literal_command(node: ast.Call) -> str:
    if not node.args or call_name(node) not in {
        "subprocess.run",
        "subprocess.Popen",
        "safe_subprocess_run",
        "create_subprocess_exec",
    }:
        return ""
    command = node.args[0]
    if isinstance(command, (ast.List, ast.Tuple)) and command.elts:
        first = command.elts[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            return first.value
    return ""


def test_all_python_files_are_machine_agnostic() -> None:
    failures = []
    files = list(python_files())
    assert files

    for path in files:
        relative_path = path.relative_to(REPOSITORY_ROOT)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(relative_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                value = node.value
                if re.match(r"^[A-Za-z]:[\\/]", value):
                    failures.append(f"{relative_path}:{node.lineno}: Windows absolute path: {value!r}")
                if value.startswith(FORBIDDEN_POSIX_PREFIXES):
                    failures.append(f"{relative_path}:{node.lineno}: POSIX absolute path: {value!r}")
            if isinstance(node, ast.Call):
                name = call_name(node)
                if name in {"Path.cwd", "os.getcwd"}:
                    failures.append(f"{relative_path}:{node.lineno}: current-directory dependency: {name}")
                command = literal_command(node)
                if command.lower() in EXTERNAL_COMMANDS:
                    failures.append(f"{relative_path}:{node.lineno}: unmapped executable: {command}")

    assert not failures, "\n" + "\n".join(failures)
