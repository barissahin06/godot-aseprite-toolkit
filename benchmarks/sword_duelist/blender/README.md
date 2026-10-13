# Blender route: Ashguard duelist

`duelist.blend` contains the original low-poly mesh, 19-bone rigid armature,
material-specific three-color lighting ramps, orthographic camera and pose keys.
The three clips share one action and have named timeline boundaries; contact and
chain-ready markers use the common brief. Nothing is imported from another game.

`duelist.aseprite` is the final editable, palette-indexed 96×80 source. Its layers
separate rendered geometry from silhouette outlines, the stabilized two-pixel
visor and warm rivet accents. These finishing pixels can be edited independently.
The exact 8/12/12 frames, variable durations and ground pivot `(44, 70)` follow
`../brief.json`. The sword retains its three-dimensional mesh and hand bone.

From the toolkit root, after installing its frozen environment:

```powershell
& pixelspark-art-mcp/.venv/Scripts/python.exe benchmarks/sword_duelist/blender/run.py
```

Pass `--blender` and `--aseprite` for other executable locations. Rendering uses
a separate background Blender process, native resolution and one render sample.
Palette assignment uses nearest colors without dithering; alpha is binary. Native
Aseprite creates the layers, cels, tags and slice before publication. Existing
owned sources receive a checkpoint. Both native calls have bounded timeouts and
process-tree cleanup. `--reuse-render` repeats import/validation without rendering.

Derived PNGs, GIFs, sheet metadata and the contact sheet are under
`generated/benchmarks/sword_duelist/blender/`. The runner asserts frame durations,
tags, palette, ground pivot, nonempty frames and unclipped silhouettes before
publishing. Repeating import on the same render leaves source bytes unchanged.
The shared benchmark uses the toolkit's existing sprite build and Godot review.

This is an art experiment, not an approved replacement for PixelSpark assets.
Low-resolution lighting and moving geometry can still cause changing pixel
clusters. Review the normal-speed loops and foot contacts before choosing a
production route; geometry consistency does not certify aesthetic quality.
