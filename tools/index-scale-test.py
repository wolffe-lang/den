#!/usr/bin/env python3
"""Reading an index of --entries entries (default 100,000) in --directories
directories (default 10,000), with its cache tree, timed beside Git.

The fixture is made with the pinned Git alone: one blob, the entries added by
update-index --index-info (no work tree), write-tree for the cache tree (one
record a directory), and a commit of that tree as HEAD. Rows, each run by both
tools on the same repository, which neither changes:

  ls-files             `ls-files`: every entry and the cache tree parsed and
                       checked, every entry printed.

Each row must equal the pinned Git's exit status, stdout and stderr. Each tool
starts through minimal-parent.c, so its peak resident set is its own. CPU time
(user + system) and peak are each tool's minimum over --takes runs, the two
tools interleaved. den is bounded against Git in the same take: its CPU at most
RELATIVE's cpu_factor times Git's plus cpu_slack, its peak at most rss_factor
times Git's plus rss_slack_kib, stated for the native tier. A den run past
--timeout seconds is ended and fails its row. Checking the cache tree's records
against the entries was quadratic in the number of directories: on this shape
that took den about a minute where Git takes milliseconds.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROWS = {
    'ls-files': ['ls-files'],
}
# den's per-entry parse is still about 25 times Git's on Linux (native); the
# bound keeps that from growing and fails the quadratic check by far (minutes).
RELATIVE = dict(cpu_factor=40.0, cpu_slack=0.1, rss_factor=8.0, rss_slack_kib=16384)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tier', default='native')
    parser.add_argument('--den')
    parser.add_argument('--entries', type=int, default=100000)
    parser.add_argument('--directories', type=int, default=10000)
    parser.add_argument('--takes', type=int, default=3)
    parser.add_argument('--timeout', type=float, default=120.0)
    parser.add_argument('--out')
    parser.add_argument('--dev-oracle', action='store_true', help='Darwin development evidence only; not the pinned Linux oracle')
    a = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = Path(a.out) if a.out else root / 'target/runs' / ('index-scale-' + a.tier)
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
    env = dict(os.environ, GIT_AUTHOR_NAME='Den Tester', GIT_AUTHOR_EMAIL='den@example.invalid',
               GIT_COMMITTER_NAME='Den Tester', GIT_COMMITTER_EMAIL='den@example.invalid',
               GIT_AUTHOR_DATE='1700000000 +0000', GIT_COMMITTER_DATE='1700000000 +0000')

    def run(args, cwd, data=None):
        p = subprocess.run([str(x) for x in args], cwd=cwd, capture_output=True, input=data, env=env)
        assert p.returncode == 0, (args, p.stdout[-300:], p.stderr[-300:])
        return p.stdout

    repo = out / 'repo'
    run([git, 'init', '-q', '-b', 'main', repo], out)
    blob = run([git, 'hash-object', '-w', '--stdin'], repo, b'one line\n').strip().decode()
    per = a.entries // a.directories
    lines = [f'100644 {blob} 0\td{d:05}/f{f:03}.txt\n' for d in range(a.directories) for f in range(per)]
    run([git, 'update-index', '--index-info'], repo, ''.join(lines).encode())
    tree = run([git, 'write-tree'], repo).strip().decode()
    commit = run([git, 'commit-tree', '-m', 'index scale', tree], repo).strip().decode()
    run([git, 'update-ref', 'HEAD', commit], repo)
    index = (repo / '.git/index').read_bytes()
    entries = int.from_bytes(index[8:12], 'big')
    print(f'SHAPE entries={entries} directories={a.directories} index={len(index)} bytes '
          f'cache-tree={index.find(b"TREE") > 0}', flush=True)

    parent = out / 'minimal-parent'
    report = out / 'measurement-usage'
    subprocess.run(['cc', '-O2', '-o', str(parent), str(root / 'tools/minimal-parent.c')], check=True)

    def measure(tool, argv):
        report.unlink(missing_ok=True)
        p = subprocess.run([str(parent), '--timeout', str(a.timeout), str(report), tool, *argv],
                           cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        if p.returncode != 0:
            raise RuntimeError(('minimal parent', p.returncode, p.stderr))
        status, maxrss, user, system, wall, timed_out = report.read_text().split()
        return dict(status=int(status), stdout=p.stdout, stderr=p.stderr, wall=float(wall),
                    cpu=float(user) + float(system), maxrss_kib=int(maxrss),
                    ended=bool(int(timed_out)) or float(wall) >= a.timeout)

    floor_kib = min(measure('/bin/true' if Path('/bin/true').exists() else '/usr/bin/true', [])['maxrss_kib']
                    for _ in range(3))
    rows = []
    for name, argv in ROWS.items():
        row = f'index-scale-{name}'
        best = {}
        sample = {}
        for take in range(a.takes):
            order = (('git', git), ('den', den)) if take % 2 == 0 else (('den', den), ('git', git))
            for label, tool in order:
                r = measure(tool, argv)
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
        rows.append(dict(row=row, passed=ok, same=not diffs, bounded=bounded, best=best, bound=bound,
                         floor_kib=floor_kib))
    (out / 'summary.json').write_text(json.dumps(dict(entries=entries, directories=a.directories, rows=rows),
                                                 indent=2) + '\n')
    failures = sum(not r['passed'] for r in rows)
    print(f'index-scale: {len(rows)} rows, {failures} failures; zero skips', flush=True)
    shutil.rmtree(repo, ignore_errors=True)
    return int(failures > 0)


if __name__ == '__main__':
    raise SystemExit(main())
