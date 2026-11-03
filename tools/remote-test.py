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
    environment = {k: v for k, v in os.environ.items() if k.startswith(('GIT_', 'DEN_')) or k in ('LC_ALL', 'TZ', 'HOME', 'PATH', 'TMPDIR')}
    work = out / 'work'
    def run(argv, cwd=None):
        r = subprocess.run(list(map(str, argv)), cwd=cwd, input=b'', capture_output=True, timeout=60)
        captures.append(dict(argv=list(map(str, argv)), environment=environment, cwd=str(cwd), stdin='', stdout=r.stdout.hex(), stderr=r.stderr.hex(), exit=r.returncode))
        (out / 'captures.json').write_text(json.dumps(captures, indent=2) + '\n')
        return r
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
    ]
    for name, commands in cases:
        outcomes = []
        for tool in ([git] if a.oracle_only else [git, den]):
            if work.exists():
                shutil.rmtree(work)
            assert run([git, 'init', '-q', work]).returncode == 0
            states = []
            for command in commands:
                r = run([tool, 'remote', *command], work)
                states.append(dict(stdout=r.stdout.hex(), stderr=r.stderr.hex(), exit=r.returncode,
                                   config=(work / '.git/config').read_bytes().hex()))
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
