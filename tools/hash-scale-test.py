#!/usr/bin/env python3
"""`hash-object` of one large file, timed beside Git: SHA-1 throughput and the
file read are what it spends, as they are what a status that must read its
files spends.

The fixture is a repository made by the pinned Git (`init`) holding one file
of --mib MiB of fixed pseudo-random bytes. Each tool runs `hash-object FILE`
there through minimal-parent.c, so its peak resident set is its own,
interleaved over --takes takes; each measure is a tool's minimum. stdout,
stderr and the exit status must equal Git's. den is bounded against Git in the
same take: its CPU at most RELATIVE's cpu_factor times Git's plus cpu_slack,
its peak at most rss_factor times Git's plus rss_slack_kib, stated for the
native tier on Linux. A den run past --timeout seconds is ended and fails.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import subprocess

# Stated for the native tier on Linux. The CPU bound fails a SHA-1 that does
# each round's arithmetic on 64-bit words masked back to 32 and keeps its
# schedule in a list; the peak bound fails a read that grows its buffer a
# byte at a time and keeps every buffer it outgrew.
RELATIVE = dict(cpu_factor=2.5, cpu_slack=0.05, rss_factor=1.5, rss_slack_kib=16384)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tier', default='native')
    parser.add_argument('--den')
    parser.add_argument('--mib', type=int, default=64)
    parser.add_argument('--takes', type=int, default=3)
    parser.add_argument('--timeout', type=float, default=120.0)
    parser.add_argument('--out')
    parser.add_argument('--dev-oracle', action='store_true', help='Darwin development evidence only; not the pinned Linux oracle')
    a = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = Path(a.out) if a.out else root / 'target/runs' / ('hash-scale-' + a.tier)
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

    parent = out / 'minimal-parent'
    report = out / 'measurement-usage'
    subprocess.run(['cc', '-O2', '-o', str(parent), str(root / 'tools/minimal-parent.c')], check=True)

    def measure(tool, work, args):
        report.unlink(missing_ok=True)
        p = subprocess.run([str(parent), '--timeout', str(a.timeout), str(report), tool, *args],
                           cwd=work, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        assert p.returncode == 0, (tool, p.returncode, p.stderr[-300:])
        status, maxrss, user, system, wall, timed_out = report.read_text().split()
        return dict(status=int(status), stdout=p.stdout, stderr=p.stderr, wall=float(wall),
                    cpu=float(user) + float(system), maxrss_kib=int(maxrss),
                    ended=bool(int(timed_out)) or float(wall) >= a.timeout)

    floor_kib = min(measure('/bin/true' if Path('/bin/true').exists() else '/usr/bin/true', out, [])['maxrss_kib']
                    for _ in range(3))
    work = out / 'work'
    p = subprocess.run([git, 'init', '-q', str(work)], capture_output=True)
    assert p.returncode == 0, p.stderr[-300:]
    size = a.mib * 1048576
    (work / 'large.bin').write_bytes(random.Random(1700000000).randbytes(size))
    row = f'hash-scale-{a.mib}mib'
    print(f'SHAPE {row} bytes={size}', flush=True)
    best = {}
    sample = {}
    for take in range(a.takes):
        order = (('git', git), ('den', den)) if take % 2 == 0 else (('den', den), ('git', git))
        for label, tool in order:
            r = measure(tool, work, ['hash-object', 'large.bin'])
            sample.setdefault(label, r)
            b = best.setdefault(label, dict(wall=r['wall'], cpu=r['cpu'], maxrss_kib=r['maxrss_kib']))
            for k in ('wall', 'cpu', 'maxrss_kib'):
                b[k] = min(b[k], r[k])
        if sample['den']['ended']:
            break
    g, d = sample['git'], sample['den']
    diffs = []
    for k in ('status', 'stdout', 'stderr'):
        if g[k] != d[k]:
            shown = (g[k], d[k]) if k == 'status' else (g[k][-160:], d[k][-160:])
            diffs.append(f'{k}: git {shown[0]!r} den {shown[1]!r}')
    bound = dict(cpu=round(best['git']['cpu'] * RELATIVE['cpu_factor'] + RELATIVE['cpu_slack'], 3),
                 rss_kib=int(best['git']['maxrss_kib'] * RELATIVE['rss_factor']) + RELATIVE['rss_slack_kib'])
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
    (out / 'summary.json').write_text(json.dumps(dict(rows=[dict(
        row=row, passed=ok, same=not diffs, bounded=bounded, best=best, bound=bound, floor_kib=floor_kib)]),
        indent=2) + '\n')
    shutil.rmtree(work, ignore_errors=True)
    print(f'hash-scale: 1 rows, {int(not ok)} failures; zero skips', flush=True)
    return int(not ok)


if __name__ == '__main__':
    raise SystemExit(main())
