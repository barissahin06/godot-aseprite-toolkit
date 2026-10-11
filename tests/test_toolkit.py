import importlib.util
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
        self.assertFalse(any(any(x in p.split('/') for x in ['our-game','.venv','.godot','.env','generated']) for p in paths))
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


if __name__ == '__main__':
    unittest.main()
