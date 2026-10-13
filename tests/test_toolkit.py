import importlib.util
import hashlib
import json
import shutil
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
    def test_consumer_allowlist_excludes_art_and_project_configuration(self):
        paths=[p.as_posix() for p in toolkit.consumer_files().values()]
        self.assertIn('toolkit.py',paths)
        self.assertIn('pixelspark-art-mcp/pixelspark_art_mcp/frame_animation.gd',paths)
        self.assertFalse(any(p.startswith(('benchmarks/','examples/','.github/')) for p in paths))
        self.assertFalse(any(p.endswith(('.aseprite','.blend','.png','.gif')) for p in paths))

    def test_consumer_update_is_idempotent_and_preserves_local_art(self):
        with tempfile.TemporaryDirectory(prefix='MCP Türkçe proje ') as folder:
            source,repo=self.consumer_fixture(Path(folder))
            local=repo/'drawing.aseprite'
            local.write_bytes(b'local art')
            args=type('Args',(),{'repo':str(repo),'target':'tools/mcp'})()
            files={source/'toolkit.py':Path('toolkit.py')}
            with patch.object(toolkit,'BASE',source),patch.object(toolkit,'consumer_files',return_value=files):
                self.assertTrue(toolkit.update(args)['changed'])
                target=repo/'tools/mcp/toolkit.py'
                stamp=target.stat().st_mtime_ns
                self.assertEqual(toolkit.update(args)['changed'],[])
                self.assertEqual(target.stat().st_mtime_ns,stamp)
                target.write_bytes(b'local override')
                with self.assertRaisesRegex(ValueError,'local MCP change'):
                    toolkit.update(args)
                self.assertEqual(target.read_bytes(),b'local override')
            self.assertEqual(local.read_bytes(),b'local art')

    def test_consumer_manifest_cannot_escape_and_dirty_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            source,repo=self.consumer_fixture(Path(folder))
            args=type('Args',(),{'repo':str(repo),'target':'tools/mcp'})()
            with patch.object(toolkit,'BASE',source),patch.object(toolkit,'consumer_files',return_value={source/'toolkit.py':Path('toolkit.py')}):
                toolkit.update(args)
                file=repo/'tools/mcp/mcp-update.json'
                data=json.loads(file.read_text())
                data['files'][0]['path']='../../outside'
                file.write_text(json.dumps(data))
                with self.assertRaisesRegex(ValueError,'escapes'):
                    toolkit.update(args)
                (source/'toolkit.py').write_text('uncommitted')
                with self.assertRaisesRegex(ValueError,'Commit and verify'):
                    toolkit.update(args)

    def test_initial_consumer_change_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            source,repo=self.consumer_fixture(Path(folder))
            target=repo/'tools/mcp/toolkit.py'
            target.parent.mkdir(parents=True)
            target.write_text('existing copy\n')
            toolkit.run(['git','add','.'],repo)
            toolkit.run(['git','-c','user.name=Toolkit Test','-c','user.email=test@example.invalid','commit','--quiet','-m','consumer fixture'],repo)
            target.write_text('local change\n')
            args=type('Args',(),{'repo':str(repo),'target':'tools/mcp'})()
            with patch.object(toolkit,'BASE',source),patch.object(toolkit,'consumer_files',return_value={source/'toolkit.py':Path('toolkit.py')}):
                with self.assertRaisesRegex(ValueError,'local MCP changes'):
                    toolkit.update(args)
            self.assertEqual(target.read_text(),'local change\n')
            self.assertFalse((target.parent/'mcp-update.json').exists())

    @staticmethod
    def consumer_fixture(folder):
        # Windows runners can expose TEMP through an 8.3 alias; compare canonical paths.
        folder=folder.resolve()
        source,repo=folder/'upstream',folder/'consumer'
        source.mkdir();repo.mkdir()
        runtime=source/'aseprite-mcp/aseprite_mcp/core/runtime.py'
        runtime.parent.mkdir(parents=True)
        shutil.copyfile(BASE/'aseprite-mcp/aseprite_mcp/core/runtime.py',runtime)
        (source/'toolkit.py').write_text('upstream code\n')
        (source/'.gitignore').write_text('.art-operation.lock\n.art-history/\n**/__pycache__/\n')
        for path in (source,repo):
            toolkit.run(['git','init','--quiet'],path)
        toolkit.run(['git','remote','add','origin','https://github.com/example/toolkit.git'],source)
        toolkit.run(['git','add','.'],source)
        toolkit.run(['git','-c','user.name=Toolkit Test','-c','user.email=test@example.invalid','commit','--quiet','-m','fixture'],source)
        return source,repo

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
