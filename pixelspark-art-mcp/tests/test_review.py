import asyncio
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from pixelspark_art_mcp.review import changed_pixels, motion_metrics, review


class ReviewTests(unittest.TestCase):
    def test_pixel_changes_detect_a_one_channel_one_level_difference(self):
        before = Image.new('RGB',(2,2))
        after = before.copy()
        after.putpixel((1,1),(1,0,0))
        self.assertEqual(changed_pixels(before,after),1)
        with self.assertRaises(ValueError):
            changed_pixels(before,Image.new('RGB',(3,2)))

    def test_unchanged_runs_include_the_initial_and_final_display_intervals(self):
        a = Image.new('RGB',(2,2))
        b = a.copy()
        b.putpixel((0,0),(0,1,0))
        result = motion_metrics([a,a,b,b,b],50)
        self.assertEqual(result['changed_pixels'],[None,0,1,0,0])
        self.assertEqual(result['unchanged_runs'],[
            {'start_sample':0,'end_sample':1,'seconds':.04},
            {'start_sample':2,'end_sample':4,'seconds':.06},
        ])

    def test_review_reports_missed_keys_and_compares_identical_timestamps(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'project.godot').write_text('window/size/viewport_width=32\nwindow/size/viewport_height=32')
            with patch('pixelspark_art_mcp.review.run_native',side_effect=self.render) as native:
                baseline = asyncio.run(review(root,root,'godot','res://fixture.tscn','attack',.06,'before',fps=50))
                result = asyncio.run(review(root,root,'godot','res://fixture.tscn','attack',.06,'after',baseline_dir='before',fps=50))
            self.assertEqual(result['sample_times'],[0,.02,.04])
            self.assertEqual(result['timeline']['phases'],{
                'before_contact':.02,'contact_to_chain_ready':.02,'after_chain_ready':.06-.04,
            })
            self.assertEqual(len(result['unsampled_frame_keys']),1)
            self.assertTrue(result['warnings'])
            self.assertTrue(all(values==[0,0,0] for values in result['baseline_changed_pixels'].values()))
            self.assertEqual(baseline['modes']['right_plain']['fps'],50)
            self.assertTrue((root/'after/right_plain_before/0002.png').is_file())
            self.assertIn('Capture sample',(root/'after/index.html').read_text())
            self.assertEqual(native.call_args_list[1].args[1][-1],'50')
            report = root/'before/review.json'
            saved = json.loads(report.read_text())
            saved['modes']['right_plain']['fps']=30
            report.write_text(json.dumps(saved))
            with patch('pixelspark_art_mcp.review.run_native') as native:
                with self.assertRaisesRegex(ValueError,'fps'):
                    asyncio.run(review(root,root,'godot','res://fixture.tscn','attack',.06,'guarded',baseline_dir='before',fps=50))
                native.assert_not_called()
            self.assertFalse((root/'guarded').exists())

    def test_bad_fps_and_overlapping_baseline_fail_before_native_work(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'project.godot').write_text('')
            with patch('pixelspark_art_mcp.review.run_native') as native:
                for fps in (True,19,51,20.5,'30'):
                    with self.assertRaisesRegex(ValueError,'fps'):
                        asyncio.run(review(root,root,'godot','res://fixture.tscn','',.1,'result',fps=fps))
                for target in ('before','before/nested'):
                    with self.assertRaisesRegex(ValueError,'separate'):
                        asyncio.run(review(root,root,'godot','res://fixture.tscn','',.1,target,baseline_dir='before'))
                native.assert_not_called()
            self.assertFalse((root/'result').exists())

    @staticmethod
    def render(executable,args,root,timeout=120):
        if '--script' not in args:
            return {'ok':True,'log':''}
        values = args[args.index('--')+1:]
        fps,count=int(values[7]),math.ceil(float(values[3])*int(values[7]))
        output=Path(values[5])
        for mode in ('right_plain','right_fx','left_plain','left_fx'):
            (output/mode).mkdir(parents=True,exist_ok=True)
            for index in range(count):
                Image.new('RGB',(32,32),(index//2,0,0)).save(output/mode/f'{index:04d}.png')
        timeline={'sampling':'exact_animation_player','seconds':.06,'loop':False,
                  'markers':{'contact':.02,'chain_ready':.04},'frame_keys':[
                      {'time':0,'seconds':.01,'frame':0,'captured_samples':[0]},
                      {'time':.01,'seconds':.01,'frame':1,'captured_samples':[]},
                      {'time':.02,'seconds':.04,'frame':2,'captured_samples':[1,2]},
                  ]}
        (output/'timeline.json').write_text(json.dumps(timeline))
        return {'ok':True,'log':f'REVIEW_OK {count*4}'}
