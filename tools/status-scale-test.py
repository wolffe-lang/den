#!/usr/bin/env python3
"""Plain `status` on checkouts whose shape makes one of its costs dominate,
timed beside Git.

Each shape's fixture is made with the pinned Git alone: one commit of --files
files spread over --directories directories (file i in directory i modulo
the count), written by fast-import into a bare repository, cloned (so the
branch has its upstream, as a clone's does), its index refreshed by Git after
the copy (stat data fresh, not racily clean). A shape with extra objects then
has that many more blobs, none reachable, written into the clone by
fast-import as a pack of their own. Shapes:

  files         10,000 files in 1,000 directories: status's own memory, what
                it keeps of the index, HEAD and the walk, is what it spends.
  directories   20,000 files, one in each of 20,000 directories: the walk's
                work per directory is what status spends.
  objects       100 files in 10 directories beside 390,000 packed objects:
                opening the packs is what status spends.

Each tool starts through minimal-parent.c, so its peak resident set is its
own. Both tools run `status` in the same checkout, which neither changes,
interleaved over --takes takes; each measure is a tool's minimum. stdout,
stderr and the exit status must equal Git's. den is bounded against Git in the
same take: its CPU at most RELATIVE's cpu_factor times Git's plus cpu_slack,
its peak at most rss_factor times Git's plus rss_slack_kib (each shape's
RELATIVE), stated for the native tier on Linux. A den run past --timeout
seconds is ended and fails its row.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

SHAPES = {
    'files': dict(files=10000, directories=1000, objects=0),
    'directories': dict(files=20000, directories=20000, objects=0),
    'objects': dict(files=100, directories=10, objects=390000),
}
# Stated for the native tier on Linux. files: the peak bound fails a status
# that keeps every list's outgrown buffers, its walk's lstat records and
# listings, and copies of the index and its entries. directories: the peak
# bound fails a walk that keeps all it made of each directory; the CPU bound
# fails a walk whose work per directory grows with the number of entries.
# objects: den still reads every pack index whole where Git reads what it
# looks up, and the peak bound is today's. Git's own time there is a
# millisecond, so the CPU bound is nearly all slack: it fails a read that
# hashes every index and spells every name in it, on a machine up to half
# again as fast as the one it was set on.
RELATIVE = {
    'files': dict(cpu_factor=10.0, cpu_slack=0.05, rss_factor=6.0, rss_slack_kib=8192),
    'directories': dict(cpu_factor=10.0, cpu_slack=0.05, rss_factor=14.0, rss_slack_kib=16384),
    'objects': dict(cpu_factor=10.0, cpu_slack=0.40, rss_factor=8.0, rss_slack_kib=98304),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tier', default='native')
    parser.add_argument('--den')
    parser.add_argument('--takes', type=int, default=3)
    parser.add_argument('--timeout', type=float, default=120.0)
    parser.add_argument('--out')
    parser.add_argument('--filter', default='')
    parser.add_argument('--dev-oracle', action='store_true', help='Darwin development evidence only; not the pinned Linux oracle')
    a = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = Path(a.out) if a.out else root / 'target/runs' / ('status-scale-' + a.tier)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    git = os.environ['DEN_GIT']
    digest = hashlib.sha256(Path(git).read_bytes()).hexdigest()
    if a.dev_oracle:
        assert os.uname().sysname == 'Darwin', 'development oracle is Darwin-only'
        print('DEV ORACLE (not pinned Linux evidence; bounds are stated for Linux):', digest, flush=True)
    else:
        assert digest == 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
    den = a.den or str(root / 'target' / a.tier / 'den')

    def run(args, cwd, data=None):
        p = subprocess.run([str(x) for x in args], cwd=cwd, capture_output=True, input=data)
        assert p.returncode == 0, (args, p.stdout[-300:], p.stderr[-300:])
        return p.stdout

    parent = out / 'minimal-parent'
    report = out / 'measurement-usage'
    subprocess.run(['cc', '-O2', '-o', str(parent), str(root / 'tools/minimal-parent.c')], check=True)

    def measure(tool, work):
        report.unlink(missing_ok=True)
        p = subprocess.run([str(parent), '--timeout', str(a.timeout), str(report), tool, 'status'],
                           cwd=work, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if p.returncode != 0:
            raise RuntimeError(('minimal parent', p.returncode, p.stderr))
        status, maxrss, user, system, wall, timed_out = report.read_text().split()
        return dict(status=int(status), stdout=p.stdout, stderr=p.stderr, wall=float(wall),
                    cpu=float(user) + float(system), maxrss_kib=int(maxrss),
                    ended=bool(int(timed_out)) or float(wall) >= a.timeout)

    floor_kib = min(measure('/bin/true' if Path('/bin/true').exists() else '/usr/bin/true', out)['maxrss_kib']
                    for _ in range(3))
    rows = []
    for name, shape in SHAPES.items():
        row = f'status-scale-{name}'
        if a.filter not in row:
            continue
        case = out / name
        case.mkdir()
        origin = case / 'origin.git'
        run([git, 'init', '-q', '--bare', '-b', 'main', origin], case)
        stream = ['commit refs/heads/main\n', 'committer Den Tester <den@example.invalid> 1700000000 +0000\n',
                  'data 6\nshape\n']
        for i in range(shape['files']):
            path = f'd{i % shape["directories"]:05}/f{i:05}.txt'
            body = f'{path}\n'
            stream.append(f'M 100644 inline {path}\ndata {len(body.encode())}\n{body}\n')
        stream.append('\n')
        run([git, 'fast-import', '--quiet'], origin, ''.join(stream).encode())
        work = case / 'work'
        run([git, 'clone', '-q', '--no-local', '-b', 'main', origin, work], case)
        run([git, 'config', 'gc.auto', '0'], work)
        run([git, 'config', 'maintenance.auto', 'false'], work)
        if shape['objects']:
            bodies = (f'object {i}\n' for i in range(shape['objects']))
            blobs = ''.join(f'blob\ndata {len(body)}\n{body}\n' for body in bodies)
            run([git, 'fast-import', '--quiet'], work, blobs.encode())
        # Git's refresh after the clone, then a later index mtime than any file's.
        time.sleep(1.1)
        run([git, 'update-index', '-q', '--refresh'], work)
        files = len(run([git, 'ls-files'], work).decode().splitlines())
        packed = run([git, 'count-objects', '-v'], work).decode().split()
        in_pack = packed[packed.index('in-pack:') + 1]
        print(f'SHAPE {row} files={files} directories={shape["directories"]} in-pack={in_pack}', flush=True)
        best = {}
        sample = {}
        for take in range(a.takes):
            order = (('git', git), ('den', den)) if take % 2 == 0 else (('den', den), ('git', git))
            for label, tool in order:
                r = measure(tool, work)
                sample.setdefault(label, r)
                b = best.setdefault(label, dict(wall=r['wall'], cpu=r['cpu'], maxrss_kib=r['maxrss_kib']))
                for k in ('wall', 'cpu', 'maxrss_kib'):
                    b[k] = min(b[k], r[k])
            # A den run ended at the timeout already fails the row: one take is enough.
            if sample['den']['ended']:
                break
        g, d = sample['git'], sample['den']
        diffs = []
        for k in ('status', 'stdout', 'stderr'):
            if g[k] != d[k]:
                shown = (g[k], d[k]) if k == 'status' else (g[k][-160:], d[k][-160:])
                diffs.append(f'{k}: git {shown[0]!r} den {shown[1]!r}')
        rel = RELATIVE[name]
        bound = dict(cpu=round(best['git']['cpu'] * rel['cpu_factor'] + rel['cpu_slack'], 3),
                     rss_kib=int(best['git']['maxrss_kib'] * rel['rss_factor']) + rel['rss_slack_kib'])
        bounded = (not d['ended'] and best['den']['cpu'] <= bound['cpu'] and
                   best['den']['maxrss_kib'] <= bound['rss_kib'])
        ok = not diffs and bounded
        print(('PASS ' if ok else 'FAIL ') + row +
              f" den wall {best['den']['wall']:.3f} s cpu {best['den']['cpu']:.3f} s peak {best['den']['maxrss_kib']} KiB;"
              f" git wall {best['git']['wall']:.3f} s cpu {best['git']['cpu']:.3f} s peak {best['git']['maxrss_kib']} KiB;"
              f" den/git cpu {best['den']['cpu'] / max(best['git']['cpu'], 1e-6):.1f}x"
              f" peak {best['den']['maxrss_kib'] / max(best['git']['maxrss_kib'], 1):.1f}x;"
              f" bounds cpu {bound['cpu']} s peak {bound['rss_kib']} KiB; floor {floor_kib} KiB" +
              (f'; ended after {a.timeout} s' if d['ended'] else '') +
              ('' if not diffs else '; DIFFERS: ' + '; '.join(diffs)), flush=True)
        rows.append(dict(row=row, passed=ok, same=not diffs, bounded=bounded, best=best, bound=bound,
                         floor_kib=floor_kib, shape=shape))
        shutil.rmtree(case, ignore_errors=True)
    assert rows, 'empty selection'
    (out / 'summary.json').write_text(json.dumps(dict(rows=rows), indent=2) + '\n')
    failures = sum(not r['passed'] for r in rows)
    print(f'status-scale: {len(rows)} rows, {failures} failures; zero skips', flush=True)
    return int(failures > 0)


if __name__ == '__main__':
    raise SystemExit(main())
