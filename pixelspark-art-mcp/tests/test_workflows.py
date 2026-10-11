import asyncio
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from aseprite_mcp.core.runtime import publish, workspace_lock, run_native
from pixelspark_art_mcp.editing import batch_edit
from pixelspark_art_mcp.review import viewport


class WorkflowTests(unittest.TestCase):
    def test_failed_publication_restores_every_file_and_removes_new_output(self):
        import os
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            a, b, new = root/'a', root/'b', root/'new'
            a.write_bytes(b'old-a')
            b.write_bytes(b'old-b')
            replace = os.replace
            count = 0
            def interrupted(source, target):
                nonlocal count
                count += 1
                if count == 3:
                    raise OSError('simulated interrupted publication')
                return replace(source,target)
            with patch('aseprite_mcp.core.runtime.os.replace',side_effect=interrupted):
                with self.assertRaises(OSError):
                    publish(root,{a:b'new-a',new:b'new',b:b'new-b'})
            self.assertEqual(a.read_bytes(),b'old-a')
            self.assertEqual(b.read_bytes(),b'old-b')
            self.assertFalse(new.exists())
            with workspace_lock(root):
                self.assertTrue((root/'.art-operation.lock').exists())

    def test_idempotent_build_does_not_rewrite_or_create_a_journal(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            file = root/'unchanged'
            file.write_bytes(b'stable')
            stamp = file.stat().st_mtime_ns
            self.assertEqual(publish(root,{file:b'stable'}),[])
            self.assertEqual(file.stat().st_mtime_ns,stamp)
            self.assertFalse((root/'.art-history').exists())

    def test_publication_rejects_paths_outside_workspace(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            with self.assertRaises(ValueError):
                publish(root,{root.parent/'outside':b'bad'})

    def test_timeout_is_a_failure(self):
        with self.assertRaisesRegex(RuntimeError,'timed out'):
            run_native(sys.executable,['-c','import time; time.sleep(5)'],Path.cwd(),1)

    def test_project_viewport_and_invalid_override(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'project.godot').write_text('window/size/viewport_width=320\nwindow/size/viewport_height=180')
            self.assertEqual(viewport(root),[320,180])
            with self.assertRaises(ValueError):
                viewport(root,[True,360])

    def test_batch_rejects_source_override_before_editing(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'source.aseprite').write_bytes(b'original')
            with self.assertRaises(ValueError):
                asyncio.run(batch_edit(root,'source.aseprite',[{'op':'pivot','args':{'filename':'outside'}}]))
            self.assertEqual((root/'source.aseprite').read_bytes(),b'original')
