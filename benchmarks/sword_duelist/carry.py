"""Revise only the sword carry on a copy of the accepted detailed walk."""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from PIL import Image, ImageChops
from aseprite_mcp.core.runtime import checkpoint, publish, run_native, workspace_lock
from pixelspark_art_mcp.assets import frames
from run import ROOT, BENCH, OUTPUT, export
from walk_study import SOURCE, MOTION, contact_report
from detail import TARGET as BASELINE, LAYERS

TARGET = BENCH / 'aseprite/walk_carry.aseprite'


def verify_scope(before: Image.Image, after: Image.Image, mask: Image.Image) -> int:
    assert before.size == after.size == mask.size
    changed = 0
    for a, b, selected in zip(before.get_flattened_data(), after.get_flattened_data(), mask.get_flattened_data()):
        if a != b:
            assert selected, 'Changed artwork outside the weapon layers'
            changed += 1
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aseprite', default='C:/Tools/Aseprite/aseprite.exe')
    parser.add_argument('--redraw', action='store_true')
    args = parser.parse_args()
    folder = OUTPUT / 'walk-carry'
    folder.mkdir(parents=True, exist_ok=True)
    protected = {path: path.read_bytes() for path in (SOURCE, BASELINE, MOTION)}
    with workspace_lock(ROOT), tempfile.TemporaryDirectory(dir=folder, prefix='carry-stage-') as directory:
        stage = Path(directory)
        if not TARGET.is_file() or args.redraw:
            checkpoint(ROOT, [p.relative_to(ROOT).as_posix() for p in protected], 'Accepted walk before sword carry revision')
            run_native(args.aseprite, ['--batch', '--script-param', f'root={BENCH.as_posix()}', '--script-param', 'study=true',
                                      '--script-param', 'inbetweens=true', '--script-param', 'carry=true',
                                      '--script-param', f'output={(stage/"guide.aseprite").as_posix()}',
                                      '--script-param', f'poses={(stage/"poses.json").as_posix()}', '--script', str(BENCH/'aseprite/author.lua')], ROOT)
            run_native(args.aseprite, ['--batch', '--script-param', f'source={(stage/"guide.aseprite").as_posix()}',
                                      '--script-param', f'output={(stage/"finished.aseprite").as_posix()}',
                                      '--script-param', f'brief={(BENCH/"brief.json").as_posix()}',
                                      '--script-param', f'poses={(stage/"poses.json").as_posix()}', '--script', str(BENCH/'aseprite/detail.lua')], ROOT)
            result = run_native(args.aseprite, ['--batch', '--script-param', f'source={BASELINE.as_posix()}',
                                               '--script-param', f'guide={(stage/"finished.aseprite").as_posix()}',
                                               '--script-param', f'output={(stage/"carry.aseprite").as_posix()}', '--script', str(BENCH/'aseprite/carry.lua')], ROOT)
            assert 'CARRY_REVISION_OK 24' in result['log']
            target = stage/'carry.aseprite'
        else:
            target = TARGET
        before, before_data = export(BASELINE, stage/'before', args.aseprite)
        after, after_data = export(target, stage/'after', args.aseprite)
        assert [f['duration'] for f in frames(before_data)] == [f['duration'] for f in frames(after_data)]
        for field in ('frameTags', 'slices', 'layers'):
            assert before_data['meta'][field] == after_data['meta'][field], f'{field} changed'
        mask = None
        for index, name in enumerate((*LAYERS, 'Material finish')):
            pictures = []
            for native, side in ((BASELINE, 'before'), (target, 'after')):
                output = stage/f'{side}-{index}.png'
                run_native(args.aseprite, ['--batch', '--layer', name, str(native), '--sheet-type', 'horizontal', '--sheet', str(output)], ROOT)
                with Image.open(output) as picture:
                    pictures.append(picture.convert('RGBA'))
            if index < 3:
                assert pictures[0].tobytes() == pictures[1].tobytes(), f'Accepted layer changed: {name}'
            if index in (3, 4):
                for picture in pictures:
                    alpha = picture.getchannel('A')
                    mask = alpha if mask is None else ImageChops.lighter(mask, alpha)
            if index == 5:
                verify_scope(pictures[0], pictures[1], mask)
        with Image.open(before) as a, Image.open(after) as b:
            changed = verify_scope(a.convert('RGBA'), b.convert('RGBA'), mask)
            assert changed, 'The carry revision is absent'
        report = contact_report(after, after_data, json.loads(protected[MOTION]))
        assert all(p.read_bytes() == content for p, content in protected.items())
        if target != TARGET:
            if TARGET.is_file():
                checkpoint(ROOT, [TARGET.relative_to(ROOT).as_posix()], 'Before explicit carry redraw')
            publish(ROOT, {TARGET: target.read_bytes()})
        report.update({'ok': True, 'changed_pixels': changed, 'original_layers_unchanged': list(LAYERS[:3]),
                       'finish_unchanged_outside_weapon': True, 'baseline_sha256': hashlib.sha256(protected[BASELINE]).hexdigest()})
        (folder/'carry-verification.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
        print('CARRY_REVISION_OK:', json.dumps(report))


if __name__ == '__main__':
    main()
