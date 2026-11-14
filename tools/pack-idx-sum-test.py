#!/usr/bin/env python3
"""A pack index whose own trailing checksum is wrong, read beside the pinned
Git (black-box: its object reads do not check that checksum; verify-pack
and fsck do).

A repository of a few commits is packed by Git, then the last byte of its
idx (the idx's own SHA-1) is flipped. Every row runs both tools on that
repository: the reads must equal Git's exit status, stdout and stderr; the
verification rows must fail for both (their messages differ).
"""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess

READS = [['cat-file', '-p', 'HEAD'], ['cat-file', '-p', 'HEAD:a.txt'], ['log', '--oneline'],
         ['show', '--stat', 'HEAD'], ['diff', '--cached', '--quiet'], ['rev-parse', 'HEAD~1^{tree}']]
CHECKS = [['verify-pack', 'IDX'], ['fsck', '--full']]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tier', default='native')
    parser.add_argument('--dev-oracle', action='store_true', help='Darwin development evidence only; not the pinned Linux oracle')
    a = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = root / 'target' / ('pack-idx-sum-' + a.tier)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    git = os.environ['DEN_GIT']
    digest = hashlib.sha256(Path(git).read_bytes()).hexdigest()
    if a.dev_oracle:
        assert os.uname().sysname == 'Darwin', 'development oracle is Darwin-only'
        print('DEV ORACLE (not pinned Linux evidence):', digest, flush=True)
    else:
        assert digest == 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
    den = str(root / 'target' / a.tier / 'den')
    env = dict(os.environ, GIT_AUTHOR_NAME='Den Tester', GIT_AUTHOR_EMAIL='den@example.invalid',
               GIT_COMMITTER_NAME='Den Tester', GIT_COMMITTER_EMAIL='den@example.invalid')

    def run(args, cwd):
        p = subprocess.run([str(x) for x in args], cwd=cwd, capture_output=True, env=env)
        assert p.returncode == 0, (args, p.stdout[-300:], p.stderr[-300:])
        return p.stdout

    repo = out / 'repo'
    run([git, 'init', '-q', '-b', 'main', repo], out)
    for i in range(4):
        (repo / 'a.txt').write_text(f'revision {i}\n' + 'line\n' * 50)
        (repo / f'f{i}.txt').write_text(f'file {i}\n')
        run([git, 'add', '-A'], repo)
        run([git, 'commit', '-q', '--date', f'{1700000000 + 60 * i} +0000',
             '-m', f'commit {i}'], repo)
    run([git, '-c', 'gc.writeCommitGraph=false', '-c', 'repack.writeBitmaps=false', 'gc', '-q'], repo)
    idx = list((repo / '.git/objects/pack').glob('*.idx'))
    assert len(idx) == 1 and not list((repo / '.git/objects').glob('[0-9a-f][0-9a-f]/*')), idx
    data = bytearray(idx[0].read_bytes())
    data[-1] ^= 1
    idx[0].chmod(0o644)
    idx[0].write_bytes(bytes(data))

    rows = []
    for argv in READS:
        g = subprocess.run([git, *argv], cwd=repo, capture_output=True)
        d = subprocess.run([den, *argv], cwd=repo, capture_output=True)
        same = (g.returncode, g.stdout, g.stderr) == (d.returncode, d.stdout, d.stderr)
        ok = same and g.returncode in (0, 1)
        name = 'idx-sum-read-' + '-'.join(x.replace('^{tree}', '-tree').replace('~', '-').replace(':', '-') for x in argv)
        print(('PASS ' if ok else 'FAIL ') + name +
              ('' if ok else f' git {g.returncode} {g.stdout[-120:]!r} {g.stderr[-160:]!r}'
                             f' den {d.returncode} {d.stdout[-120:]!r} {d.stderr[-160:]!r}'), flush=True)
        rows.append(ok)
    for argv in CHECKS:
        argv = [str(idx[0]) if x == 'IDX' else x for x in argv]
        g = subprocess.run([git, *argv], cwd=repo, capture_output=True)
        d = subprocess.run([den, *argv], cwd=repo, capture_output=True)
        ok = g.returncode != 0 and d.returncode != 0
        name = 'idx-sum-check-' + argv[0]
        print(('PASS ' if ok else 'FAIL ') + name + f' git exit {g.returncode} den exit {d.returncode}' +
              ('' if ok else f' den {d.stderr[-160:]!r}'), flush=True)
        rows.append(ok)
    failures = sum(not ok for ok in rows)
    print(f'pack-idx-sum: {len(rows)} rows, {failures} failures; zero skips', flush=True)
    return int(failures > 0)


if __name__ == '__main__':
    raise SystemExit(main())
