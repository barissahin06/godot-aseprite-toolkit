"""Bounded native-tool execution and reversible source revisions. No image synthesis."""
from __future__ import annotations
import hashlib
import json
import os
import re
import subprocess
import time
import uuid
from pathlib import Path
from contextlib import contextmanager
from contextvars import ContextVar

_held = ContextVar("art_workspace_locks", default=())

def _inside(root: Path, relative: str) -> Path:
    root = root.resolve()
    value = (root / relative).resolve()
    if Path(relative).is_absolute() or not value.is_relative_to(root):
        raise ValueError("path escapes workspace")
    return value

@contextmanager
def workspace_lock(root: Path):
    root = root.resolve()
    if root in _held.get():
        yield
        return
    lock = root / ".art-operation.lock"
    token = f"{os.getpid()}:{uuid.uuid4().hex}"
    try:
        with lock.open("x", encoding="utf-8") as stream:
            stream.write(token)
    except FileExistsError:
        raise RuntimeError("Another art operation owns .art-operation.lock; inspect its PID before removing a stale lock")
    state = _held.set((*_held.get(), root))
    try:
        recover_publications(root)
        yield
    finally:
        _held.reset(state)
        if lock.is_file() and lock.read_text(encoding="utf-8") == token:
            lock.unlink()

def recover_publications(root: Path) -> list[str]:
    recovered = []
    for record in (root / ".art-history").glob("publish-*/publication.json"):
        data = json.loads(record.read_text(encoding="utf-8"))
        if data["state"] != "prepared":
            continue
        verified = {}
        for name, info in data["files"].items():
            target = _inside(root, name)
            if info is None:
                verified[target] = None
            else:
                blob = _inside(record.parent, info["blob"])
                content = blob.read_bytes()
                if hashlib.sha256(content).hexdigest() != info["sha256"]:
                    raise ValueError("publication backup hash mismatch")
                verified[target] = content
        for target, content in verified.items():
            if content is None:
                target.unlink(missing_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                temp = target.with_name(target.name + ".rollback-tmp")
                temp.write_bytes(content)
                os.replace(temp, target)
        data["state"] = "rolled_back"
        record.write_text(json.dumps(data, indent=2), encoding="utf-8")
        recovered.append(record.parent.name)
    return recovered

def publish(root: Path, writes: dict[Path, bytes]) -> list[str]:
    root = root.resolve()
    with workspace_lock(root):
        changed = {}
        for target, content in writes.items():
            target = target.resolve()
            if not target.is_relative_to(root):
                raise ValueError("publication escapes workspace")
            if not target.is_file() or target.read_bytes() != content:
                changed[target] = content
        if not changed:
            return []
        folder = root / ".art-history" / ("publish-" + uuid.uuid4().hex)
        folder.mkdir(parents=True)
        entries = {}
        for i, target in enumerate(changed):
            name = target.relative_to(root).as_posix()
            entries[name] = None
            if target.is_file():
                content = target.read_bytes()
                blob = f"{i:03d}.bin"
                (folder / blob).write_bytes(content)
                entries[name] = {"blob": blob, "sha256": hashlib.sha256(content).hexdigest()}
        record = folder / "publication.json"
        data = {"state": "prepared", "files": entries}
        record.write_text(json.dumps(data, indent=2), encoding="utf-8")
        try:
            for target, content in changed.items():
                target.parent.mkdir(parents=True, exist_ok=True)
                temp = target.with_name(target.name + ".publish-tmp")
                temp.write_bytes(content)
                os.replace(temp, target)
            data["state"] = "committed"
            record.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except BaseException:
            recover_publications(root)
            raise
        return list(entries)


def run_native(executable: str, args: list[str], cwd: Path, timeout: int = 120) -> dict:
    if not 1 <= timeout <= 600:
        raise ValueError("timeout must be 1..600 seconds")
    start = time.monotonic()
    process = subprocess.Popen([executable, *args], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding="utf-8", errors="replace",
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
        else:
            process.kill()
        stdout, stderr = process.communicate()
        raise RuntimeError(f"Native tool timed out after {timeout}s\n{stdout[-4000:]}{stderr[-4000:]}")
    log = stdout + stderr
    failed = process.returncode != 0 or re.search(r"(?m)^\s*(?:SCRIPT ERROR:|ERROR:|Error:|ASSERTION FAILED)", log)
    if failed:
        raise RuntimeError(log[-16000:] or f"process exited {process.returncode}")
    return {"ok": True, "seconds": round(time.monotonic()-start, 3), "log": log[-16000:]}

def checkpoint(root: Path, paths: list[str], label: str) -> dict:
    if not paths or len(paths)>100:
        raise ValueError("checkpoint requires 1..100 explicit source files")
    sources = {name: _inside(root, name) for name in paths}
    if any(not p.is_file() or p.stat().st_size > 100_000_000 for p in sources.values()):
        raise ValueError("source missing or larger than 100 MB")
    revision = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    folder = root / ".art-history" / revision
    folder.mkdir(parents=True)
    entries = {}
    for i, (name, source) in enumerate(sources.items()):
        data = source.read_bytes()
        saved = f"{i:03d}.bin"
        (folder / saved).write_bytes(data)
        entries[name] = {"blob":saved, "sha256":hashlib.sha256(data).hexdigest()}
    report = {"revision":revision, "label":label, "files":entries}
    (folder / "revision.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report

def restore(root: Path, revision: str) -> dict:
    if not re.fullmatch(r"\d{8}-\d{6}-[a-f0-9]{8}", revision):
        raise ValueError("invalid revision")
    root = root.resolve()
    folder = root / ".art-history" / revision
    report = json.loads((folder / "revision.json").read_text(encoding="utf-8"))
    writes = {}
    for name, info in report["files"].items():
        destination = _inside(root, name)
        if not re.fullmatch(r"\d{3}\.bin", info["blob"]):
            raise ValueError("invalid checkpoint blob")
        data = (folder / info["blob"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != info["sha256"]:
            raise ValueError("checkpoint hash mismatch")
        writes[destination] = data
    existing = [p.relative_to(root).as_posix() for p in writes if p.is_file()]
    backup = checkpoint(root, existing, "before restore " + revision) if existing else None
    publish(root, writes)
    return {"restored":revision, "backup":backup["revision"] if backup else None}

def revisions(root: Path) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted((root / ".art-history").glob("*/revision.json"), reverse=True)]
