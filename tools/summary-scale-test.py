#!/usr/bin/env python3
"""den#105: the change summary a pull or merge prints after it moves HEAD, at
sizes past 2,000 differing lines in a file, beside the pinned Git.

Every row runs Git and den in fresh copies of one clone and requires den's
exit status, stdout, stderr and HEAD to equal Git's. Fixtures are made with
the pinned Git alone; each remote is one or two commits ahead of its clone.

  summary-rewrite-pull    a fast-forward pull that rewrites every line of a
                          2,500-line file (5,000 differing lines);
  summary-rewrite-merge   the same through a true merge (`pull --no-rebase`
                          beside one local commit);
  summary-generated-pull  a fast-forward pull of a generated table of --lines
                          lines (a parser's shape: lines drawn from a
                          vocabulary of --vocabulary, so every changed line
                          also occurs elsewhere), every --every-th line
                          replaced, about --lines / --every * 2 differing
                          lines; den's peak and CPU are bounded against Git's;
  summary-diff-stat       `diff --stat` of that table's two commits;
  summary-diff-numstat    `diff --numstat` of the same;
  summary-binary-N        a fast-forward pull adding a binary file beside a text
                          file of N-digit line count (N = 1, 2, 4, 5): the
                          `Bin` row's place in the count column.

Each tool starts through minimal-parent.c, so its peak resident set is its own.
The generated row's bound is stated for the native tier on Linux: den's peak
at most rss_factor times Git's plus rss_slack_kib, its CPU at most cpu_factor
times Git's plus cpu_slack. A trace of the line diff kept whole grows as the
square of the differing lines (at --lines 60,000 and --every 12, about
10,000 of them: hundreds of megabytes); the linear-space count holds the
two inputs' line tables and one row of the search.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import subprocess

GENERATED = dict(rss_factor=4.0, rss_slack_kib=32768, cpu_factor=60.0, cpu_slack=2.0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tier', default='native')
    parser.add_argument('--den')
    parser.add_argument('--lines', type=int, default=60000)
    parser.add_argument('--vocabulary', type=int, default=500)
    parser.add_argument('--every', type=int, default=12)
    parser.add_argument('--timeout', type=float, default=300.0)
    parser.add_argument('--out')
    parser.add_argument('--filter', default='')
    parser.add_argument('--dev-oracle', action='store_true', help='Darwin development evidence only; not the pinned Linux oracle')
    a = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = Path(a.out) if a.out else root / 'target/runs' / ('summary-scale-' + a.tier)
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

    def fixture(name, base_files, next_files, local=False):
        """A clone one commit behind its remote; with local, one local commit too."""
        case = out / name
        case.mkdir()
        origin, work = case / 'origin', case / 'seed'
        run([git, 'init', '-q', '-b', 'main', origin], case)
        for path, data in base_files.items():
            (origin / path).parent.mkdir(parents=True, exist_ok=True)
            (origin / path).write_bytes(data)
        run([git, 'add', '.'], origin)
        run([git, 'commit', '-qm', 'base'], origin)
        run([git, 'clone', '-q', origin, work], case)
        run([git, 'config', 'gc.auto', '0'], work)
        run([git, 'config', 'maintenance.auto', 'false'], work)
        if local:
            (work / 'local.txt').write_text('local\n')
            run([git, 'add', 'local.txt'], work)
            run([git, 'commit', '-qm', 'local'], work)
        for path, data in next_files.items():
            (origin / path).write_bytes(data)
        run([git, 'add', '.'], origin)
        run([git, 'commit', '-qm', 'next'], origin)
        if local:
            run([git, 'fetch', '-q', 'origin'], work)
        return case

    rows = []

    def row(name, case, argv, bound=None):
        if a.filter not in name:
            return
        seed = case / 'seed'
        sample, best = {}, {}
        for label, tool in (('git', git), ('den', den)):
            work = case / ('work-' + label)
            if work.exists():
                shutil.rmtree(work)
            shutil.copytree(seed, work, symlinks=True)
            r = measure([tool, *argv], work)
            r['head'] = run([git, 'rev-parse', 'HEAD'], work).strip().decode()
            sample[label] = r
            best[label] = dict(wall=r['wall'], cpu=r['cpu'], maxrss_kib=r['maxrss_kib'])
            shutil.rmtree(work)
        g, d = sample['git'], sample['den']
        diffs = []
        for key in ('status', 'stdout', 'stderr', 'head'):
            if g[key] != d[key]:
                shown = (g[key], d[key]) if key in ('status', 'head') else (g[key][-240:], d[key][-240:])
                diffs.append(f'{key}: git {shown[0]!r} den {shown[1]!r}')
        limits = None
        bounded = not d['ended']
        if bound:
            limits = dict(cpu=round(g['cpu'] * bound['cpu_factor'] + bound['cpu_slack'], 3),
                          rss_kib=int(g['maxrss_kib'] * bound['rss_factor']) + bound['rss_slack_kib'])
            bounded = bounded and d['cpu'] <= limits['cpu'] and d['maxrss_kib'] <= limits['rss_kib']
        ok = not diffs and bounded and g['status'] == 0
        print(('PASS ' if ok else 'FAIL ') + name +
              f" den cpu {d['cpu']:.3f} s peak {d['maxrss_kib']} KiB; git cpu {g['cpu']:.3f} s peak {g['maxrss_kib']} KiB" +
              (f"; bounds cpu {limits['cpu']} s peak {limits['rss_kib']} KiB"
               f" (peak at {100 * d['maxrss_kib'] / limits['rss_kib']:.1f}% of its bound)" if limits else '') +
              (f'; ended after {a.timeout} s' if d['ended'] else '') +
              ('' if not diffs else '; DIFFERS: ' + '; '.join(diffs)), flush=True)
        rows.append(dict(row=name, passed=ok, same=not diffs, bounded=bounded, best=best, bound=limits))

    want = lambda prefix: any(prefix in n and a.filter in n for n in (
        'summary-rewrite-pull', 'summary-rewrite-merge', 'summary-generated-pull', 'summary-diff-stat',
        'summary-diff-numstat', 'summary-binary-1', 'summary-binary-2', 'summary-binary-4', 'summary-binary-5'))

    old = ''.join(f'old line {i}\n' for i in range(2500)).encode()
    new = ''.join(f'new line {i}\n' for i in range(2500)).encode()
    if want('summary-rewrite-pull'):
        case = fixture('rewrite-pull', {'long.txt': old, 'a.txt': b'a\n'}, {'long.txt': new})
        row('summary-rewrite-pull', case, ['pull', '--ff-only', 'origin', 'main'])
    if want('summary-rewrite-merge'):
        case = fixture('rewrite-merge', {'long.txt': old, 'a.txt': b'a\n'}, {'long.txt': new}, local=True)
        row('summary-rewrite-merge', case, ['pull', '--no-rebase', 'origin', 'main'])

    if want('summary-generated') or want('summary-diff'):
        r = random.Random(105)
        words = [f'    [{i}] = {{.count = {i % 7}, .reusable = {"true" if i % 3 else "false"}}}, SHIFT({i * 13 % 997}),\n'
                 for i in range(a.vocabulary)]
        table = [words[r.randrange(a.vocabulary)] for _ in range(a.lines)]
        changed = list(table)
        for i in range(0, a.lines, a.every):
            changed[i] = words[r.randrange(a.vocabulary)]
        case = fixture('generated', {'src/parser.c': ''.join(table).encode(), 'README': b'table\n'},
                       {'src/parser.c': ''.join(changed).encode(), 'README': b'table, again\n'})
        shortstat = run([git, 'diff', '--shortstat', 'HEAD~', 'HEAD'], case / 'origin').decode().strip()
        print(f'SHAPE generated lines={a.lines} vocabulary={a.vocabulary} every={a.every}: {shortstat}', flush=True)
        row('summary-generated-pull', case, ['pull', '--ff-only', 'origin', 'main'], GENERATED)
        tip = run([git, 'rev-parse', 'HEAD'], case / 'origin').strip().decode()
        run([git, 'fetch', '-q', 'origin'], case / 'seed')
        row('summary-diff-stat', case, ['diff', '--stat', 'HEAD', tip])
        row('summary-diff-numstat', case, ['diff', '--numstat', 'HEAD', tip])

    for digits, count in ((1, 5), (2, 42), (4, 1234), (5, 12345)):
        name = f'summary-binary-{digits}'
        if not want(name):
            continue
        text = ''.join(f'text line {i}\n' for i in range(count)).encode()
        blob = bytes(range(256)) * 19 + b'\0tail'
        case = fixture(f'binary-{digits}', {'a.txt': b'a\n'}, {'counted.txt': text, 'image.bin': blob})
        row(name, case, ['pull', '--ff-only', 'origin', 'main'])

    assert rows, 'empty selection'
    (out / 'summary.json').write_text(json.dumps(rows, indent=2) + '\n')
    failures = sum(not x['passed'] for x in rows)
    print(f'summary-scale: {len(rows)} rows, {failures} failures; zero skips', flush=True)
    for case in out.iterdir():
        if case.is_dir():
            shutil.rmtree(case, ignore_errors=True)
    return int(failures > 0)


if __name__ == '__main__':
    raise SystemExit(main())
