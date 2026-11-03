#!/usr/bin/env python3
"""Pull policies and M3 integration against pinned Git; every file remains compared."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tier', default='native')
    parser.add_argument('--filter', default='')
    a = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    out = root / 'target/runs' / ('wire-pull-' + a.tier)
    out.mkdir(parents=True, exist_ok=True)
    git = os.environ['DEN_GIT']
    assert hashlib.sha256(Path(git).read_bytes()).hexdigest() == 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
    den = str(root / 'target' / a.tier / 'den')
    oracle = runpy.run_path(str(root / 'tools/oracle.py'))
    os.environ.update(GIT_AUTHOR_NAME='Den Tester', GIT_AUTHOR_EMAIL='den@example.invalid',
                      GIT_COMMITTER_NAME='Den Tester', GIT_COMMITTER_EMAIL='den@example.invalid', GIT_MERGE_AUTOEDIT='no')
    environment = {k: v for k, v in os.environ.items() if k.startswith(('GIT_', 'DEN_')) or k in ('HOME', 'TZ', 'LC_ALL', 'PATH', 'TMPDIR')}
    captures = out / 'captures.jsonl'
    captures.write_text('')
    def run(argv, cwd=None):
        p = subprocess.run(list(map(str, argv)), cwd=cwd, input=b'', capture_output=True, timeout=60)
        with captures.open('a') as f:
            f.write(json.dumps(dict(argv=list(map(str, argv)), cwd=str(cwd), environment=environment, stdin='',
                                   stdout=p.stdout.hex(), stderr=p.stderr.hex(), exit=p.returncode)) + '\n')
        assert p.returncode == 0, (argv, p.stdout, p.stderr)
        return p.stdout.strip().decode()
    cases = [
        ('ff-default', 'ff', [], []),
        ('ff-explicit', 'ff', ['origin', 'main'], []),
        ('uptodate', 'uptodate', [], []),
        ('uptodate-rebase', 'uptodate', ['--rebase'], []),
        ('divergent-unconfigured', 'clean', [], []),
        ('merge-linear', 'clean', ['--no-rebase'], []),
        ('merge-config', 'clean', [], [('pull.rebase', 'false')]),
        ('merge-ff-config-false', 'clean', [], [('pull.ff', 'false')]),
        ('ff-no-ff-config', 'ff', [], [('pull.ff', 'false')]),
        ('ff-no-ff-flag', 'ff', ['--no-ff'], []),
        ('divergent-ff-only', 'clean', ['--ff-only'], []),
        ('divergent-ff-only-config', 'clean', [], [('pull.ff', 'only')]),
        ('rebase-linear', 'clean', ['--rebase'], []),
        ('rebase-config', 'clean', [], [('pull.rebase', 'true')]),
        ('merge-conflict', 'conflict', ['--no-rebase'], []),
        ('rebase-conflict', 'conflict', ['--rebase'], []),
        ('ff-rebase', 'ff', ['--rebase'], []),
        ('ff-rebase-config', 'ff', [], [('pull.rebase', 'true')]),
        ('quiet-ff', 'ff', ['-q'], []),
        ('quiet-rebase', 'clean', ['-q', '--rebase'], []),
        ('rebase-overrides-ff-only', 'clean', ['--rebase'], [('pull.ff', 'only')]),
        ('merge-overrides-ff-only', 'clean', ['--no-rebase'], [('pull.ff', 'only')]),
        ('ff-only-overrides-rebase', 'clean', ['--ff-only'], [('pull.rebase', 'true')]),
        ('no-rebase-overrides-config', 'clean', ['--no-rebase'], [('pull.rebase', 'true')]),
        ('rebase-overrides-config', 'clean', ['--rebase'], [('pull.rebase', 'false')]),
        ('ff-true-config', 'clean', [], [('pull.ff', 'true')]),
    ]
    rows = []
    for name, kind, flags, config in cases:
        if a.filter not in name:
            continue
        directory = out / name
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir()
        origin, server, seed, work = [directory / n for n in ('origin', 'remote.git', 'seed', 'work')]
        run([git, 'init', '-q', origin])
        (origin / 'a').write_text('first\nmiddle\nlast\n')
        (origin / 'keep').write_text('keep\n')
        run([git, 'add', '.'], origin)
        run([git, 'commit', '-qm', 'base'], origin)
        run([git, 'clone', '-q', '--bare', origin, server])
        run([git, 'clone', '-q', server.as_uri(), seed])
        for key, value in [('gc.auto', '0'), ('maintenance.auto', 'false'), *config]:
            run([git, 'config', key, value], seed)
        if kind in ('clean', 'conflict'):
            (seed / 'a').write_text('ours\nmiddle\nlast\n')
            run([git, 'commit', '-qam', 'ours'], seed)
        if kind != 'uptodate':
            (origin / 'a').write_text('theirs\nmiddle\nlast\n' if kind == 'conflict' else 'first\nmiddle\ntheirs\n')
            run([git, 'commit', '-qam', 'theirs'], origin)
            run([git, 'push', '-q', server.as_uri(), 'HEAD:refs/heads/main'], origin)
        results = []
        for tool in (git, den):
            if work.exists():
                shutil.rmtree(work)
            shutil.copytree(seed, work, symlinks=True)
            argv = [tool, 'pull', *flags]
            result = oracle['capture'](argv, work, index_proof=True)
            with captures.open('a') as f:
                f.write(json.dumps(dict(argv=argv, cwd=str(work), environment=environment, stdin='',
                                       stdout=result['stdout'], stderr=result['stderr'], exit=result['status'], state=result)) + '\n')
            results.append(result)
        equal = oracle['equivalent'](*results, 'index-stat-proven')
        rows.append(dict(name=name, kind=kind, argv=['pull', *flags], config=config, parity=equal, outcomes=results))
        print(('PASS' if equal else 'FAIL') + ' pull-' + name, flush=True)
    assert rows, 'empty pull selection'
    (out / 'summary.json').write_text(json.dumps(dict(rows=rows, zero_skips=True), indent=2) + '\n')
    failures = sum(not row['parity'] for row in rows)
    print(f'pull: {len(rows)} groups, {failures} failures; zero skips', flush=True)
    return int(bool(failures))


if __name__ == '__main__':
    raise SystemExit(main())
