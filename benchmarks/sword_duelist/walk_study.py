"""Native Aseprite walk refinement with explicit foot contacts and Godot root motion."""
from __future__ import annotations

import argparse
import json
import math
import hashlib
import shutil
import tempfile
from pathlib import Path
from PIL import Image
from aseprite_mcp.core.runtime import checkpoint, publish, run_native, workspace_lock
from pixelspark_art_mcp.assets import build, frames, quality
from run import ROOT, BENCH, PROJECT, BRIEF, OUTPUT, export

FOLDER = OUTPUT / "walk-study"
SOURCE = BENCH / "aseprite/walk_study.aseprite"
MOTION = BENCH / "aseprite/walk_motion.json"


def contact_report(sheet: Path, data: dict, motion: dict) -> dict:
    source = frames(data)
    poses = motion["poses"]
    assert len(source) == len(poses) == 24
    assert sum(bool(p["key"]) for p in poses) == 8
    assert [f["duration"] for f in source] == [p["duration_ms"] for p in poses] == [40] * 24
    assert motion["stride_pixels"] == 48 and motion["cycle_seconds"] == 0.96
    assert motion["velocity_pixels_per_second"] == 50
    assert motion["anchor"] == BRIEF["anchor"]
    assert [(t["name"], t["from"], t["to"]) for t in data["meta"]["frameTags"]] == [("walk", 0, 23)]
    ground = next(s for s in data["meta"]["slices"] if s["name"] == "ground")
    assert ground["keys"][0]["pivot"] == {"x": 44, "y": 70}
    groups, active, checks = [], {}, 0
    with Image.open(sheet) as image:
        atlas = image.convert("RGBA")
        assert set(atlas.getchannel("A").get_flattened_data()) <= {0, 255}
        for index in range(48):
            frame = source[index % 24]
            pose = poses[index % 24]
            current = set()
            for contact in pose["contacts"]:
                x, y = contact["pixel"]
                assert 0 <= x < 96 and 0 <= y < 80
                assert atlas.getpixel((frame["frame"]["x"] + x, frame["frame"]["y"] + y))[3] == 255, "Declared contact is not on a source pixel"
                key = contact["foot"] + ("_heel" if contact["mode"] == "heel" else "_sole")
                current.add(key)
                position = (x + index * 2, y)
                if key not in active:
                    active[key] = []
                    groups.append(active[key])
                active[key].append(position)
                checks += 1
            active = {key: value for key, value in active.items() if key in current}
    drift = max(max(p[0] for p in group) - min(p[0] for p in group) for group in groups)
    assert drift == 0 and all(len({p[1] for p in group}) == 1 for group in groups), "Planted contact slides in authored root motion"
    audit = quality(sheet, data, list(BRIEF["palette"].values()))
    assert all(audit["bounds"])
    assert not any(w["kind"] in {"palette_deviation", "silhouette_touches_canvas"} for w in audit["warnings"])
    return {"contact_checks": checks, "planted_anchor_drift_pixels": drift, "key_poses": 8, "frames": 24,
            "note": "Explicitly authored contacts, not automatic foot detection or aesthetic approval."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aseprite", default="C:/Tools/Aseprite/aseprite.exe")
    parser.add_argument("--godot", default="C:/Tools/Godot/godot_console.exe")
    parser.add_argument("--redraw", action="store_true")
    parser.add_argument("--detail", action="store_true", help="Review the separate material finish with the accepted walk as baseline")
    args = parser.parse_args()
    folder = OUTPUT/'walk-detail' if args.detail else FOLDER
    source = BENCH/'aseprite/walk_detail.aseprite' if args.detail else SOURCE
    folder.mkdir(parents=True, exist_ok=True)
    if args.detail and args.redraw:
        parser.error('Use detail.py --redraw to recreate the material finish')
    if args.detail and not source.is_file():
        raise FileNotFoundError('Run detail.py before reviewing the material finish')
    if not source.is_file() or args.redraw:
        with workspace_lock(ROOT), tempfile.TemporaryDirectory(dir=folder, prefix="source-stage-") as directory:
            stage = Path(directory)
            run_native(args.aseprite, ["--batch", "--script-param", f"root={BENCH.as_posix()}", "--script-param", "study=true",
                                      "--script-param", "inbetweens=true", "--script-param", f"output={(stage/'walk.aseprite').as_posix()}",
                                      "--script-param", f"motion={(stage/'motion.json').as_posix()}", "--script", str(BENCH/'aseprite/author.lua')], ROOT)
            sheet, data = export(stage/'walk.aseprite', stage/'export', args.aseprite)
            contact_report(sheet, data, json.loads((stage/'motion.json').read_text()))
            existing = [p.relative_to(ROOT).as_posix() for p in (source, MOTION) if p.is_file()]
            if existing:
                checkpoint(ROOT, existing, "Explicit walk study redraw")
            publish(ROOT, {source: (stage/'walk.aseprite').read_bytes(), MOTION: (stage/'motion.json').read_bytes()})
    sheet, data = export(source, folder, args.aseprite)
    report = contact_report(sheet, data, json.loads(MOTION.read_text()))
    recipe = folder/'recipe.json'
    recipe.write_text(json.dumps({"version": 1, "kind": "sprite", "asset_id": "walk_study", "source": source.relative_to(ROOT).as_posix(),
                                  "output": "benchmarks/sword_duelist/project/assets/walk_study", "palette": list(BRIEF["palette"].values())}))
    original = source.read_bytes()
    build(ROOT, PROJECT, recipe.relative_to(ROOT).as_posix(), args.aseprite, args.godot)
    assert not build(ROOT, PROJECT, recipe.relative_to(ROOT).as_posix(), args.aseprite, args.godot)["changed"]
    assert source.read_bytes() == original
    run_native(args.godot, ["--headless", "--path", str(PROJECT), "--editor", "--import"], ROOT)
    review = folder/'review'
    count = 87
    result = run_native(args.godot, ["--path", str(PROJECT), "--rendering-method", "gl_compatibility", "--fixed-fps", "30", "--disable-vsync",
                                   "--resolution", "640x360", "--quit-after", "1800", "--script", str(BENCH/'capture.gd'), "--", str(review), str(count), "res://walk_study.tscn"], ROOT)
    assert f"COMPARISON_OK {count*4}" in result["log"]
    timing = [(round((i+1)*100/30)-round(i*100/30))*10 for i in range(count)]
    pixel_checks = 0
    for mode in ("dark_right", "dark_left", "light_right", "light_left"):
        captures = [Image.open(review/mode/f"{i:04d}.png").convert("RGB") for i in range(count)]
        captures[0].save(review/(mode+'.gif'), save_all=True, append_images=captures[1:], duration=timing, loop=0)
        native_x = 96 if mode.endswith('left') else 104
        native = [p.crop((native_x,160,native_x+96,240)) for p in captures]
        if mode.endswith('right'):
            with Image.open(sheet) as atlas:
                atlas = atlas.convert('RGBA')
                for sample in (0, 7, 15, 26):
                    frame_index = math.floor(sample/30/0.04+0.00001) % 24
                    expected = atlas.crop((frame_index*96,0,(frame_index+1)*96,80))
                    for source_pixel, actual in zip(expected.get_flattened_data(),native[sample].get_flattened_data()):
                        if source_pixel[3]:
                            assert source_pixel[:3] == actual
                            pixel_checks += 1
        native[0].save(review/('native_'+mode+'.gif'), save_all=True, append_images=native[1:], duration=timing, loop=0)
        captures[0].save(review/(mode+'.png'))
        for p in captures + native:
            p.close()
    with Image.open(sheet) as atlas:
        keys = Image.new('RGBA', (384,160), '#202333')
        for i in range(8):
            keys.alpha_composite(atlas.crop((i*3*96,0,(i*3+1)*96,80)), ((i%4)*96,(i//4)*80))
        keys.resize((1152,480), Image.Resampling.NEAREST).save(review/'key-poses.png')
    if args.detail:
        baseline_sheet, baseline_data = export(SOURCE, folder/'baseline', args.aseprite)
        with Image.open(baseline_sheet) as baseline:
            comparison = Image.new('RGBA', (384,160), '#202333')
            for row, path in enumerate((baseline_sheet,sheet)):
                with Image.open(path) as atlas:
                    for column, index in enumerate((0,6,12,18)):
                        comparison.alpha_composite(atlas.crop((index*96,0,(index+1)*96,80)),(column*96,row*80))
            comparison.resize((1152,480),Image.Resampling.NEAREST).save(review/'material-comparison.png')
            for mode in ("dark_right", "dark_left", "light_right", "light_left"):
                for prefix in ('native_', ''):
                    before = FOLDER/'review'/(prefix+mode+'.gif')
                    if not before.is_file():
                        raise FileNotFoundError('Capture the accepted walk first with walk_study.py')
                    shutil.copyfile(before, review/('before_'+prefix+mode+'.gif'))
            for sample in (0,7,15,26):
                frame_index = math.floor(sample/30/0.04+0.00001) % 24
                expected = baseline.crop((frame_index*96,0,(frame_index+1)*96,80)).convert('RGBA')
                with Image.open(FOLDER/'review/dark_right'/f'{sample:04d}.png') as picture:
                    before = picture.convert('RGB').crop((104,160,200,240))
                    assert all(not p[3] or p[:3] == q for p,q in zip(expected.get_flattened_data(),before.get_flattened_data())), 'Before capture does not match the accepted source'
        report['baseline_sha256'] = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    report.update({"ok": True, "source_sha256":hashlib.sha256(original).hexdigest(), "capture_fps": 30, "source_fps": 25, "viewport": [640,360], "opaque_pixel_checks": pixel_checks,
                   "root_motion": "2 native pixels per authored 40ms frame"})
    (review/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    html = HTML
    if args.detail:
        html = html.replace('Aseprite / controlled walk','Aseprite / material finish')
        html = html.replace('8 drawn key poses, 16 in-betweens. Original comparison kept in Git. Inspect the silhouettes, weight transfer and foot plants.',
                            'Before / after. Accepted poses, silhouette, foot contacts and timings are unchanged. Helmet, metal edges, cloth folds and leather are finished on a separate layer.')
        html = html.replace('<img id="native"', '<p>Before</p><img id="before" class="pixel-preview" width="288" alt="Accepted walk before material finish"><p>After</p><img id="native"')
        html = html.replace('document.querySelector(\'#scene\').src=mode+\'.gif\'', 'document.querySelector(\'#scene\').src=mode+\'.gif\';document.querySelector(\'#before\').src=\'before_native_\'+mode+\'.gif\'')
        html = html.replace('<a href="key-poses.png">Eight key poses</a>', '<a href="material-comparison.png">Before/after key poses</a> / <a href="key-poses.png">Finished key poses</a>')
    (review/'index.html').write_text(html,encoding='utf-8')
    print('WALK_STUDY_OK:',json.dumps(report))


HTML = """<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,"><title>Aseprite walk refinement</title>
<style>body{background:#171b27;color:#e6dfbc;font:16px system-ui;max-width:900px;margin:16px auto;padding:12px}img{image-rendering:pixelated}button,label{margin:6px}#world{overflow:auto}.pixel-preview{display:block;margin:12px auto}</style>
<h1>Aseprite / controlled walk</h1><p>8 drawn key poses, 16 in-betweens. Original comparison kept in Git. Inspect the silhouettes, weight transfer and foot plants.</p>
<button onclick="document.querySelectorAll('.pixel-preview').forEach(i=>i.width=96)">Native</button><button onclick="document.querySelectorAll('.pixel-preview').forEach(i=>i.width=288)">Nearest 3×</button><label><input type="checkbox" id="light" onchange="refresh()">Light background</label><label><input type="checkbox" id="left" onchange="refresh()">Face left</label>
<img id="native" class="pixel-preview" width="288" alt="Controlled Aseprite walk"><div id="world"><img id="scene" width="640" alt="Godot moving-ground and moving-character views"></div>
<p>World view uses authored root motion: 48 pixels in 0.96 seconds, sampled at 25 fps and displayed at 30 fps. Foot-contact checks do not certify aesthetic quality.</p>
<p><a href="key-poses.png">Eight key poses</a> / <a href="verification.json">Contact report</a></p>
<script>function refresh(){const mode=(document.querySelector('#light').checked?'light':'dark')+'_'+(document.querySelector('#left').checked?'left':'right');document.querySelector('#native').src='native_'+mode+'.gif';document.querySelector('#scene').src=mode+'.gif'}refresh()</script>"""


if __name__ == '__main__':
    main()
