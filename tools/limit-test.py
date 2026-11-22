#!/usr/bin/env python3
"""den#100: every bound a user reaches from fetch, pull, clone, merge and
checkout names itself and its value.

Each row trips one bound through the command line and requires exit 128, a
last stderr line `fatal: limit: <the bound and its value>`, no bare
`fatal: limit` line and no `not yet implemented` line, and HEAD unchanged.
The pinned Git is run on the same fixture and its exit status recorded beside
each row: these are bounds den keeps, not parity rows.

Every pinned-Git command here runs with MAINTENANCE: a commit, fetch, pull or
merge starts `git maintenance run --auto`, which takes the object database's
lock (maintenance.lock) and, by default, detaches and goes on in the
background (git-config(1), maintenance.autoDetach). A detached run outlived
its command and took or dropped its lock while this harness copied or removed
the repository (copytree, rmtree): `FileNotFoundError: maintenance.lock`.
limit-git-maintenance-foreground, first, traces one pinned-Git commit run
that way and requires the maintenance it starts not to detach.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

# The pinned Git's options for every command this harness runs.
MAINTENANCE = ['-c', 'maintenance.autoDetach=false']


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
        if args and args[0] == git:
            args = [git, *MAINTENANCE, *args[1:]]
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

    def big_message(name):
        """A clone with a 17 MB commit message file beside a staged change."""
        work = plain(name)
        (work / 'a').write_text('changed\n')
        run([git, 'add', 'a'], work)
        (work / 'message').write_bytes(b'subject\n\n' + b'body line\n' * 1700000)
        return work

    def big_config(name):
        """A clone whose .git/config is past 1 MiB (a long comment)."""
        work = plain(name)
        with (work / '.git/config').open('a') as f:
            f.write(('# ' + 'x' * 1022 + '\n') * 1100)
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

    def maintenance_foreground():
        """A pinned-Git commit as this harness runs one, traced: the automatic
        maintenance it starts must not detach (no `--detach` child)."""
        name = 'git-maintenance-foreground'
        probe = out / 'maintenance-probe'
        probe.mkdir()
        run([git, 'init', '-q', probe], out)
        (probe / 'a').write_text('a\n')
        run([git, 'add', 'a'], probe)
        trace = out / 'maintenance-probe.trace'
        q = subprocess.run([git, *MAINTENANCE, 'commit', '-qm', 'probe'], cwd=probe, capture_output=True,
                           env=dict(os.environ, GIT_TRACE=str(trace)))
        started = [line.split('start_command: ', 1)[1] for line in trace.read_text().splitlines()
                   if 'start_command: ' in line and ' maintenance run ' in line]
        detached = [line for line in started if '--detach' in line.split()]
        ok = q.returncode == 0 and bool(started) and not detached
        print(('PASS ' if ok else 'FAIL ') + f'limit-{name}' +
              ('' if ok else f' git exit {q.returncode}; maintenance started {started!r}'), flush=True)
        rows.append(dict(row=name, passed=ok, argv=['commit'], expected='no detached maintenance',
                         exit=q.returncode, stderr=q.stderr.decode(errors='replace'), git_exit=q.returncode))
        shutil.rmtree(probe)

    if a.filter in 'git-maintenance-foreground':
        maintenance_foreground()

    def row(name, setup, argv, expected, published=False):
        if a.filter not in name:
            return
        made = setup(name)
        work, detail = made if isinstance(made, tuple) else (made, None)
        wanted = expected(work, detail)
        before = head(work)
        mirror = out / (name + '-git')
        shutil.copytree(work.parent, mirror, symlinks=True)
        oracle = subprocess.run([git, *MAINTENANCE, *argv], cwd=mirror / 'work', capture_output=True)
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
    # Kept as protections, named with their paths (den#145): a commit message
    # file past 16 MiB, a configuration file past 1 MiB. Git takes both.
    row('commit-message-file', big_message, ['commit', '-F', 'message'],
        lambda w, _: "limit: the message file 'message' is larger than 16777216 bytes")
    row('config-file', big_config, ['status'],
        lambda w, _: 'limit: the configuration file .git/config is larger than 1048576 bytes')
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
