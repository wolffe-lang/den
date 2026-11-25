#!/usr/bin/env python3
"""A packed 16 MiB blob read whole, timed beside Git: what reading an entry well over a MiB costs.

A repository holds two 16 MiB blobs, one incompressible (seeded random bytes) and one compressible (numbered
lines), packed by the pinned Git with no deltas. Each tool runs `cat-file -p` of each blob through
minimal-parent.c, so its peak resident set is its own; the two tools are interleaved over --takes takes and
each measure is a tool's minimum. stdout, stderr and the exit status must equal Git's.

A read reserves its output at most a MiB before it makes any (a declared size is the entry's own claim) and
grows it as it is made, doubling to an eighth of the size and then the size: about 1.2 times the size reserved
in all, once (tools/pack-entry-test.py's big rows count it). Its stream is read in windows of at most a MiB,
one held at a time. Above those, the read keeps the body as the store hands it back, and cat-file writes it. The
bounds are den's measured peak and CPU against Git's in the same take, stated for the native tier on Linux:
den's peak at most RELATIVE's rss_factor times Git's plus rss_slack_kib, its CPU at most cpu_factor times
Git's plus cpu_slack. The row prints both tools' figures and the ratios, the figures a change of the read
path states beside Git.
"""
import argparse
import hashlib
import os
from pathlib import Path
import random
import shutil
import subprocess

RELATIVE = dict(cpu_factor=12.0, cpu_slack=0.1, rss_factor=3.5, rss_slack_kib=16384)
SIZE = 16 << 20


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tier', default='native')
    parser.add_argument('--takes', type=int, default=3)
    parser.add_argument('--timeout', type=float, default=120.0)
    parser.add_argument('--dev-oracle', action='store_true', help='Darwin development evidence only; not the pinned Linux oracle')
    a = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = root / 'target/runs' / ('read-scale-' + a.tier)
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
    den = str(root / 'target' / a.tier / 'den')
    env = dict(os.environ, GIT_AUTHOR_NAME='Den Tester', GIT_AUTHOR_EMAIL='den@example.invalid',
               GIT_COMMITTER_NAME='Den Tester', GIT_COMMITTER_EMAIL='den@example.invalid',
               GIT_AUTHOR_DATE='1700000000 +0000', GIT_COMMITTER_DATE='1700000000 +0000')

    def run(args, cwd):
        p = subprocess.run([str(x) for x in args], cwd=cwd, capture_output=True, env=env)
        assert p.returncode == 0, (args, p.stdout[-300:], p.stderr[-300:])
        return p.stdout

    parent = out / 'minimal-parent'
    report = out / 'measurement-usage'
    subprocess.run(['cc', '-O2', '-o', str(parent), str(root / 'tools/minimal-parent.c')], check=True)

    def measure(tool, work, name):
        report.unlink(missing_ok=True)
        p = subprocess.run([str(parent), '--timeout', str(a.timeout), str(report), tool, 'cat-file', '-p', name],
                           cwd=work, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if p.returncode != 0:
            raise RuntimeError(('minimal parent', p.returncode, p.stderr))
        status, maxrss, user, system, wall, timed_out = report.read_text().split()
        return dict(status=int(status), stdout=hashlib.sha256(p.stdout).hexdigest(), stderr=p.stderr,
                    wall=float(wall), cpu=float(user) + float(system), maxrss_kib=int(maxrss),
                    ended=bool(int(timed_out)) or float(wall) >= a.timeout)

    work = out / 'work'
    run([git, 'init', '-q', '-b', 'main', work], out)
    rng = random.Random(0x72656164)
    lines = b''.join(b'%08d the compressible form of a 16 MiB blob, line by line\n' % i for i in range(300000))
    bodies = {'incompressible': rng.randbytes(SIZE), 'compressible': lines[:SIZE]}
    for name, body in bodies.items():
        (work / name).write_bytes(body)
    run([git, 'add', '-A'], work)
    run([git, 'commit', '-q', '-m', 'big'], work)
    run([git, 'repack', '-adfq', '--window=0', '--depth=0'], work)
    run([git, 'prune-packed'], work)
    floor_kib = min(measure('/bin/true' if Path('/bin/true').exists() else '/usr/bin/true', out, 'x')['maxrss_kib']
                    for _ in range(3))
    rows = []
    for label, body in bodies.items():
        name = run([git, 'rev-parse', f'HEAD:{label}'], work).decode().strip()
        best, sample = {}, {}
        for take in range(a.takes):
            order = (('git', git), ('den', den)) if take % 2 == 0 else (('den', den), ('git', git))
            for who, tool in order:
                r = measure(tool, work, name)
                sample.setdefault(who, r)
                b = best.setdefault(who, dict(wall=r['wall'], cpu=r['cpu'], maxrss_kib=r['maxrss_kib']))
                for k in ('wall', 'cpu', 'maxrss_kib'):
                    b[k] = min(b[k], r[k])
            if sample['den']['ended']:
                break
        g, d = sample['git'], sample['den']
        diffs = [f'{k}: git {g[k]!r} den {d[k]!r}' for k in ('status', 'stdout', 'stderr') if g[k] != d[k]]
        bound = dict(cpu=round(best['git']['cpu'] * RELATIVE['cpu_factor'] + RELATIVE['cpu_slack'], 3),
                     rss_kib=int(best['git']['maxrss_kib'] * RELATIVE['rss_factor']) + RELATIVE['rss_slack_kib'])
        ok = (not diffs and not d['ended'] and best['den']['cpu'] <= bound['cpu'] and
              best['den']['maxrss_kib'] <= bound['rss_kib'])
        size_kib = len(body) // 1024
        print(('PASS ' if ok else 'FAIL ') + f'read-scale-{label}' +
              f" den wall {best['den']['wall']:.3f} s cpu {best['den']['cpu']:.3f} s peak {best['den']['maxrss_kib']} KiB"
              f" ({best['den']['maxrss_kib'] / size_kib:.2f} of the blob);"
              f" git wall {best['git']['wall']:.3f} s cpu {best['git']['cpu']:.3f} s peak {best['git']['maxrss_kib']} KiB"
              f" ({best['git']['maxrss_kib'] / size_kib:.2f} of the blob);"
              f" den/git cpu {best['den']['cpu'] / max(best['git']['cpu'], 1e-6):.1f}x"
              f" peak {best['den']['maxrss_kib'] / max(best['git']['maxrss_kib'], 1):.1f}x;"
              f" bounds cpu {bound['cpu']} s peak {bound['rss_kib']} KiB; floor {floor_kib} KiB" +
              ('' if not diffs else '; ' + '; '.join(diffs)), flush=True)
        rows.append(ok)
    failures = rows.count(False)
    print(f'read-scale: {len(rows)} rows, {failures} failures; zero skips', flush=True)
    raise SystemExit(1 if failures else 0)


if __name__ == '__main__':
    main()
