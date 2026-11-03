#!/usr/bin/env python3
"""Typed push matrix against the pinned binary, never implementation source."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tier', default='native')
    parser.add_argument('--oracle-only', action='store_true')
    a = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    out = root / 'target/runs' / ('wire-policy-' + a.tier)
    out.mkdir(parents=True, exist_ok=True)
    git = os.environ['DEN_GIT']
    assert hashlib.sha256(Path(git).read_bytes()).hexdigest() == 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
    den = root / 'target' / a.tier / 'den'
    captures, rows = [], []
    capture_path = out / 'captures.jsonl'
    capture_path.write_text('')
    selected_env = {k: v for k, v in os.environ.items() if k.startswith(('GIT_', 'DEN_')) or k in ('HOME', 'TZ', 'LC_ALL', 'PATH', 'TMPDIR')}

    def run(argv, cwd=None, data=None, check=True):
        p = subprocess.run(list(map(str, argv)), cwd=cwd, input=data, capture_output=True, timeout=60)
        row = dict(argv=list(map(str, argv)), cwd=str(cwd), environment=selected_env,
                   stdin=(data or b'').hex(), stdout=p.stdout.hex(), stderr=p.stderr.hex(), exit=p.returncode)
        with capture_path.open('a') as f:
            f.write(json.dumps(row) + '\n')
        if check:
            assert p.returncode == 0, row
        return p

    source = out / 'source.git'
    if source.exists():
        shutil.rmtree(source)
    run([git, 'init', '-q', '--bare', source])
    def object_id(*args, data=None):
        return run([git, *args], source, data).stdout.strip().decode()
    blob = object_id('hash-object', '-w', '--stdin', data=b'one\n')
    other = object_id('hash-object', '-w', '--stdin', data=b'two\n')
    tree = object_id('mktree', data=f'100644 blob {blob}\tfile\n'.encode())
    c0 = object_id('commit-tree', tree, '-m', 'base')
    c1 = object_id('commit-tree', tree, '-p', c0, '-m', 'forward')
    side = object_id('commit-tree', tree, '-p', c0, '-m', 'side')
    def tag(target, kind, name):
        return object_id('mktag', data=(f'object {target}\ntype {kind}\ntag {name}\ntagger Den <den@example.invalid> 1700000000 +0000\n\n{name}\n').encode())
    t0 = tag(c0, 'commit', 'old')
    t1 = tag(c1, 'commit', 'new')
    tt = tag(tree, 'tree', 'tree')
    values = dict(commit=c0, forward=c1, divergent=side, tag=t0, forward_tag=t1, tree_tag=tt, tree=tree, blob=blob, other_blob=other)
    target = out / 'target.git'
    failures = []
    namespaces = ('refs/heads/item', 'refs/tags/item', 'refs/notes/item', 'refs/stash', 'refs/custom/item', 'refs/remotes/item')
    for ref in namespaces:
        for before_name in ('absent', *values):
            for after_name, after in values.items():
                # Heads cannot hold non-commits even as a fixture input.
                if ref.startswith('refs/heads/') and before_name not in ('absent', 'commit', 'forward', 'divergent'):
                    continue
                for force in (False, True):
                    # Force cases cover all source types and rewind, not duplicate the full table.
                    if force and before_name != 'forward':
                        continue
                    name = f'{ref}:{before_name}->{after_name}' + (':force' if force else '')
                    outcomes = []
                    for tool in ([git] if a.oracle_only else [git, den]):
                        if target.exists():
                            shutil.rmtree(target)
                        shutil.copytree(source, target)
                        if before_name != 'absent':
                            run([git, 'update-ref', ref, values[before_name]], target)
                        before = run([git, 'for-each-ref', '--format=%(refname) %(objectname)'], target).stdout
                        p = run([tool, 'push', '-q', *(['--force'] if force else []), target.as_uri(), f'{after}:{ref}'], source, check=False)
                        after_refs = run([git, 'for-each-ref', '--format=%(refname) %(objectname)'], target).stdout
                        if p.returncode:
                            assert after_refs == before, name + ': rejection changed refs'
                        else:
                            assert run([git, 'rev-parse', ref], target).stdout.strip().decode() == after, name
                        outcomes.append(dict(exit=p.returncode, stdout=p.stdout.hex(), stderr=p.stderr.hex(), refs=after_refs.hex()))
                    equal = a.oracle_only or ((outcomes[0]['exit'] == 0) == (outcomes[1]['exit'] == 0) and outcomes[0]['refs'] == outcomes[1]['refs'])
                    rows.append(dict(name=name, parity=equal, outcomes=outcomes))
                    if not equal:
                        failures.append(name)
                    if len(rows) % 50 == 0:
                        print(f'policy rows {len(rows)}, mismatches {len(failures)}', flush=True)
    (out / 'summary.json').write_text(json.dumps(dict(rows=rows, failures=failures, zero_skips=True), indent=2) + '\n')
    for name in failures:
        print('FAIL wire-policy ' + name, flush=True)
    print(f'wire-policy: {len(rows)} rows, {len(failures)} failures; zero skips', flush=True)
    return int(bool(failures))


if __name__ == '__main__':
    raise SystemExit(main())
