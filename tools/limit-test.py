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

    def appended(name, local):
        """A clone one commit behind its remote, whose remote appended 2,500
        lines to a 3-line file; with `local`, a local commit changed its first
        line (a true merge of that file), else the work tree appended them."""
        base = out / name
        base.mkdir()
        origin, work = base / 'origin', base / 'work'
        run([git, 'init', '-q', origin], base)
        (origin / 'f').write_text('one\ntwo\nthree\n')
        run([git, 'add', '.'], origin)
        run([git, 'commit', '-qm', 'base'], origin)
        run([git, 'clone', '-q', origin, work], base)
        more = ''.join(f'appended {i}\n' for i in range(2500))
        if local:
            (work / 'f').write_text('first\ntwo\nthree\n')
            run([git, 'commit', '-qam', 'local'], work)
            (origin / 'f').write_text('one\ntwo\nthree\n' + more)
            run([git, 'commit', '-qam', 'append'], origin)
        else:
            (work / 'f').write_text('one\ntwo\nthree\n' + more)
        return work

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

    def row(name, setup, argv, expected, published=False):
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
        # A bound the merge's stat reaches comes after the update is
        # published: HEAD has moved, and no merge state is left behind.
        moved = head(work) != before and not (work / '.git' / 'MERGE_HEAD').exists()
        ok = (p.returncode == 128 and last_ok and
              'fatal: limit' not in lines and not any('not yet implemented' in x for x in lines) and
              (moved if published else head(work) == before))
        print(('PASS ' if ok else 'FAIL ') + f'limit-{name}' +
              ('' if ok else f' den exit {p.returncode} stderr tail {lines[-2:]!r}; wanted {wanted!r}') +
              f' (Git exit {oracle.returncode})', flush=True)
        rows.append(dict(row=name, passed=ok, argv=argv, expected=wanted, exit=p.returncode,
                         stderr=p.stderr.decode(errors='replace'), git_exit=oracle.returncode))
        shutil.rmtree(mirror)

    # A merge and a pull of a changed 17 MB file stopped at the object
    # readers' 16 MiB bound; tools/large-blob-test.py holds those pulls, and
    # the other everyday commands over such a blob, to Git's output (den#145).
    packs_bound = lambda w, _: 'limit: more than 256 packs in objects/pack'
    # A line diff's script keeps a budget of 2,000 differing lines (Git's has
    # none): a patch and a three-way file merge past it name it.
    row('diff-patch-lines', lambda n: appended(n, False), ['diff'],
        lambda w, _: 'limit: a file whose line diff passes 2000 differing lines in a patch')
    row('pull-merge-lines', lambda n: appended(n, True), ['pull', '--no-rebase', 'origin', 'main'],
        lambda w, _: 'limit: a file whose line diff passes 2000 differing lines in a three-way file merge')
    row('fetch-pack-count', many_packs, ['fetch', 'origin'], packs_bound)
    row('pull-pack-count', many_packs, ['pull', 'origin', 'main'], packs_bound)
    row('checkout-pack-count', many_packs, ['checkout', '-q', 'origin/other'], packs_bound)
    row('merge-pack-count', many_packs, ['merge', 'origin/other'], packs_bound)
    row('fetch-packed-refs', many_refs, ['fetch', 'origin'],
        lambda w, _: 'limit: packed-refs larger than 16777216 bytes')

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
    # A 2,500-line rewrite under pull and merge reached the stat's bound on
    # differing lines; it has none now, and tools/summary-scale-test.py holds
    # those pulls to Git's output (den#105).
    assert rows, 'empty selection'
    (out / 'summary.json').write_text(json.dumps(rows, indent=2) + '\n')
    failures = sum(not r['passed'] for r in rows)
    print(f'limit: {len(rows)} rows, {failures} failures; zero skips', flush=True)
    return int(failures > 0)


if __name__ == '__main__':
    raise SystemExit(main())
