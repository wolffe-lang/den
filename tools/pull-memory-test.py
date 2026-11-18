#!/usr/bin/env python3
"""den#138: a fast-forward pull's peak memory and CPU beside Git's, when the
pull adds paths throughout a large tree and changes files beside them.

The fixture has the shape of a week of a busy public repository: --files files
in --directories directories, one commit, then --moved commits on the remote
that add --added files spread through the tree (each sorts among existing
paths, not after them) and change --modified files of --lines lines each (a
few dozen lines apiece, so every file's line diff stays small). It is written
by the pinned Git's fast-import. The clone is one pack behind the remote's tip,
its origin a file URL, so the pull fetches the moved commits and fast-forwards.

Rows, each a pull in a fresh copy of the clone, for both tools:

  pull-memory-quiet  `pull --ff-only -q`: the fetch and the fast-forward's
                     work tree and index update, with no change summary;
  pull-memory-stat   `pull --ff-only`: the same, then the change summary Git
                     prints after a fast-forward.

Each tool starts through minimal-parent.c, so its peak resident set is its own.
Takes interleave the tools; each measure is a tool's minimum over --takes.
stdout, stderr, the exit status and HEAD must equal Git's. den is bounded
against Git in the same run: its peak at most RELATIVE's rss_factor times
Git's plus rss_slack_kib, its CPU at most cpu_factor times Git's plus
cpu_slack, stated for the native tier on Linux. A den run past --timeout
seconds is ended and fails its row.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

# Stated for the native tier on Linux. The peak bound holds a pull's memory
# as it stands with its index entries and its summary's changes put in path
# order without copies: on Linux the quiet pull peaked at 22 and the
# summarised one at 26 times Git's 14.6 MB (78% and 90% of their bounds),
# where the copying sort they replace kept 1.5 GB (more than three times
# either bound). What remains is the work tree scans, the trees and the
# ancestry walk, each in proportion to the repository. The CPU bound is
# slack against a stall or a search that grows with the square of the
# paths: den's pull takes about 30 times Git's CPU here, sorted either way.
RELATIVE = {
    'quiet': dict(argv=['pull', '--ff-only', '-q'],
                  rss_factor=20.0, rss_slack_kib=131072, cpu_factor=40.0, cpu_slack=2.0),
    'stat': dict(argv=['pull', '--ff-only'],
                 rss_factor=20.0, rss_slack_kib=131072, cpu_factor=40.0, cpu_slack=2.0),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tier', default='native')
    parser.add_argument('--den')
    parser.add_argument('--files', type=int, default=12000)
    parser.add_argument('--directories', type=int, default=1000)
    parser.add_argument('--added', type=int, default=200)
    parser.add_argument('--modified', type=int, default=100)
    parser.add_argument('--lines', type=int, default=400)
    parser.add_argument('--moved', type=int, default=40)
    parser.add_argument('--takes', type=int, default=3)
    parser.add_argument('--timeout', type=float, default=300.0)
    parser.add_argument('--out')
    parser.add_argument('--filter', default='')
    parser.add_argument('--dev-oracle', action='store_true', help='Darwin development evidence only; not the pinned Linux oracle')
    a = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = Path(a.out) if a.out else root / 'target/runs' / ('pull-memory-' + a.tier)
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
    os.environ['GIT_MERGE_AUTOEDIT'] = 'no'

    def run(args, cwd, data=None):
        p = subprocess.run([str(x) for x in args], cwd=cwd, capture_output=True, input=data)
        assert p.returncode == 0, (args, p.stdout[-300:], p.stderr[-300:])
        return p.stdout

    origin = out / 'origin.git'
    run([git, 'init', '-q', '--bare', '-b', 'main', origin], out)
    paths = [f'd{i % a.directories:03}/s{(i // a.directories) % 4}/f{i:05}.txt' for i in range(a.files)]
    # Spread through the tree: the k-th of each list falls in a different
    # directory, far from the end of the path order.
    step = max(1, a.files // max(1, a.modified))
    modified = [paths[(k * step + k) % a.files] for k in range(a.modified)]
    added = [f'd{(k * 7) % a.directories:03}/s{k % 4}/g{k:05}.txt' for k in range(a.added)]

    def body(path, revision):
        text = [f'{path}\n']
        for n in range(a.lines):
            # Every tenth line of a changed file names the revision, so each
            # change is a few dozen lines, never a rewrite.
            text.append(f'line {n} of {path}' + (f' at revision {revision}\n' if n % 10 == 0 else '\n'))
        return ''.join(text)

    stream = ['commit refs/heads/main\n', 'committer Den Tester <den@example.invalid> 1700000000 +0000\n',
              'data 5\nbase\n']
    big = set(modified)
    for p in paths:
        data = body(p, 0) if p in big else f'{p}\n'
        stream.append(f'M 100644 inline {p}\ndata {len(data.encode())}\n{data}\n')
    stream.append('\n')
    for c in range(a.moved):
        stream.append('commit refs/heads/main\n')
        stream.append(f'committer Den Tester <den@example.invalid> {1700000001 + c} +0000\n')
        message = f'week {c}\n'
        stream.append(f'data {len(message)}\n{message}')
        for p in added[c::a.moved]:
            data = f'{p} added in {c}\n'
            stream.append(f'M 100644 inline {p}\ndata {len(data.encode())}\n{data}\n')
        for p in modified[c::a.moved]:
            data = body(p, c + 1)
            stream.append(f'M 100644 inline {p}\ndata {len(data.encode())}\n{data}\n')
        stream.append('\n')
    run([git, 'fast-import', '--quiet'], origin, ''.join(stream).encode())
    tip = run([git, 'rev-parse', 'main'], origin).strip().decode()
    behind = out / 'behind.git'
    run([git, 'clone', '-q', '--bare', '--no-local', origin, behind], out)
    run([git, 'update-ref', 'refs/heads/main', f'{tip}~{a.moved}'], behind)
    run([git, 'reflog', 'expire', '--expire=now', '--all'], behind)
    run([git, 'gc', '-q', '--prune=now'], behind)
    seed = out / 'seed'
    run([git, 'clone', '-q', '--no-local', '-b', 'main', behind, seed], out)
    shutil.rmtree(behind)
    run([git, 'config', 'gc.auto', '0'], seed)
    run([git, 'config', 'maintenance.auto', 'false'], seed)
    run([git, 'remote', 'set-url', 'origin', origin.as_uri()], seed)
    shortstat = run([git, 'diff', '--shortstat', f'{tip}~{a.moved}', tip], origin).decode().strip()
    files = len(run([git, 'ls-files'], seed).decode().splitlines())
    print(f'SHAPE files={files} moved={a.moved} added={a.added} modified={a.modified} lines={a.lines}; {shortstat}',
          flush=True)

    parent = out / 'minimal-parent'
    report = out / 'measurement-usage'
    run(['cc', '-O2', '-o', parent, root / 'tools/minimal-parent.c'], out)

    def measure(argv, cwd):
        report.unlink(missing_ok=True)
        p = subprocess.run([str(parent), '--timeout', str(a.timeout), str(report), *map(str, argv)],
                           cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if p.returncode != 0:
            raise RuntimeError(('minimal parent', p.returncode, p.stderr))
        status, maxrss, user, system, wall, timed_out = report.read_text().split()
        return dict(status=int(status), stdout=p.stdout, stderr=p.stderr, wall=float(wall),
                    cpu=float(user) + float(system), maxrss_kib=int(maxrss),
                    ended=bool(int(timed_out)) or float(wall) >= a.timeout)

    floor_kib = min(measure(['/bin/true' if Path('/bin/true').exists() else '/usr/bin/true'], out)['maxrss_kib']
                    for _ in range(3))
    work = out / 'work'

    def take(tool, argv):
        if work.exists():
            shutil.rmtree(work)
        shutil.copytree(seed, work, symlinks=True)
        r = measure([tool, *argv], work)
        r['head'] = run([git, 'rev-parse', 'HEAD'], work).strip().decode()
        return r

    rows = []
    for name, rel in RELATIVE.items():
        row = f'pull-memory-{name}'
        if a.filter not in row:
            continue
        best = {}
        sample = {}
        for k in range(a.takes):
            order = (('git', git), ('den', den)) if k % 2 == 0 else (('den', den), ('git', git))
            for label, tool in order:
                r = take(tool, rel['argv'])
                sample.setdefault(label, r)
                b = best.setdefault(label, dict(wall=r['wall'], cpu=r['cpu'], maxrss_kib=r['maxrss_kib']))
                for key in ('wall', 'cpu', 'maxrss_kib'):
                    b[key] = min(b[key], r[key])
            # A den run ended at the timeout already fails the row: one take is enough.
            if sample['den']['ended']:
                break
        g, d = sample['git'], sample['den']
        diffs = []
        for key in ('status', 'stdout', 'stderr', 'head'):
            if g[key] != d[key]:
                shown = (g[key], d[key]) if key in ('status', 'head') else (g[key][-160:], d[key][-160:])
                diffs.append(f'{key}: git {shown[0]!r} den {shown[1]!r}')
        if g['head'] != tip:
            diffs.append(f'git left HEAD at {g["head"]}, not the tip {tip}')
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
              f" bounds cpu {bound['cpu']} s peak {bound['rss_kib']} KiB"
              f" (peak at {100 * best['den']['maxrss_kib'] / bound['rss_kib']:.1f}% of its bound); floor {floor_kib} KiB" +
              (f'; ended after {a.timeout} s' if d['ended'] else '') +
              ('' if not diffs else '; DIFFERS: ' + '; '.join(diffs)), flush=True)
        rows.append(dict(row=row, passed=ok, same=not diffs, bounded=bounded, best=best, bound=bound,
                         floor_kib=floor_kib))
    assert rows, 'empty selection'
    (out / 'summary.json').write_text(json.dumps(dict(shortstat=shortstat, files=files, rows=rows), indent=2) + '\n')
    failures = sum(not r['passed'] for r in rows)
    print(f'pull-memory: {len(rows)} rows, {failures} failures; zero skips', flush=True)
    shutil.rmtree(work, ignore_errors=True)
    shutil.rmtree(seed, ignore_errors=True)
    shutil.rmtree(origin, ignore_errors=True)
    return int(failures > 0)


if __name__ == '__main__':
    raise SystemExit(main())
