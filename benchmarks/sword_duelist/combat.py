"""Append a controlled attack to the accepted walk; review native AnimationPlayer playback."""
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
from run import ROOT, BENCH, PROJECT, OUTPUT, BRIEF, export
from carry import TARGET as WALK

SOURCE = BENCH/'aseprite/combat_study.aseprite'
DURATIONS = [80,50,40,40,30,40,40,40,40,40,50,50,40,40,50,50]
FLOW_DURATIONS = [30,25,25,25,25,25,20,20,20,20,20,20,25,25,30,30,25,25,25,25]


def review_frame(seconds: float, flow: bool = False) -> int:
    durations = FLOW_DURATIONS if flow else DURATIONS
    attack_start = 1.04 if flow else 1.2
    attack_end = attack_start + sum(durations)/1000
    phase = seconds % (attack_end + .1 if flow else 2.4)
    if phase < .96-1e-5:
        return min(23, math.floor(phase/.04+1e-5))
    if attack_start-1e-5 <= phase < attack_end-1e-5:
        elapsed = max(0.0, phase-attack_start)
        for index, duration in enumerate(durations):
            if elapsed < duration/1000-1e-5:
                return 24+index
            elapsed -= duration/1000
        return 23+len(durations)
    return 24


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aseprite', default='C:/Tools/Aseprite/aseprite.exe')
    parser.add_argument('--godot', default='C:/Tools/Godot/godot_console.exe')
    parser.add_argument('--redraw', action='store_true')
    parser.add_argument('--flow', action='store_true', help='Separate continuous preparation/recovery study')
    args = parser.parse_args()
    source = BENCH/'aseprite/combat_flow.aseprite' if args.flow else SOURCE
    durations = FLOW_DURATIONS if args.flow else DURATIONS
    asset_id = 'combat_flow' if args.flow else 'combat_study'
    attack_seconds = sum(durations)/1000
    markers = {'contact':.235,'chain_ready':.410} if args.flow else {'contact':.28,'chain_ready':.54}
    fps = 50 if args.flow else 30
    folder = OUTPUT/('combat-flow' if args.flow else 'combat-study')
    folder.mkdir(parents=True, exist_ok=True)
    original = WALK.read_bytes()
    previous = SOURCE.read_bytes() if args.flow else None
    with workspace_lock(ROOT), tempfile.TemporaryDirectory(dir=folder, prefix='combat-stage-') as directory:
        stage = Path(directory)
        if not source.is_file() or args.redraw:
            checkpoint(ROOT, [WALK.relative_to(ROOT).as_posix()], 'Accepted walk before attack study')
            run_native(args.aseprite, ['--batch','--script-param',f'root={BENCH.as_posix()}','--script-param','combat=true',
                                      '--script-param',f'flow={str(args.flow).lower()}',
                                      '--script-param',f'output={(stage/"poses.aseprite").as_posix()}',
                                      '--script-param',f'poses={(stage/"poses.json").as_posix()}', '--script',str(BENCH/'aseprite/author.lua')], ROOT)
            run_native(args.aseprite, ['--batch','--script-param',f'source={(stage/"poses.aseprite").as_posix()}',
                                      '--script-param',f'output={(stage/"detail.aseprite").as_posix()}',
                                      '--script-param',f'brief={(BENCH/"brief.json").as_posix()}',
                                      '--script-param',f'poses={(stage/"poses.json").as_posix()}', '--script',str(BENCH/'aseprite/detail.lua')], ROOT)
            result = run_native(args.aseprite, ['--batch','--script-param',f'source={WALK.as_posix()}',
                                              '--script-param',f'guide={(stage/"detail.aseprite").as_posix()}',
                                              '--script-param',f'output={(stage/"combat.aseprite").as_posix()}', '--script',str(BENCH/'aseprite/append_attack.lua')], ROOT)
            assert f'COMBAT_SOURCE_OK {24+len(durations)}' in result['log']
            target = stage/'combat.aseprite'
        else:
            target = source
        before, baseline = export(WALK, stage/'before', args.aseprite)
        sheet, data = export(target, folder, args.aseprite)
        source_frames = frames(data)
        assert len(source_frames) == 24+len(durations)
        assert [f['duration'] for f in source_frames] == [40]*24+durations
        assert data['meta']['slices'] == baseline['meta']['slices']
        tags = {t['name']: (t['from'],t['to']) for t in data['meta']['frameTags']}
        assert tags == {'walk':(0,23),'ready':(24,24),'attack':(24,23+len(durations))}
        with Image.open(before) as old, Image.open(sheet) as new:
            atlas = new.convert('RGBA')
            assert old.convert('RGBA').tobytes() == atlas.crop((0,0,96*24,80)).tobytes()
            end = 23+len(durations)
            assert atlas.crop((24*96,0,25*96,80)).tobytes() == atlas.crop((end*96,0,(end+1)*96,80)).tobytes(), 'Recovery does not return to ready'
            for index in range(24,end+1):
                assert all(atlas.getpixel((index*96+x,69))[3] == 255 for x in (37,61)), 'Attack foot contact moved'
        audit = quality(sheet,data,list(BRIEF['palette'].values()))
        assert all(audit['bounds']) and not any(w['kind'] in {'palette_deviation','silhouette_touches_canvas'} for w in audit['warnings'])
        if target != source:
            if source.is_file():
                checkpoint(ROOT,[source.relative_to(ROOT).as_posix()],'Before explicit attack redraw')
            publish(ROOT,{source:target.read_bytes()})
    assert WALK.read_bytes() == original
    if args.flow:
        assert SOURCE.read_bytes() == previous, 'Previous attack study changed'
    recipe = folder/'recipe.json'
    recipe.write_text(json.dumps({'version':1,'kind':'sprite','asset_id':asset_id,'source':source.relative_to(ROOT).as_posix(),
                                  'output':f'benchmarks/sword_duelist/project/assets/{asset_id}','palette':list(BRIEF['palette'].values()),
                                  'animations':{'walk':{'loop':True},'ready':{'loop':True},'attack':{'loop':False,'markers':markers}},
                                  'required_markers':{'attack':['contact','chain_ready']}}))
    build(ROOT,PROJECT,recipe.relative_to(ROOT).as_posix(),args.aseprite,args.godot)
    assert not build(ROOT,PROJECT,recipe.relative_to(ROOT).as_posix(),args.aseprite,args.godot)['changed']
    review = folder/'review'
    run_native(args.godot,['--headless','--path',str(PROJECT),'--editor','--import'],ROOT)
    count = math.ceil((1.04+attack_seconds+.1)*2*fps) if args.flow else 144
    result = run_native(args.godot,['--path',str(PROJECT),'--rendering-method','gl_compatibility','--fixed-fps',str(fps),'--disable-vsync',
                                   '--resolution','640x360','--quit-after','1800','--script',str(BENCH/'capture.gd'),'--',str(review),str(count),f'res://{asset_id}.tscn',str(fps)],ROOT)
    assert f'COMPARISON_OK {count*4}' in result['log']
    timing = [(round((i+1)*100/fps)-round(i*100/fps))*10 for i in range(count)]
    pixel_checks = 0
    with Image.open(sheet) as picture:
        atlas = picture.convert('RGBA')
        for mode in ('dark_right','dark_left','light_right','light_left'):
            captures = [Image.open(review/mode/f'{i:04d}.png').convert('RGB') for i in range(count)]
            captures[0].save(review/(mode+'.gif'),save_all=True,append_images=captures[1:],duration=timing,loop=0)
            native_x = 96 if mode.endswith('left') else 104
            native = [p.crop((native_x,160,native_x+96,240)) for p in captures]
            if mode.endswith('right'):
                for sample in range(count) if args.flow else (0,7,30,36,40,44,45,48,51,55,59):
                    index = review_frame(sample/fps,args.flow)
                    expected = atlas.crop((index*96,0,(index+1)*96,80))
                    for source_pixel, actual in zip(expected.get_flattened_data(),native[sample].get_flattened_data()):
                        if source_pixel[3]:
                            assert source_pixel[:3] == actual, f'Native animation differs at sample {sample}'
                            pixel_checks += 1
            native[0].save(review/('native_'+mode+'.gif'),save_all=True,append_images=native[1:],duration=timing,loop=0)
            captures[0].save(review/(mode+'.png'))
            for p in captures+native:
                p.close()
        keys = Image.new('RGBA',(384,80*math.ceil(len(durations)/4)),'#202333')
        for index in range(len(durations)):
            keys.alpha_composite(atlas.crop(((24+index)*96,0,(25+index)*96,80)),((index%4)*96,(index//4)*80))
        keys.resize((1152,keys.height*3),Image.Resampling.NEAREST).save(review/'attack-poses.png')
    report = {'ok':True,'frames':24+len(durations),'walk_frames_unchanged':24,'planted_attack_contacts':2*len(durations),'opaque_pixel_checks':pixel_checks,
              'baseline_sha256':hashlib.sha256(original).hexdigest(),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
              'attack_seconds':attack_seconds,'markers':markers,'viewport':[640,360],'fps':fps,'user_acceptance':'pending'}
    if args.flow:
        report['previous_attack_unchanged_sha256'] = hashlib.sha256(previous).hexdigest()
    (review/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    html = HTML.replace('16 drawn attack poses','20 drawn attack poses').replace('0.72-second','0.485-second') if args.flow else HTML
    (review/'index.html').write_text(html,encoding='utf-8')
    print('COMBAT_STUDY_OK:',json.dumps(report))


HTML = """<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,"><title>Aseprite combat study</title>
<style>body{background:#171b27;color:#e6dfbc;font:16px system-ui;max-width:900px;margin:16px auto;padding:12px}img{image-rendering:pixelated}button,label{margin:6px}#world{overflow:auto}#native{display:block;margin:12px auto}</style>
<h1>Aseprite / controlled strike</h1><p>Accepted walk → low ready → 16 drawn attack poses → ready. A 0.72-second single attack uses native AnimationPlayer frame keys and contact/recovery markers. Review the weight transfer, grip and recovery at normal speed.</p>
<button onclick="document.querySelector('#native').width=96">Native</button><button onclick="document.querySelector('#native').width=288">Nearest 3×</button><label><input type="checkbox" id="light" onchange="refresh()">Light background</label><label><input type="checkbox" id="left" onchange="refresh()">Face left</label>
<img id="native" width="288" alt="Walk and controlled attack"><div id="world"><img id="scene" width="640" alt="Godot native and nearest combat views"></div>
<p>The review repeats a walk/ready/attack/ready sequence; the exported attack itself does not loop. This is a toolkit experiment, not a PixelSpark character replacement.</p>
<p><a href="attack-poses.png">Attack poses</a> / <a href="verification.json">Validation</a></p>
<script>function refresh(){const mode=(document.querySelector('#light').checked?'light':'dark')+'_'+(document.querySelector('#left').checked?'left':'right');document.querySelector('#native').src='native_'+mode+'.gif';document.querySelector('#scene').src=mode+'.gif'}refresh()</script>"""


if __name__ == '__main__':
    main()
