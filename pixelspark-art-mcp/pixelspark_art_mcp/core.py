"""Pure file generation and validation for the PixelSpark art pipeline."""

from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path
from typing import Any

NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _vec2(value: Any, label: str) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2 or not all(
        isinstance(item, (int, float)) and not isinstance(item, bool) and math.isfinite(item) for item in value
    ):
        raise ValueError(f"{label} must be [x, y]")
    return float(value[0]), float(value[1])


def _godot_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)[1:-1]


def _project_path(project_root: Path, resource: str) -> Path:
    if not resource.startswith("res://"):
        raise ValueError(f"texture must use res://: {resource}")
    relative = Path(resource[6:])
    resolved = (project_root / relative).resolve()
    if project_root.resolve() not in resolved.parents and resolved != project_root.resolve():
        raise ValueError(f"texture escapes project root: {resource}")
    return resolved


def validate_manifest(manifest: dict[str, Any], project_root: Path) -> dict[str, Any]:
    if manifest.get("version") != 1:
        raise ValueError("manifest version must be 1")
    asset_id = manifest.get("asset_id")
    if not isinstance(asset_id, str) or not NAME.fullmatch(asset_id):
        raise ValueError("asset_id must be a safe identifier")

    bones = manifest.get("bones")
    parts = manifest.get("parts")
    if not isinstance(bones, list) or not bones:
        raise ValueError("bones must contain at least one bone")
    if not isinstance(parts, list):
        raise ValueError("parts must be a list")

    bone_names: set[str] = set()
    parents: dict[str, str | None] = {}
    for bone in bones:
        if not isinstance(bone, dict):
            raise ValueError("each bone must be an object")
        name = bone.get("name")
        parent = bone.get("parent")
        if not isinstance(name, str) or not NAME.fullmatch(name):
            raise ValueError(f"invalid bone name: {name!r}")
        if name in bone_names:
            raise ValueError(f"duplicate bone: {name}")
        if parent is not None and not isinstance(parent, str):
            raise ValueError(f"invalid parent for bone: {name}")
        _vec2(bone.get("position", [0, 0]), f"bone {name}.position")
        length = bone.get("length", 16)
        if not isinstance(length, (int, float)) or isinstance(length, bool) or not math.isfinite(length) or length <= 0:
            raise ValueError(f"bone {name}.length must be positive")
        bone_names.add(name)
        parents[name] = parent

    for name, parent in parents.items():
        if parent is not None and parent not in bone_names:
            raise ValueError(f"bone {name} references missing parent {parent}")
        seen: set[str] = set()
        current: str | None = name
        while current is not None:
            if current in seen:
                raise ValueError(f"bone hierarchy cycle at {current}")
            seen.add(current)
            current = parents[current]

    part_names: set[str] = set()
    for part in parts:
        if not isinstance(part, dict):
            raise ValueError("each part must be an object")
        name = part.get("name")
        bone = part.get("bone")
        texture = part.get("texture")
        if not isinstance(name, str) or not NAME.fullmatch(name):
            raise ValueError(f"invalid part name: {name!r}")
        if name in part_names:
            raise ValueError(f"duplicate part: {name}")
        if not isinstance(bone, str) or bone not in bone_names:
            raise ValueError(f"part {name} references missing bone {bone}")
        if not isinstance(texture, str):
            raise ValueError(f"part {name}.texture is required")
        if not _project_path(project_root, texture).is_file():
            raise ValueError(f"texture does not exist: {texture}")
        _vec2(part.get("position", [0, 0]), f"part {name}.position")
        rotation = part.get("rotation", 0)
        if not isinstance(rotation, (int, float)) or isinstance(rotation, bool) or not math.isfinite(rotation):
            raise ValueError(f"part {name}.rotation must be numeric")
        z_index = part.get("z_index", 0)
        if not isinstance(z_index, int) or isinstance(z_index, bool):
            raise ValueError(f"part {name}.z_index must be an integer")
        if not isinstance(part.get("centered", True), bool):
            raise ValueError(f"part {name}.centered must be boolean")
        part_names.add(name)

    library = manifest.get("animation_library")
    if library is not None and (not isinstance(library, str) or not _project_path(project_root, library).is_file()):
        raise ValueError("animation_library must be an existing res:// resource")
    if library and manifest.get("animations"):
        raise ValueError("use animation_library or inline animations, not both")

    animations = manifest.get("animations", {})
    if not isinstance(animations, dict):
        raise ValueError("animations must be an object")
    for name, animation in animations.items():
        if not isinstance(name, str) or not NAME.fullmatch(name) or not isinstance(animation, dict):
            raise ValueError(f"invalid animation: {name!r}")
        length = animation.get("length", 1)
        if not isinstance(length, (int, float)) or isinstance(length, bool) or not math.isfinite(length) or length <= 0:
            raise ValueError(f"animation {name}.length must be positive")
        if not isinstance(animation.get("loop", False), bool):
            raise ValueError(f"animation {name}.loop must be boolean")
        tracks = animation.get("tracks", [])
        if not isinstance(tracks, list):
            raise ValueError(f"animation {name}.tracks must be a list")
        for track in tracks:
            if not isinstance(track, dict) or track.get("bone") not in bone_names or track.get("property") != "rotation":
                raise ValueError(f"animation {name} must target an existing bone rotation")
            keys = track.get("keys")
            if not isinstance(keys, list) or not keys:
                raise ValueError(f"animation {name} track needs keys")
            previous = -1.0
            for key in keys:
                if not isinstance(key, list) or len(key) != 2 or any(
                    not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value)
                    for value in key
                ) or not 0 <= key[0] <= length or not previous < key[0]:
                    raise ValueError(f"animation {name} has invalid key")
                previous = key[0]
    autoplay = manifest.get("autoplay")
    if autoplay is not None and not library and autoplay not in animations:
        raise ValueError("autoplay must name an animation")
    return manifest


def load_manifest(path: Path, project_root: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("manifest root must be an object")
    return validate_manifest(manifest, project_root)


def _bone_path(name: str, parents: dict[str, str | None]) -> str:
    chain: list[str] = []
    current: str | None = name
    while current is not None:
        chain.append(current)
        current = parents[current]
    return "/".join(reversed(chain))


def generate_scene(manifest: dict[str, Any], output_path: Path, project_root: Path) -> Path:
    data = validate_manifest(manifest, project_root)
    output_path = output_path.resolve()
    root = project_root.resolve()
    if root not in output_path.parents:
        raise ValueError("output scene must be inside the Godot project")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    parents = {bone["name"]: bone.get("parent") for bone in data["bones"]}
    textures = sorted({part["texture"] for part in data["parts"]})
    animations = data.get("animations", {})
    library = data.get("animation_library")
    animation_names = list(animations)
    lines = [
        f"[gd_scene load_steps={len(textures) + len(animation_names) + (2 if animation_names else 1) + bool(library)} format=3]",
        "",
    ]
    for index, texture in enumerate(textures, 1):
        lines.append(
            f'[ext_resource type="Texture2D" path="{_godot_string(texture)}" id="tex_{index}"]'
        )
    if library:
        lines.append(f'[ext_resource type="AnimationLibrary" path="{_godot_string(library)}" id="motion"]')
    if animation_names:
        for index, name in enumerate(animation_names, 1):
            animation = animations[name]
            length = float(animation.get("length", 1.0))
            loop_mode = 1 if animation.get("loop", False) else 0
            lines.extend([
                f'[sub_resource type="Animation" id="Animation_{name}"]',
                f'resource_name = "{_godot_string(name)}"',
                f"length = {length:g}",
                f"loop_mode = {loop_mode}",
            ])
            for track_index, track in enumerate(animation.get("tracks", [])):
                keys = track.get("keys", [])
                times = ", ".join(f"{float(key[0]):g}" for key in keys)
                values = ", ".join(f"{float(key[1]):g}" for key in keys)
                transitions = ", ".join("1" for _ in keys)
                path = f"Skeleton2D/{_bone_path(track['bone'], parents)}:{track['property']}"
                lines.extend([
                    f"tracks/{track_index}/type = \"value\"",
                    f"tracks/{track_index}/imported = false",
                    f"tracks/{track_index}/enabled = true",
                    f'tracks/{track_index}/path = NodePath("{_godot_string(path)}")',
                    f"tracks/{track_index}/interp = 1",
                    f"tracks/{track_index}/loop_wrap = true",
                    f'tracks/{track_index}/keys = {{"times": PackedFloat32Array({times}), "transitions": PackedFloat32Array({transitions}), "update": 0, "values": [{values}]}}',
                ])
            lines.append("")
        lines.extend([
            '[sub_resource type="AnimationLibrary" id="AnimationLibrary_main"]',
            "_data = {" + ", ".join(f'&"{_godot_string(name)}": SubResource("Animation_{name}")' for name in animation_names) + "}",
            "",
        ])
    lines.extend(["", '[node name="Rig" type="Node2D"]', ""])
    lines.extend(['[node name="Skeleton2D" type="Skeleton2D" parent="."]', ""])

    for bone in sorted(data["bones"], key=lambda b: len(_bone_path(b["name"], parents).split("/"))):
        parent = bone.get("parent")
        parent_path = "Skeleton2D" if parent is None else f"Skeleton2D/{_bone_path(parent, parents)}"
        x, y = _vec2(bone.get("position", [0, 0]), f"bone {bone['name']}.position")
        lines.extend([
            f'[node name="{bone["name"]}" type="Bone2D" parent="{parent_path}"]',
            f"position = Vector2({x:g}, {y:g})",
            f"rest = Transform2D(1, 0, 0, 1, {x:g}, {y:g})",
            "auto_calculate_length_and_angle = false",
            f"length = {float(bone.get('length', 16)):g}",
            "",
        ])

    texture_ids = {texture: f"tex_{index}" for index, texture in enumerate(textures, 1)}
    for part in data["parts"]:
        x, y = _vec2(part.get("position", [0, 0]), f"part {part['name']}.position")
        parent_path = f"Skeleton2D/{_bone_path(part['bone'], parents)}"
        lines.extend([
            f'[node name="{part["name"]}" type="Sprite2D" parent="{parent_path}"]',
            f"texture = ExtResource(\"{texture_ids[part['texture']]}\")",
            f"position = Vector2({x:g}, {y:g})",
            *([] if part.get("centered", True) else ["centered = false"]),
            f"rotation = {float(part.get('rotation', 0)):g}",
            f"z_index = {part.get('z_index', 0)}",
            "",
        ])
    if animation_names or library:
        lines.extend([
            '[node name="AnimationPlayer" type="AnimationPlayer" parent="."]',
            'libraries = {&"": ExtResource("motion")}' if library else 'libraries = {&"": SubResource("AnimationLibrary_main")}',
            *([f'autoplay = "{data["autoplay"]}"'] if data.get("autoplay") else []),
            "",
        ])

    temporary = output_path.with_suffix(".tscn.tmp")
    temporary.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    os.replace(temporary, output_path)
    return output_path
