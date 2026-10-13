"""Native animation review with local, timestamped artifacts and visible limitations."""
from __future__ import annotations

import json
import math
import re
import shutil
from pathlib import Path
from typing import Any
from PIL import Image, ImageChops
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


def changed_pixels(before: Image.Image, after: Image.Image) -> int:
    if before.size != after.size:
        raise ValueError('Comparison viewport differs')
    red, green, blue = ImageChops.difference(before.convert('RGB'), after.convert('RGB')).split()
    difference = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    return difference.point(lambda value: 255 if value else 0).histogram()[255]


def motion_metrics(pictures: list[Image.Image], fps: int) -> dict[str, Any]:
    changes = [None] + [changed_pixels(a,b) for a,b in zip(pictures,pictures[1:])]
    runs, start = [], 0
    for index in range(1,len(pictures)+1):
        if index == len(pictures) or changes[index]:
            if index-start > 1:
                runs.append({'start_sample':start,'end_sample':index-1,'seconds':(index-start)/fps})
            start = index
    return {'changed_pixels':changes,'unchanged_runs':runs,
            'longest_unchanged_seconds':max((run['seconds'] for run in runs),default=0)}


async def review(root: Path, project: Path, godot: str, scene: str, animation: str,
           duration: float, output_dir: str, animation_player: str = "AnimationPlayer",
           baseline_dir: str = "", source_path: str = "", effects: list[str] | None = None,
           requested_viewport: list[int] | None = None, fps: int = 30) -> dict[str, Any]:
    _project_path(project, scene)
    if isinstance(duration,bool) or not math.isfinite(duration) or not 0 < duration <= 10:
        raise ValueError("duration must be finite and in (0,10]")
    if not isinstance(fps,int) or isinstance(fps,bool) or not 20 <= fps <= 50:
        raise ValueError("fps must be an integer in 20..50")
    output = _inside(root, output_dir)
    size = viewport(project, requested_viewport)
    count = math.ceil(duration*fps)
    baseline = _inside(root, baseline_dir) if baseline_dir else None
    if baseline:
        if output.is_relative_to(baseline) or baseline.is_relative_to(output):
            raise ValueError('Baseline and output directories must be separate')
        old_report = json.loads((baseline/'review.json').read_text(encoding='utf-8'))
        if old_report.get('viewport') != size or any(
            old_report.get('modes',{}).get(mode,{}).get('fps') != fps or
            old_report.get('modes',{}).get(mode,{}).get('frames') != count
            for mode in ('right_plain','right_fx','left_plain','left_fx')
        ):
            raise ValueError('Baseline viewport, fps and frame count must match')
        expected_sampling = 'exact_animation_player' if animation else 'engine_playback'
        if old_report.get('timeline',{}).get('sampling') != expected_sampling:
            raise ValueError('Baseline sampling differs; regenerate it with the current review tool')
    output.mkdir(parents=True, exist_ok=True)
    run_native(godot, ["--headless", "--path", str(project), "--editor", "--import", "--quit-after", "120"], root)
    result = run_native(godot, ["--path",str(project),"--rendering-method","gl_compatibility","--fixed-fps",str(fps),"--disable-vsync","--resolution",f'{size[0]}x{size[1]}',"--quit-after","2400","--script",str(Path(__file__).with_name('review.gd')),"--",scene,animation_player,animation,str(duration),json.dumps(size),str(output),json.dumps(effects or []),str(fps)], root, 120)
    if f'REVIEW_OK {count*4}' not in result['log']:
        raise RuntimeError('Incomplete native review')
    modes, comparison, motion = {}, {}, {}
    for mode in ('right_plain','right_fx','left_plain','left_fx'):
        pictures = [Image.open(output/mode/f'{i:04d}.png').convert('RGB') for i in range(count)]
        timing = [(round((i+1)*100/fps)-round(i*100/fps))*10 for i in range(count)]
        pictures[0].save(output/(mode+'.gif'), save_all=True, append_images=pictures[1:], duration=timing, loop=0, disposal=2)
        modes[mode] = {'frames':count,'fps':fps,'gif':mode+'.gif'}
        motion[mode] = motion_metrics(pictures,fps)
        if baseline:
            previous_frames = output/(mode+'_before')
            previous_frames.mkdir(exist_ok=True)
            comparison[mode] = []
            for index, picture in enumerate(pictures):
                previous = baseline/mode/f'{index:04d}.png'
                with Image.open(previous) as before:
                    comparison[mode].append(changed_pixels(before,picture))
                shutil.copyfile(previous,previous_frames/previous.name)
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
    timeline = json.loads((output/'timeline.json').read_text(encoding='utf-8'))
    missed = [key for key in timeline.get('frame_keys',[]) if key['seconds'] > 0 and not key['captured_samples']]
    warnings = ['Some authored frame keys have no capture sample; increase fps or capture duration.'] if missed else []
    markers = timeline.get('markers',{})
    if 'contact' in markers and 'chain_ready' in markers:
        contact, ready = markers['contact'], markers['chain_ready']
        if 0 <= contact <= ready <= timeline['seconds']:
            timeline['phases'] = {'before_contact':contact,'contact_to_chain_ready':ready-contact,
                                  'after_chain_ready':timeline['seconds']-ready}
        else:
            warnings.append('contact/chain_ready markers are out of order or outside the clip.')
    report = {'ok':True,'viewport':size,'scene':scene,'animation':animation,'duration':count/fps,'modes':modes,
              'sample_times':[index/fps for index in range(count)],'timeline':timeline,'unsampled_frame_keys':missed,
              'motion':motion,'warnings':warnings,'baseline_changed_pixels':comparison,'source_audit':audit,
              'limitations':['Footprint, unchanged runs and pixel-change metrics are review hints, not aesthetic approval.',
                             'Exact time-zero sampling applies to the selected AnimationPlayer; procedural scenes advance normally.',
                             'Effects toggle only the explicit CanvasItem paths supplied by the caller.'],
              'contact_sheet':str(output/'contact-sheet.png'),'review_page':str(output/'index.html')}
    (output/'review.json').write_text(json.dumps(report,indent=2)+'\n', encoding='utf-8')
    settings = {'fps':fps,'count':count,'modes':list(modes),'comparison':list(comparison),'timeline':timeline,'warnings':warnings}
    (output/'index.html').write_text(HTML.replace('__SETTINGS__',json.dumps(settings).replace('<','\\u003c')),encoding='utf-8')
    return report


HTML = '''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,"><title>Native asset review</title>
<style>body{background:#26232b;color:#f5e1bf;font:16px system-ui;margin:24px}img{image-rendering:pixelated;background:#26232b;max-width:none}section{margin:12px;overflow:auto;max-width:calc(100% - 24px)}.pair{display:flex;flex-wrap:wrap}button,input{margin:6px}#timeline{white-space:pre-wrap}#frame{width:min(480px,90%)}</style>
<h1>Native asset review</h1><p id="summary"></p><p>Compare both directions with and without effects. Metrics require visual interpretation.</p>
<button id="native">Native size</button><button id="zoom">Nearest 3x</button><button id="play">Frame review</button>
<label>Sample <input id="frame" aria-label="Capture sample" type="range" min="0" value="0" disabled></label><output id="time"></output>
<p id="timeline"></p><p id="warnings"></p><div id="views"></div><p><a href="review.json">Technical report</a> | <a href="contact-sheet.png">Key samples</a></p>
<script>
const data=__SETTINGS__, images=[], slider=document.querySelector('#frame');let frames=false,scale=1;
slider.max=data.count-1;
document.querySelector('#summary').textContent='Normal speed: '+data.fps+' fps. '+data.count+' capture samples. '+(data.timeline.sampling==='exact_animation_player'?'Selected clip starts at time zero.':'Procedural engine playback.');
document.querySelector('#warnings').textContent=data.warnings.join(' ');
document.querySelector('#timeline').textContent=Object.entries(data.timeline.markers||{}).map(([name,time])=>name+': '+time.toFixed(3)+' s (sample '+Math.ceil(time*data.fps)+')').join(' | ');
for(const mode of data.modes){const pair=document.createElement('div');pair.className='pair';for(const stem of (data.comparison.includes(mode)?[mode+'_before',mode]:[mode])){const section=document.createElement('section'),heading=document.createElement('h2'),img=document.createElement('img');heading.textContent=stem;img.alt=stem+' animation';img.onload=()=>img.style.width=img.naturalWidth*scale+'px';section.append(heading,img);pair.append(section);images.push({img,stem});}document.querySelector('#views').append(pair);}
function refresh(){for(const {img,stem} of images){img.src=frames?stem+'/'+String(slider.value).padStart(4,'0')+'.png':stem+'.gif';img.style.width=img.naturalWidth*scale+'px';}document.querySelector('#time').textContent=frames?(Number(slider.value)/data.fps).toFixed(3)+' s':'';}
document.querySelector('#native').onclick=()=>{scale=1;refresh();};document.querySelector('#zoom').onclick=()=>{scale=3;refresh();};
document.querySelector('#play').onclick=()=>{frames=!frames;slider.disabled=!frames;document.querySelector('#play').textContent=frames?'Play at normal speed':'Frame review';refresh();};slider.oninput=refresh;refresh();
</script>'''
