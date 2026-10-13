# Godot–Aseprite toolkit

Windows-first Codex tools. The private barissahin06/godot-aseprite-toolkit repository
is the development upstream. PixelSpark consumes tested versions; the toolkit needs
no game files. The initial import's provenance is retained in source-manifest.json.

## Project installation

Requires Python 3.13, uv, Node.js 18+, Aseprite with Lua and Godot 4.6.3.
Use your own Aseprite installation; application binaries and credentials are not bundled.
Run these commands from the toolkit root: `tools/mcp` in PixelSpark, or the standalone checkout root.

```powershell
python toolkit.py setup --repo "C:/Games/My Game" --project "C:/Games/My Game/game" --aseprite C:/Tools/Aseprite/aseprite.exe --godot C:/Tools/Godot/godot_console.exe
python toolkit.py doctor --repo "C:/Games/My Game"
```

Setup installs frozen environments
and changes only its named MCP tables in project .codex/config.toml, with a backup.
Repeat setup is idempotent. Other servers, credentials, models and approval settings stay intact.
Inline/quoted managed tables are rejected without changing the config; convert only those
headers first. Codex must trust the project and reconnect MCP servers. Setup does not alter trust.

Servers: aseprite, aseprite-godot-art, and @coding-solo/godot-mcp@0.1.1.
The generic server is the MIT-licensed [Coding-Solo/godot-mcp](https://github.com/Coding-Solo/godot-mcp), installed through npm with its upstream license.
The legacy pixelspark-art duplicate is disabled only for this project. ART_REPO and ART_PROJECT
explicitly select the workspace. Local generated configuration should remain outside Git.

## Packages and production

- aseprite-mcp: maintained MIT fork of Divyansh Singh's native Aseprite tools.
- pixelspark-art-mcp: portable asset/motion/review bridge; the legacy Python module remains compatible.
- Aseprite owns pixels/layers/cels/pivots; recipes own mapping; AnimationLibrary owns motion.
- Checkpoints and publication backups live in ignored .art-history. Shared locks use .art-operation.lock.
  Inspect the recorded PID before removing a stale lock. The next operation verifies and rolls back an incomplete publication.
- Lua/GDScript execute trusted code, not a sandbox. Reports are diagnostics; users approve aesthetics.

Inspect → checkpoint → draw/pose → build → import → exact samples and normal-speed review → revise.
Use strong drawn poses, rigid bones and alternate cels where interpolation deforms pixels.
The bridge adds batch_edit_sprite, edit_animation, build_asset and review_asset.
See its README for contracts. Four independent examples cover rig, FX, UI atlas and layered environment.
Their authored motion is kept; derived textures/scenes/caches are excluded from distribution.

The [sword duelist benchmark](benchmarks/sword_duelist/README.md) compares native
Aseprite poses with a real Blender rig rendered to pixels and retouched in Aseprite.
It includes editable sources and an identical Godot review; the geometric examples
remain technical fixtures rather than art quality targets.

## Verification and distribution

```powershell
$env:ASEPRITE_PATH = 'C:/Tools/Aseprite/aseprite.exe'
$env:GODOT_PATH = 'C:/Tools/Godot/godot_console.exe'
uv run --directory pixelspark-art-mcp --frozen python -m unittest discover -s tests
uv run --directory pixelspark-art-mcp --frozen python tests/integration_native.py
python toolkit.py package --output "C:/Packages/godot-aseprite-toolkit"
```

Native acceptance uses temporary copies, Unicode/spaces and real MCP/app calls. Hosted CI checks
contracts and actual wheels. Aseprite native acceptance needs the licensed local app;
Linux/macOS native behavior is unverified. The destination must be empty and separate.
Only named packages, authored examples, tests, setup/docs and CI are copied. source-manifest.json
records each SHA-256 and the current upstream commit; initial import provenance is
kept separately in `imported_from`. A dirty source tree is explicitly marked.
Repackaging without Git preserves the recorded provenance. Commit sources before distribution.
Develop here. After committing and verifying an upstream revision, update only the
consumer's MCP packages and setup/update script:

```powershell
python toolkit.py update --repo "C:/Games/PixelSpark" --target tools/mcp
```

The update uses an allowlist and records the exact source commit and file hashes in
`mcp-update.json`. Shared locks, source checkpoints and publication rollback protect
the consumer. A repeated update changes nothing. Local edits or missing managed files
stop the update; retired upstream files require review. The first update of an existing
consumer requires its managed Git files to be clean. Run frozen `uv sync` for each
package, validate it, then reconnect the servers. Configuration and local environments
stay intact. Benchmarks, drawings, examples, previews and toolkit CI are not transferred.
