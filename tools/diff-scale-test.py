#!/usr/bin/env python3
"""den#101: the questions a script asks a checkout of 10,000 files, timed
beside Git.

The fixture is generated with Git's fast-import: --files files (default
10,000) in about --files/10 directories, --commits commits (default 1,000)
each editing a few files, its objects spread over --packs packs as fetches
leave them, then checked out clean with Git's index (stat data fresh, not
racily clean). Rows, each in fresh copies for both tools:

  diff-quiet         `diff --quiet` on the clean checkout;
  diff-cached-quiet  `diff --cached --quiet`;
  log-oneline        `log --oneline` over every commit;
  status             `status`;
  script             rev-parse HEAD, diff --quiet, diff --cached --quiet,
                     pull --ff-only (up to date, from a file:// remote), and
                     rev-parse HEAD again, one process after another.

Each row must equal the pinned Git's exit status, stdout and stderr, step by
step. CPU time (user + system) and peak resident set are den's minimum over
--takes runs; a run past --timeout seconds is ended and fails its row (one
take is enough when the first is over its bound). Each tool starts through
minimal-parent.c, so its peak does not inherit this Python runner's high-water
mark. That minimal parent's floor is printed beside the measurements. den
must stay under BOUNDS, stated for the native tier on a Linux x86-64 host
(the release tier is faster); before den#101 the two diff rows took minutes
and up to 2 GiB on this shape.

The -lf-attributes rows run status and diff --quiet with `* text=auto
eol=lf` in the copies' info/attributes, as a checkout that normalizes line
endings has them; Git reads none of the stat-clean bodies. Each take runs
Git and den with the attributes and den without them, and den's own cost of
the attributes is bounded by RELATIVE: its best CPU at most 1.25 times its
attribute-free best plus 20 ms, its best peak at most 1.10 times plus 4 MiB.
Git's numbers are printed beside.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

BOUNDS = {
    'diff-quiet': dict(cpu=2.0, rss_kib=192 * 1024),
    'diff-cached-quiet': dict(cpu=1.0, rss_kib=192 * 1024),
    'log-oneline': dict(cpu=3.0, rss_kib=192 * 1024),
    'status': dict(cpu=3.0, rss_kib=256 * 1024),
    'script': dict(cpu=6.0, rss_kib=256 * 1024),
}
SCRIPT = [['rev-parse', 'HEAD'], ['diff', '--quiet'], ['diff', '--cached', '--quiet'],
          ['pull', '--ff-only'], ['rev-parse', 'HEAD']]
LF_ATTRIBUTES = b'* text=auto eol=lf\n'
# An attribute row: its den baseline, measured in the same takes without the
# attributes, and the factors and slack of its bound.
ATTRIBUTE_ROWS = {
    'status-lf-attributes': 'status',
    'diff-quiet-lf-attributes': 'diff-quiet',
}
RELATIVE = dict(cpu_factor=1.25, cpu_slack=0.02, rss_factor=1.10, rss_slack_kib=4096)
ROWS = {
    'diff-quiet': [['diff', '--quiet']],
    'diff-cached-quiet': [['diff', '--cached', '--quiet']],
    'log-oneline': [['log', '--oneline']],
    'status': [['status']],
    'script': SCRIPT,
    'status-lf-attributes': [['status']],
    'diff-quiet-lf-attributes': [['diff', '--quiet']],
}


class Measurement:
    """The scale runner's process and resource-use boundary."""

    def __init__(self, root, out, timeout):
        self.root = Path(root).resolve()
        self.out = Path(out).resolve()
        self.timeout = timeout
        if not 0 < timeout <= 86400:
            raise ValueError('timeout must be positive and at most 86400 seconds')
        self.parent = self.out / 'minimal-parent'
        self.report = self.out / 'measurement-usage'
        subprocess.run(['cc', '-O2', '-o', str(self.parent), str(self.root / 'tools/minimal-parent.c')], check=True)

    def run(self, tool, argv, work):
        self.report.unlink(missing_ok=True)
        proc = subprocess.run([str(self.parent), '--timeout', str(self.timeout), str(self.report), tool, *argv],
                              cwd=work, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if proc.returncode != 0:
            raise RuntimeError(('minimal parent', proc.returncode, proc.stderr))
        status, maxrss, user, system, wall, timed_out = self.report.read_text().split()
        return dict(status=int(status), stdout=proc.stdout.hex(), stderr=proc.stderr.hex(),
                    wall=float(wall), cpu=float(user) + float(system), maxrss_kib=int(maxrss),
                    ended=bool(int(timed_out)) or float(wall) >= self.timeout)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tier', default='native')
    parser.add_argument('--den')
    parser.add_argument('--files', type=int, default=10000)
    parser.add_argument('--commits', type=int, default=1000)
    parser.add_argument('--packs', type=int, default=8)
    parser.add_argument('--takes', type=int, default=3)
    parser.add_argument('--timeout', type=float, default=300.0)
    parser.add_argument('--out')
    parser.add_argument('--filter', default='')
    parser.add_argument('--dev-oracle', action='store_true', help='Darwin development evidence only; not the pinned Linux oracle')
    a = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = Path(a.out) if a.out else root / 'target/runs' / ('diff-scale-' + a.tier)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    git = os.environ['DEN_GIT']
    digest = hashlib.sha256(Path(git).read_bytes()).hexdigest()
    if a.dev_oracle:
        assert os.uname().sysname == 'Darwin', 'development oracle is Darwin-only'
        print('DEV ORACLE (not pinned Linux evidence; BOUNDS are stated for Linux):', digest, flush=True)
    else:
        assert digest == 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
    den = a.den or str(root / 'target' / a.tier / 'den')
    branch = 'main'

    def run(args, cwd, data=None):
        p = subprocess.run([str(x) for x in args], cwd=cwd, capture_output=True, input=data)
        assert p.returncode == 0, (args, p.stdout[-300:], p.stderr[-300:])
        return p.stdout

    origin = out / 'origin.git'
    run([git, 'init', '-q', '--bare', '-b', branch, origin], out)
    stream = []
    paths = [f'd{i % (a.files // 10 or 1):04}/f{i:05}.txt' for i in range(a.files)]
    for c in range(a.commits):
        changed = paths if c == 0 else [paths[(c * 7 + k * 131) % len(paths)] for k in range(3)]
        stream.append(f'commit refs/heads/{branch}\n')
        stream.append(f'committer Den Tester <den@example.invalid> {1700000000 + 60 * c} +0000\n')
        message = f'change {c}\n'
        stream.append(f'data {len(message)}\n{message}')
        for p in changed:
            body = f'{p} revision {c}\n' + 'line of text\n' * 20
            stream.append(f'M 100644 inline {p}\ndata {len(body.encode())}\n{body}\n')
        stream.append('\n')
    run([git, 'fast-import', '--quiet'], origin, ''.join(stream).encode())

    seed = out / 'seed'
    run([git, 'clone', '-q', '--no-local', '-b', branch, origin, seed], out)
    run([git, 'config', 'gc.auto', '0'], seed)
    run([git, 'config', 'maintenance.auto', 'false'], seed)
    # Past 16,384 packed objects Git's default short names grow to eight
    # digits where den's log prints seven (a separate gap); seven for both.
    run([git, 'config', 'core.abbrev', '7'], seed)
    run([git, 'remote', 'set-url', 'origin', origin.as_uri()], seed)
    # Spread the clone's objects over packs, as many fetches leave them.
    old = list((seed / '.git/objects/pack').glob('pack-*'))
    names = [line.split()[0] for line in run([git, 'rev-list', '--objects', '--all'], seed).decode().splitlines()]
    step = (len(names) + a.packs - 1) // a.packs
    for start in range(0, len(names), step):
        run([git, 'pack-objects', '-q', '.git/objects/pack/pack'], seed,
            ('\n'.join(names[start:start + step]) + '\n').encode())
    for p in old:
        p.unlink()
    shape = run([git, 'count-objects', '-v'], seed).decode().replace('\n', ' ')
    files = len(run([git, 'ls-files'], seed).decode().splitlines())
    commits = run([git, 'rev-list', '--count', 'HEAD'], seed).strip().decode()
    print(f'SHAPE files={files} commits={commits} {shape}', flush=True)

    measurement = Measurement(root, out, a.timeout)
    floor_kib = min(measurement.run('/bin/true', [], out)['maxrss_kib'] for _ in range(3))
    print(f'FLOOR resident set of a child of the minimal parent: {floor_kib} KiB', flush=True)

    def take(tool, steps, attributes=False):
        work = out / 'work'
        if work.exists():
            shutil.rmtree(work)
        shutil.copytree(seed, work, symlinks=True)
        # Git's refresh after the copy: fresh stat data, then a later index
        # mtime than any file's, so no entry is racily clean for either tool.
        time.sleep(1.1)
        run([git, 'update-index', '-q', '--refresh'], work)
        if attributes:
            (work / '.git/info').mkdir(exist_ok=True)
            (work / '.git/info/attributes').write_bytes(LF_ATTRIBUTES)
        results = [measurement.run(tool, argv, work) for argv in steps]
        return dict(steps=results, wall=sum(r['wall'] for r in results), cpu=sum(r['cpu'] for r in results),
                    maxrss_kib=max(r['maxrss_kib'] for r in results), ended=any(r['ended'] for r in results))

    rows = []
    for name, steps in ROWS.items():
        row = f'diff-scale-{name}'
        if a.filter not in row:
            continue
        best = {}
        sample = {}
        attributes = name in ATTRIBUTE_ROWS
        tools = (('git', git), ('den', den)) + ((('den-plain', den),) if attributes else ())
        for _ in range(a.takes):
            for label, tool in tools:
                r = take(tool, steps, attributes and label != 'den-plain')
                sample.setdefault(label, r)
                b = best.setdefault(label, dict(wall=r['wall'], cpu=r['cpu'], maxrss_kib=r['maxrss_kib']))
                for k in ('wall', 'cpu', 'maxrss_kib'):
                    b[k] = min(b[k], r[k])
            # A den run over its bound already fails the row: one take is enough.
            if not attributes and sample['den']['cpu'] > BOUNDS[name]['cpu']:
                break
        g, d = sample['git'], sample['den']
        diffs = []
        for i, (gs, ds) in enumerate(zip(g['steps'], d['steps'])):
            for k in ('status', 'stdout', 'stderr'):
                if gs[k] != ds[k]:
                    shown = (gs[k], ds[k]) if k == 'status' else (bytes.fromhex(gs[k])[-160:], bytes.fromhex(ds[k])[-160:])
                    diffs.append(f'step {i} {" ".join(steps[i])} {k}: git {shown[0]!r} den {shown[1]!r}')
        if attributes:
            plain = best['den-plain']
            bound = dict(cpu=round(plain['cpu'] * RELATIVE['cpu_factor'] + RELATIVE['cpu_slack'], 3),
                         rss_kib=int(plain['maxrss_kib'] * RELATIVE['rss_factor']) + RELATIVE['rss_slack_kib'])
        else:
            bound = BOUNDS[name]
        bounded = (not d['ended'] and best['den']['cpu'] <= bound['cpu'] and
                   best['den']['maxrss_kib'] <= bound['rss_kib'])
        ok = not diffs and bounded
        print(('PASS ' if ok else 'FAIL ') + row +
              f" den wall {best['den']['wall']:.3f} s cpu {best['den']['cpu']:.3f} s peak {best['den']['maxrss_kib']} KiB;"
              f" git wall {best['git']['wall']:.3f} s cpu {best['git']['cpu']:.3f} s peak {best['git']['maxrss_kib']} KiB;" +
              (f" den without attributes cpu {best['den-plain']['cpu']:.3f} s peak {best['den-plain']['maxrss_kib']} KiB;"
               if attributes else '') +
              f" bounds cpu {bound['cpu']} s peak {bound['rss_kib']} KiB; floor {floor_kib} KiB" +
              (f'; ended after {a.timeout} s' if d['ended'] else '') +
              ('' if not diffs else '; DIFFERS: ' + '; '.join(diffs)), flush=True)
        rows.append(dict(row=row, passed=ok, same=not diffs, bounded=bounded, best=best, bound=bound,
                         floor_kib=floor_kib, git=g, den=d))
    assert rows, 'empty selection'
    (out / 'summary.json').write_text(json.dumps(dict(shape=shape, files=files, commits=commits, rows=rows), indent=2) + '\n')
    failures = sum(not r['passed'] for r in rows)
    print(f'diff-scale: {len(rows)} rows, {failures} failures; zero skips', flush=True)
    shutil.rmtree(out / 'work', ignore_errors=True)
    return int(failures > 0)


if __name__ == '__main__':
    raise SystemExit(main())
