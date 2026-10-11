"""Build both native art routes and capture the same Godot composition at exact times."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import tempfile
from pathlib import Path

from PIL import Image
from aseprite_mcp.core.runtime import checkpoint, publish, run_native, workspace_lock
from pixelspark_art_mcp.assets import build, frames, quality

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "benchmarks/sword_duelist"
PROJECT = BENCH / "project"
OUTPUT = ROOT / "generated/benchmarks/sword_duelist"
BRIEF = json.loads((BENCH / "brief.json").read_text(encoding="utf-8"))
ROUTES = ("aseprite", "blender")
CLIPS = tuple(BRIEF["clips"])


def export(source: Path, folder: Path, aseprite: str) -> tuple[Path, dict]:
    folder.mkdir(parents=True, exist_ok=True)
    sheet, metadata = folder / "sheet.png", folder / "frames.json"
    run_native(aseprite, ["--batch", "--list-tags", "--list-layers", "--list-slices", str(source),
                         "--sheet-type", "horizontal", "--sheet", str(sheet), "--data", str(metadata)], ROOT)
    if not sheet.is_file() or not metadata.is_file():
        raise RuntimeError("Native export did not produce the sheet and metadata")
    data = json.loads(metadata.read_text(encoding="utf-8"))
    return sheet, data


def validate(sheet: Path, data: dict) -> dict:
    source = frames(data)
    tags = data.get("meta", {}).get("frameTags", [])
    assert [tag["name"] for tag in tags] == list(CLIPS), "Clip order/names differ from brief"
    start = 0
    for tag in tags:
        expected = BRIEF["clips"][tag["name"]]["durations_ms"]
        assert tag["from"] == start and tag["to"] == start + len(expected) - 1
        assert [frame["duration"] for frame in source[start:start+len(expected)]] == expected
        start += len(expected)
    assert start == len(source)
    assert all([frame["sourceSize"]["w"], frame["sourceSize"]["h"]] == BRIEF["canvas"] for frame in source)
    ground = next(s for s in data["meta"]["slices"] if s["name"] == "ground")
    assert [ground["keys"][0]["pivot"][axis] for axis in ("x", "y")] == BRIEF["anchor"]
    report = quality(sheet, data, list(BRIEF["palette"].values()))
    assert all(report["bounds"]), "Blank animation frame"
    assert not any(w["kind"] in {"palette_deviation", "silhouette_touches_canvas"} for w in report["warnings"])
    with Image.open(sheet) as image:
        assert set(image.convert("RGBA").getchannel("A").get_flattened_data()) <= {0, 255}, "Antialiased alpha"
    return report


def author_native(aseprite: str, redraw: bool) -> None:
    target = BENCH / "aseprite/duelist.aseprite"
    if target.is_file() and not redraw:
        return
    with workspace_lock(ROOT), tempfile.TemporaryDirectory(dir=OUTPUT, prefix="native-stage-") as directory:
        if target.is_file():
            checkpoint(ROOT, [target.relative_to(ROOT).as_posix()], "explicit native benchmark redraw")
        staged = Path(directory) / "duelist.aseprite"
        run_native(aseprite, ["--batch", "--script-param", f"root={BENCH.as_posix()}",
                             "--script-param", f"output={staged.as_posix()}", "--script", str(BENCH / "aseprite/author.lua")], ROOT)
        sheet, data = export(staged, Path(directory) / "export", aseprite)
        validate(sheet, data)
        publish(ROOT, {target: staged.read_bytes()})


def selected_frame(seconds: float, durations: list[int]) -> int:
    remaining = (seconds % 0.96) * 1000
    for index, duration in enumerate(durations[:-1]):
        if remaining < duration - 0.001:
            return index
        remaining -= duration
    return len(durations) - 1


def encode_review(exports: dict[str, tuple[Path, dict]], count: int) -> dict:
    """Encode genuine Godot renders; verify opaque source pixels survive at native size."""
    review = OUTPUT / "review"
    durations = [(round((i+1)*100/30) - round(i*100/30))*10 for i in range(count)]
    pixel_checks = 0
    for mode in ("dark_right", "dark_left", "light_right", "light_left"):
        captures = [Image.open(review / mode / f"{i:04d}.png").convert("RGB") for i in range(count)]
        captures[0].save(review / (mode + ".gif"), save_all=True, append_images=captures[1:], duration=durations, loop=0)
        for row, route in enumerate(ROUTES):
            sheet, data = exports[route]
            with Image.open(sheet) as atlas:
                atlas = atlas.convert("RGBA")
                tags = {tag["name"]: tag for tag in data["meta"]["frameTags"]}
                for column, clip in enumerate(CLIPS):
                    x = (48 if mode.endswith("left") else 56) + 200 * column
                    y = 70 + 142 * row
                    views = [capture.crop((x, y, x+96, y+80)) for capture in captures]
                    views[0].save(review / f"{route}_{clip}_{mode}.gif", save_all=True, append_images=views[1:], duration=durations, loop=0)
                    if mode.endswith("right"):
                        for index in (0, 7, 15, 26):
                            frame = frames(data)[tags[clip]["from"] + selected_frame(index/30, BRIEF["clips"][clip]["durations_ms"])]
                            rect = frame["frame"]
                            expected = atlas.crop((rect["x"], rect["y"], rect["x"]+96, rect["y"]+80))
                            for native, actual in zip(expected.get_flattened_data(), views[index].get_flattened_data()):
                                if native[3]:
                                    assert native[:3] == actual, (mode, route, clip, index, native, actual)
                                    pixel_checks += 1
                    for view in views:
                        view.close()
        captures[0].save(review / (mode + ".png"))
        for capture in captures:
            capture.close()
    report = {"ok": True, "viewport": [640, 360], "fps": 30, "frames_per_view": count,
              "opaque_pixel_checks": pixel_checks, "attack_preview_recovery_hold_seconds": 0.26,
              "sources": {route: hashlib.sha256((BENCH / route / "duelist.aseprite").read_bytes()).hexdigest() for route in ROUTES},
              "limitations": ["This compares two original interpretations of the same brief, not identical artwork.",
                               "Palette/alpha/timing and Godot pixel preservation are technical checks; aesthetics require a person.",
                               "No VFX, game combat logic, normal maps or dynamic lighting are included."]}
    (review / "verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (review / "index.html").write_text(HTML, encoding="utf-8")
    return report


HTML = """<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,"><title>Sword duelist / two routes</title>
<style>body{background:#171b27;color:#e6dfbc;font:16px system-ui;max-width:1100px;margin:16px auto;padding:0 12px}h1{font-size:clamp(20px,3vw,30px)}button{padding:8px;margin:4px}img{image-rendering:pixelated}#grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.card{background:#252839;padding:12px}.card img{display:block;margin:8px auto}label{display:inline-block;margin:8px}@media(max-width:700px){html[data-zoom="3"] #grid{grid-template-columns:minmax(0,1fr)}}</style>
<h1>Ashguard duelist: Aseprite / Blender → Aseprite</h1><p>Same 96×80 canvas, palette and timings. First inspect at native size and normal speed; enlarge to inspect clusters.</p>
<button onclick="scale=1;refresh()">Native size</button><button onclick="scale=3;refresh()">Nearest 3×</button><button onclick="restart()">Restart together</button>
<label><input type="checkbox" id="light" onchange="refresh()">Light background</label><label><input type="checkbox" id="mirror" onchange="refresh()">Face left</label>
<div id="grid"></div><p><a href="verification.json">Technical checks and limits</a> / <a href="dark_right.gif">Actual 640×360 Godot capture</a></p>
<p>Look for silhouette, readable materials, pose weight, preparation/contact/recovery, planted feet, loop seams and moving pixel clusters. Attack repeats with a 0.26-second recovery hold for comparison. No VFX.</p>
<script>let scale=1;const grid=document.querySelector('#grid');function refresh(){grid.replaceChildren();document.documentElement.dataset.zoom=scale;const mode=(document.querySelector('#light').checked?'light':'dark')+'_'+(document.querySelector('#mirror').checked?'left':'right');for(const clip of ['idle','walk','attack'])for(const route of ['aseprite','blender']){const d=document.createElement('section');d.className='card';const h=document.createElement('div');h.textContent=route.toUpperCase()+' / '+clip;const img=document.createElement('img');img.alt=route+' '+clip+' animation';img.src=route+'_'+clip+'_'+mode+'.gif';img.width=96*scale;img.height=80*scale;d.append(h,img);grid.append(d)}}function restart(){const stamp=Date.now();for(const img of document.querySelectorAll('img')){const src=img.src;img.src='';img.src=src.split('?')[0]+'?restart='+stamp}}refresh()</script>"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aseprite", default="C:/Tools/Aseprite/aseprite.exe")
    parser.add_argument("--godot", default="C:/Tools/Godot/godot_console.exe")
    parser.add_argument("--redraw-native", action="store_true", help="Checkpoint and replace only the native route with its authored Lua poses")
    parser.add_argument("--build-only", action="store_true")
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    author_native(args.aseprite, args.redraw_native)
    exports = {}
    builds = {}
    for route in ROUTES:
        source = BENCH / route / "duelist.aseprite"
        if not source.is_file():
            raise FileNotFoundError(f"Finish the {route} source first: {source}")
        sheet, data = export(source, OUTPUT / route / "export", args.aseprite)
        validate(sheet, data)
        exports[route] = sheet, data
        recipe = OUTPUT / route / "recipe.json"
        recipe.write_text(json.dumps({"version": 1, "kind": "sprite", "asset_id": "duelist",
                                     "source": source.relative_to(ROOT).as_posix(),
                                     "output": f"benchmarks/sword_duelist/project/assets/{route}",
                                     "palette": list(BRIEF["palette"].values())}, indent=2) + "\n", encoding="utf-8")
        original = source.read_bytes()
        builds[route] = build(ROOT, PROJECT, recipe.relative_to(ROOT).as_posix(), args.aseprite, args.godot)
        repeated = build(ROOT, PROJECT, recipe.relative_to(ROOT).as_posix(), args.aseprite, args.godot)
        assert not repeated["changed"], repeated
        assert source.read_bytes() == original, "Build mutated native artwork"
    (OUTPUT / "builds.json").write_text(json.dumps(builds, indent=2) + "\n", encoding="utf-8")
    if args.build_only:
        print("BENCHMARK_BUILD_OK: both sources validated; repeated builds unchanged")
        return
    run_native(args.godot, ["--headless", "--path", str(PROJECT), "--editor", "--import"], ROOT)
    count = math.ceil(0.96 * 3 * 30)
    result = run_native(args.godot, ["--path", str(PROJECT), "--rendering-method", "gl_compatibility",
                                  "--fixed-fps", "30", "--disable-vsync", "--resolution", "640x360",
                                  "--quit-after", "1800", "--script", str(BENCH / "capture.gd"), "--", str(OUTPUT / "review"), str(count)], ROOT)
    assert f"COMPARISON_OK {count * 4}" in result["log"], result
    print("BENCHMARK_REVIEW_OK:", json.dumps(encode_review(exports, count)))


if __name__ == "__main__":
    main()
