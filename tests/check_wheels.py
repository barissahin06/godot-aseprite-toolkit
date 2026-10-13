"""Check actual wheel contents, including native helper resources and console scripts."""
import sys
import zipfile
from pathlib import Path

directory=Path(sys.argv[1])
wheels=list(directory.glob('*.whl'))
assert len(wheels)==2,wheels
for path in wheels:
    with zipfile.ZipFile(path) as wheel:
        names=wheel.namelist()
        assert any(n.endswith('entry_points.txt') for n in names),path
        assert not any('/tests/' in n or '.venv/' in n or 'our-game/' in n for n in names)
        if path.name.startswith('pixelspark_art_mcp'):
            for name in ['capture.gd','inspect.gd','edit_motion.gd','review.gd','frame_animation.gd']:
                assert 'pixelspark_art_mcp/'+name in names,name
        else:
            assert 'aseprite_mcp/core/runtime.py' in names
print('WHEEL_CONTENTS PASS')
