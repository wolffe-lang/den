#!/usr/bin/env python3
"""den#145: everyday commands over a blob just past 16 MiB, and one just
under it, beside the pinned Git.

The remote (bare, reached by a file URL or a path) has two commits on main:

  base  big.json, a text file of --size less 256 KiB; blob.bin, 4 KiB of
        binary; a, a small text file;
  grow  big.json grown to --size by lines appended at its end (one hunk, so
        den's three-way merge, which takes one hunk a side, can combine it);
        blob.bin replaced by --size bytes of binary.

and a branch `moved` on grow that renames big.json to moved.json and changes
one line. With the default --size (16 MiB and 4 KiB) every grown body is past
16 MiB; with --under it is 16 MiB less 4 KiB, so every body is under it.

Rows, each run by both tools in a fresh copy of one template at one path:

  clone-url, clone-path   clone the remote through a file URL, and a path;
  fetch                   fetch grow into a clone of base (the objects are new);
  pull-ff, pull-ff-quiet  `pull --ff-only` with its stat, and with -q;
  pull-merge              `pull --no-rebase` beside a local commit of another
                          file (a true merge; big.json changed on one side);
  pull-merge-both         the same with big.json's first line changed locally,
                          so the merge combines both sides' big.json;
  checkout-back           `checkout -q HEAD~1` in a clone of grow;
  checkout-forward        `checkout -q main` from base, detached;
  status                  `status` with big.json changed in the work tree;
  status-untracked        `status` with a new file of --size bytes;
  status-touched          `status --porcelain` with big.json's stat data
                          changed and its bytes not;
  diff, diff-stat         `diff` and `diff --stat` of the changed big.json;
  diff-cached             `diff --cached` with it staged;
  diff-commits(-stat)     `diff HEAD~1 HEAD` and its `--stat`;
  diff-binary             `diff` with blob.bin changed in the work tree;
  add, add-new            `add` the changed big.json, and a new large file;
  commit, commit-all      `commit -m` with it staged, and `commit -am`;
  commit-new              `commit -m` with a new large file staged;
  rename-stat             `diff -M --stat origin/main origin/moved`;
  merge-rename            `merge --ff-only origin/moved`, its stat and rename.

Each row requires den's exit status, stdout and stderr to equal Git's byte
for byte, and the state after it: HEAD, every ref, the index (`ls-files
-s`), MERGE_HEAD, and every work tree file's mode and digest, read by the
pinned Git. Each tool starts through minimal-parent.c, so its peak resident
set is its own; den's peak is bounded by Git's in the same take (RSS_FACTOR
times Git's plus RSS_SLACK_KIB) and its CPU likewise, stated for the native
tier on Linux. A den run past --timeout seconds is ended and fails its row.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import shlex
import shutil
import stat
import subprocess

MIB = 1048576
RSS_FACTOR, RSS_SLACK_KIB = 4.0, 65536
CPU_FACTOR, CPU_SLACK = 40.0, 5.0


def text(size, edited):
    """A JSON-like text of exactly `size` bytes: numbered lines, with every
    25,000th line edited when `edited` (a new file's body), and a newline at
    its end. A shorter text is a prefix of a longer one but for its last line."""
    parts, total, n = [], 0, 0
    while total < size:
        line = f'  {{"row": {n}, "value": "{(n * 2654435761) % 4294967296:010d}", "note": "entry"}},\n'
        if edited and n % 25000 == 12500:
            line = f'  {{"row": {n}, "value": "edited", "note": "changed in grow"}},\n'
        parts.append(line)
        total += len(line)
        n += 1
    data = ''.join(parts).encode()[:size]
    return data[:-1] + b'\n'


def binary(size, seed):
    return random.Random(seed).randbytes(size)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tier', default='native')
    parser.add_argument('--den')
    parser.add_argument('--size', type=int, default=16 * MIB + 4096)
    parser.add_argument('--under', action='store_true', help='--size becomes 16 MiB less 4 KiB')
    parser.add_argument('--takes', type=int, default=1)
    parser.add_argument('--timeout', type=float, default=300.0)
    parser.add_argument('--wrap', default='', help='a command prefix for each measured run (a memory cap)')
    parser.add_argument('--out')
    parser.add_argument('--filter', default='')
    parser.add_argument('--dev-oracle', action='store_true', help='Darwin development evidence only; not the pinned Linux oracle')
    a = parser.parse_args()
    size = 16 * MIB - 4096 if a.under else a.size
    label = 'under' if a.under else ('over' if a.size == 16 * MIB + 4096 else f'size-{a.size}')
    root = Path(__file__).resolve().parents[1]
    out = Path(a.out) if a.out else root / 'target/runs' / f'large-blob-{label}-{a.tier}'
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
    wrap = shlex.split(a.wrap)
    os.environ['GIT_MERGE_AUTOEDIT'] = 'no'

    def run(args, cwd, data=None):
        p = subprocess.run([str(x) for x in args], cwd=cwd, capture_output=True, input=data)
        assert p.returncode == 0, (args, p.stdout[-300:], p.stderr[-300:])
        return p.stdout

    # The remote and its history, made by the pinned Git alone.
    base_size = size - 262144
    big0, big1 = text(base_size, False), text(size, False)
    bin0, bin1 = binary(4096, 1), binary(size, 2)
    work = out / 'origin'
    run([git, 'init', '-q', '-b', 'main', work], out)
    (work / 'a').write_text('a\n')
    (work / 'big.json').write_bytes(big0)
    (work / 'blob.bin').write_bytes(bin0)
    run([git, 'add', '.'], work)
    run([git, 'commit', '-qm', 'base'], work)
    (work / 'big.json').write_bytes(big1)
    (work / 'blob.bin').write_bytes(bin1)
    run([git, 'commit', '-qam', 'grow'], work)
    run([git, 'checkout', '-qb', 'moved'], work)
    run([git, 'mv', 'big.json', 'moved.json'], work)
    moved = bytearray(big1)
    moved[0:1] = b'['
    (work / 'moved.json').write_bytes(bytes(moved))
    run([git, 'commit', '-qam', 'move'], work)
    run([git, 'checkout', '-q', 'main'], work)
    remote = out / 'remote.git'
    run([git, 'clone', '-q', '--bare', '--no-local', work, remote], out)
    shutil.rmtree(work)
    tip = run([git, 'rev-parse', 'main'], remote).strip().decode()
    old = run([git, 'rev-parse', 'main~1'], remote).strip().decode()
    print(f'SHAPE size={size} big.json {base_size} -> {size} bytes; blob.bin 4096 -> {size} bytes; '
          f'main {old[:12]} -> {tip[:12]}', flush=True)

    templates = out / 'templates'
    templates.mkdir()

    def configure(w):
        run([git, 'config', 'gc.auto', '0'], w)
        run([git, 'config', 'maintenance.auto', 'false'], w)

    # behind: a clone of base whose remote has moved to grow; its pack lacks
    # every object grow added.
    behind_remote = out / 'behind.git'
    run([git, 'clone', '-q', '--bare', '--no-local', remote, behind_remote], out)
    run([git, 'update-ref', 'refs/heads/main', old], behind_remote)
    run([git, 'update-ref', '-d', 'refs/heads/moved'], behind_remote)
    run([git, 'reflog', 'expire', '--expire=now', '--all'], behind_remote)
    run([git, 'gc', '-q', '--prune=now'], behind_remote)
    behind = templates / 'behind' / 'w'
    behind.parent.mkdir()
    run([git, 'clone', '-q', '--no-local', '-b', 'main', behind_remote, behind], out)
    shutil.rmtree(behind_remote)
    configure(behind)
    run([git, 'remote', 'set-url', 'origin', remote.as_uri()], behind)

    def derive(name, source, change):
        target = templates / name / 'w'
        shutil.copytree(source, target, symlinks=True)
        change(target)
        return target

    def local_commit(w):
        (w / 'local').write_text('local\n')
        run([git, 'add', 'local'], w)
        run([git, 'commit', '-qm', 'local'], w)

    def local_big(w):
        data = bytearray((w / 'big.json').read_bytes())
        data[0:1] = b'['
        (w / 'big.json').write_bytes(bytes(data))
        run([git, 'commit', '-qam', 'local first line'], w)

    derive('behind-local', behind, local_commit)
    derive('behind-big', behind, local_big)

    current = templates / 'current' / 'w'
    current.parent.mkdir()
    run([git, 'clone', '-q', '--no-local', remote, current], out)
    configure(current)

    def edit_big(w):
        data = (w / 'big.json').read_bytes()
        middle = data.index(b'\n', len(data) // 2) + 1
        (w / 'big.json').write_bytes(data[:middle] + b'  {"row": "inserted in the work tree"},\n' +
                                     data[middle:] + b'  {"row": "appended in the work tree"}\n')

    def new_large(w):
        (w / 'new.json').write_bytes(text(size, True))

    def touch_big(w):
        p = w / 'big.json'
        st = p.stat()
        os.utime(p, (st.st_atime, st.st_mtime + 100))

    def edit_bin(w):
        data = bytearray((w / 'blob.bin').read_bytes())
        data[len(data) // 2] ^= 0xff
        (w / 'blob.bin').write_bytes(bytes(data))

    derive('edited', current, edit_big)
    derive('staged', current, lambda w: (edit_big(w), run([git, 'add', 'big.json'], w)))
    derive('untracked', current, new_large)
    derive('new-staged', current, lambda w: (new_large(w), run([git, 'add', 'new.json'], w)))
    derive('touched', current, touch_big)
    derive('binary-edited', current, edit_bin)
    derive('detached-base', current, lambda w: run([git, 'checkout', '-q', 'HEAD~1'], w))
    empty = templates / 'empty' / 'w'
    empty.mkdir(parents=True)

    rows = [
        ('clone-url', 'empty', ['clone', remote.as_uri(), 'c'], 'c'),
        ('clone-path', 'empty', ['clone', str(remote), 'c'], 'c'),
        ('fetch', 'behind', ['fetch', 'origin'], '.'),
        ('pull-ff', 'behind', ['pull', '--ff-only'], '.'),
        ('pull-ff-quiet', 'behind', ['pull', '--ff-only', '-q'], '.'),
        ('pull-merge', 'behind-local', ['pull', '--no-rebase'], '.'),
        ('pull-merge-both', 'behind-big', ['pull', '--no-rebase'], '.'),
        ('checkout-back', 'current', ['checkout', '-q', 'HEAD~1'], '.'),
        ('checkout-forward', 'detached-base', ['checkout', '-q', 'main'], '.'),
        ('status', 'edited', ['status'], '.'),
        ('status-untracked', 'untracked', ['status'], '.'),
        ('status-touched', 'touched', ['status', '--porcelain'], '.'),
        ('diff', 'edited', ['diff'], '.'),
        ('diff-stat', 'edited', ['diff', '--stat'], '.'),
        ('diff-cached', 'staged', ['diff', '--cached'], '.'),
        ('diff-commits', 'current', ['diff', 'HEAD~1', 'HEAD'], '.'),
        ('diff-commits-stat', 'current', ['diff', '--stat', 'HEAD~1', 'HEAD'], '.'),
        ('diff-binary', 'binary-edited', ['diff'], '.'),
        ('add', 'edited', ['add', 'big.json'], '.'),
        ('add-new', 'untracked', ['add', 'new.json'], '.'),
        ('commit', 'staged', ['commit', '-m', 'change'], '.'),
        ('commit-all', 'edited', ['commit', '-am', 'change'], '.'),
        ('commit-new', 'new-staged', ['commit', '-m', 'new'], '.'),
        ('rename-stat', 'current', ['diff', '-M', '--stat', 'origin/main', 'origin/moved'], '.'),
        ('merge-rename', 'current', ['merge', '--ff-only', 'origin/moved'], '.'),
    ]

    parent = out / 'minimal-parent'
    report = out / 'measurement-usage'
    run(['cc', '-O2', '-o', parent, root / 'tools/minimal-parent.c'], out)

    def measure(argv, cwd):
        report.unlink(missing_ok=True)
        p = subprocess.run([str(parent), '--timeout', str(a.timeout), str(report), *wrap, *map(str, argv)],
                           cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if p.returncode != 0:
            raise RuntimeError(('minimal parent', p.returncode, p.stderr))
        status, maxrss, user, system, wall, timed_out = report.read_text().split()
        return dict(status=int(status), stdout=p.stdout, stderr=p.stderr, wall=float(wall),
                    cpu=float(user) + float(system), maxrss_kib=int(maxrss),
                    ended=bool(int(timed_out)) or float(wall) >= a.timeout)

    def state(w):
        """What the command left, read by the pinned Git: never den."""
        if not (w / '.git').exists():
            return dict(missing=True)
        def ask(*args):
            p = subprocess.run([git, *args], cwd=w, capture_output=True)
            return p.returncode, p.stdout.decode(errors='replace')
        files = {}
        for path in sorted(w.rglob('*')):
            relative = path.relative_to(w)
            if relative.parts[0] == '.git' or path.is_dir():
                continue
            mode = path.lstat().st_mode
            files[str(relative)] = (stat.S_IMODE(mode) & 0o111 != 0,
                                    hashlib.sha256(path.read_bytes()).hexdigest())
        return dict(head=ask('rev-parse', '--verify', '-q', 'HEAD'),
                    symbolic=ask('symbolic-ref', '-q', 'HEAD'),
                    refs=ask('for-each-ref', '--format=%(refname) %(objectname)'),
                    index=ask('ls-files', '-s'),
                    merge_head=(w / '.git/MERGE_HEAD').exists(),
                    files=files)

    floor_kib = min(measure(['/bin/true' if Path('/bin/true').exists() else '/usr/bin/true'], out)['maxrss_kib']
                    for _ in range(3))
    results = []
    for name, template, argv, where in rows:
        row = f'large-blob-{label}-{name}'
        if a.filter not in row:
            continue
        place = out / 'run'
        best, sample = {}, {}
        for k in range(a.takes):
            order = (('git', git), ('den', den)) if k % 2 == 0 else (('den', den), ('git', git))
            for tool_label, tool in order:
                if place.exists():
                    shutil.rmtree(place)
                shutil.copytree(templates / template, place, symlinks=True)
                r = measure([tool, *argv], place / 'w')
                r['state'] = state(place / 'w' / where)
                sample.setdefault(tool_label, r)
                b = best.setdefault(tool_label, dict(wall=r['wall'], cpu=r['cpu'], maxrss_kib=r['maxrss_kib']))
                for key in ('wall', 'cpu', 'maxrss_kib'):
                    b[key] = min(b[key], r[key])
            if sample['den']['ended']:
                break
        shutil.rmtree(place)
        g, d = sample['git'], sample['den']
        diffs = []
        for key in ('status', 'stdout', 'stderr'):
            if g[key] != d[key]:
                shown = (g[key], d[key]) if key == 'status' else (g[key][-200:], d[key][-200:])
                diffs.append(f'{key}: git {shown[0]!r} den {shown[1]!r}')
        if g['state'] != d['state']:
            keys = sorted(k for k in g['state'] if g['state'].get(k) != d['state'].get(k))
            diffs.append(f'state differs in {keys}')
        if g['status'] != 0:
            diffs.append(f'Git exited {g["status"]}: the fixture does not make this row')
        bound = dict(cpu=round(best['git']['cpu'] * CPU_FACTOR + CPU_SLACK, 3),
                     rss_kib=int(best['git']['maxrss_kib'] * RSS_FACTOR) + RSS_SLACK_KIB)
        bounded = (not d['ended'] and best['den']['cpu'] <= bound['cpu'] and
                   best['den']['maxrss_kib'] <= bound['rss_kib'])
        ok = not diffs and bounded
        print(('PASS ' if ok else 'FAIL ') + row +
              f" den wall {best['den']['wall']:.3f} s cpu {best['den']['cpu']:.3f} s peak {best['den']['maxrss_kib']} KiB;"
              f" git wall {best['git']['wall']:.3f} s cpu {best['git']['cpu']:.3f} s peak {best['git']['maxrss_kib']} KiB;"
              f" peak {best['den']['maxrss_kib'] / max(best['git']['maxrss_kib'], 1):.1f}x"
              f" ({100 * best['den']['maxrss_kib'] / bound['rss_kib']:.1f}% of its bound)" +
              (f'; ended after {a.timeout} s' if d['ended'] else '') +
              ('' if bounded else f"; bounds cpu {bound['cpu']} s peak {bound['rss_kib']} KiB") +
              ('' if not diffs else '; DIFFERS: ' + '; '.join(diffs)), flush=True)
        results.append(dict(row=row, passed=ok, same=not diffs, bounded=bounded, best=best, bound=bound,
                            den_exit=d['status'], den_stderr=d['stderr'].decode(errors='replace')[-400:]))
    assert results, 'empty selection'
    (out / 'summary.json').write_text(json.dumps(dict(size=size, floor_kib=floor_kib, rows=results), indent=2) + '\n')
    failures = sum(not r['passed'] for r in results)
    print(f'large-blob {label}: {len(results)} rows, {failures} failures; floor {floor_kib} KiB; zero skips',
          flush=True)
    return int(failures > 0)


if __name__ == '__main__':
    raise SystemExit(main())
