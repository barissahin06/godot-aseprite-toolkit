import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image

BASE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("duelist_benchmark", BASE / "benchmarks/sword_duelist/run.py")
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)
sys.path.insert(0,str(BASE / "benchmarks/sword_duelist"))
try:
    study_spec = importlib.util.spec_from_file_location("walk_study", BASE / "benchmarks/sword_duelist/walk_study.py")
    study = importlib.util.module_from_spec(study_spec)
    study_spec.loader.exec_module(study)
finally:
    sys.path.pop(0)


class BenchmarkTests(unittest.TestCase):
    def test_contact_frame_boundary_and_recovery_hold(self):
        durations = benchmark.BRIEF["clips"]["attack"]["durations_ms"]
        self.assertEqual(benchmark.selected_frame(0.279, durations), 4)
        self.assertEqual(benchmark.selected_frame(0.28, durations), 5)
        self.assertEqual(benchmark.selected_frame(0.70, durations), 11)
        self.assertEqual(benchmark.selected_frame(0.959, durations), 11)
        self.assertEqual(benchmark.selected_frame(0.96, durations), 0)

    def test_common_loops_and_single_attack_contract(self):
        brief = json.loads((BASE / "benchmarks/sword_duelist/brief.json").read_text())
        self.assertEqual(sum(brief["clips"]["idle"]["durations_ms"]), 960)
        self.assertEqual(sum(brief["clips"]["walk"]["durations_ms"]), 960)
        self.assertEqual(sum(brief["clips"]["attack"]["durations_ms"]), 700)
        self.assertFalse(brief["clips"]["attack"]["loop"])
        self.assertLess(brief["clips"]["attack"]["contact_seconds"], brief["clips"]["attack"]["chain_ready_seconds"])

    def test_contact_gate_rejects_a_sliding_foot_and_a_transparent_anchor(self):
        with tempfile.TemporaryDirectory() as folder:
            sheet = Path(folder) / 'walk.png'
            image = Image.new('RGBA',(96*24,80))
            motion = {'stride_pixels':48,'cycle_seconds':0.96,'velocity_pixels_per_second':50,'anchor':[44,70],'poses':[]}
            data = {'frames':[], 'meta':{'frameTags':[{'name':'walk','from':0,'to':23}],
                                       'slices':[{'name':'ground','keys':[{'pivot':{'x':44,'y':70}}]}]}}
            for i in range(24):
                image.putpixel((i*96+44,25),(18,21,34,255))
                contacts = []
                if 3 <= i <= 11 or 15 <= i <= 23:
                    x = (61 if i<12 else 85) - 2*i
                    contacts = [{'foot':'near' if i<12 else 'far','mode':'flat','pixel':[x,69]}]
                    image.putpixel((i*96+x,69),(18,21,34,255))
                motion['poses'].append({'key':i%3==0,'duration_ms':40,'contacts':contacts})
                data['frames'].append({'duration':40,'frame':{'x':i*96,'y':0,'w':96,'h':80}})
            image.save(sheet)
            self.assertEqual(study.contact_report(sheet,data,motion)['planted_anchor_drift_pixels'],0)
            contact = motion['poses'][4]['contacts'][0]
            x,y = contact['pixel']
            image.putpixel((4*96+x,y),(0,0,0,0))
            image.save(sheet)
            with self.assertRaisesRegex(AssertionError,'not on a source pixel'):
                study.contact_report(sheet,data,motion)
            contact['pixel'][0] += 1
            image.putpixel((4*96+x+1,y),(18,21,34,255))
            image.save(sheet)
            with self.assertRaisesRegex(AssertionError,'slides'):
                study.contact_report(sheet,data,motion)


if __name__ == "__main__":
    unittest.main()
