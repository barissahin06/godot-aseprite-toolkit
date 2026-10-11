# Aseprite–Godot Art MCP 0.2

Use the parent toolkit setup/doctor commands. Configure ART_REPO, ART_PROJECT, ASEPRITE_PATH
and GODOT_PATH. Legacy PIXELSPARK_REPO/PROJECT and pixelspark_art_mcp imports remain supported.
The canonical server/console is aseprite-godot-art. Viewport comes from the Godot project;
640×360 remains the fallback. Windows/Godot 4.6.3 is the verified native environment.

## Existing APIs

inspect_workspace, edit_aseprite, build_aseprite_skeleton2d, validate_rig_manifest,
generate_skeleton2d_scene, checkpoint_sources, list_source_revisions, restore_source_revision,
import_godot_assets, run_godot_script, inspect_godot_scene and capture_animation retain
names and required arguments. capture_animation adds optional viewport_size.

## High-level edits

batch_edit_sprite(source_path, operations) accepts 1–100 {op,args} entries.
Ops reuse existing tools: palette_remap, cel_position, cel_opacity, frame_duration,
pivot and copy_cel; use their arguments excluding filename. All operations must succeed
on the working copy before publication. Palettes detach linked images to preserve unselected frames.

edit_animation(library_path, clip, patch) edits an existing AnimationLibrary.
Patch fields: length, loop, tracks, markers. Tracks have path and optional keys
([[seconds,value]]), remove_keys, interpolation (linear/nearest/cubic).
Two-number values become Vector2. Markers map names to seconds; null removes one.
Unspecified tracks/keys persist. Invalid times, marker collisions and length truncation fail
before saving the source. Native ResourceSaver writes the staged result.

## Build recipes

Version 1, workspace-relative source/output paths. Output must stay in ART_PROJECT.

- rig: existing source/root/parts/scene/manifest/textures/animation_library contract.
- sprite: source/output/asset_id; frame tags become SpriteFrames/AnimatedSprite2D.
- ui_atlas: source/output/asset_id, optional margins [left,top,right,bottom]; atlas views and nine-patch preview.
- layered_scene: source/output/asset_id and unique {name,z_index} layers with their own frame animation.

build_asset(recipe_path) validates in staged Godot before publication. It returns scene as
res:// for all kinds; the legacy rig API keeps its original repo-relative scene result.
Content-addressed PNGs and stable views prevent unnecessary rewrites. Old image revisions remain
recoverable. Missing pivots, invalid duration/bounds and engine errors fail; palette and footprint
warnings require visual interpretation. No automatic repainting or pixel smoothing is applied.

## Review and recovery

review_asset(scene, animation="", duration=2, ...) records actual 30fps playback, up to ten seconds.
Four modes show left/right and explicit effects on/off. Standalone subjects are centered;
use an asset/staging scene, not a game coordinator. animation_player selects nested players;
effects lists CanvasItem paths, source_path enables Aseprite coverage/overlap audit,
baseline_dir enables comparison, viewport_size overrides the configured viewport.
Output: GIFs, PNGs, contact sheet, JSON and nearest-pixel HTML. Serve the directory locally
if browser file-fetch restrictions block the comparison JSON. Diagnostics do not approve aesthetics.

Shared locks, bounded processes, checkpoints and verified publication journals are used by both
packages. Inspect a stale lock PID before removal; incomplete publication is rolled back on the next
acquired operation. Lua/GDScript are trusted code, not sandboxes.

uv run --frozen python -m unittest discover -s tests runs pure contracts.
uv run --frozen python tests/integration_native.py tests real stdio/native apps on temporary
copies of independent examples; PixelSpark sources are never used as mutable fixtures.
