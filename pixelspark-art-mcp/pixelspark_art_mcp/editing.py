"""High-level edits reuse the native authoring tools and publish only complete results."""
from __future__ import annotations

import asyncio
import inspect
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from aseprite_mcp.core.runtime import checkpoint, publish, run_native, workspace_lock
from aseprite_mcp.tools import animation, canvas, palette, slices
from .aseprite import _inside

OPERATIONS = {
    "palette_remap": palette.remap_colors_in_cel_range,
    "cel_position": animation.set_cel_position,
    "cel_opacity": animation.set_cel_opacity,
    "frame_duration": canvas.set_frame_duration,
    "pivot": slices.set_slice_pivot,
    "copy_cel": animation.copy_cel,
}


async def batch_edit(root: Path, source_path: str, operations: list[dict[str, Any]]) -> dict[str, Any]:
    source = _inside(root, source_path)
    if not source.is_file() or source.suffix not in {".aseprite", ".ase"}:
        raise ValueError("Expected an existing native Aseprite source")
    if not 1 <= len(operations) <= 100:
        raise ValueError("Expected 1..100 operations")
    calls = []
    for operation in operations:
        if not isinstance(operation, dict) or set(operation) != {"op", "args"}:
            raise ValueError("Each operation needs op and args")
        function = OPERATIONS.get(operation["op"])
        arguments = operation["args"]
        if function is None or not isinstance(arguments, dict) or "filename" in arguments:
            raise ValueError("Unsupported operation or source override")
        signature = inspect.signature(function)
        signature.bind(filename=str(source), **arguments)
        for name, value in arguments.items():
            expected = signature.parameters[name].annotation
            if expected is int and (not isinstance(value, int) or isinstance(value, bool)):
                raise ValueError(f"{name} must be an integer")
            if expected is str and not isinstance(value, str):
                raise ValueError(f"{name} must be text")
            if expected is bool and not isinstance(value, bool):
                raise ValueError(f"{name} must be boolean")
        if operation["op"] == "frame_duration" and arguments["duration_ms"] <= 0:
            raise ValueError("duration_ms must be positive")
        if operation["op"] == "cel_opacity" and not 0 <= arguments["opacity"] <= 255:
            raise ValueError("opacity must be 0..255")
        calls.append((function, arguments))
    with workspace_lock(root), tempfile.TemporaryDirectory(prefix="art-batch-") as folder:
        working = Path(folder) / source.name
        shutil.copyfile(source, working)
        results = []
        for function, arguments in calls:
            result = await function(filename=working.as_posix(), **arguments)
            if result.startswith(("Failed", "ERROR", "Invalid", "File ", "Mappings", "Duration")):
                raise ValueError(result)
            results.append(result.replace(working.as_posix(), source_path))
        data = working.read_bytes()
        revision = checkpoint(root, [source_path], "before batch edit") if data != source.read_bytes() else None
        changed = publish(root, {source: data})
        return {"ok": True, "changed": changed, "checkpoint": revision, "operations": results}


def edit_motion(root: Path, project: Path, executable: str, library_path: str,
                clip: str, patch: dict[str, Any]) -> dict[str, Any]:
    source = _inside(root, library_path)
    if not source.is_file() or source.suffix != ".tres":
        raise ValueError("Expected an authored AnimationLibrary .tres")
    with workspace_lock(root), tempfile.TemporaryDirectory(prefix="art-motion-") as folder:
        operation = Path(folder) / "patch.json"
        operation.write_text(json.dumps(patch, allow_nan=False), encoding="utf-8")
        output = Path(folder) / "motion.tres"
        result = run_native(executable, ["--headless", "--path", str(project), "--quit-after", "120", "--script",
                            str(Path(__file__).with_name("edit_motion.gd")), "--", str(source),
                            clip, str(operation), str(output)], root)
        if "MOTION_EDIT_OK" not in result["log"] or not output.is_file():
            raise RuntimeError("Incomplete native motion edit; source preserved")
        revision = checkpoint(root, [library_path], "before animation edit")
        changed = publish(root, {source: output.read_bytes()})
        return {"ok": True, "changed": changed, "checkpoint": revision, **result}
