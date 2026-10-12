# Sword duelist art benchmark

Two original interpretations of the same brief: native Aseprite pixel poses and
Blender geometry/animation rendered to pixels, then imported into Aseprite.
`brief.json` is the common size, palette, anchor and timing contract.
The reference is Dead Cells' pose clarity and timing, not its characters or art.

Judge the work at native size and normal speed first: silhouette, material separation,
anticipation, contact and recovery, planted feet, moving pixel clusters and loop seams.
Nearest enlargement is for inspecting pixels. Technical passes do not certify visual quality.

The routes keep editable sources. Derived sheets, Godot resources and review reports
are generated locally; these experiments do not change PixelSpark's game assets.

From the toolkit root, after installing the frozen bridge environment:

```powershell
uv run --directory pixelspark-art-mcp --frozen python ../benchmarks/sword_duelist/run.py
```

This validates the palette, binary alpha, 32 frames, tags, exact durations and ground
pivot. It builds each source twice with the existing `build_asset` code and requires
the second build to change nothing. It then captures 640×360 Godot renders at exact
30 fps samples, verifies source pixels in the renders and writes a comparison page
to `generated/benchmarks/sword_duelist/review/index.html`. The page has native/nearest
size, light/dark backgrounds and both directions. No effects mask the motion.

The 0.70-second attack holds its last recovery pose for another 0.26 seconds in the
review only, so all three preview cycles align at 0.96 seconds. This is not gameplay
timing. The benchmark controller honors the brief; the generic sprite recipe currently
loops every exported tag and does not consume a ground slice automatically.

Existing native sources are preserved. `--redraw-native` explicitly checkpoints the
Aseprite source before regenerating it from `aseprite/author.lua`. The Blender route
has its own author/import commands in its README. Keep manual pixel changes in the
native source; repeating an author command replaces them only when explicitly requested.

Next tooling decisions should follow the comparison: drawing tools cannot compensate
for weak poses, and 3D rendering does not guarantee clean pixel clusters. Judge the
result before adding new generators or choosing a production route.

## First review decision

The user preferred the native Aseprite drawing and rejected both walking loops.
The Blender rendering was not liked; its three-quarter camera also read as a diagonal
facing direction. These sources are retained as the first comparison, not approved
game assets. Pause the Blender route. The next experiment should focus on a full
side-view Aseprite walk: strong contact/down/passing/up poses on both legs, weight
transfer, stable planted feet in a moving-ground test and restrained secondary motion.
Review the silhouettes before adding finish or more intermediate frames.

## Controlled walk refinement

The separate `aseprite/walk_study.aseprite` keeps the first comparison intact. It has
eight drawn side-view contact/down/passing/up keys and sixteen intermediate frames.
The head is steadier than the torso, the free arm counters the legs, and heel contact
and toe push-off have different boot silhouettes. The source is 25 fps with a
0.96-second cycle. All five original editing layers remain separate.

```powershell
uv run --directory pixelspark-art-mcp --frozen python ../benchmarks/sword_duelist/walk_study.py
```

This builds and reviews the source without redrawing it. `--redraw` checkpoints and
recreates only this study and its `walk_motion.json` contacts. That JSON and Aseprite
user data hold the declared contact pixels; they are not inferred from a bounding box.
Tests reject transparent contact pixels and moving planted anchors across the loop.
The Godot scene shows native/nearest sizes, moving ground and a moving character.
Its root motion advances two native pixels per authored 40 ms frame, totaling
48 pixels per stride. The capture is 30 fps; it repeats frames rather than blending
pixels. The world preview resets its path when the captured GIF repeats.

Review: `generated/benchmarks/sword_duelist/walk-study/review/index.html`.
Contact metrics validate the explicit authored model, not integration with a game's
movement controller. The user accepted this movement as the basis for the next
drawing pass; this is not approval of a production game asset. The general MCP
drawing API and PixelSpark assets are not changed by the study.

## Separate material finish

`aseprite/walk_detail.aseprite` adds a sixth `Material finish` layer over the accepted
walk: helmet planes, plate edges, scarf and coat folds, leather accents and quieter
rear limbs. The five original layers, silhouette, contacts, pivots and frame timings
stay unchanged. `walk_study.aseprite` and `walk_motion.json` remain the baseline.

```powershell
uv run --directory pixelspark-art-mcp --frozen python ../benchmarks/sword_duelist/detail.py
uv run --directory pixelspark-art-mcp --frozen python ../benchmarks/sword_duelist/walk_study.py --detail
```

The first command checks the native source and reports per-frame color changes and
unchanged original layers. It does not redraw an existing finished source. Explicit
`detail.py --redraw` checkpoints it before replacing only the finish study in a staged
publication. The second command builds twice and captures the same Godot views as
the baseline, with native and nearest before/after previews in both directions and
on both backgrounds. It verifies saved baseline renders against the accepted source.

Review: `generated/benchmarks/sword_duelist/walk-detail/review/index.html`.
The user accepted the material detail. No gameplay integration is included.

## Low ready sword carry

`aseprite/walk_carry.aseprite` revises the weapon arm on a copy of that accepted
detailed walk. The hand is lower, the elbow bends, fingers wrap across the handle,
and the blade angle varies slightly through the stride while its geometric length
stays fixed. The accepted body, feet, rear arm, cloth and their finish remain intact.

```powershell
uv run --directory pixelspark-art-mcp --frozen python ../benchmarks/sword_duelist/carry.py
uv run --directory pixelspark-art-mcp --frozen python ../benchmarks/sword_duelist/walk_study.py --carry
```

The authoring command draws staged weapon poses using the existing native recipes,
then replaces only the weapon layers and finish pixels inside their old/new coverage.
It verifies all other layer pixels, timing, tags, pivots, palette and declared foot
contacts before publication. Existing sources are not redrawn without `--redraw`;
both accepted walk sources and their motion metadata are protected by hashes.

Review: `generated/benchmarks/sword_duelist/walk-carry/review/index.html` compares
the accepted detailed walk with this revision. The user accepted this carry pose.
This remains a character study; production combat and gameplay integration are separate.
