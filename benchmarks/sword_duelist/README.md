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
