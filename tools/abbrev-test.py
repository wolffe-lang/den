#!/usr/bin/env python3
"""den#100: short object names in a large repository, as fetch, pull, merge
and checkout print them.

Git prints seven-digit names only below 16,384 packed objects; from there each
further factor of four in the packed count adds one digit (eight from 16,384,
nine from 65,536), loose objects are not counted, and an object stored in two
packs counts twice. The fetch and push summary column is at least two names
and "..." wide, at the configured length or this default. A repository the issue's size (42,651 objects) prints
eight-digit names. Each row runs the pinned Git and den on identical copies
and requires the same exit status, stdout, stderr and HEAD.
"""
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
    parser.add_argument('--den')
    parser.add_argument('--filter', default='')
    a = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = root / 'target/runs' / ('abbrev-' + a.tier)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    git = os.environ['DEN_GIT']
    assert hashlib.sha256(Path(git).read_bytes()).hexdigest() == 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
    den = a.den or str(root / 'target' / a.tier / 'den')
    os.environ['GIT_MERGE_AUTOEDIT'] = 'no'

    def run(args, cwd, data=None):
        p = subprocess.run([str(x) for x in args], cwd=cwd, capture_output=True, input=data)
        assert p.returncode == 0, (args, p.stdout[-300:], p.stderr[-300:])
        return p.stdout

    def blobs(n, salt):
        return ''.join(f'blob\ndata {len(body)}\n{body}\n'
                       for body in (f'{salt} {i}\n' for i in range(n))).encode()

    def fixture(name, packed=0, loose=0, duplicated=0, local=False, config=None, moved=1):
        """A clone of a small remote, its object store grown to the given shape;
        the remote then moves on by `moved` commits."""
        base = out / name
        base.mkdir()
        origin, work = base / 'origin', base / 'work'
        run([git, 'init', '-q', origin], base)
        (origin / 'a').write_text('a\n')
        run([git, 'add', 'a'], origin)
        run([git, 'commit', '-qm', 'base'], origin)
        run([git, 'clone', '-q', origin, work], base)
        run([git, 'config', 'gc.auto', '0'], work)
        if config is not None:
            run([git, 'config', 'core.abbrev', config], work)
        run([git, 'repack', '-qad'], work)
        if packed:
            run([git, 'fast-import', '--quiet'], work, blobs(packed, 'packed'))
        if duplicated:
            run([git, 'fast-import', '--quiet'], work, blobs(duplicated, 'duplicated'))
            ids = run([git, 'cat-file', '--batch-all-objects', '--batch-check=%(objectname) %(objecttype)'], work)
            wanted = [line.split()[0] for line in ids.decode().splitlines() if line.endswith(' blob')]
            run([git, 'pack-objects', '-q', '.git/objects/pack/pack'], work, ('\n'.join(wanted) + '\n').encode())
        if loose:
            src = base / 'loose'
            src.mkdir()
            paths = []
            for i in range(loose):
                p = src / str(i)
                p.write_text(f'loose {i}\n')
                paths.append(str(p))
            run([git, 'hash-object', '-w', '--stdin-paths'], work, ('\n'.join(paths) + '\n').encode())
            shutil.rmtree(src)
        if local:
            (work / 'local').write_text('local\n')
            run([git, 'add', 'local'], work)
            run([git, 'commit', '-qm', 'local'], work)
        for i in range(moved):
            (origin / 'a').write_text(f'a {i}\n')
            run([git, 'commit', '-qam', f'next {i}'], origin)
        return work

    rows = []

    def row(name, argv, **shape):
        if a.filter not in name:
            return
        work = fixture(name, **shape)
        # Both tools run at the same paths: Git on the fixture, then den on a
        # fresh copy of it put back in the same place.
        pristine = out / (name + '-pristine')
        shutil.copytree(work.parent, pristine, symlinks=True)
        results = {}
        for label, tool in (('git', git), ('den', den)):
            if label == 'den':
                shutil.rmtree(work.parent)
                shutil.copytree(pristine, work.parent, symlinks=True)
            p = subprocess.run([tool, *argv], cwd=work, capture_output=True)
            results[label] = dict(exit=p.returncode, stdout=p.stdout.decode(errors='replace'),
                                  stderr=p.stderr.decode(errors='replace'),
                                  head=run([git, 'rev-parse', 'HEAD'], work).strip().decode())
        shutil.rmtree(pristine)
        g, d = results['git'], results['den']
        differs = [k for k in ('exit', 'stdout', 'stderr', 'head') if g[k] != d[k]]
        ok = not differs
        print(('PASS ' if ok else 'FAIL ') + f'abbrev-{name}' +
              ''.join(f' {k}: git {g[k]!r} den {d[k]!r}' for k in differs), flush=True)
        rows.append(dict(row=name, passed=ok, argv=argv, shape=shape, git=g, den=d))
        shutil.rmtree(work.parent)

    row('fetch-below-16384', ['fetch', 'origin'], packed=16000)
    row('fetch-at-16384', ['fetch', 'origin'], packed=16384)
    row('fetch-at-65536', ['fetch', 'origin'], packed=65536)
    row('fetch-loose-uncounted', ['fetch', 'origin'], packed=8000, loose=9000)
    row('fetch-duplicates-counted', ['fetch', 'origin'], duplicated=8192)
    row('fetch-auto', ['fetch', 'origin'], packed=16384, config='auto')
    row('fetch-configured', ['fetch', 'origin'], packed=16384, config='7')
    row('fetch-configured-short', ['fetch', 'origin'], config='4')
    row('fetch-configured-long', ['fetch', 'origin'], config='10')
    row('pull-up-to-date', ['pull', 'origin', 'main'], packed=16384, moved=0)
    row('pull-fast-forward', ['pull', '--no-rebase', 'origin', 'main'], packed=16384)
    row('pull-merge', ['pull', '--no-rebase', 'origin', 'main'], packed=16384, local=True)
    row('checkout-detach', ['checkout', '--detach'], packed=16384, moved=0)
    row('reset-hard', ['reset', '--hard', 'HEAD'], packed=16384, moved=0)
    row('push-new-branch', ['push', 'origin', 'HEAD:refs/heads/topic'], packed=16384, moved=0, local=True)
    assert rows, 'empty selection'
    (out / 'summary.json').write_text(json.dumps(rows, indent=2) + '\n')
    failures = sum(not r['passed'] for r in rows)
    print(f'abbrev: {len(rows)} rows, {failures} failures; zero skips', flush=True)
    return int(failures > 0)


if __name__ == '__main__':
    raise SystemExit(main())
