import copy
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from pixelspark_art_mcp.core import generate_scene, validate_manifest
from pixelspark_art_mcp.studio import checkpoint, restore, run_native

class StudioTests(unittest.TestCase):
    def test_workspace_lock_refuses_other_writer_and_releases_its_own(self):
        import pixelspark_art_mcp.__main__ as server
        with tempfile.TemporaryDirectory() as tmp, patch.object(server,"REPO_ROOT",Path(tmp)):
            @server.exclusive_workspace
            def action():
                self.assertTrue((Path(tmp)/".art-operation.lock").exists())
                return 42
            self.assertEqual(action(),42)
            lock=Path(tmp)/".art-operation.lock"
            self.assertFalse(lock.exists())
            lock.write_text("other owner")
            with self.assertRaisesRegex(RuntimeError,"Another art operation"):
                action()
            self.assertEqual(lock.read_text(),"other owner")

    def test_restore_preserves_pre_restore_source_and_detects_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/"nested").mkdir()
            root = Path(tmp)/"nested"/".."
            (root/"hero.aseprite").write_bytes(b"original")
            rev = checkpoint(root, ["hero.aseprite"], "before edit")
            (root/"hero.aseprite").write_bytes(b"edited")
            result = restore(root, rev["revision"])
            self.assertEqual((root/"hero.aseprite").read_bytes(), b"original")
            restore(root, result["backup"])
            self.assertEqual((root/"hero.aseprite").read_bytes(), b"edited")
            (root/".art-history"/rev["revision"]/"000.bin").write_bytes(b"broken")
            with self.assertRaisesRegex(ValueError,"hash mismatch"):
                restore(root,rev["revision"])

    def test_bad_engine_log_is_failure_even_with_exit_zero(self):
        with self.assertRaises(RuntimeError):
            run_native(sys.executable,["-c","print('SCRIPT ERROR: broken')"],Path.cwd())
        self.assertTrue(run_native(sys.executable,["-c","print('PASS')"],Path.cwd())["ok"])

    def test_manifest_boundaries_and_parent_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"part.png").write_bytes(b"png")
            data={"version":1,"asset_id":"test","bones":[
                {"name":"arm","parent":"root","position":[1,2]},
                {"name":"root","parent":None,"position":[0,0]}],
                "parts":[{"name":"skin","bone":"arm","texture":"res://part.png"}]}
            text=generate_scene(data,root/"rig.tscn",root).read_text()
            self.assertLess(text.index('name="root"'),text.index('name="arm"'))
            self.assertIn("auto_calculate_length_and_angle = false",text)
            invalid=copy.deepcopy(data)
            invalid["parts"][0]["texture"]="res://../outside.png"
            with self.assertRaisesRegex(ValueError,"escapes"):
                validate_manifest(invalid,root)
            invalid=copy.deepcopy(data)
            invalid["parts"][0]["rotation"]=float("nan")
            with self.assertRaises(ValueError):
                validate_manifest(invalid,root)
            invalid=copy.deepcopy(data)
            invalid["bones"][1]["parent"]="arm"
            with self.assertRaisesRegex(ValueError,"cycle"):
                validate_manifest(invalid,root)
            invalid=copy.deepcopy(data)
            invalid["animations"]={"bad":{"length":1,"tracks":[{"bone":"arm","property":"rotation","keys":[[-0.1,0],[1,2]]}]}}
            with self.assertRaisesRegex(ValueError,"invalid key"):
                validate_manifest(invalid,root)
            with self.assertRaises(ValueError):
                checkpoint(root,["../outside"],"bad")

if __name__=="__main__":
    unittest.main()
