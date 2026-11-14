#!/usr/bin/env python3
"""den#100: every bound a user reaches from fetch, pull, clone, merge and
checkout names itself and its value.

Each row trips one bound through the command line and requires exit 128, a
last stderr line `fatal: limit: <the bound and its value>`, no bare
`fatal: limit` line and no `not yet implemented` line, and HEAD unchanged.
The pinned Git is run on the same fixture and its exit status recorded beside
each row: these are bounds den keeps, not parity rows.
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
    out = root / 'target/runs' / ('limit-' + a.tier)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    git = os.environ['DEN_GIT']
    assert hashlib.sha256(Path(git).read_bytes()).hexdigest() == 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
    den = a.den or str(root / 'target' / a.tier / 'den')
    os.environ['GIT_MERGE_AUTOEDIT'] = 'no'

    def run(args, cwd, data=None):
        p = subprocess.run([str(x) for x in args], cwd=cwd, capture_output=True, input=data)
        assert p.returncode == 0, (args, p.stdout, p.stderr)
        return p.stdout

    def head(w):
        return run([git, 'rev-parse', 'HEAD'], w).strip().decode()

    big = b'0123456789abcdef' * (17000000 // 16)

    def large_change(name):
        """A clone one true merge behind its remote; the remote changed a 17 MB file."""
        base = out / name
        base.mkdir()
        origin, work = base / 'origin', base / 'work'
        run([git, 'init', '-q', origin], base)
        (origin / 'big').write_bytes(b'small\n')
        (origin / 'a').write_text('a\n')
        run([git, 'add', '.'], origin)
        run([git, 'commit', '-qm', 'base'], origin)
        run([git, 'clone', '-q', origin, work], base)
        (work / 'local').write_text('local\n')
        run([git, 'add', 'local'], work)
        run([git, 'commit', '-qm', 'local'], work)
        (origin / 'big').write_bytes(big)
        run([git, 'commit', '-qam', 'grow'], origin)
        run([git, 'fetch', '-q', 'origin'], work)
        blob = run([git, 'rev-parse', 'origin/main:big'], work).strip().decode()
        return work, blob

    def many_packs(name):
        """A clone whose objects/pack holds 257 packs; its remote moved one commit on."""
        base = out / name
        base.mkdir()
        origin, work = base / 'origin', base / 'work'
        run([git, 'init', '-q', origin], base)
        (origin / 'a').write_text('a\n')
        run([git, 'add', '.'], origin)
        run([git, 'commit', '-qm', 'base'], origin)
        run([git, 'branch', 'other'], origin)
        run([git, 'clone', '-q', origin, work], base)
        run([git, 'config', 'gc.auto', '0'], work)
        run([git, 'repack', '-qad'], work)
        for i in range(256):
            blob = run([git, 'hash-object', '-w', '--stdin'], work, f'pack {i}\n'.encode()).strip()
            run([git, 'pack-objects', '-q', '.git/objects/pack/pack'], work, blob + b'\n')
        for loose in (work / '.git/objects').glob('[0-9a-f][0-9a-f]'):
            shutil.rmtree(loose)
        (origin / 'a').write_text('b\n')
        run([git, 'commit', '-qam', 'next'], origin)
        return work

    def many_refs(name):
        """A clone whose packed-refs file is larger than 16 MiB."""
        base = out / name
        base.mkdir()
        origin, work = base / 'origin', base / 'work'
        run([git, 'init', '-q', origin], base)
        (origin / 'a').write_text('a\n')
        run([git, 'add', '.'], origin)
        run([git, 'commit', '-qm', 'base'], origin)
        run([git, 'clone', '-q', origin, work], base)
        tip = head(work)
        lines = ['# pack-refs with: peeled fully-peeled sorted \n']
        for i in range(330000):
            lines.append(f'{tip} refs/tags/t{i:07}\n')
        lines.sort(key=lambda line: line.split(' ')[-1] if not line.startswith('#') else '')
        (work / '.git/packed-refs').write_text(''.join(lines))
        return work

    rows = []

    def row(name, setup, argv, expected):
        if a.filter not in name:
            return
        made = setup(name)
        work, detail = made if isinstance(made, tuple) else (made, None)
        wanted = expected(work, detail)
        before = head(work)
        mirror = out / (name + '-git')
        shutil.copytree(work.parent, mirror, symlinks=True)
        oracle = subprocess.run([git, *argv], cwd=mirror / 'work', capture_output=True)
        p = subprocess.run([den, *argv], cwd=work, capture_output=True)
        lines = p.stderr.decode(errors='replace').splitlines()
        last_ok = (lines and lines[-1].startswith(f'fatal: {wanted[0]}') and lines[-1].endswith(wanted[1])
                   if isinstance(wanted, tuple) else lines and lines[-1] == f'fatal: {wanted}')
        ok = (p.returncode == 128 and last_ok and
              'fatal: limit' not in lines and not any('not yet implemented' in x for x in lines) and
              head(work) == before)
        print(('PASS ' if ok else 'FAIL ') + f'limit-{name}' +
              ('' if ok else f' den exit {p.returncode} stderr tail {lines[-2:]!r}; wanted {wanted!r}') +
              f' (Git exit {oracle.returncode})', flush=True)
        rows.append(dict(row=name, passed=ok, argv=argv, expected=wanted, exit=p.returncode,
                         stderr=p.stderr.decode(errors='replace'), git_exit=oracle.returncode))
        shutil.rmtree(mirror)

    blob_bound = lambda w, blob: f'limit: object {blob} is larger than 16777216 bytes'
    packs_bound = lambda w, _: 'limit: more than 256 packs in objects/pack'
    row('merge-changed-file', large_change, ['merge', '--no-edit', 'origin/main'], blob_bound)
    row('pull-changed-file', large_change, ['pull', '--no-rebase', 'origin', 'main'], blob_bound)
    row('fetch-pack-count', many_packs, ['fetch', 'origin'], packs_bound)
    row('pull-pack-count', many_packs, ['pull', 'origin', 'main'], packs_bound)
    row('checkout-pack-count', many_packs, ['checkout', '-q', 'origin/other'], packs_bound)
    row('merge-pack-count', many_packs, ['merge', 'origin/other'], packs_bound)
    # The path is the repository's own, as den resolved it.
    row('fetch-packed-refs', many_refs, ['fetch', 'origin'],
        lambda w, _: ("limit: '", "/packed-refs' is larger than 16777216 bytes"))

    def plain(name):
        base = out / name
        base.mkdir()
        run([git, 'init', '-q', base / 'work'], base)
        (base / 'work' / 'a').write_text('a\n')
        run([git, 'add', 'a'], base / 'work')
        run([git, 'commit', '-qm', 'base'], base / 'work')
        return base / 'work'
    row('clone-url', plain, ['clone', 'git://127.0.0.1:1/' + 'x' * 5000, 'unused'],
        lambda w, _: 'limit: a remote URL longer than 4096 bytes')
    assert rows, 'empty selection'
    (out / 'summary.json').write_text(json.dumps(rows, indent=2) + '\n')
    failures = sum(not r['passed'] for r in rows)
    print(f'limit: {len(rows)} rows, {failures} failures; zero skips', flush=True)
    return int(failures > 0)


if __name__ == '__main__':
    raise SystemExit(main())
