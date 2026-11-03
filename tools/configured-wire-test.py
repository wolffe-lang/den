#!/usr/bin/env python3
"""Configured file transport porcelain: exact output/status and complete file state."""
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
    a = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    out = root / 'target/runs' / ('wire-configured-' + a.tier)
    out.mkdir(parents=True, exist_ok=True)
    git = os.environ['DEN_GIT']
    assert hashlib.sha256(Path(git).read_bytes()).hexdigest() == 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
    den = root / 'target' / a.tier / 'den'
    env = dict(os.environ, GIT_AUTHOR_NAME='Den Tester', GIT_AUTHOR_EMAIL='den@example.invalid',
               GIT_COMMITTER_NAME='Den Tester', GIT_COMMITTER_EMAIL='den@example.invalid')
    environment = {k: v for k, v in env.items() if k.startswith(('GIT_', 'DEN_')) or k in ('HOME', 'TZ', 'LC_ALL', 'TMPDIR', 'PATH')}
    captures = []
    def run(argv, cwd=None, check=True, data=b''):
        p = subprocess.run(list(map(str, argv)), cwd=cwd, env=env, input=data, capture_output=True, timeout=60)
        captures.append(dict(argv=list(map(str, argv)), cwd=str(cwd), environment=environment, stdin=data.hex(),
                             stdout=p.stdout.hex(), stderr=p.stderr.hex(), exit=p.returncode))
        (out / 'captures.json').write_text(json.dumps(captures, indent=2) + '\n')
        if check:
            assert p.returncode == 0, captures[-1]
        return p
    def reset(path, template=None):
        if path.exists():
            shutil.rmtree(path)
        if template:
            shutil.copytree(template, path)
    def snapshot(path):
        return {str(p.relative_to(path)): [p.stat().st_mode & 0o777, p.read_bytes().hex()]
                for p in path.rglob('*') if p.is_file()}
    source, original, work, seed = [out / n for n in ('remote.git', 'original.git', 'work', 'seed')]
    for path in (source, original, work, seed):
        reset(path)
    run([git, 'init', '-q', '--bare', source])
    tree = run([git, 'mktree'], source).stdout.strip().decode()
    first = run([git, 'commit-tree', tree, '-m', 'base'], source).stdout.strip().decode()
    second = run([git, 'commit-tree', tree, '-p', first, '-m', 'forward'], source).stdout.strip().decode()
    for ref in ('refs/heads/main', 'refs/heads/topic'):
        run([git, 'update-ref', ref, first], source)
    run([git, 'clone', '-q', source.as_uri(), seed])
    # Keep every canonical input object locally: these rows isolate config/ref
    # publication. The inherited wire matrix independently requires pack import.
    shutil.copytree(source / 'objects', seed / '.git/objects', dirs_exist_ok=True)
    run([git, 'config', 'gc.auto', '0'], seed)
    run([git, 'config', 'maintenance.auto', 'false'], seed)
    shutil.copytree(source, original)
    cases = [
        ('fetch-named-quiet', ['fetch', '-q', 'origin']),
        ('fetch-default-quiet', ['fetch', '-q']),
        ('fetch-named-report', ['fetch', 'origin']),
        ('fetch-default-report', ['fetch']),
        ('fetch-prune-quiet', ['fetch', '-q', '--prune']),
        ('fetch-prune-report', ['fetch', '--prune']),
        ('fetch-rewind-tracking', ['fetch', '-q']),
        ('fetch-different-remote', ['fetch', '-q', 'upstream']),
        ('push-default-quiet', ['push', '-q']),
        ('push-u-quiet', ['push', '-q', '-u', 'origin', 'main']),
        ('push-default-report', ['push']),
        ('push-u-report', ['push', '-u', 'origin', 'main']),
    ]
    rows = []
    for name, argv in cases:
        outcomes = []
        for tool in (git, den):
            reset(source, original)
            reset(work, seed)
            if name.startswith('fetch-'):
                run([git, 'update-ref', 'refs/heads/main', second], source)
                if 'prune' in name:
                    run([git, 'update-ref', '-d', 'refs/heads/topic'], source)
                if name == 'fetch-rewind-tracking':
                    run([git, 'update-ref', 'refs/remotes/origin/main', second], work)
                    run([git, 'update-ref', 'refs/heads/main', first], source)
                if name == 'fetch-different-remote':
                    run([git, 'remote', 'rename', 'origin', 'upstream'], work)
            else:
                run([git, 'update-ref', 'refs/heads/main', second], work)
                if name.startswith('push-u-'):
                    run([git, 'config', '--remove-section', 'branch.main'], work)
            result = run([tool, *argv], work, check=False)
            outcomes.append(dict(stdout=result.stdout.hex(), stderr=result.stderr.hex(), exit=result.returncode,
                                 local=snapshot(work), remote=snapshot(source)))
        equal = outcomes[0] == outcomes[1]
        rows.append(dict(name=name, parity=equal, outcomes=outcomes))
        if not equal:
            print('FAIL configured-' + name, flush=True)
    (out / 'summary.json').write_text(json.dumps(dict(rows=rows, zero_skips=True), indent=2) + '\n')
    failures = sum(not row['parity'] for row in rows)
    print(f'configured: {len(rows)} rows, {failures} failures; zero skips', flush=True)
    return int(bool(failures))


if __name__ == '__main__':
    raise SystemExit(main())
