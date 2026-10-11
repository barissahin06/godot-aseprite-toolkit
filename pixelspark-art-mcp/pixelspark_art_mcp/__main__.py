from __future__ import annotations
import json
import math
import os
import shutil
import sys
import tempfile
import functools
import inspect
from pathlib import Path
from mcp.server.fastmcp import FastMCP, Image
from .aseprite import build_aseprite_rig, _inside
from .core import generate_scene, load_manifest, _project_path
from .studio import checkpoint, restore, revisions, run_native, workspace_lock, publish
from .editing import batch_edit, edit_motion
from .assets import build
from .review import review, viewport
from typing import Any

mcp = FastMCP("aseprite-godot-art", instructions="Inspect configured roots first. Checkpoint native sources, edit staged copies, build and inspect in Godot, then review at native size and normal speed. Preserve unselected artwork and motion. Strong drawn key poses plus rigid Skeleton2D motion and alternate cels preserve pixel art. Reports are diagnostics; the user approves aesthetics. Lua and GDScript are trusted native code.")
REPO_ROOT = Path(os.environ.get("ART_REPO",os.environ.get("PIXELSPARK_REPO",Path.cwd()))).resolve()
PROJECT_ROOT = Path(os.environ.get("ART_PROJECT",os.environ.get("PIXELSPARK_PROJECT",REPO_ROOT/"our-game"))).resolve()
PACKAGE = Path(__file__).parent

def exclusive_workspace(function):
    if inspect.iscoroutinefunction(function):
        @functools.wraps(function)
        async def async_wrapped(*args, **kwargs):
            with workspace_lock(REPO_ROOT):
                return await function(*args, **kwargs)
        return async_wrapped
    @functools.wraps(function)
    def wrapped(*args, **kwargs):
        with workspace_lock(REPO_ROOT):
            return function(*args, **kwargs)
    return wrapped

def executable(key: str, fallback: str) -> str:
    value=os.environ.get(key) or shutil.which(fallback)
    if not value or not Path(value).is_file(): raise FileNotFoundError(f"Set {key}")
    return value

def godot(args: list[str], graphical: bool=False) -> dict:
    return run_native(executable("GODOT_PATH","godot"),[
        "--path",str(PROJECT_ROOT),*([] if graphical else ["--headless"]),*args],REPO_ROOT)

@mcp.tool()
def inspect_workspace() -> dict:
    """Read configured workspace and executable versions without changing project files."""
    return {"repo":str(REPO_ROOT),"project":str(PROJECT_ROOT),
            "aseprite":run_native(executable("ASEPRITE_PATH","aseprite"),["--version"],REPO_ROOT),
            "godot":godot(["--version"])}

@mcp.tool()
def validate_rig_manifest(manifest_path: str) -> dict:
    """Validate a generated rig manifest against the configured project."""
    data=load_manifest(_inside(REPO_ROOT,manifest_path),PROJECT_ROOT)
    return {"ok":True,"asset_id":data["asset_id"],"bones":len(data["bones"]),"parts":len(data["parts"])}

@mcp.tool()
@exclusive_workspace
def generate_skeleton2d_scene(manifest_path: str,output_scene: str) -> dict:
    """Generate a native scene. Then call inspect_godot_scene to validate it in the engine."""
    data=load_manifest(_inside(REPO_ROOT,manifest_path),PROJECT_ROOT)
    path=generate_scene(data,_inside(REPO_ROOT,output_scene),PROJECT_ROOT)
    return {"scene":str(path)}

@mcp.tool()
@exclusive_workspace
def build_aseprite_skeleton2d(recipe_path: str) -> dict:
    """Export native layers/pivots, stage/validate, rebuild rig and stable texture references."""
    return build_aseprite_rig(_inside(REPO_ROOT,recipe_path),REPO_ROOT,PROJECT_ROOT,
                             Path(executable("ASEPRITE_PATH","aseprite")))

@mcp.tool()
@exclusive_workspace
def checkpoint_sources(paths: list[str],label: str) -> dict:
    """Save explicit editable sources before an iteration. Revisions survive session restarts."""
    return checkpoint(REPO_ROOT,paths,label)

@mcp.tool()
def list_source_revisions() -> list[dict]:
    """Read persisted source revision history to resume work."""
    return revisions(REPO_ROOT)

@mcp.tool()
@exclusive_workspace
def restore_source_revision(revision: str) -> dict:
    """Restore verified sources, preserving current files in a new revision. Rebuild afterwards."""
    return restore(REPO_ROOT,revision)

@mcp.tool()
@exclusive_workspace
def edit_aseprite(source_path: str,script: str) -> dict:
    """Edit app.sprite with trusted Lua; a working copy/checkpoint protects the original.
    Do not open other sprites or save files yourself. This tool saves on success.
    Unrestricted Lua, not a sandbox. Inspect the result visually after editing."""
    source=_inside(REPO_ROOT,source_path)
    revision=checkpoint(REPO_ROOT,[source_path],"before native Lua edit")
    with tempfile.TemporaryDirectory(prefix="art-edit-") as tmp:
        target=Path(tmp)/"working.aseprite"
        shutil.copyfile(source,target)
        lua=Path(tmp)/"edit.lua"
        lua.write_text(script+'\nassert(app.sprite, "No active sprite")\napp.sprite:saveAs('+
                       json.dumps(target.as_posix())+')\nprint("ART_EDIT_SAVED")\n',encoding="utf-8")
        result=run_native(executable("ASEPRITE_PATH","aseprite"),["-b",str(target),"--script",str(lua)],REPO_ROOT)
        if "ART_EDIT_SAVED" not in result["log"]: raise RuntimeError("Lua did not complete; source preserved")
        data=target.read_bytes()
        if len(data)<128 or data[4:6]!=b"\xe0\xa5": raise ValueError("Invalid Aseprite output")
        publish(REPO_ROOT, {source: data})
    return {"source":source_path,"checkpoint":revision["revision"],**result}

@mcp.tool()
@exclusive_workspace
def run_godot_script(script_path: str,arguments: list[str] | None=None) -> dict:
    """Execute saved trusted GDScript for native scene/AnimationLibrary edits and tests.
    Must extend SceneTree and quit. Logs containing engine errors fail even on exit zero.
    Unrestricted code, not a sandbox. Checkpoint editable resources before mutations."""
    path=_inside(REPO_ROOT,script_path)
    if not path.is_file() or path.suffix!=".gd": raise ValueError("Expected a saved .gd script")
    return godot(["--script",str(path),"--",*(arguments or [])])

@mcp.tool()
@exclusive_workspace
def import_godot_assets() -> dict:
    """Run native import before loading newly exported textures/scenes."""
    return godot(["--editor","--import","--quiet"])

@mcp.tool()
@exclusive_workspace
def inspect_godot_scene(scene: str,report_path: str="generated/art-review/scene.json") -> dict:
    """Load a native scene and report nodes, bones, animation tracks and timing markers."""
    _project_path(PROJECT_ROOT,scene)
    report=_inside(REPO_ROOT,report_path)
    report.parent.mkdir(parents=True,exist_ok=True)
    godot(["--script",str(PACKAGE/"inspect.gd"),"--",scene,str(report)])
    return json.loads(report.read_text(encoding="utf-8"))

@mcp.tool()
@exclusive_workspace
def capture_animation(scene: str,animation: str,times: list[float],
                      animation_player: str="AnimationPlayer",
                      output_dir: str="generated/art-review/poses",
                      viewport_size: list[int] | None=None) -> list:
    """Render 1..12 exact clip times at the project viewport; return PNGs and an inline contact sheet.
    Requires a graphical renderer. Use a staging scene to get game-sized framing."""
    _project_path(PROJECT_ROOT,scene)
    if not 1<=len(times)<=12 or any(not math.isfinite(t) or t<0 for t in times):
        raise ValueError("times must contain 1..12 finite nonnegative numbers")
    output=_inside(REPO_ROOT,output_dir)
    size=viewport(PROJECT_ROOT, viewport_size)
    result=godot(["--resolution",f"{size[0]}x{size[1]}","--quit-after","600","--script",str(PACKAGE/"capture.gd"),"--",
                  scene,animation_player,animation,json.dumps(times),str(output),json.dumps(size)],True)
    if f"CAPTURE_OK {len(times)}" not in result["log"]: raise RuntimeError("Incomplete render")
    return [json.dumps({"directory":str(output),"frames":len(times)}),
            Image(path=str(output/"contact-sheet.png"))]

@mcp.tool()
@exclusive_workspace
async def batch_edit_sprite(source_path: str, operations: list[dict[str, Any]]) -> dict[str, Any]:
    """Batch op/args edits: palette_remap, cel_position, cel_opacity, frame_duration, pivot, copy_cel. Source is published only after every operation succeeds."""
    return await batch_edit(REPO_ROOT, source_path, operations)

@mcp.tool()
@exclusive_workspace
def edit_animation(library_path: str, clip: str, patch: dict[str, Any]) -> dict[str, Any]:
    """Patch authored motion: length/loop, value tracks (path, keys, interpolation), markers. Untouched tracks persist; invalid keys/collisions preserve the source."""
    return edit_motion(REPO_ROOT, PROJECT_ROOT, executable("GODOT_PATH", "godot"), library_path, clip, patch)

@mcp.tool()
@exclusive_workspace
def build_asset(recipe_path: str) -> dict[str, Any]:
    """Build version-1 rig/sprite/ui_atlas/layered_scene recipes, validate in staged Godot, publish owned outputs with rollback."""
    return build(REPO_ROOT, PROJECT_ROOT, recipe_path, executable("ASEPRITE_PATH", "aseprite"), executable("GODOT_PATH", "godot"))

@mcp.tool()
@exclusive_workspace
async def review_asset(scene: str, animation: str="", duration: float=2.0,
                 output_dir: str="generated/art-review/playback", animation_player: str="AnimationPlayer",
                 baseline_dir: str="", source_path: str="", effects: list[str] | None=None,
                 viewport_size: list[int] | None=None) -> dict[str, Any]:
    """Capture actual 30fps playback, both directions, explicit effects on/off; return GIFs, comparison/report and local nearest-pixel review page."""
    return await review(REPO_ROOT, PROJECT_ROOT, executable("GODOT_PATH","godot"), scene, animation, duration,
                  output_dir, animation_player, baseline_dir, source_path, effects, viewport_size)

def main():
    if len(sys.argv)==3 and sys.argv[1]=="build":
        print(json.dumps(build_aseprite_skeleton2d(sys.argv[2])))
    else:
        mcp.run(transport="stdio")

if __name__=="__main__":
    main()
