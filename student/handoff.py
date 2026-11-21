"""Verify or stage a CoChem teaching handoff using only the standard library."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import tempfile
import zipfile

SCHEMA = "cochem.student-conformer-handoff/1"
ALLOWED = {"H": 1, "C": 6, "N": 7, "O": 8}
CORE = {"input.xyz", "crest_conformers.xyz", "crest.log", "engines.json", "ranking.json",
        "pyscf.json", "pyscf.log", "refined.xyz"}


def frames(text, energy=False):
    lines = text.strip().splitlines()
    offset = 0
    parsed = []
    while offset < len(lines):
        n = int(lines[offset])
        end = offset + n + 2
        if not 2 <= n <= 16 or end > len(lines) or len(parsed) >= 32:
            raise ValueError("Expected 2â€“16 atoms per frame and at most 32 complete frames")
        symbols, coords = [], []
        for row in lines[offset+2:end]:
            symbol, x, y, z = row.split()
            xyz = [float(value) for value in (x, y, z)]
            if symbol not in ALLOWED or not all(math.isfinite(v) for v in xyz):
                raise ValueError("Expected H/C/N/O and finite angstrom coordinates")
            coords.append(xyz)
            symbols.append(symbol)
        if sum(ALLOWED[s] for s in symbols) % 2:
            raise ValueError("Neutral singlet requires an even electron count")
        value = float(lines[offset+1].split()[0]) if energy else None
        if energy and not math.isfinite(value):
            raise ValueError("Missing finite CREST energy")
        parsed.append({"symbols": symbols, "coords": coords, "energy": value,
                       "text": "\n".join(lines[offset:end]) + "\n"})
        offset = end
    if not parsed:
        raise ValueError("Empty XYZ")
    return parsed


def read_input(path):
    if path.stat().st_size > 8192:
        raise ValueError("Starting XYZ exceeds 8 KiB")
    rows = frames(path.read_text(encoding="ascii"))
    if len(rows) != 1:
        raise ValueError("Supply exactly one starting geometry")
    return rows[0]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def seal(directory, output, receipt):
    files = sorted(p for p in directory.rglob("*") if p.is_file())
    inventory = {p.relative_to(directory).as_posix(): digest(p.read_bytes()) for p in files}
    manifest = {"schema": SCHEMA, **receipt, "files_sha256": inventory}
    output.mkdir(parents=True, exist_ok=True)
    name = f"CoChem-{receipt['input_name'][:-4]}-{receipt['run_id']}-{receipt['attempt']}.zip"
    target = output / name
    with zipfile.ZipFile(target, "x", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("handoff.json", json.dumps(manifest, indent=2, allow_nan=False) + "\n")
        for p in files:
            archive.write(p, p.relative_to(directory).as_posix())
    verify(target)
    (output / (name + ".sha256")).write_text(f"{digest(target.read_bytes())}  {name}\n", encoding="ascii")


def verify(path, destination=None, expected_sha256=None):
    if path.stat().st_size > 32 * 1024**2:
        raise ValueError("Archive exceeds 32 MiB")
    with path.open("rb") as stream:
        archive_hash = hashlib.file_digest(stream, "sha256").hexdigest()
        if expected_sha256 is not None and archive_hash != expected_sha256.lower():
            raise ValueError("Archive does not match the expected producer SHA-256")
        stream.seek(0)
        with zipfile.ZipFile(stream) as archive:
            return verify_contents(archive, destination, archive_hash)


def verify_contents(archive, destination, archive_hash):
    infos = archive.infolist()
    names = {i.filename for i in infos}
    if (len(names) != len(infos) or len(infos) > 41 or "handoff.json" not in names
            or sum(i.file_size for i in infos) > 64 * 1024**2):
        raise ValueError("Invalid or oversized handoff inventory")
    receipt = json.loads(archive.read("handoff.json"))
    n = receipt["candidate_count"]
    if receipt.get("schema") != SCHEMA or type(n) != int or not 1 <= n <= 32:
        raise ValueError("Unrecognized handoff schema or candidate count")
    if (receipt.get("charge") != 0 or receipt.get("multiplicity") != 1
            or receipt.get("length_unit") != "angstrom"
            or not re.fullmatch(r"[0-9a-f]{40}", receipt.get("commit", ""))):
        raise ValueError("Invalid molecular state, units or producing revision")
    isomers = [f"isomers/crest-{i:03}.xyz" for i in range(1, n+1)]
    expected = CORE | set(isomers)
    checksums = receipt["files_sha256"]
    if set(checksums) != expected or names != expected | {"handoff.json"}:
        raise ValueError("Unexpected, duplicate or missing archive members")
    for name in sorted(expected):
        if digest(archive.read(name)) != checksums[name]:
            raise ValueError(f"SHA-256 mismatch for {name}")
    starting = frames(archive.read("input.xyz").decode("ascii"))
    native = frames(archive.read("crest_conformers.xyz").decode("ascii"), energy=True)
    ranking = json.loads(archive.read("ranking.json"))
    candidates = ranking["candidates"]
    if (len(starting) != 1 or len(native) != n or len(candidates) != n
            or [c["xyz"] for c in candidates] != isomers):
        raise ValueError("Candidate count/order disagrees with native CREST ensemble")
    for name, frame, candidate in zip(isomers, native, candidates):
        result = candidate["mace"]
        if (archive.read(name) != frame["text"].encode("ascii") or frame["symbols"] != starting[0]["symbols"]
                or frame["energy"] != candidate["crest_energy_hartree"] or result["status"] != "SUCCESS"
                or not math.isfinite(result["energy_hartree"]) or result["checkpoint_sha256"] != ranking["model_sha256"]):
            raise ValueError(f"Inconsistent science record for {name}")
        check_gradient(result["gradient_hartree_per_bohr"], len(frame["symbols"]))
    selected = min(candidates, key=lambda c: c["mace"]["energy_hartree"])["xyz"]
    final = json.loads(archive.read("pyscf.json"))
    refined = frames(archive.read("refined.xyz").decode("ascii"), energy=True)
    if (selected != receipt["selected"] or selected != ranking["selected"] or len(refined) != 1
            or refined[0]["symbols"] != starting[0]["symbols"] or receipt["refined_xyz"] != "refined.xyz"
            or not math.isclose(refined[0]["energy"], final["energy_hartree"], rel_tol=0, abs_tol=1e-12)
            or final["method"] != "RHF" or final["basis"] != "STO-3G"
            or final["optimizer_converged"] is not True or final["scf_converged"] is not True):
        raise ValueError("Final PySCF result or selection does not agree with the handoff")
    check_gradient(final["gradient_hartree_per_bohr"], len(starting[0]["symbols"]))
    if destination is not None:
        destination.mkdir(parents=True, exist_ok=True)
        target = destination / archive_hash
        with tempfile.TemporaryDirectory(dir=destination) as tmp:
            stage = Path(tmp) / "contents"
            for name in sorted(names):
                out = stage / name
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(archive.read(name))
            if not target.exists() and not target.is_symlink():
                try:
                    stage.rename(target)
                except OSError:
                    if not target.exists():
                        raise
            if target.is_symlink() or not target.is_dir():
                raise ValueError("Expected a regular staging directory")
            existing = list(target.rglob("*"))
            if (any(f.is_symlink() for f in existing)
                    or {f.relative_to(target).as_posix() for f in existing if f.is_file()} != names
                    or any(digest((target / name).read_bytes()) != checksums[name] for name in expected)
                    or (target / "handoff.json").read_bytes() != archive.read("handoff.json")):
                raise ValueError("An existing received bundle differs on disk")
        print(f"Staged {n} CREST isomer(s) and refined.xyz in {target}")
    return receipt


def check_gradient(gradient, atoms):
    if len(gradient) != atoms or any(len(row) != 3 or not all(math.isfinite(v) for v in row) for row in gradient):
        raise ValueError("Invalid gradient dimensions or nonfinite gradient")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--expected-sha256", help="ZIP digest from the producer's Actions summary")
    parser.add_argument("--stage", type=Path, help="Write verified inputs into a digest-named directory")
    args = parser.parse_args()
    print(json.dumps(verify(args.archive, args.stage, args.expected_sha256), indent=2))
