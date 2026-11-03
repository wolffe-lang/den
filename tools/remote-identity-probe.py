#!/usr/bin/env python3
"""Reproduce remote-rename identity with visible global config, without overrides."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parent.parent
out = root / 'target/runs/wire-remote-identity'
out.mkdir(parents=True, exist_ok=True)
git = os.environ['DEN_GIT']
assert hashlib.sha256(Path(git).read_bytes()).hexdigest() == 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
env = dict(os.environ)
for key in ('GIT_AUTHOR_NAME', 'GIT_AUTHOR_EMAIL', 'GIT_COMMITTER_NAME', 'GIT_COMMITTER_EMAIL', 'EMAIL'):
    env.pop(key, None)
selected = {k: v for k, v in env.items() if k.startswith(('GIT_', 'DEN_')) or k in ('HOME', 'TZ', 'LC_ALL', 'TMPDIR', 'PATH')}
captures = []
work = out / 'work'
if work.exists():
    shutil.rmtree(work)
def run(args):
    p = subprocess.run([git, *args], cwd=work if work.exists() else root,
                       input=b'', capture_output=True, env=env, timeout=60)
    captures.append(dict(argv=[git, *args], environment=selected, stdin='', stdout=p.stdout.hex(), stderr=p.stderr.hex(), exit=p.returncode))
    (out / 'captures.json').write_text(json.dumps(captures, indent=2) + '\n')
    assert p.returncode == 0, captures[-1]
    return p.stdout
run(['init', '-q', str(work)])
visible = {}
for key in ('user.name', 'user.email'):
    visible[key] = run(['config', '--show-origin', '--get', key]).decode()
tree = run(['mktree']).strip().decode()
commit = run(['commit-tree', tree, '-m', 'identity fixture']).strip().decode()
run(['remote', 'add', 'origin', 'file:///unused/fixture.git'])
run(['update-ref', 'refs/remotes/origin/main', commit])
before = (work / '.git/logs/refs/remotes/origin/main').read_bytes()
run(['remote', 'rename', 'origin', 'next'])
after = (work / '.git/logs/refs/remotes/next/main').read_bytes()
assert after.startswith(before)
for key in ('user.name', 'user.email'):
    assert run(['config', '--show-origin', '--get', key]).decode() == visible[key]
summary = dict(visible_global=visible, environment=selected,
               home_visible=Path(env['HOME']).is_dir(),
               global_config_visible=Path(env['GIT_CONFIG_GLOBAL']).is_file(),
               global_config=Path(env['GIT_CONFIG_GLOBAL']).read_bytes().hex(),
               original_log=before.hex(), renamed_log=after.hex(), appended=after[len(before):].hex())
(out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print('remote identity probe: global config visibility checked before/after rename; raw identity retained')
