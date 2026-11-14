#!/usr/bin/env python3
"""den#101: the stat shortcut a diff against the index takes, held to the
pinned Git wherever trusting stat data and reading the file could answer
differently.

A clean checkout of a, b and the symbolic link l (to a). Each case is
prepared once: a fresh copy whose index Git has just refreshed, its index file
then dated five seconds after every file, and the case's change. Git runs
first; then the index file's bytes and dates are put back and den runs on the
same files (the same inodes and stat data), so the two answer one state:

  clean              nothing changed;
  same-size          a's bytes replaced by others of its size in a later
                     second than the refresh, its mtime put back: its ctime
                     moved (Git compares whole seconds);
  trusted            a's index entry names another stored blob of a's size
                     while all ten stat words still match the file, and the
                     index file is newer than the file: Git trusts the stat
                     data;
  racy-equal         the same entry, the index file's mtime equal to a's to
                     the nanosecond: racily clean;
  racy-same-second   the same entry, the index file's mtime later than a's
                     but inside the same second;
  racy-older         the same entry, the index file older than a;
  rewritten          a changed to bytes of its size with its mtime put back,
                     then the index written again (Git's
                     --force-write-index) and dated inside a's second;
  mode-only          a made executable, nothing else;
  link-retarget      l pointed at a target of the same length, its mtime put
                     back;
  file-to-dir        a replaced by a directory holding one file;
  dir-back           that directory replaced by a file with a's bytes again;
  touch-all          every file's mtime moved ten seconds on, content kept;
  touch-twice        the same, after the tool's own `diff` has already run
                     once (its refresh), so the second run reads stat only.

The crafted index (trusted, racy-*) is inconsistent with HEAD's tree, so
`diff --cached` is not asked of it: the pinned Git's answer there depends on
the worktree's stat data (measured), which no cached comparison of den's
reads. file-to-dir does not ask `status`: Git lists no untracked path inside a
directory that replaced a tracked file, and den lists the file (a separate
status difference, present before this test).

The crafted index drops its extensions (a cache tree would name the old blob)
and carries a recomputed checksum. Commands: diff --quiet, diff --exit-code,
diff (patch), diff --cached --quiet, status --porcelain. Each must equal Git's
exit status, stdout, stderr and repository bytes; the index's inode and time
words compare only where proved against each tool's own files.
"""
import argparse, hashlib, json, os, pathlib, runpy, shutil, subprocess, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
O = runpy.run_path(str(ROOT / 'tools/oracle.py'))
COMMANDS = [['diff', '--quiet'], ['diff', '--exit-code'], ['diff'], ['diff', '--cached', '--quiet'],
            ['status', '--porcelain']]
CASES = ['clean', 'same-size', 'trusted', 'racy-equal', 'racy-same-second', 'racy-older', 'rewritten',
         'mode-only', 'link-retarget', 'file-to-dir', 'dir-back', 'touch-all', 'touch-twice']


def swap_entry(index, path, oid):
    """index bytes with path's object id replaced and no extensions."""
    assert index[:4] == b'DIRC' and int.from_bytes(index[4:8], 'big') == 2
    count = int.from_bytes(index[8:12], 'big')
    pos, out = 12, bytearray(index[:12])
    for _ in range(count):
        flags = int.from_bytes(index[pos + 60:pos + 62], 'big')
        name_len = flags & 0xfff
        name = index[pos + 62:pos + 62 + name_len]
        size = (62 + name_len + 8) // 8 * 8
        entry = bytearray(index[pos:pos + size])
        if name == path:
            entry[40:60] = oid
        out += entry
        pos += size
    out += hashlib.sha1(bytes(out)).digest()
    return bytes(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tier', choices=('native', 'release'), default='native')
    ap.add_argument('--den', help='another den binary to hold to Git (default: the tier\'s build)')
    a = ap.parse_args()
    git = os.environ['DEN_GIT']
    den = a.den or str(ROOT / f'target/{a.tier}/den')
    base = ROOT / f'target/diff-racy-{a.tier}'
    if base.exists():
        shutil.rmtree(base)
    source = base / 'source'
    source.mkdir(parents=True)

    def g(*args, cwd=source, data=None):
        return subprocess.run([git, *args], cwd=cwd, input=data, check=True, capture_output=True).stdout

    (source / 'a').write_bytes(b'aaaa\n')
    (source / 'b').write_bytes(b'bbbb\n')
    os.symlink('a', source / 'l')
    g('init', '-q')
    g('add', '-A')
    g('commit', '-qm', 'base')
    # Another stored blob of a's size, for the crafted entry to name.
    other = bytes.fromhex(g('hash-object', '-w', '--stdin', data=b'AAAA\n').decode().strip())

    def date_index(repo, ns):
        os.utime(repo / '.git/index', ns=(ns, ns))

    def next_second():
        now = time.time_ns()
        time.sleep((1_000_000_000 - now % 1_000_000_000) / 1e9 + 0.01)

    def prepare(case):
        repo = base / 'repo'
        if repo.exists():
            shutil.rmtree(repo)
        shutil.copytree(source, repo, symlinks=True)
        # Git's refresh after the copy, then an index newer than every file.
        date_index(repo, 0)
        subprocess.run([git, 'update-index', '-q', '--refresh'], cwd=repo, check=True, capture_output=True)
        st = os.lstat(repo / 'a')
        later = st.st_mtime_ns + 5_000_000_000
        date_index(repo, later)
        second = st.st_mtime_ns - st.st_mtime_ns % 1_000_000_000
        inside = second + 999_000_000 if st.st_mtime_ns < second + 999_000_000 else st.st_mtime_ns
        if case == 'same-size':
            next_second()
            (repo / 'a').write_bytes(b'AAAA\n')
            os.utime(repo / 'a', ns=(st.st_atime_ns, st.st_mtime_ns))
        elif case in ('trusted', 'racy-equal', 'racy-same-second', 'racy-older'):
            (repo / '.git/index').write_bytes(swap_entry((repo / '.git/index').read_bytes(), b'a', other))
            date_index(repo, {'trusted': later, 'racy-equal': st.st_mtime_ns, 'racy-same-second': inside,
                              'racy-older': st.st_mtime_ns - 1_000_000_000}[case])
        elif case == 'rewritten':
            (repo / 'a').write_bytes(b'AAAA\n')
            os.utime(repo / 'a', ns=(st.st_atime_ns, st.st_mtime_ns))
            subprocess.run([git, 'update-index', '--force-write-index'], cwd=repo, check=True, capture_output=True)
            date_index(repo, inside)
        elif case == 'mode-only':
            os.chmod(repo / 'a', 0o755)
        elif case == 'link-retarget':
            lst = os.lstat(repo / 'l')
            os.unlink(repo / 'l')
            os.symlink('b', repo / 'l')
            os.utime(repo / 'l', ns=(lst.st_atime_ns, lst.st_mtime_ns), follow_symlinks=False)
        elif case in ('file-to-dir', 'dir-back'):
            os.unlink(repo / 'a')
            (repo / 'a').mkdir()
            (repo / 'a' / 'inner').write_bytes(b'inner\n')
            if case == 'dir-back':
                shutil.rmtree(repo / 'a')
                (repo / 'a').write_bytes(b'aaaa\n')
        elif case in ('touch-all', 'touch-twice'):
            moved = st.st_mtime_ns + 10_000_000_000
            for name in ('a', 'b', 'l'):
                os.utime(repo / name, ns=(moved, moved), follow_symlinks=False)
        index = repo / '.git/index'
        return repo, index.read_bytes(), os.stat(index).st_mtime_ns

    def put_back(repo, saved, mtime):
        (repo / '.git/index.lock').unlink(missing_ok=True)
        (repo / '.git/index').write_bytes(saved)
        date_index(repo, mtime)

    rows = []
    for case in CASES:
        commands = [c for c in COMMANDS
                    if not (case in ('trusted', 'racy-equal', 'racy-same-second', 'racy-older') and '--cached' in c)
                    and not (case == 'file-to-dir' and c[0] == 'status')]
        for command in commands:
            repo, saved, mtime = prepare(case)
            if case == 'touch-twice':
                subprocess.run([git, 'diff'], cwd=repo, capture_output=True)
            expected = O['capture']([git, *command], repo, index_proof=True)
            put_back(repo, saved, mtime)
            if case == 'touch-twice':
                subprocess.run([den, 'diff'], cwd=repo, capture_output=True)
            actual = O['capture']([den, *command], repo, index_proof=True)
            ok = O['equivalent'](expected, actual, 'index-stat-proven')
            name = f'racy-{case}-{"-".join(c.strip("-") for c in command)}'
            print(('PASS ' if ok else 'FAIL ') + name + f" git status {expected['status']} den status {actual['status']}"
                  + ('' if ok else f" git stdout {bytes.fromhex(expected['stdout'])[:120]!r}"
                                    f" den stdout {bytes.fromhex(actual['stdout'])[:120]!r}"
                                    f" den stderr {bytes.fromhex(actual['stderr'])[:160]!r}"), flush=True)
            rows.append(dict(name=name, case=case, command=command, ok=ok, git=expected, den=actual))
    (ROOT / f'target/diff-racy-{a.tier}.json').write_text(json.dumps({'rows': rows}, indent=2) + '\n')
    failures = [r['name'] for r in rows if not r['ok']]
    print(f'diff-racy: {len(rows)} rows, {len(failures)} failures; zero skips', flush=True)
    return int(bool(failures))


if __name__ == '__main__':
    raise SystemExit(main())
