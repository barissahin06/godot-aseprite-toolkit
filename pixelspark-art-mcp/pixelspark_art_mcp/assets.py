"""Portable 2D asset recipes; no game registry, class names or runtime rules."""
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any
from PIL import Image

from .aseprite import _inside, build_aseprite_rig
from .core import NAME
from .studio import publish, run_native, workspace_lock


def quoted(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def frames(data: dict) -> list[dict]:
    value = data["frames"]
    result = list(value.values()) if isinstance(value, dict) else value
    if not result or any(f["duration"] <= 0 for f in result):
        raise ValueError("Missing frames or non-positive duration")
    return result


def frame_resource(texture: str, frame: dict) -> str:
    rect = frame["frame"]
    return ('[sub_resource type="AtlasTexture" id="frame_%d"]\natlas = ExtResource("sheet")\n'
            'region = Rect2(%s)\n' % (frame["index"], ", ".join(str(rect[k]) for k in ("x", "y", "w", "h"))))


def sprite_frames(texture: str, data: dict) -> str:
    source = frames(data)
    output = [f'[gd_resource type="SpriteFrames" load_steps={len(source)+2} format=3]\n',
              f'[ext_resource type="Texture2D" path={quoted(texture)} id="sheet"]\n']
    for index, frame in enumerate(source):
        output.append(frame_resource(texture, {**frame, "index": index}))
    tags = data.get("meta", {}).get("frameTags") or [{"name": "default", "from": 0, "to": len(source)-1}]
    animations = []
    for tag in tags:
        lo, hi = tag["from"], tag["to"]
        if not isinstance(lo, int) or not isinstance(hi, int) or not 0 <= lo <= hi < len(source):
            raise ValueError("Invalid frame tag")
        order = list(range(lo, hi+1))
        if tag.get("direction") == "reverse":
            order.reverse()
        elif tag.get("direction") == "pingpong":
            order += order[-2:0:-1]
        elif tag.get("direction", "forward") != "forward":
            raise ValueError("Unsupported tag direction")
        values = ', '.join('{"duration": %s, "texture": SubResource("frame_%d")}' % (source[i]["duration"] / 1000, i) for i in order)
        animations.append('{"name": &%s, "speed": 1.0, "loop": true, "frames": [%s]}' % (quoted(tag["name"]), values))
    output.append('[resource]\nanimations = [%s]\n' % ', '.join(animations))
    return '\n'.join(output)


def quality(sheet: Path, data: dict, expected_palette: list[str] | None = None) -> dict[str, Any]:
    image = Image.open(sheet).convert("RGBA")
    source = frames(data)
    bounds, colors, areas = [], set(), []
    for frame in source:
        rect = frame["frame"]
        box = (rect["x"], rect["y"], rect["x"]+rect["w"], rect["y"]+rect["h"])
        if min(box) < 0 or box[2] > image.width or box[3] > image.height:
            raise ValueError("Frame escapes atlas")
        part = image.crop(box)
        bounds.append(part.getchannel("A").getbbox())
        opaque = [pixel for pixel in part.getdata() if pixel[3]]
        areas.append(len(opaque))
        colors.update('#%02X%02X%02X' % pixel[:3] for pixel in opaque)
    if not any(areas):
        raise ValueError("Unexpected completely blank asset")
    warnings = []
    if expected_palette:
        drift = sorted(colors - {c.upper() for c in expected_palette})
        if drift:
            warnings.append({"kind": "palette_deviation", "colors": drift})
    nonempty = [b for b in bounds if b]
    footprint = [(b[0]+b[2])/2 for b in nonempty]
    if footprint and max(footprint)-min(footprint) > 2:
        warnings.append({"kind": "footprint_drift", "pixels": max(footprint)-min(footprint), "note": "Review planted feet; intentional movement can explain this proxy."})
    if any(b and (b[0] == 0 or b[1] == 0 or b[2] == frame["frame"]["w"] or b[3] == frame["frame"]["h"]) for b, frame in zip(bounds, source)):
        warnings.append({"kind": "silhouette_touches_canvas", "note": "May be deliberate for environment/UI; review clipping."})
    changes = [abs(a-b) for a,b in zip(areas, areas[1:])]
    if changes and max(changes) > max(areas)*0.25:
        warnings.append({"kind": "pixel_crawl_or_pose_change", "note": "Large silhouette change; inspect onion skin before judging."})
    return {"bounds": bounds, "opaque_pixels": areas, "palette": sorted(colors), "warnings": warnings}


def validate_staged(project: Path, scene: str, godot: str, required_markers: dict | None = None) -> None:
    (project / "project.godot").write_text('config_version=5\n[rendering]\nrenderer/rendering_method="gl_compatibility"\ntextures/default_filters/use_nearest_mipmap_filter=false\n', encoding="utf-8")
    run_native(godot, ["--headless", "--path", str(project), "--editor", "--import"], project)
    report = project / "inspection.json"
    result = run_native(godot, ["--headless", "--path", str(project), "--script", str(Path(__file__).with_name("inspect.gd")), "--", scene, str(report)], project)
    if "INSPECT_OK" not in result["log"]:
        raise RuntimeError("Incomplete native scene validation")
    inspection = json.loads(report.read_text(encoding="utf-8"))
    clips = {clip['name']:clip for clip in inspection['animations']}
    for clip, names in (required_markers or {}).items():
        if not isinstance(names,list) or clip not in clips or any(name not in clips[clip]['markers'] for name in names):
            raise ValueError(f'Missing required markers for {clip}')


def build(root: Path, project: Path, recipe_path: str, aseprite: str, godot: str) -> dict[str, Any]:
    recipe = json.loads(_inside(root, recipe_path).read_text(encoding="utf-8"))
    kind = recipe.get("kind", "rig")
    if kind == "rig":
        result = build_aseprite_rig(_inside(root, recipe_path), root, project, Path(aseprite), godot)
        result["scene_file"] = result["scene"]
        result["scene"] = "res://" + _inside(root, result["scene"]).relative_to(project).as_posix()
        return result
    if kind not in {"sprite", "ui_atlas", "layered_scene"} or recipe.get("version") != 1:
        raise ValueError("Unsupported asset recipe version/kind")
    asset_id = recipe.get("asset_id", "")
    if not isinstance(asset_id, str) or not NAME.fullmatch(asset_id):
        raise ValueError("asset_id must be a safe identifier")
    source = _inside(root, recipe["source"])
    destination = _inside(root, recipe["output"])
    if not destination.is_relative_to(project.resolve()):
        raise ValueError("Asset output must be inside the Godot project")
    relative = destination.relative_to(project)
    layers = recipe.get("layers", []) if kind == "layered_scene" else [{"name": "", "z_index": 0}]
    if not isinstance(layers, list) or not layers or len(layers) > 64:
        raise ValueError("Expected 1..64 layers")
    with workspace_lock(root), tempfile.TemporaryDirectory(prefix="art-build-") as folder:
        stage = Path(folder) / "project"
        exported = stage / relative
        exported.mkdir(parents=True)
        nodes, resources, reports, writes = [], [], [], {}
        names = set()
        for index, layer in enumerate(layers):
            name = layer["name"] or asset_id
            if not NAME.fullmatch(name) or name in names:
                raise ValueError("Layers need unique safe names")
            names.add(name)
            sheet, metadata = exported / (name+'.png'), exported / (name+'.json')
            run_native(aseprite, ["--batch", *(["--layer", layer["name"]] if layer["name"] else []), "--list-tags", str(source), "--sheet-type", "horizontal", "--sheet", str(sheet), "--data", str(metadata)], root)
            data = json.loads(metadata.read_text())
            reports.append({"layer": name, **quality(sheet, data, recipe.get("palette"))})
            digest = hashlib.sha256(sheet.read_bytes()).hexdigest()[:12]
            hashed = name+'_'+digest+'.png'
            sheet.rename(exported / hashed)
            texture = 'res://'+(relative / hashed).as_posix()
            if kind == "ui_atlas":
                for frame_index, frame in enumerate(frames(data)):
                    text = '[gd_resource type="AtlasTexture" load_steps=2 format=3]\n\n[ext_resource type="Texture2D" path=%s id="sheet"]\n\n[resource]\natlas = ExtResource("sheet")\nregion = Rect2(%s)\n' % (quoted(texture), ', '.join(str(frame['frame'][k]) for k in ('x','y','w','h')))
                    (exported / f'{name}_{frame_index:03d}.tres').write_text(text, encoding='utf-8')
                resource = 'res://'+(relative / f'{name}_000.tres').as_posix()
                resources.append(f'[ext_resource type="Texture2D" path={quoted(resource)} id="{index}"]')
                margins = recipe.get('margins', [0,0,0,0])
                size = frames(data)[0]['sourceSize']
                if len(margins) != 4 or any(not isinstance(x, int) or isinstance(x, bool) or x < 0 for x in margins) or margins[0]+margins[2] > size['w'] or margins[1]+margins[3] > size['h']:
                    raise ValueError('Invalid nine-patch margins')
                nodes.append('[node name="Preview" type="NinePatchRect" parent="."]\ntexture = ExtResource("0")\ntexture_filter = 1\noffset_left = -32.0\noffset_top = -16.0\noffset_right = 32.0\noffset_bottom = 16.0\n'+''.join(f'patch_margin_{side} = {value}\n' for side,value in zip(('left','top','right','bottom'), margins)))
            else:
                (exported / (name+'.tres')).write_text(sprite_frames(texture, data), encoding='utf-8')
                resources.append(f'[ext_resource type="SpriteFrames" path={quoted("res://"+(relative/(name+".tres")).as_posix())} id="{index}"]')
                z = layer.get('z_index', index)
                if not isinstance(z,int) or isinstance(z,bool) or not -4096 <= z <= 4096:
                    raise ValueError('Invalid layer z_index')
                tag = data.get('meta',{}).get('frameTags', [{'name':'default'}])[0]['name']
                nodes.append(f'[node name={quoted(name)} type="AnimatedSprite2D" parent="."]\nz_index = {z}\ntexture_filter = 1\nsprite_frames = ExtResource("{index}")\nanimation = &{quoted(tag)}\nautoplay = {quoted(tag)}\n')
        scene = exported / (asset_id+'.tscn')
        scene.write_text(f'[gd_scene load_steps={len(resources)+1} format=3]\n\n'+'\n'.join(resources)+f'\n\n[node name={quoted(asset_id)} type="Node2D"]\ntexture_filter = 1\n\n'+'\n'.join(nodes), encoding='utf-8')
        scene_resource = 'res://'+scene.relative_to(stage).as_posix()
        validate_staged(stage, scene_resource, godot)
        for path in exported.rglob('*'):
            if path.is_file() and path.suffix in {'.png', '.tres', '.tscn', '.json'}:
                writes[project/path.relative_to(stage)] = path.read_bytes()
        report = {"kind": kind, "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "scene": scene_resource, "layers": reports}
        writes[destination/(asset_id+'.build.json')] = (json.dumps(report, indent=2)+'\n').encode()
        changed = publish(root, writes)
        return {"ok": True, **report, "changed": changed}
