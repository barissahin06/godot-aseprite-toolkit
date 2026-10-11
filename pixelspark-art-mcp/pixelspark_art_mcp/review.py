"""Native animation review with local, timestamped artifacts and visible limitations."""
from __future__ import annotations

import json
import math
import re
import shutil
from pathlib import Path
from typing import Any
from PIL import Image
from aseprite_mcp.tools.quality import audit_animation
from .aseprite import _inside
from .core import _project_path
from .studio import run_native


def viewport(project: Path, requested: list[int] | None = None) -> list[int]:
    if requested is None:
        config = (project / "project.godot").read_text(encoding="utf-8")
        requested = []
        for name, default in (("width",640), ("height",360)):
            match = re.search(r'window/size/viewport_'+name+r'\s*=\s*(\d+)', config)
            requested.append(int(match[1]) if match else default)
    if len(requested) != 2 or any(not isinstance(x,int) or isinstance(x,bool) or not 32 <= x <= 4096 for x in requested):
        raise ValueError("viewport must have two integer dimensions in 32..4096")
    return requested


async def review(root: Path, project: Path, godot: str, scene: str, animation: str,
           duration: float, output_dir: str, animation_player: str = "AnimationPlayer",
           baseline_dir: str = "", source_path: str = "", effects: list[str] | None = None,
           requested_viewport: list[int] | None = None) -> dict[str, Any]:
    _project_path(project, scene)
    if isinstance(duration,bool) or not math.isfinite(duration) or not 0 < duration <= 10:
        raise ValueError("duration must be finite and in (0,10]")
    output = _inside(root, output_dir)
    output.mkdir(parents=True, exist_ok=True)
    size = viewport(project, requested_viewport)
    run_native(godot, ["--headless", "--path", str(project), "--editor", "--import"], root)
    result = run_native(godot, ["--path",str(project),"--rendering-method","gl_compatibility","--fixed-fps","30","--disable-vsync","--resolution",f'{size[0]}x{size[1]}',"--quit-after","1800","--script",str(Path(__file__).with_name('review.gd')),"--",scene,animation_player,animation,str(duration),json.dumps(size),str(output),json.dumps(effects or [])], root, 120)
    count = math.ceil(duration*30)
    if f'REVIEW_OK {count*4}' not in result['log']:
        raise RuntimeError('Incomplete native review')
    modes, comparison = {}, {}
    baseline = _inside(root, baseline_dir) if baseline_dir else None
    for mode in ('right_plain','right_fx','left_plain','left_fx'):
        pictures = [Image.open(output/mode/f'{i:04d}.png').convert('RGB') for i in range(count)]
        timing = [(round((i+1)*100/30)-round(i*100/30))*10 for i in range(count)]
        pictures[0].save(output/(mode+'.gif'), save_all=True, append_images=pictures[1:], duration=timing, loop=0, disposal=2)
        modes[mode] = {'frames':count,'fps':30,'gif':mode+'.gif'}
        if baseline:
            previous = baseline/mode/'0000.png'
            if previous.is_file():
                old = Image.open(previous).convert('RGB')
                if old.size != pictures[0].size:
                    raise ValueError('Baseline viewport differs')
                changed_pixels = []
                for index, picture in enumerate(pictures):
                    with Image.open(baseline/mode/f'{index:04d}.png') as before:
                        if before.size != picture.size:
                            raise ValueError('Baseline viewport differs')
                        changed_pixels.append(sum(a != b for a,b in zip(before.convert('RGB').getdata(),picture.getdata())))
                comparison[mode] = changed_pixels
                old.save(output/(mode+'_before.gif'))
                shutil.copyfile(baseline/(mode+'.gif'),output/(mode+'_before.gif'))
        for picture in pictures:
            picture.close()
    sheet = Image.new('RGB',(size[0]*3, size[1]*4))
    # Reopen exact samples after GIF encoding; each row is a direction/effect mode.
    for row, mode in enumerate(modes):
        for col, index in enumerate((0,count//2,count-1)):
            with Image.open(output/mode/f'{index:04d}.png') as picture:
                sheet.paste(picture,(col*size[0],row*size[1]))
    sheet.save(output/'contact-sheet.png')
    audit = None
    if source_path:
        source = _inside(root, source_path)
        raw = await audit_animation(source.as_posix(), report_bounds=True, report_cels=True)
        try:
            audit = json.loads(raw)
        except json.JSONDecodeError:
            raise RuntimeError(raw)
    report = {'ok':True,'viewport':size,'scene':scene,'animation':animation,'duration':count/30,'modes':modes,'baseline_changed_pixels':comparison,'source_audit':audit,'limitations':['Footprint and pixel-change metrics are review hints, not aesthetic approval.','Effects toggle only the explicit CanvasItem paths supplied by the caller.'],'contact_sheet':str(output/'contact-sheet.png')}
    (output/'review.json').write_text(json.dumps(report,indent=2)+'\n', encoding='utf-8')
    (output/'index.html').write_text('''<!doctype html><meta charset="utf-8"><title>Native asset review</title><style>body{background:#26232b;color:#f5e1bf;font:16px system-ui;margin:24px}img{image-rendering:pixelated;background:#26232b}section{display:inline-block;margin:12px}button{margin:6px}#views{display:flex;flex-wrap:wrap}</style><h1>Native asset review</h1><p>Normal speed: 30 fps. Compare both directions with and without effects. Metrics require visual interpretation.</p><button onclick="document.querySelectorAll('img').forEach(i=>i.style.width=i.naturalWidth+'px')">Native size</button><button onclick="document.querySelectorAll('img').forEach(i=>i.style.width=(i.naturalWidth*3)+'px')">Nearest 3x</button><div id="views"></div><p><a href="review.json">Technical report</a> | <a href="contact-sheet.png">Key samples</a></p><script>const modes=['right_plain','right_fx','left_plain','left_fx'];for(const m of modes){const s=document.createElement('section');s.innerHTML='<h2>'+m+'</h2><img src="'+m+'.gif">';document.querySelector('#views').append(s);}const comparison=__BASELINE__;for(const m of Object.keys(comparison)){const s=document.createElement('section');s.innerHTML='<h2>'+m+' before</h2><img src="'+m+'_before.gif">';document.querySelector('#views').append(s);}</script>'''.replace('__BASELINE__',json.dumps(comparison)), encoding='utf-8')
    return report
