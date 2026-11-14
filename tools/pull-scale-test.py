#!/usr/bin/env python3
"""den#100: pulls of a repository of the reported size, timed beside Git.

The fixture has the shape of the issue's repository: about 10,500 files in
about 1,000 directories, 5,000 commits, the clone's objects in 44 packs. It is
generated with Git's fast-import (or, with --source, copied from an existing
repository). Three pulls, each in fresh copies for both tools:

  uptodate  the local branch is at the remote's tip;
  ff        the remote is --moved commits ahead (a fast-forward);
  merge     the same, with one local commit (a true merge).

Each pull must equal the pinned Git's exit status, stdout, stderr and HEAD.
Wall time, CPU time (user + system, from rusage) and peak resident set are the
minimum over --takes runs; the resident-set floor this parent gives any child
(ru_maxrss survives fork and exec) is measured and printed beside them. den
must stay under the stated bounds, which are well under what the issue's
pulls took before this change (6 min 55 s for an up-to-date pull; 3.2 GiB
for a moved one).
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import time

BOUNDS = {
    'uptodate': dict(cpu=10.0, rss_kib=512 * 1024),
    'ff': dict(cpu=90.0, rss_kib=768 * 1024),
    'merge': dict(cpu=120.0, rss_kib=768 * 1024),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tier', default='native')
    parser.add_argument('--den')
    parser.add_argument('--source', help='an existing repository to copy instead of generating one')
    parser.add_argument('--branch', default='main')
    parser.add_argument('--files', type=int, default=10500)
    parser.add_argument('--commits', type=int, default=5000)
    parser.add_argument('--packs', type=int, default=44)
    parser.add_argument('--moved', type=int, default=20)
    parser.add_argument('--takes', type=int, default=3)
    parser.add_argument('--out')
    parser.add_argument('--filter', default='')
    a = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = Path(a.out) if a.out else root / 'target/runs' / ('pull-scale-' + a.tier)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    git = os.environ['DEN_GIT']
    assert hashlib.sha256(Path(git).read_bytes()).hexdigest() == 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
    den = a.den or str(root / 'target' / a.tier / 'den')
    os.environ['GIT_MERGE_AUTOEDIT'] = 'no'
    branch = a.branch

    def run(args, cwd, data=None):
        p = subprocess.run([str(x) for x in args], cwd=cwd, capture_output=True, input=data)
        assert p.returncode == 0, (args, p.stdout[-300:], p.stderr[-300:])
        return p.stdout

    def generate(origin):
        run([git, 'init', '-q', '--bare', '-b', branch, origin], out)
        stream = []
        mark = 0
        paths = [f'd{i % 1000:03}/s{(i // 1000) % 4}/f{i:05}.txt' for i in range(a.files)]
        for c in range(a.commits):
            changed = paths if c == 0 else [paths[(c * 7 + k * 131) % len(paths)] for k in range(3)]
            stream.append(f'commit refs/heads/{branch}\n')
            stream.append(f'committer Den Tester <den@example.invalid> {1700000000 + c} +0000\n')
            message = f'change {c}\n'
            stream.append(f'data {len(message)}\n{message}')
            for p in changed:
                body = f'{p} revision {c}\n' + 'line of text\n' * 20
                stream.append(f'M 100644 inline {p}\ndata {len(body.encode())}\n{body}\n')
            stream.append('\n')
        run([git, 'fast-import', '--quiet'], origin, ''.join(stream).encode())

    def reshape(work, packs):
        """Spread the clone's objects over packs, as many fetches leave them."""
        old = list((work / '.git/objects/pack').glob('pack-*'))
        names = [line.split()[0] for line in run([git, 'rev-list', '--objects', '--all'], work).decode().splitlines()]
        step = (len(names) + packs - 1) // packs
        for start in range(0, len(names), step):
            run([git, 'pack-objects', '-q', '.git/objects/pack/pack'], work,
                ('\n'.join(names[start:start + step]) + '\n').encode())
        for p in old:
            p.unlink()

    origin = out / 'origin.git'
    if a.source:
        run([git, 'clone', '-q', '--bare', '--no-local', a.source, origin], out)
    else:
        generate(origin)
    tip = run([git, 'rev-parse', branch], origin).strip().decode()
    # The behind remote holds history only up to tip~moved, so a pull must
    # fetch, and its clone's packs hold nothing from later.
    behind = out / 'behind.git'
    run([git, 'clone', '-q', '--bare', '--no-local', origin, behind], out)
    run([git, 'update-ref', f'refs/heads/{branch}', f'{tip}~{a.moved}'], behind)
    run([git, 'reflog', 'expire', '--expire=now', '--all'], behind)
    run([git, 'gc', '-q', '--prune=now'], behind)
    seeds = {}
    for name, source in (('uptodate', origin), ('ff', behind), ('merge', behind)):
        work = out / f'seed-{name}'
        run([git, 'clone', '-q', '--no-local', '-b', branch, source, work], out)
        run([git, 'config', 'gc.auto', '0'], work)
        run([git, 'config', 'maintenance.auto', 'false'], work)
        run([git, 'remote', 'set-url', 'origin', origin.as_uri()], work)
        if name == 'merge':
            (work / 'local-witness.txt').write_text('local independent change\n')
            run([git, 'add', 'local-witness.txt'], work)
            run([git, 'commit', '-qm', 'Add an independent local change'], work)
        reshape(work, a.packs)
        seeds[name] = work
    shape = run([git, 'count-objects', '-v'], seeds['ff']).decode().replace('\n', ' ')
    files = len(run([git, 'ls-files'], seeds['ff']).decode().splitlines())
    commits = run([git, 'rev-list', '--count', tip], origin).strip().decode()
    print(f'SHAPE files={files} commits={commits} moved={a.moved} {shape}', flush=True)

    floor = []
    for _ in range(3):
        pid = subprocess.Popen(['/bin/true']).pid
        _, _, usage = os.wait4(pid, 0)
        floor.append(usage.ru_maxrss)
    floor_kib = min(floor)
    print(f'FLOOR resident set of a child of this parent: {floor_kib} KiB', flush=True)

    def take(tool, argv, seed):
        work = out / 'work'
        if work.exists():
            shutil.rmtree(work)
        shutil.copytree(seed, work, symlinks=True)
        start = time.monotonic()
        with open(out / 'take.stdout', 'wb') as so, open(out / 'take.stderr', 'wb') as se:
            pid = subprocess.Popen([tool, *argv], cwd=work, stdout=so, stderr=se).pid
            _, status, usage = os.wait4(pid, 0)
        wall = time.monotonic() - start
        head = run([git, 'rev-parse', 'HEAD'], work).strip().decode()
        return dict(status=os.waitstatus_to_exitcode(status), stdout=(out / 'take.stdout').read_bytes().hex(),
                    stderr=(out / 'take.stderr').read_bytes().hex(), head=head, wall=wall,
                    cpu=usage.ru_utime + usage.ru_stime, maxrss_kib=usage.ru_maxrss)

    rows = []
    for name in ('uptodate', 'ff', 'merge'):
        row = f'pull-scale-{name}'
        if a.filter not in row:
            continue
        argv = ['pull', '--no-rebase', 'origin', branch]
        best = {}
        sample = {}
        for _ in range(a.takes):
            for label, tool in (('git', git), ('den', den)):
                r = take(tool, argv, seeds[name])
                sample.setdefault(label, r)
                b = best.setdefault(label, dict(wall=r['wall'], cpu=r['cpu'], maxrss_kib=r['maxrss_kib']))
                for k in ('wall', 'cpu', 'maxrss_kib'):
                    b[k] = min(b[k], r[k])
        g, d = sample['git'], sample['den']
        same = all(g[k] == d[k] for k in ('status', 'stdout', 'stderr', 'head'))
        bound = BOUNDS[name]
        bounded = best['den']['cpu'] <= bound['cpu'] and best['den']['maxrss_kib'] <= bound['rss_kib']
        ok = same and bounded and d['status'] == 0
        print(('PASS ' if ok else 'FAIL ') + row +
              f" den wall {best['den']['wall']:.2f} s cpu {best['den']['cpu']:.2f} s peak {best['den']['maxrss_kib']} KiB;"
              f" git wall {best['git']['wall']:.3f} s cpu {best['git']['cpu']:.3f} s peak {best['git']['maxrss_kib']} KiB;"
              f" bounds cpu {bound['cpu']} s peak {bound['rss_kib']} KiB; floor {floor_kib} KiB" +
              ('' if same else f" DIFFERS den exit {d['status']} stderr {bytes.fromhex(d['stderr'])[-200:]!r}"), flush=True)
        rows.append(dict(row=row, passed=ok, same=same, bounded=bounded, best=best, bound=bound,
                         floor_kib=floor_kib, git=g, den=d))
    assert rows, 'empty selection'
    (out / 'summary.json').write_text(json.dumps(dict(shape=shape, files=files, commits=commits, rows=rows), indent=2) + '\n')
    failures = sum(not r['passed'] for r in rows)
    print(f'pull-scale: {len(rows)} rows, {failures} failures; zero skips', flush=True)
    shutil.rmtree(out / 'work', ignore_errors=True)
    return int(failures > 0)


if __name__ == '__main__':
    raise SystemExit(main())
