#!/usr/bin/env python3
"""den#100: pull, merge and switch beside large untracked and ignored output.

A pull or switch needs the tracked files and the paths it writes; it does not
need the bodies of unrelated untracked or ignored files. Each row runs the
same command with the pinned Git and with den in two copies of one fixture
and compares exit status, stdout, stderr, HEAD and the in-the-way paths'
contents byte for byte. den must also stay under a read budget (rchar, the
bytes it read through read(2)) and a peak resident set budget, so a row that
passes by reading a large body is still red.

scan rows: a 1,500,000,000-byte sparse file (untracked, or ignored), an ignored
tree of three 400,000,000-byte files, and 1,000,001 empty files in an
untracked or an ignored directory, beside a true merge, a fast-forward, a
rebase pull and a switch.

way rows: the target adds paths where the work tree holds untracked or ignored
files or directories. Git refuses for an untracked file in the way, also below
an untracked directory, and overwrites an ignored one.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time

READ_BUDGET = 64 * 1024 * 1024
RSS_BUDGET_KIB = 256 * 1024
MODES = {
    'merge': ['pull', '--no-rebase', 'origin', 'main'],
    'ff': ['pull', 'origin', 'main'],
    'rebase': ['pull', '--rebase', 'origin', 'main'],
    'switch': ['checkout', '-q', 'origin/main'],
}
SCAN = ['untracked-large', 'ignored-large', 'ignored-tree', 'untracked-count', 'ignored-count']
WAY = {
    'untracked-file': lambda w: (w / 'x').write_text('local\n'),
    'untracked-file-same': lambda w: (w / 'x').write_text('target x\n'),
    'ignored-file': lambda w: (w / 'x.o').write_text('local\n'),
    'ignored-file-same': lambda w: (w / 'x.o').write_text('target x.o\n'),
    'ignored-dir-at-path': lambda w: ((w / 'build').mkdir(), (w / 'build' / 'out').write_text('local\n')),
    'ignored-dir-other': lambda w: ((w / 'build').mkdir(), (w / 'build' / 'other').write_text('local\n')),
    'untracked-dir-at-path': lambda w: ((w / 'newdir').mkdir(), (w / 'newdir' / 'x').write_text('local\n')),
    'untracked-dir-ignored-at-path': lambda w: ((w / 'newdir').mkdir(), (w / 'newdir' / 'y.o').write_text('local\n')),
    'untracked-dir-other': lambda w: ((w / 'newdir').mkdir(), (w / 'newdir' / 'other').write_text('local\n')),
}
WAY_PATHS = ['x', 'x.o', 'build', 'newdir']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tier', default='native')
    parser.add_argument('--den')
    parser.add_argument('--filter', default='')
    parser.add_argument('--no-count', action='store_true', help='leave out the 1,000,001-file rows')
    a = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = root / 'target/runs' / ('pull-scan-' + a.tier)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    git = os.environ['DEN_GIT']
    assert hashlib.sha256(Path(git).read_bytes()).hexdigest() == 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
    den = a.den or str(root / 'target' / a.tier / 'den')
    os.environ['GIT_MERGE_AUTOEDIT'] = 'no'

    def run(args, cwd):
        p = subprocess.run([str(x) for x in args], cwd=cwd, capture_output=True)
        assert p.returncode == 0, (args, p.stdout, p.stderr)
        return p.stdout

    def measured(args, cwd):
        """Run args; return exit, stdout, stderr, peak rchar and peak RSS (KiB)."""
        proc = subprocess.Popen([str(x) for x in args], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        peak = [0]
        done = threading.Event()

        def poll():
            while not done.is_set():
                try:
                    for line in open(f'/proc/{proc.pid}/io'):
                        if line.startswith('rchar:'):
                            peak[0] = max(peak[0], int(line.split()[1]))
                except OSError:
                    pass
                time.sleep(0.002)
        watcher = threading.Thread(target=poll)
        watcher.start()
        chunks = {}

        def drain(name, stream):
            chunks[name] = stream.read()
        readers = [threading.Thread(target=drain, args=(n, s)) for n, s in (('out', proc.stdout), ('err', proc.stderr))]
        for r in readers:
            r.start()
        _, status, usage = os.wait4(proc.pid, 0)
        for r in readers:
            r.join()
        done.set()
        watcher.join()
        code = os.waitstatus_to_exitcode(status)
        proc.returncode = code
        return code, chunks['out'], chunks['err'], peak[0], usage.ru_maxrss

    def seed(name, mode):
        base = out / f'seed-{name}-{mode}'
        base.mkdir()
        origin, remote, work = base / 'origin', base / 'remote.git', base / 'seed'
        run([git, 'init', '-q', origin], root)
        (origin / 'a').write_text('before\n')
        (origin / '.gitignore').write_text('*.o\nbuild/\nbuild-output\nbuild-tree/\nignored-tree/\n')
        run([git, 'add', '.'], origin)
        run([git, 'commit', '-qm', 'base'], origin)
        run([git, 'clone', '-q', '--bare', origin, remote], root)
        run([git, 'clone', '-q', remote.as_uri(), work], root)
        run([git, 'config', 'gc.auto', '0'], work)
        if mode in ('merge', 'rebase'):
            (work / 'b').write_text('local independent change\n')
            run([git, 'add', 'b'], work)
            run([git, 'commit', '-qm', 'local'], work)
        (origin / 'a').write_text('after\n')
        if name == 'way':
            (origin / 'x').write_text('target x\n')
            (origin / 'x.o').write_text('target x.o\n')
            (origin / 'build').mkdir()
            (origin / 'build' / 'out').write_text('target out\n')
            (origin / 'newdir').mkdir()
            (origin / 'newdir' / 'x').write_text('target newdir/x\n')
            (origin / 'newdir' / 'y.o').write_text('target newdir/y.o\n')
            run([git, 'add', '-f', '.'], origin)
        run([git, 'commit', '-qam', 'next'], origin)
        run([git, 'push', '-q', remote.as_uri(), 'HEAD:refs/heads/main'], origin)
        if mode == 'switch':
            run([git, 'fetch', '-q', 'origin'], work)
        return work

    pools = {}

    def pool(name):
        if name not in pools:
            d = out / f'pool-{name}'
            d.mkdir()
            for i in range(1000001):
                open(d / f'{i:07}', 'wb').close()
            pools[name] = d
        return pools[name]

    def place(case, w):
        """Make the case's material in w; return (paths it must leave, undo)."""
        if case in ('untracked-large', 'ignored-large'):
            f = w / ('scratch-output' if case == 'untracked-large' else 'build-output')
            with f.open('wb') as h:
                h.truncate(1500000000)
            return [f], None
        if case == 'ignored-tree':
            d = w / 'build-tree' / 'nested'
            d.mkdir(parents=True)
            made = []
            for i in range(3):
                with (d / f'part{i}').open('wb') as h:
                    h.truncate(400000000)
                made.append(d / f'part{i}')
            return made, None
        name = 'untracked-tree' if case == 'untracked-count' else 'ignored-tree'
        source = pool(name)
        os.rename(source, w / name)
        return [w / name], lambda: os.rename(w / name, source)

    def state(w):
        found = {}
        for n in WAY_PATHS:
            q = w / n
            if q.is_dir():
                found[n] = {str(c.relative_to(w)): c.read_text() for c in sorted(q.rglob('*')) if c.is_file()}
            elif q.exists():
                found[n] = q.read_text()
        return found

    rows = []
    cases = [('scan', c) for c in SCAN if not (a.no_count and c.endswith('-count'))] + [('way', s) for s in WAY]
    for mode, argv in MODES.items():
        seeds = {}
        for family, case in cases:
            name = f'pull-{family}-{mode}-{case}'
            if a.filter not in name:
                continue
            if family not in seeds:
                seeds[family] = seed(family, mode)
            results = {}
            for label, tool in (('git', git), ('den', den)):
                work = out / 'work'
                if work.exists():
                    shutil.rmtree(work)
                shutil.copytree(seeds[family], work, symlinks=True)
                if family == 'scan':
                    kept, undo = place(case, work)
                else:
                    WAY[case](work)
                    kept, undo = [], None
                try:
                    code, so, se, rchar, rss = measured([tool, *argv], work)
                    head = run([git, 'rev-parse', 'HEAD'], work).strip().decode()
                    intact = all(p.exists() for p in kept)
                    paths = state(work)
                finally:
                    if undo:
                        undo()
                results[label] = dict(status=code, stdout=so.hex(), stderr=se.hex(), head=head,
                                      intact=intact, state=paths, rchar=rchar, maxrss_kib=rss)
            g, d = results['git'], results['den']
            same = all(g[k] == d[k] for k in ('status', 'stdout', 'stderr', 'head', 'intact', 'state'))
            bounded = d['rchar'] <= READ_BUDGET and d['maxrss_kib'] <= RSS_BUDGET_KIB
            ok = same and bounded
            note = '' if same else (f' den exit {d["status"]} stderr {bytes.fromhex(d["stderr"])[-160:]!r};'
                                    f' git exit {g["status"]} stderr {bytes.fromhex(g["stderr"])[-160:]!r}')
            print(('PASS ' if ok else 'FAIL ') + name +
                  f' den read {d["rchar"]} bytes, peak {d["maxrss_kib"]} KiB' + note, flush=True)
            rows.append(dict(name=name, passed=ok, same=same, bounded=bounded, git=g, den=d))
    assert rows, 'empty selection'
    (out / 'summary.json').write_text(json.dumps(rows, indent=2) + '\n')
    failures = sum(not r['passed'] for r in rows)
    print(f'pull-scan: {len(rows)} rows, {failures} failures; zero skips', flush=True)
    for p in out.glob('pool-*'):
        shutil.rmtree(p)
    return int(failures > 0)


if __name__ == '__main__':
    raise SystemExit(main())
