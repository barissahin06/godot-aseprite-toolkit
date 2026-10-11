import importlib.util
import hashlib
import json
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('toolkit',BASE/'toolkit.py')
toolkit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(toolkit)


class ToolkitTests(unittest.TestCase):
    def test_setup_preserves_unrelated_config_and_is_idempotent(self):
        original='model = "unchanged"\n\n[mcp_servers.other]\ncommand = "other"\n\n[mcp_servers.aseprite]\ncommand = "old"\n[mcp_servers.aseprite.env]\nASEPRITE_PATH = "old"\n'
        desired=toolkit.settings(Path('repo'),Path('repo/game'),'aseprite','godot','uv')
        result=toolkit.merge_config(original,desired)
        config=tomllib.loads(result)
        self.assertEqual(config['model'],'unchanged')
        self.assertEqual(config['mcp_servers']['other'],{'command':'other'})
        self.assertFalse(config['mcp_servers']['pixelspark-art']['enabled'])
        for server in config['mcp_servers'].values():
            self.assertTrue(server.get('command') or server.get('url'))
        self.assertEqual(result,toolkit.merge_config(result,desired))

    def test_inline_collision_is_rejected_without_rewriting(self):
        with self.assertRaises(ValueError):
            toolkit.merge_config('mcp_servers = { aseprite = {command="original"}}',{'aseprite':{'command':'new'}})

    def test_allowlist_contains_no_game_or_local_environment(self):
        files=toolkit.distribution_files()
        paths=[p.as_posix() for p in files.values()]
        self.assertTrue(any(p.endswith('core/runtime.py') for p in paths))
        self.assertTrue(any(p.endswith('motion.tres') for p in paths))
        self.assertIn('tests/check_wheels.py',paths)
        self.assertIn('benchmarks/sword_duelist/brief.json',paths)
        self.assertIn('benchmarks/sword_duelist/project/compare.gd',paths)
        self.assertFalse(any('project/assets/' in p for p in paths))
        self.assertFalse(any(any(x in p.split('/') for x in ['our-game','.venv','.godot','.art-history','.env','generated']) for p in paths))
        self.assertNotIn('aseprite-mcp/.mcp.json',paths)

    def test_packages_include_native_resource_data(self):
        metadata=tomllib.loads((BASE/'pixelspark-art-mcp/pyproject.toml').read_text())
        self.assertIn('*.gd',metadata['tool']['setuptools']['package-data']['pixelspark_art_mcp'])

    def test_distribution_can_be_packaged_again(self):
        with tempfile.TemporaryDirectory() as folder:
            first,second=Path(folder)/'first',Path(folder)/'second'
            toolkit.package(type('Args',(),{'output':str(first)})())
            with patch.object(toolkit,'BASE',first):
                toolkit.package(type('Args',(),{'output':str(second)})())
            self.assertEqual(json.loads((first/'source-manifest.json').read_text())['source_commit'],json.loads((second/'source-manifest.json').read_text())['source_commit'])
            for entry in json.loads((first/'source-manifest.json').read_text())['files']:
                self.assertEqual((first/entry['path']).read_bytes(),(second/entry['path']).read_bytes())

    def test_blend_binary_is_copied_without_text_normalization(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'source.blend'
            content=b'BLENDER\x00\r\n\xff\x01\r\n'
            source.write_bytes(content)
            destination=Path(folder)/'package'
            with patch.object(toolkit,'distribution_files',return_value={source:Path('benchmarks/duelist.blend')}):
                toolkit.package(type('Args',(),{'output':str(destination)})())
            self.assertEqual((destination/'benchmarks/duelist.blend').read_bytes(),content)
            entry=json.loads((destination/'source-manifest.json').read_text())['files'][0]
            self.assertEqual(entry['sha256'],hashlib.sha256(content).hexdigest())

    def test_upstream_commit_replaces_import_provenance_without_losing_it(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'source'
            root.mkdir()
            source=root/'README.md'
            source.write_text('source')
            imported={'source_repository':'barissahin06/PixelSpark','source_commit':'import-sha'}
            (root/'source-manifest.json').write_text(json.dumps(imported))
            destination=Path(folder)/'package'
            with patch.object(toolkit,'BASE',root), patch.object(toolkit,'distribution_files',return_value={source:Path('README.md')}), patch.object(toolkit,'run',side_effect=['toolkit-sha','https://github.com/barissahin06/godot-aseprite-toolkit.git',' M README.md']):
                toolkit.package(type('Args',(),{'output':str(destination)})())
            manifest=json.loads((destination/'source-manifest.json').read_text())
            self.assertEqual(manifest['source_repository'],'barissahin06/godot-aseprite-toolkit')
            self.assertEqual(manifest['source_commit'],'toolkit-sha')
            self.assertEqual(manifest['imported_from'],imported)
            self.assertTrue(manifest['source_tree_dirty'])


if __name__ == '__main__':
    unittest.main()
