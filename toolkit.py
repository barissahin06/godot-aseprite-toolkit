"""Windows-first, project-scoped Codex setup and allowlisted MCP distribution."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
import tomllib
from pathlib import Path

BASE = Path(__file__).resolve().parent
PACKAGES = {"aseprite": "aseprite-mcp", "aseprite-godot-art": "pixelspark-art-mcp"}
OWNED = {*PACKAGES, "godot", "pixelspark-art"}


def run(args: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    if result.returncode:
        raise RuntimeError(result.stderr[-4000:] or result.stdout[-4000:])
    return result.stdout.strip()


def executable(value: str | None, name: str) -> str:
    path = value or shutil.which(name)
    if not path or not Path(path).is_file():
        raise ValueError(f"Provide --{name} or put {name} on PATH")
    return str(Path(path).resolve())


def settings(repo: Path, project: Path, aseprite: str, godot: str, uv: str) -> dict:
    shared = {"ART_REPO": str(repo), "ART_PROJECT": str(project), "ASEPRITE_PATH": aseprite, "GODOT_PATH": godot}
    servers = {name: {"command": uv, "args": ["--directory",str(BASE/package),"run","--frozen","--no-dev","-m", "aseprite_mcp" if name == "aseprite" else "pixelspark_art_mcp"], "env":shared} for name,package in PACKAGES.items()}
    servers['godot'] = {"command": "npx", "args": ["-y", "@coding-solo/godot-mcp@0.1.1"], "env":{"GODOT_PATH":godot}}
    # Disabled entries still require a valid transport in Codex config.
    servers['pixelspark-art'] = {**servers['aseprite-godot-art'], "enabled":False}
    return servers


def merge_config(previous: str, servers: dict) -> str:
    parsed = tomllib.loads(previous)
    sections = re.split(r'(?m)(?=^\[)', previous)
    kept = []
    removed = set()
    for section in sections:
        match = re.match(r'^\[mcp_servers\.([\w-]+)(?:\.[^\]]*)?\]', section)
        if match and match[1] in OWNED:
            removed.add(match[1])
        else:
            kept.append(section)
    existing = set(parsed.get('mcp_servers', {})) & OWNED
    if existing - removed:
        raise ValueError('Owned MCP tables use inline/quoted syntax; convert those tables to standard headers before setup. Other settings were preserved.')
    blocks = []
    for name, values in servers.items():
        blocks.append(f'[mcp_servers.{name}]')
        for key,value in values.items():
            if key != 'env':
                blocks.append(f'{key} = {json.dumps(value, ensure_ascii=True)}')
        if values.get('env'):
            blocks.append(f'[mcp_servers.{name}.env]')
            blocks.extend(f'{key} = {json.dumps(value, ensure_ascii=True)}' for key,value in values['env'].items())
        blocks.append('')
    result = ''.join(kept).rstrip() + '\n\n' + '\n'.join(blocks)
    check = tomllib.loads(result)
    unchanged = {k:v for k,v in parsed.items() if k != 'mcp_servers'}
    assert unchanged == {k:v for k,v in check.items() if k != 'mcp_servers'}
    for name, values in parsed.get('mcp_servers', {}).items():
        if name not in OWNED:
            assert check['mcp_servers'][name] == values
    return result


def setup(args) -> dict:
    repo, project = Path(args.repo).resolve(), Path(args.project).resolve()
    if not repo.is_dir() or not project.is_relative_to(repo) or not (project/'project.godot').is_file():
        raise ValueError('Existing Godot project must be inside the target repo')
    aseprite = executable(args.aseprite or os.environ.get('ASEPRITE_PATH'), 'aseprite')
    godot = executable(args.godot or os.environ.get('GODOT_PATH'), 'godot')
    uv = executable(None, 'uv')
    for package in PACKAGES.values():
        run([uv,'sync','--directory',str(BASE/package),'--frozen','--no-dev'])
    file = repo/'.codex/config.toml'
    previous = file.read_text(encoding='utf-8') if file.exists() else ''
    result = merge_config(previous, settings(repo, project, aseprite, godot, uv))
    changed = result != previous
    backup = None
    if changed:
        file.parent.mkdir(parents=True, exist_ok=True)
        if file.exists():
            backup = file.with_name(file.name+'.backup-'+time.strftime('%Y%m%d-%H%M%S')+'-'+hashlib.sha256(previous.encode()).hexdigest()[:8])
            if backup.exists() and backup.read_text(encoding='utf-8') != previous:
                raise ValueError('Existing configuration backup differs')
            backup.write_text(previous, encoding='utf-8', newline='\n')
        temporary = file.with_name('config.pending.toml')
        temporary.write_text(result, encoding='utf-8', newline='\n')
        os.replace(temporary, file)
    return {"ok":True,"changed":changed,"config":str(file),"backup":str(backup) if backup else None,"next":"Run doctor and reconnect Codex MCP servers. Project config requires a trusted project; setup does not change trust or approval policy."}


def doctor(args) -> dict:
    repo = Path(args.repo).resolve()
    file = repo/'.codex/config.toml'
    config = tomllib.loads(file.read_text(encoding='utf-8'))
    servers = config.get('mcp_servers', {})
    for name in (*PACKAGES, 'godot'):
        if name not in servers:
            raise ValueError(f'Missing managed server {name}')
    env = servers['aseprite-godot-art']['env']
    if Path(env['ART_REPO']).resolve() != repo or not (Path(env['ART_PROJECT'])/'project.godot').is_file():
        raise ValueError('Configured repo/project is stale')
    versions = {name:run([env[key],'--version']) for name,key in [('aseprite','ASEPRITE_PATH'),('godot','GODOT_PATH')]}
    if not versions['godot'].startswith('4.6.'):
        raise ValueError('This release is verified with Godot 4.6; use 4.6.3')
    if 'pixelspark-art' in servers and servers['pixelspark-art'].get('enabled',True):
        raise ValueError('Legacy duplicate bridge must be disabled for this project')
    lock = repo/'.art-operation.lock'
    return {"ok":True,"versions":versions,"repo":str(repo),"project":env['ART_PROJECT'],"lock_owner":lock.read_text() if lock.exists() else None,"servers":list(servers),"godot_mcp":"@coding-solo/godot-mcp@0.1.1"}


def distribution_files() -> dict[Path, Path]:
    result = {}
    for name in PACKAGES.values():
        package = BASE/name
        module = 'aseprite_mcp' if name == 'aseprite-mcp' else 'pixelspark_art_mcp'
        for filename in ('pyproject.toml','uv.lock','README.md','LICENSE','MANIFEST.in'):
            source = package/filename
            if source.is_file():
                result[source] = source.relative_to(BASE)
        for directory in (package/module, package/'tests'):
            for source in directory.rglob('*'):
                if source.is_file() and not any(part in {'__pycache__','.venv'} for part in source.parts) and (source.suffix in {'.py','.gd','.lua'} or source.name.endswith('.gd.uid')):
                    result[source] = source.relative_to(BASE)
    for source in (BASE/'examples').rglob('*'):
        relative = source.relative_to(BASE)
        if source.is_file() and not any(part in {'.godot','generated','__pycache__'} for part in relative.parts):
            authored = relative.as_posix() in {'examples/project/project.godot','examples/project/.gitignore','examples/project/rig/motion.tres'}
            if authored or (source.parent != BASE/'examples/project' and 'project' not in relative.parts and (source.suffix in {'.aseprite','.lua','.gd','.json','.md'} or source.name.endswith('.gd.uid'))):
                result[source] = relative
    for source in (BASE/'benchmarks/sword_duelist').rglob('*'):
        relative = source.relative_to(BASE)
        if source.is_file() and not any(part in {'.godot','.art-history','.venv','.pytest_cache','generated','__pycache__','assets'} for part in relative.parts) and source.suffix in {'.py','.lua','.gd','.uid','.json','.md','.aseprite','.blend','.godot','.tscn'}:
            result[source] = relative
    result[BASE/'toolkit.py'] = Path('toolkit.py')
    result[BASE/'README.md'] = Path('README.md')
    for source_name,target_name in [('toolkit-ci.yml','.github/workflows/verify.yml'),('toolkit.gitignore','.gitignore'),('toolkit.gitattributes','.gitattributes')]:
        source = BASE/source_name if (BASE/source_name).is_file() else BASE/target_name
        result[source] = Path(target_name)
    license_file = BASE/'LICENSE' if (BASE/'LICENSE').is_file() else BASE.parents[1]/'LICENSE'
    result[license_file] = Path('LICENSE')
    for source in (BASE/'tests').glob('test_*.py'):
        result[source] = source.relative_to(BASE)
    result[BASE/'tests/check_wheels.py'] = Path('tests/check_wheels.py')
    return result


def consumer_files() -> dict[Path, Path]:
    return {source: relative for source, relative in distribution_files().items()
            if relative.parts[0] in PACKAGES.values() or relative.as_posix() == 'toolkit.py'}


def update(args) -> dict:
    repo = Path(args.repo).resolve()
    target = (repo/args.target).resolve()
    if not repo.is_dir() or target == repo or not target.is_relative_to(repo) or target == BASE or target.is_relative_to(BASE) or BASE.is_relative_to(target):
        raise ValueError('Use a separate consumer directory inside the target repository')
    spec = importlib.util.spec_from_file_location('mcp_update_runtime', BASE/'aseprite-mcp/aseprite_mcp/core/runtime.py')
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    revisions = []
    source_root = Path(run(['git', 'rev-parse', '--show-toplevel'], BASE)).resolve()
    with runtime.workspace_lock(source_root), runtime.workspace_lock(repo):
        commit = run(['git', 'rev-parse', 'HEAD'], BASE)
        if run(['git', 'status', '--porcelain'], BASE):
            raise ValueError('Commit and verify the upstream source before updating a consumer')
        origin = run(['git', 'remote', 'get-url', 'origin'], BASE)
        identity = re.search(r'github\.com[:/]([^/:\s]+/[^/\s]+?)(?:\.git)?$', origin)
        entries, writes = [], {}
        for source, relative in sorted(consumer_files().items()):
            destination = (target/relative).resolve()
            if not destination.is_relative_to(target) or not source.resolve().is_relative_to(BASE):
                raise ValueError('MCP update path escapes its source or destination')
            data = source.read_bytes().replace(b'\r\n', b'\n')
            writes[destination] = data
            entries.append({'path': relative.as_posix(), 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)})
        manifest_file = (target/'mcp-update.json').resolve()
        if not manifest_file.is_relative_to(target):
            raise ValueError('MCP manifest path escapes the consumer')
        if manifest_file.is_file():
            previous = json.loads(manifest_file.read_text(encoding='utf-8'))
            old = previous.get('files') if isinstance(previous, dict) else None
            if not isinstance(old, list):
                raise ValueError('Invalid MCP update manifest')
            current = {entry['path'] for entry in entries}
            for entry in old:
                if not isinstance(entry, dict) or not isinstance(entry.get('path'), str) or not isinstance(entry.get('sha256'), str):
                    raise ValueError('Invalid MCP update file entry')
                path = (target/entry['path']).resolve()
                if not path.is_relative_to(target):
                    raise ValueError('MCP manifest path escapes the consumer')
                # shortcut: retired files need review; add transactional deletion when a release removes one.
                if entry['path'] not in current:
                    raise ValueError('Upstream retired a managed file; review it before updating: '+entry['path'])
                if not path.is_file() or hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest() != entry['sha256']:
                    raise ValueError('Preserve or reconcile the local MCP change first: '+entry['path'])
        elif target.exists():
            prefix = target.relative_to(repo).as_posix()
            dirty = set(run(['git', 'ls-files', '--modified', '--deleted', '--others', '--exclude-standard', '-z', '--', prefix], repo).split('\0'))
            tracked = set(run(['git', 'ls-files', '-z', '--', prefix], repo).split('\0'))
            if any(path.relative_to(repo).as_posix() in dirty for path in (*writes, manifest_file)):
                raise ValueError('The initial consumer has local MCP changes; preserve them before updating')
            if any(path.is_file() and path.relative_to(repo).as_posix() not in tracked for path in writes):
                raise ValueError('Initial consumer files must be tracked in Git or use a new empty target')
        manifest = {'scope': 'mcp-runtime-only', 'source_repository': identity[1] if identity else 'local',
                    'source_commit': commit, 'files': entries}
        writes[manifest_file] = (json.dumps(manifest, indent=2)+'\n').encode('utf-8')
        changed = {path: data for path, data in writes.items() if not path.is_file() or path.read_bytes().replace(b'\r\n', b'\n') != data}
        existing = [path.relative_to(repo).as_posix() for path in changed if path.is_file()]
        for start in range(0, len(existing), 100):
            revisions.append(runtime.checkpoint(repo, existing[start:start+100], 'Before MCP consumer update')['revision'])
        published = runtime.publish(repo, changed)
        for path, data in changed.items():
            if path.read_bytes() != data:
                raise RuntimeError('MCP update copy verification failed')
    return {'ok': True, 'source_commit': commit, 'changed': published, 'checkpoints': revisions,
            'next': 'Run frozen uv sync for each MCP package, test and reconnect MCP servers. Local configuration is preserved.'}


def package(args) -> dict:
    destination = Path(args.output).resolve()
    if destination == BASE or destination.is_relative_to(BASE) or BASE.is_relative_to(destination):
        raise ValueError('Distribution must be separate from the source toolkit')
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('Use an empty distribution directory')
    entries = []
    for source,relative in sorted(distribution_files().items()):
        original = source.read_bytes()
        data = original if source.suffix in {'.aseprite','.blend','.png','.gif'} else original.replace(b'\r\n',b'\n')
        target = destination/relative
        assert target.resolve().is_relative_to(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise RuntimeError('Distribution copy verification failed')
        entries.append({"path":relative.as_posix(),"sha256":digest,"source_sha256":hashlib.sha256(original).hexdigest(),"bytes":len(data)})
    try:
        commit = run(['git','rev-parse','HEAD'],BASE)
    except RuntimeError:
        commit = None
    manifest = {"version":"0.2.0","source_repository":None,"source_commit":commit,"files":entries}
    previous_manifest = BASE/'source-manifest.json'
    provenance = {}
    if previous_manifest.is_file():
        provenance = json.loads(previous_manifest.read_text(encoding='utf-8'))
    if commit:
        try:
            origin = run(['git','remote','get-url','origin'],BASE)
        except RuntimeError:
            origin = ''
        identity = re.search(r'github\.com[:/]([^/:\s]+/[^/\s]+?)(?:\.git)?$',origin)
        manifest['source_repository'] = identity[1] if identity else 'local'
        manifest['source_tree_dirty'] = bool(run(['git','status','--porcelain','--untracked-files=normal'],BASE))
        imported = provenance.get('imported_from')
        if not imported and provenance.get('source_repository') != manifest['source_repository'] and provenance.get('source_commit'):
            imported = {key:provenance[key] for key in ('source_repository','source_commit')}
        if imported:
            manifest['imported_from'] = imported
    elif provenance:
        manifest.update({key:provenance[key] for key in ('source_repository','source_commit','source_tree_dirty','imported_from') if key in provenance})
    (destination/'source-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n', encoding='utf-8')
    return {"ok":True,"output":str(destination),"files":len(entries),"source_commit":manifest['source_commit']}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command',required=True)
    install = commands.add_parser('setup')
    install.add_argument('--repo',required=True)
    install.add_argument('--project',required=True)
    install.add_argument('--aseprite')
    install.add_argument('--godot')
    health = commands.add_parser('doctor')
    health.add_argument('--repo',required=True)
    export = commands.add_parser('package')
    export.add_argument('--output',required=True)
    upgrade = commands.add_parser('update')
    upgrade.add_argument('--repo',required=True)
    upgrade.add_argument('--target',required=True,help='Consumer directory relative to that repo, e.g. tools/mcp')
    args = parser.parse_args()
    print(json.dumps({'setup':setup,'doctor':doctor,'package':package,'update':update}[args.command](args),indent=2))


if __name__ == '__main__':
    main()
