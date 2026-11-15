#!/usr/bin/env python3
"""den#91: `add` of thousands of files, its peak memory bounded, beside Git.

Before this row, every byte an add allocated was held until den exited: the
deflate match tables of every object it wrote (512 KiB each) and about five
copies of the whole index for every path it staged. 5000 new files needed
about 25 GiB, and were killed. The rows, each on fresh copies of one seed for
both tools:

  add-scale-N              `add .` of N new files in a fresh repository
                           (N = 500, 2000, 5000; each tool runs its own
                           `init -q` first, outside the measurement)
  add-scale-tracked-2000   `add .` over 2000 files Git committed, the index
                           stat-clean, plus one new file `d0/new.txt`
  add-scale-commit-a-2000  `commit -a -q -m change` over the same tree with
                           one file changed

The trees have the shape of den#91's report: directories `dI` of 100 files
`fJ.txt`, each holding `px142 den row file I J`. Each run's exit status,
stdout and stderr must equal the pinned Git's, and so must the index it
leaves: `ls-files -s` and the TREE extension's bytes (Git leaves a stat-clean
entry's cache-tree records valid); after `commit -a`, HEAD's tree and the
status as well. Each tool is started by tools/minimal-parent.c, so its peak
is its own (den#114), under a 2 GiB address-space cap on Linux so a regressed
den stops there and is named, not killed by the host. den's peak must stay
within BOUND_KIB. Wall and CPU (user + system, from rusage) are printed for
both tools: den's wall is mostly its fsyncs, three per object it writes.
"""
import argparse
import hashlib
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import threading
import time

BOUND_KIB = 64 * 1024
CAP = 2 * 1024 ** 3
ENV = dict(os.environ, GIT_AUTHOR_NAME='Den Tester', GIT_AUTHOR_EMAIL='den@example.invalid',
           GIT_COMMITTER_NAME='Den Tester', GIT_COMMITTER_EMAIL='den@example.invalid',
           GIT_AUTHOR_DATE='1700000000 +0000', GIT_COMMITTER_DATE='1700000000 +0000')


def capped():
    if sys.platform.startswith('linux'):
        resource.setrlimit(resource.RLIMIT_AS, (CAP, CAP))


def run(args, cwd, check=True):
    p = subprocess.run([str(x) for x in args], cwd=cwd, capture_output=True, env=ENV)
    if check:
        assert p.returncode == 0, (args, p.stdout[-300:], p.stderr[-300:])
    return p.stdout


def files(root, n):
    for k in range(n):
        i, j = divmod(k, 100)
        d = root / f'd{i}'
        d.mkdir(parents=True, exist_ok=True)
        (d / f'f{j}.txt').write_bytes(f'px142 den row file {i} {j}\n'.encode())


def tree_extension(work):
    """The index's TREE extension bytes, from the documented v2/v3 layout."""
    d = (work / '.git/index').read_bytes()
    assert d[:4] == b'DIRC', d[:4]
    version, count = int.from_bytes(d[4:8], 'big'), int.from_bytes(d[8:12], 'big')
    assert version in (2, 3), version
    pos = 12
    for _ in range(count):
        flags = int.from_bytes(d[pos + 60:pos + 62], 'big')
        start = pos + 62 + (2 if version == 3 and flags & 0x4000 else 0)
        end = d.index(b'\0', start)
        pos += ((start - pos + end - start) // 8 + 1) * 8
    while pos + 8 <= len(d) - 20:
        size = int.from_bytes(d[pos + 4:pos + 8], 'big')
        if d[pos:pos + 4] == b'TREE':
            return d[pos + 8:pos + 8 + size]
        pos += 8 + size
    return b''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tier', default='release')
    parser.add_argument('--den')
    parser.add_argument('--takes', type=int, default=1)
    parser.add_argument('--out')
    parser.add_argument('--filter', default='')
    a = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = Path(a.out) if a.out else root / 'target/runs' / ('add-scale-' + a.tier)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    git = os.environ['DEN_GIT']
    assert hashlib.sha256(Path(git).read_bytes()).hexdigest() == 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
    den = a.den or str(root / 'target' / a.tier / 'den')
    parent = out / 'minimal-parent'
    run(['cc', '-O2', '-o', parent, root / 'tools/minimal-parent.c'], out)
    report = out / 'usage'

    def measured(argv, cwd):
        report.unlink(missing_ok=True)
        proc = subprocess.Popen([str(parent), str(report), *map(str, argv)], cwd=cwd, env=ENV,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=capped)
        chunks = {}

        def drain(label, stream):
            chunks[label] = stream.read()
        readers = [threading.Thread(target=drain, args=(n, s)) for n, s in (('out', proc.stdout), ('err', proc.stderr))]
        for r in readers:
            r.start()
        for r in readers:
            r.join()
        assert proc.wait() == 0, ('minimal parent', proc.returncode)
        status, maxrss, user, system, wall = report.read_text().split()
        return dict(status=int(status), stdout=chunks['out'], stderr=chunks['err'],
                    wall=float(wall), cpu=float(user) + float(system), maxrss_kib=int(maxrss))

    floor_kib = min(measured(['/bin/true'], out)['maxrss_kib'] for _ in range(3))
    print(f'FLOOR resident set of a child of the minimal parent: {floor_kib} KiB', flush=True)

    def seed(name, n, committed):
        s = out / f'seed-{name}'
        files(s, n)
        if committed:
            run([git, 'init', '-q'], s)
            run([git, 'add', '.'], s)
            run([git, 'commit', '-q', '-m', 'tree'], s)
        return s

    # Name, seed, the command, whether each tool inits first, and the change
    # made in its copy before the command.
    seeds = {}
    plan = []
    for n in (500, 2000, 5000):
        plan.append((f'add-scale-{n}', ('fresh', n), ['add', '.'], True, None))
    plan.append(('add-scale-tracked-2000', ('tracked', 2000), ['add', '.'], False, 'new'))
    plan.append(('add-scale-commit-a-2000', ('tracked', 2000), ['commit', '-a', '-q', '-m', 'change'], False, 'change'))

    def prepared(key, init, tool, change):
        if key not in seeds:
            seeds[key] = seed(f'{key[0]}-{key[1]}', key[1], key[0] == 'tracked')
        work = out / 'work'
        if work.exists():
            shutil.rmtree(work)
        shutil.copytree(seeds[key], work, symlinks=True)
        if init:
            run([tool, 'init', '-q'], work)
        else:
            # The copy keeps mtimes but not inodes: refresh, as in a repository
            # one works in, so both tools start from the same stat-clean index.
            # Wait out the second first, so no entry is racily clean.
            time.sleep(1.1)
            run([git, 'update-index', '-q', '--refresh'], work, check=False)
        if change == 'new':
            (work / 'd0/new.txt').write_bytes(b'one new file\n')
        elif change == 'change':
            with open(work / 'd0/f0.txt', 'ab') as f:
                f.write(b'changed\n')
        return work

    def result(work, argv):
        r = dict(lsfiles=run([git, 'ls-files', '-s'], work, check=False),
                 tree=tree_extension(work).hex())
        if argv[0] == 'commit':
            r['head_tree'] = run([git, 'rev-parse', 'HEAD^{tree}'], work, check=False).strip()
            r['porcelain'] = run([git, 'status', '--porcelain'], work, check=False)
        return r

    rows = 0
    failures = 0
    for name, key, argv, init, change in plan:
        if a.filter not in name:
            continue
        rows += 1
        best, sample = {}, {}
        for _ in range(a.takes):
            for label, tool in (('git', git), ('den', den)):
                work = prepared(key, init, tool, change)
                r = measured([tool, *argv], work)
                if r['status'] == 0:
                    r.update(result(work, argv))
                sample.setdefault(label, r)
                b = best.setdefault(label, dict(wall=r['wall'], cpu=r['cpu'], maxrss_kib=r['maxrss_kib']))
                for k in ('wall', 'cpu', 'maxrss_kib'):
                    b[k] = min(b[k], r[k])
        g, d = sample['git'], sample['den']
        keys = ('status', 'stdout', 'stderr', 'lsfiles', 'tree', 'head_tree', 'porcelain')
        differs = [k for k in keys if (k in g or k in d) and g.get(k) != d.get(k)]
        bounded = best['den']['maxrss_kib'] <= BOUND_KIB
        ok = not differs and bounded and d['status'] == 0
        failures += not ok
        print(('PASS ' if ok else 'FAIL ') + name +
              f" den peak {best['den']['maxrss_kib']} KiB wall {best['den']['wall']:.2f} s cpu {best['den']['cpu']:.3f} s;"
              f" git peak {best['git']['maxrss_kib']} KiB wall {best['git']['wall']:.3f} s cpu {best['git']['cpu']:.3f} s;"
              f" bound {BOUND_KIB} KiB; floor {floor_kib} KiB" +
              ('' if bounded else ' OVER BOUND') +
              ('' if not differs else ' DIFFERS in ' + ', '.join(
                  f'{k}: git {str(g.get(k))[-120:]!r} den {str(d.get(k))[-120:]!r}' for k in differs)), flush=True)
    assert rows, 'empty selection'
    print(f'add-scale: {rows} rows, {failures} failures; zero skips', flush=True)
    shutil.rmtree(out / 'work', ignore_errors=True)
    return int(failures > 0)


if __name__ == '__main__':
    raise SystemExit(main())
