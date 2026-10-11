"""Turn an Aseprite layer/slice document into a Godot cutout rig."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import struct
import tempfile
from pathlib import Path
from typing import Any
from aseprite_mcp.core.runtime import publish, run_native, workspace_lock

from .core import _vec2, generate_scene, validate_manifest

NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _inside(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("recipe paths must be relative")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"path escapes repository: {relative}")
    return path


def _run(executable: Path, args: list[str]) -> None:
    run_native(str(executable), ["--batch", *args], Path.cwd(), 90)


def _png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        header = stream.read(26)
    if header[:8] != PNG_SIGNATURE or header[12:16] != b"IHDR" or len(header) != 26:
        raise ValueError(f"invalid PNG: {path.name}")
    width, height, depth, color = struct.unpack(">IIBB", header[16:26])
    if depth != 8 or color != 6:
        raise ValueError(f"{path.name} must be 8-bit RGBA")
    return width, height


def _slices(meta: dict[str, Any], expected: set[str]) -> dict[str, tuple[list[int], int]]:
    found: dict[str, tuple[list[int], int]] = {}
    for item in meta.get("slices", []):
        name = item.get("name")
        if name not in expected:
            continue
        keys = item.get("keys", [])
        if not keys or keys[0].get("frame") != 0 or "pivot" not in keys[0]:
            raise ValueError(f"slice {name} needs a frame 1 pivot")
        positions = []
        for key in keys:
            bounds, pivot = key["bounds"], key.get("pivot")
            if pivot is None:
                raise ValueError(f"slice {name} has a key without pivot")
            positions.append([bounds["x"] + pivot["x"], bounds["y"] + pivot["y"]])
        if any(position != positions[0] for position in positions):
            raise ValueError(f"slice {name} moves its joint across frames")
        if name in found:
            raise ValueError(f"duplicate slice: {name}")
        bounds = keys[0]["bounds"]
        found[name] = (positions[0], max(bounds["w"], bounds["h"]))
    if set(found) != expected:
        raise ValueError(f"missing pivot slices: {sorted(expected - set(found))}")
    return found


def _ordered_parts(parts: dict[str, Any]) -> list[str]:
    ordered: list[str] = []
    visiting: set[str] = set()

    def visit(name: str) -> None:
        if name in ordered:
            return
        if name in visiting:
            raise ValueError(f"bone hierarchy cycle: {name}")
        visiting.add(name)
        parent = parts[name].get("parent")
        if parent != "root":
            if parent not in parts:
                raise ValueError(f"missing parent for {name}: {parent}")
            visit(parent)
        visiting.remove(name)
        ordered.append(name)

    for name in parts:
        visit(name)
    return ordered


def build_aseprite_rig(
    recipe_path: Path, repo_root: Path, project_root: Path, aseprite_executable: Path, godot_executable: str | None = None
) -> dict[str, Any]:
    repo_root, project_root = repo_root.resolve(), project_root.resolve()
    recipe_path = recipe_path.resolve()
    if not recipe_path.is_relative_to(repo_root):
        raise ValueError("recipe must be inside repository")
    recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
    if recipe.get("version") != 1 or not isinstance(recipe.get("asset_id"), str) or not NAME.fullmatch(recipe["asset_id"]):
        raise ValueError("recipe needs version 1 and a safe asset_id")
    parts = recipe.get("parts")
    if not isinstance(parts, dict) or not parts or any(
        not isinstance(name, str) or not NAME.fullmatch(name) or not isinstance(spec, dict)
        for name, spec in parts.items()
    ):
        raise ValueError("recipe.parts must map safe layer names to objects")
    ordered = _ordered_parts(parts)
    if "root" in parts:
        raise ValueError("root is reserved for the skeleton origin")
    root_joint = list(_vec2(recipe.get("root"), "root"))
    source = _inside(repo_root, recipe.get("source"))
    manifest_path = _inside(repo_root, recipe.get("manifest"))
    scene_path = _inside(repo_root, recipe.get("scene"))
    texture_dir = _inside(repo_root, recipe.get("textures"))
    if not scene_path.is_relative_to(project_root) or not texture_dir.is_relative_to(project_root):
        raise ValueError("scene and textures must be inside Godot project")
    if not source.is_file() or not aseprite_executable.is_file():
        raise FileNotFoundError("Aseprite source or executable is missing")

    with workspace_lock(repo_root), tempfile.TemporaryDirectory(prefix="pixelspark-aseprite-") as temporary:
        temp = Path(temporary)
        data_path = temp / "metadata.json"
        _run(aseprite_executable, [
            "--list-layers", "--list-slices", str(source),
            "--sheet", str(temp / "sheet.png"), "--data", str(data_path),
        ])
        data = json.loads(data_path.read_text(encoding="utf-8"))
        raw_frames = data["frames"]
        frames = list(raw_frames.values()) if isinstance(raw_frames, dict) else raw_frames
        if not frames:
            raise ValueError("Aseprite source has no frames")
        from .assets import quality
        quality_report = quality(temp / "sheet.png", data, recipe.get("palette"))
        canvas = frames[0]["sourceSize"]
        size = (canvas["w"], canvas["h"])
        layer_names = [layer["name"] for layer in data["meta"].get("layers", [])]
        if len(layer_names) != len(set(layer_names)) or not set(parts).issubset(layer_names):
            raise ValueError(f"missing or duplicate layers: {sorted(set(parts) - set(layer_names))}")
        joints = _slices(data["meta"], set(parts))

        _run(aseprite_executable, [
            "--split-layers", str(source),
            "--save-as", str(temp / "{layer}-{frame01}.png"),
        ])
        exports: dict[str, list[Path]] = {}
        for name in ordered:
            exports[name] = [temp / f"{name}-{index:02d}.png" for index in range(1, len(frames) + 1)]
            for image in exports[name]:
                if not image.is_file() or _png_size(image) != size:
                    raise ValueError(f"missing, misaligned, or non-RGBA part: {image.name}")

        # Immutable texture revisions keep an old scene valid if publishing is interrupted.
        export_names = {
            image: f"{image.stem}_{hashlib.sha256(image.read_bytes()).hexdigest()[:12]}.png"
            for images in exports.values() for image in images
        }

        manifest: dict[str, Any] = {
            "version": 1,
            "asset_id": recipe["asset_id"],
            "source": {"aseprite_document": source.relative_to(repo_root).as_posix(), "canvas": list(size)},
            "bones": [{"name": "root", "parent": None, "position": root_joint, "length": 16}],
            "parts": [],
            "animations": recipe.get("animations", {}),
        }
        if recipe.get("autoplay"):
            manifest["autoplay"] = recipe["autoplay"]
        if recipe.get("animation_library"):
            manifest["animation_library"] = recipe["animation_library"]
        for name in ordered:
            joint, slice_length = joints[name]
            parent = parts[name]["parent"]
            parent_joint = root_joint if parent == "root" else joints[parent][0]
            manifest["bones"].append({
                "name": name,
                "parent": parent,
                "position": [joint[0] - parent_joint[0], joint[1] - parent_joint[1]],
                "length": parts[name].get("length", slice_length),
            })
            resources = [
                "res://" + (texture_dir / (image.stem + ".tres")).relative_to(project_root).as_posix()
                for image in exports[name]
            ]
            manifest["parts"].append({
                "name": name + "_part",
                "bone": name,
                "texture": resources[0],
                "frames": resources,
                "position": [-joint[0], -joint[1]],
                "centered": False,
                "z_index": parts[name].get("z_index", 0),
                "joint": joint,
            })

        # Validate the complete build in staging before touching published outputs.
        staging_project = temp / "project"
        texture_views = {}
        for images in exports.values():
            for image in images:
                staged = staging_project / texture_dir.relative_to(project_root) / export_names[image]
                staged.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(image, staged)
                resource = "res://" + (texture_dir / export_names[image]).relative_to(project_root).as_posix()
                view = staged.parent / (image.stem + ".tres")
                view.write_text(
                    '[gd_resource type="AtlasTexture" load_steps=2 format=3]\n\n'
                    f'[ext_resource type="Texture2D" path="{resource}" id="image"]\n\n'
                    '[resource]\natlas = ExtResource("image")\n'
                    f'region = Rect2(0, 0, {size[0]}, {size[1]})\n', encoding="utf-8")
                texture_views[texture_dir / view.name] = view.read_bytes()
        if manifest.get("animation_library"):
            from .core import _project_path
            library = _project_path(project_root, manifest["animation_library"])
            staged = staging_project / library.relative_to(project_root)
            staged.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(library, staged)
        validate_manifest(manifest, staging_project)
        writes = {}
        changed = []
        for images in exports.values():
            for image in images:
                destination = texture_dir / export_names[image]
                content = image.read_bytes()
                writes[destination] = content
                if not destination.is_file() or destination.read_bytes() != content:
                    changed.append(destination.name)
        changed_views = [p.name for p, content in texture_views.items()
                         if not p.is_file() or p.read_bytes() != content]
        writes.update(texture_views)
        staged_scene = staging_project / scene_path.relative_to(project_root)
        generate_scene(manifest, staged_scene, staging_project)
        if godot_executable:
            from .assets import validate_staged
            validate_staged(staging_project, "res://" + staged_scene.relative_to(staging_project).as_posix(), godot_executable, recipe.get("required_markers"))
        writes[scene_path] = staged_scene.read_bytes()
        writes[manifest_path] = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
        publish(repo_root, writes)
        return {
            "asset_id": recipe["asset_id"],
            "frames": len(frames),
            "parts": len(parts),
            "changed_textures": changed,
            "changed_views": changed_views,
            "quality": quality_report,
            "manifest": manifest_path.relative_to(repo_root).as_posix(),
            "scene": scene_path.relative_to(repo_root).as_posix(),
        }
