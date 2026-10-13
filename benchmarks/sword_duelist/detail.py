"""Separate native material finish; preserve every accepted pose layer and silhouette."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from PIL import Image
from aseprite_mcp.core.runtime import checkpoint, publish, run_native, workspace_lock
from run import ROOT, BENCH, OUTPUT, export
from walk_study import SOURCE, MOTION, contact_report

TARGET = BENCH / 'aseprite/walk_detail.aseprite'
LAYERS = ('far limbs', 'coat and scarf', 'body and helmet', 'sword arm', 'steel sword')


def verify_finish(before: Path, after: Path, before_data: dict, after_data: dict) -> list[int]:
    from pixelspark_art_mcp.assets import frames
    original, finished = frames(before_data), frames(after_data)
    assert len(original) == len(finished)
    assert [f['duration'] for f in original] == [f['duration'] for f in finished], 'Frame timing changed'
    assert before_data['meta']['frameTags'] == after_data['meta']['frameTags'], 'Tags changed'
    assert before_data['meta']['slices'] == after_data['meta']['slices'], 'Pivots changed'
    changed = []
    with Image.open(before) as base, Image.open(after) as result:
        base, result = base.convert('RGBA'), result.convert('RGBA')
        assert base.size == result.size
        assert base.getchannel('A').tobytes() == result.getchannel('A').tobytes(), 'Silhouette changed'
        for old, new in zip(original, finished):
            assert old['frame'] == new['frame'] and old['sourceSize'] == new['sourceSize']
            rect = old['frame']
            box = (rect['x'], rect['y'], rect['x']+rect['w'], rect['y']+rect['h'])
            a, b = base.crop(box), result.crop(box)
            changed.append(sum(x != y for x,y in zip(a.get_flattened_data(), b.get_flattened_data())))
    assert all(count >= 20 for count in changed), 'Material finish is absent on a frame'
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aseprite', default='C:/Tools/Aseprite/aseprite.exe')
    parser.add_argument('--redraw', action='store_true')
    args = parser.parse_args()
    folder = OUTPUT / 'walk-detail'
    folder.mkdir(parents=True, exist_ok=True)
    if not SOURCE.is_file():
        raise FileNotFoundError('Build and accept the base walk study first')
    initial = SOURCE.read_bytes()
    motion_bytes = MOTION.read_bytes()
    with workspace_lock(ROOT), tempfile.TemporaryDirectory(dir=folder,prefix='material-stage-') as directory:
        stage = Path(directory)
        base = stage/'base.aseprite'
        shutil.copyfile(SOURCE,base)
        baseline_sheet, baseline_data = export(base,stage/'before',args.aseprite)
        if not TARGET.is_file() or args.redraw:
            checkpoint(ROOT,[SOURCE.relative_to(ROOT).as_posix()],'Accepted walk before material finish')
            run_native(args.aseprite,['--batch','--script-param',f'root={BENCH.as_posix()}','--script-param','study=true',
                                     '--script-param','inbetweens=true','--script-param',f'output={(stage/"guide.aseprite").as_posix()}',
                                     '--script-param',f'poses={(stage/"poses.json").as_posix()}','--script',str(BENCH/'aseprite/author.lua')],ROOT)
            guide_sheet,_ = export(stage/'guide.aseprite',stage/'guide',args.aseprite)
            with Image.open(baseline_sheet) as accepted, Image.open(guide_sheet) as guide:
                assert accepted.getchannel('A').tobytes() == guide.getchannel('A').tobytes(), 'Update the pose guide before finishing a modified silhouette'
            run_native(args.aseprite,['--batch','--script-param',f'source={base.as_posix()}',
                                     '--script-param',f'output={(stage/"finish.aseprite").as_posix()}',
                                     '--script-param',f'brief={(BENCH/"brief.json").as_posix()}',
                                     '--script-param',f'poses={(stage/"poses.json").as_posix()}',
                                     '--script',str(BENCH/'aseprite/detail.lua')],ROOT)
            target = stage/'finish.aseprite'
        else:
            target = TARGET
        sheet,data = export(target,stage/'after',args.aseprite)
        changed = verify_finish(baseline_sheet,sheet,baseline_data,data)
        contact_report(sheet,data,json.loads(motion_bytes))
        assert [entry['name'] for entry in data['meta']['layers']] == [*LAYERS,'Material finish']
        for index,name in enumerate(LAYERS):
            pictures=[]
            for native,side in ((base,'before'),(target,'after')):
                output=stage/f'{side}-{index}.png'
                run_native(args.aseprite,['--batch','--layer',name,str(native),'--sheet-type','horizontal','--sheet',str(output)],ROOT)
                with Image.open(output) as image:
                    pictures.append(image.convert('RGBA').tobytes())
            assert pictures[0] == pictures[1], f'Accepted layer changed: {name}'
        assert SOURCE.read_bytes() == initial and MOTION.read_bytes() == motion_bytes
        if target != TARGET:
            if TARGET.is_file():
                checkpoint(ROOT,[TARGET.relative_to(ROOT).as_posix()],'Before explicit material redraw')
            publish(ROOT,{TARGET:target.read_bytes()})
        report={'ok':True,'frames':24,'original_layers_unchanged':list(LAYERS),'alpha_unchanged':True,
                'changed_pixels_per_frame':changed,'baseline_sha256':hashlib.sha256(initial).hexdigest(),
                'motion_sha256':hashlib.sha256(motion_bytes).hexdigest(),'source':TARGET.relative_to(ROOT).as_posix()}
        (folder/'material-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print('MATERIAL_FINISH_OK:',json.dumps(report))


if __name__ == '__main__':
    main()
