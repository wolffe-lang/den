#!/usr/bin/env python3
"""Exact remote command/config comparisons under one physical path."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--tier', default='native')
    p.add_argument('--oracle-only', action='store_true')
    a = p.parse_args()
    root = Path(__file__).resolve().parent.parent
    out = root / 'target/runs' / ('wire-remote-' + a.tier)
    out.mkdir(parents=True, exist_ok=True)
    git = os.environ['DEN_GIT']
    assert hashlib.sha256(Path(git).read_bytes()).hexdigest() == 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
    den = root / 'target' / a.tier / 'den'
    captures, rows = [], []
    identity_env = dict(GIT_AUTHOR_NAME='Den Tester', GIT_AUTHOR_EMAIL='den@example.invalid',
                        GIT_COMMITTER_NAME='Den Tester', GIT_COMMITTER_EMAIL='den@example.invalid')
    environment = {k: v for k, v in os.environ.items() if k.startswith(('GIT_', 'DEN_')) or k in ('LC_ALL', 'TZ', 'HOME', 'PATH', 'TMPDIR')}
    environment.update(identity_env)
    work = out / 'work'
    def run(argv, cwd=None):
        r = subprocess.run(list(map(str, argv)), cwd=cwd, input=b'', capture_output=True, timeout=60,
                           env={**os.environ, **identity_env})
        captures.append(dict(argv=list(map(str, argv)), environment=environment, cwd=str(cwd), stdin='', stdout=r.stdout.hex(), stderr=r.stderr.hex(), exit=r.returncode))
        (out / 'captures.json').write_text(json.dumps(captures, indent=2) + '\n')
        return r
    visible = {}
    for key in ('user.name', 'user.email'):
        result = run([git, 'config', '--show-origin', '--get', key], root)
        assert result.returncode == 0
        visible[key] = result.stdout.decode()
    (out / 'identity-inputs.json').write_text(json.dumps(dict(environment=environment, visible_global=visible,
        global_config=Path(os.environ['GIT_CONFIG_GLOBAL']).read_bytes().hex()), indent=2) + '\n')
    add = ['add', 'origin', 'file:///a/source.git']
    cases = [
        ('empty', [[]]),
        ('empty-verbose', [['-v']]),
        ('add', [add]),
        ('add-list', [add, []]),
        ('add-verbose', [add, ['-v']]),
        ('add-get-url', [add, ['get-url', 'origin']]),
        ('duplicate', [add, add]),
        ('two-sorted', [['add', 'z', 'z-url'], ['add', 'a', 'a-url'], []]),
        ('two-verbose', [['add', 'z', 'z-url'], ['add', 'a', 'a-url'], ['-v']]),
        ('set-url', [add, ['set-url', 'origin', 'file:///b/source.git'], ['get-url', 'origin']]),
        ('set-url-verbose', [add, ['set-url', 'origin', 'file:///b/source.git'], ['-v']]),
        ('set-url-quoted', [add, ['set-url', 'origin', 'space and "quote"\\path']]),
        ('add-quoted', [['add', 'origin', 'space and "quote"\\path']]),
        ('get-missing', [['get-url', 'missing']]),
        ('set-missing', [['set-url', 'missing', 'file:///b']]),
        ('remove', [add, ['remove', 'origin'], []]),
        ('remove-missing', [['remove', 'missing']]),
        ('remove-alias', [add, ['rm', 'origin']]),
        ('rename', [add, ['rename', 'origin', 'upstream'], ['-v']]),
        ('rename-missing', [['rename', 'missing', 'upstream']]),
        ('rename-existing', [add, ['add', 'upstream', 'other'], ['rename', 'origin', 'upstream']]),
        ('rename-self', [add, ['rename', 'origin', 'origin']]),
        ('name-slash', [['add', 'team/sub', 'file:///a/source.git'], ['-v']]),
        ('name-invalid', [['add', 'bad..name', 'file:///a/source.git']]),
        ('add-space-edges', [['add', 'origin', ' leading and trailing ']]),
        ('add-comment-value', [['add', 'origin', 'a#b;c']]),
        ('add-control-value', [['add', 'origin', 'a\nb\tc']]),
        ('mode-preserved', [add]),
        ('set-comment', [['set-url', 'origin', 'new']]),
        ('set-blank', [['set-url', 'origin', 'new']]),
        ('remove-comment', [['remove', 'origin']]),
        ('rename-only-fetch', [['rename', 'origin', 'next']]),
        ('foreign-lock', [add]),
        ('no-newline', [add]),
        ('duplicate-sections', [['set-url', 'origin', 'new']]),
        ('empty-section', [['get-url', 'origin']]),
        ('tracking-rename', [['rename', 'origin', 'next']]),
        ('tracking-remove', [['remove', 'origin']]),
        ('tracking-rename-packed', [['rename', 'origin', 'next']]),
        ('tracking-remove-packed', [['remove', 'origin']]),
        ('tracking-rename-symbolic', [['rename', 'origin', 'next']]),
        ('tracking-remove-symbolic', [['remove', 'origin']]),
        ('upstream-current', [['@branch', '--set-upstream-to=origin/main']]),
        ('upstream-named', [['@branch', '--set-upstream-to', 'origin/main', 'main']]),
        ('upstream-short', [['@branch', '-u', 'origin/main']]),
        ('upstream-missing', [['@branch', '--set-upstream-to=origin/missing']]),
        ('upstream-local', [['@branch', '--set-upstream-to=other']]),
        ('upstream-then-remove', [['@branch', '-u', 'origin/main'], ['remove', 'origin']]),
    ]
    setups = {
        'set-comment': '[remote "origin"] # header\n  url = old # trailing\n  fetch = +refs/heads/*:refs/remotes/origin/*\n',
        'set-blank': '[remote "origin"]\n\n  url = old\n\n  fetch = +refs/heads/*:refs/remotes/origin/*\n\n',
        'remove-comment': '# before\n[remote "origin"]\n # inside\n url = old\n# after\n[extra]\n key = value\n',
        'rename-only-fetch': '[remote "origin"]\n url = +refs/heads/*:refs/remotes/origin/*\n fetch = +refs/heads/*:refs/remotes/origin/*\n',
        'duplicate-sections': '[remote "origin"]\n fetch = +refs/heads/*:refs/remotes/origin/*\n[remote "origin"]\n url = old\n',
        'empty-section': '[remote "origin"]\n',
    }
    for name, commands in cases:
        outcomes = []
        for tool in ([git] if a.oracle_only else [git, den]):
            if work.exists():
                shutil.rmtree(work)
            assert run([git, 'init', '-q', work]).returncode == 0
            config = work / '.git/config'
            if name in setups:
                with config.open('a') as f:
                    f.write(setups[name])
            if name == 'mode-preserved':
                config.chmod(0o600)
            if name == 'foreign-lock':
                (work / '.git/config.lock').write_bytes(b'foreign\n')
            if name == 'no-newline':
                config.write_bytes(config.read_bytes().rstrip(b'\n'))
            if name.startswith(('tracking-', 'upstream-')):
                tree = run([git, 'mktree'], work).stdout.strip().decode()
                commit = run([git, 'commit-tree', tree, '-m', 'base'], work).stdout.strip().decode()
                for ref in ('refs/heads/main', 'refs/heads/other', 'refs/remotes/origin/main', 'refs/remotes/origin/topic', 'refs/remotes/unrelated/main'):
                    assert run([git, 'update-ref', ref, commit], work).returncode == 0
                assert run([git, 'remote', *add], work).returncode == 0
                if name.startswith('tracking-'):
                    assert run([git, 'branch', '-u', 'origin/main'], work).returncode == 0
                if name.endswith('-packed'):
                    assert run([git, 'pack-refs', '--all'], work).returncode == 0
                if name.endswith('-symbolic'):
                    assert run([git, 'symbolic-ref', 'refs/remotes/origin/HEAD', 'refs/remotes/origin/main'], work).returncode == 0
            states = []
            for command in commands:
                argv = ['branch', *command[1:]] if command and command[0] == '@branch' else ['remote', *command]
                r = run([tool, *argv], work)
                refstate = {}
                for folder in ('refs', 'logs'):
                    for path in (work / '.git' / folder).rglob('*'):
                        if path.is_file():
                            refstate[str(path.relative_to(work / '.git'))] = [path.read_bytes().hex(), path.stat().st_mode & 0o777]
                packed = work / '.git/packed-refs'
                if packed.exists():
                    refstate['packed-refs'] = [packed.read_bytes().hex(), packed.stat().st_mode & 0o777]
                states.append(dict(stdout=r.stdout.hex(), stderr=r.stderr.hex(), exit=r.returncode,
                                   refs=refstate, config=config.read_bytes().hex(), mode=config.stat().st_mode & 0o777,
                                   lock=(work / '.git/config.lock').read_bytes().hex() if (work / '.git/config.lock').exists() else None))
            outcomes.append(states)
        equal = a.oracle_only or outcomes[0] == outcomes[1]
        rows.append(dict(name=name, parity=equal, outcomes=outcomes))
        if not equal:
            print('FAIL remote-' + name, flush=True)
    (out / 'summary.json').write_text(json.dumps(dict(rows=rows, zero_skips=True), indent=2) + '\n')
    failures = sum(not r['parity'] for r in rows)
    print(f'remote: {len(rows)} rows, {failures} failures; zero skips', flush=True)
    return int(bool(failures))


if __name__ == '__main__':
    raise SystemExit(main())
