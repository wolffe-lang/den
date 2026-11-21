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
  same-second        a's bytes replaced in place by others of its size and
                     its mtime put back to the nanosecond, all inside the
                     second of the entry's own ctime (same inode): only the
                     ctime's nanoseconds moved, and Git compares whole
                     seconds, so it trusts the stat data (the case is
                     retaken until that precondition holds);
  mode-only          a made executable, nothing else;
  link-trusted       l's index entry names another stored blob of its
                     length while every stat word still matches the link,
                     and the index file is newer: Git trusts a symbolic
                     link's stat data as it does a file's;
  link-retarget      l pointed at a target of the same length in a later
                     second than the refresh, as a new link renamed over it
                     (a new inode), its mtime put back;
  file-to-dir        a replaced by a directory holding one file;
  dir-back           that directory replaced by a file with a's bytes again;
  touch-all          every file's mtime moved ten seconds on, content kept;
  touch-twice        the same, after the tool's own `diff` has already run
                     once (its refresh), so the second run reads stat only.

The crafted index (trusted, racy-*, link-trusted) is inconsistent with
HEAD's tree, so
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

Around each tool's run the test also observes what it did to .git: the .git
directory, dated to a fixed old time just before the run, has its mtime moved
by any file created or removed in it (a lock taken and dropped leaves no bytes
behind, but moves it), and the index file's inode and mtime show whether it
was written again. For the worktree diffs (diff --quiet, diff --exit-code,
diff) in the clean and touch-all cases, den's observation must equal Git's,
and on the clean tree both must leave the index's bytes as they were. The
pinned Git leaves a clean tree's .git untouched, and takes the lock and writes
the index again when every file is stat-dirty with its content unchanged
(measured). Every other row records the observation and asserts nothing on it:
status --porcelain takes the lock on a clean tree in Git and not in den, and
writes a stat-dirty index again in Git and not in den (measured; a separate
status difference, present before this test).
"""
import argparse, hashlib, json, os, pathlib, runpy, shutil, subprocess, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
O = runpy.run_path(str(ROOT / 'tools/oracle.py'))
COMMANDS = [['diff', '--quiet'], ['diff', '--exit-code'], ['diff'], ['diff', '--cached', '--quiet'],
            ['status', '--porcelain']]
CASES = ['clean', 'same-size', 'trusted', 'racy-equal', 'racy-same-second', 'racy-older', 'rewritten',
         'same-second', 'mode-only', 'link-trusted', 'link-retarget', 'file-to-dir', 'dir-back', 'touch-all',
         'touch-twice']
CRAFTED = ('trusted', 'racy-equal', 'racy-same-second', 'racy-older', 'link-trusted')
# Where den must touch .git exactly as Git does (the docstring's observation).
TOUCH_CASES = ('clean', 'touch-all')
OLD_DIR_TIME = 1_600_000_000_000_000_000


def observed(repo, run):
    """run()'s result, and what it did to .git: whether any file was created
    or removed there (the directory's mtime moved from a fixed old time), and
    whether the index was written again (its inode or mtime moved), with the
    index's bytes afterwards."""
    os.utime(repo / '.git', ns=(OLD_DIR_TIME, OLD_DIR_TIME))
    before = os.stat(repo / '.git/index')
    result = run()
    after = os.stat(repo / '.git/index')
    touched = dict(dir_moved=os.stat(repo / '.git').st_mtime_ns != OLD_DIR_TIME,
                   index_written=(before.st_ino, before.st_mtime_ns) != (after.st_ino, after.st_mtime_ns))
    return result, touched, (repo / '.git/index').read_bytes()


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
    # Another stored blob of a's size, and one of l's (a link's blob is its
    # target), for the crafted entries to name.
    other = bytes.fromhex(g('hash-object', '-w', '--stdin', data=b'AAAA\n').decode().strip())
    other_link = bytes.fromhex(g('hash-object', '-w', '--stdin', data=b'b').decode().strip())

    def date_index(repo, ns):
        os.utime(repo / '.git/index', ns=(ns, ns))

    def next_second():
        now = time.time_ns()
        time.sleep((1_000_000_000 - now % 1_000_000_000) / 1e9 + 0.01)

    def entry_words(repo, path):
        data = (repo / '.git/index').read_bytes()
        pos = 12
        for _ in range(int.from_bytes(data[8:12], 'big')):
            flags = int.from_bytes(data[pos + 60:pos + 62], 'big')
            if data[pos + 62:pos + 62 + (flags & 0xfff)] == path:
                return [int.from_bytes(data[pos + 4 * i:pos + 4 * i + 4], 'big') for i in range(10)]
            pos += (62 + (flags & 0xfff) + 8) // 8 * 8
        raise AssertionError(path)

    def prepare(case):
        # same-second needs the copy, the refresh and the change inside one
        # second: start just after a boundary, and take the case again (at
        # most five times) until the entry's ctime second and inode still
        # match the changed file.
        for _ in range(5):
            if case == 'same-second':
                next_second()
            prepared = prepare_once(case)
            if case != 'same-second':
                return prepared
            repo = prepared[0]
            entry, st = entry_words(repo, b'a'), os.lstat(repo / 'a')
            if entry[0] == (st.st_ctime_ns // 10**9) & 0xffffffff and entry[5] == st.st_ino & 0xffffffff:
                return prepared
        raise AssertionError('same-second: no take kept the change inside the entry\'s ctime second')

    def prepare_once(case):
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
        elif case == 'link-trusted':
            (repo / '.git/index').write_bytes(swap_entry((repo / '.git/index').read_bytes(), b'l', other_link))
            date_index(repo, later)
        elif case == 'same-second':
            (repo / 'a').write_bytes(b'AAAA\n')
            os.utime(repo / 'a', ns=(st.st_atime_ns, st.st_mtime_ns))
        elif case == 'rewritten':
            (repo / 'a').write_bytes(b'AAAA\n')
            os.utime(repo / 'a', ns=(st.st_atime_ns, st.st_mtime_ns))
            subprocess.run([git, 'update-index', '--force-write-index'], cwd=repo, check=True, capture_output=True)
            date_index(repo, inside)
        elif case == 'mode-only':
            os.chmod(repo / 'a', 0o755)
        elif case == 'link-retarget':
            # A later second and a new inode: neither may match the entry.
            lst = os.lstat(repo / 'l')
            next_second()
            os.symlink('b', repo / 'l.new')
            os.rename(repo / 'l.new', repo / 'l')
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
                    if not (case in CRAFTED and '--cached' in c)
                    and not (case == 'file-to-dir' and c[0] == 'status')]
        for command in commands:
            repo, saved, mtime = prepare(case)
            if case == 'touch-twice':
                subprocess.run([git, 'diff'], cwd=repo, capture_output=True)
            before = (repo / '.git/index').read_bytes()
            expected, git_touched, git_index = observed(
                repo, lambda: O['capture']([git, *command], repo, index_proof=True))
            put_back(repo, saved, mtime)
            if case == 'touch-twice':
                subprocess.run([den, 'diff'], cwd=repo, capture_output=True)
            actual, den_touched, den_index = observed(
                repo, lambda: O['capture']([den, *command], repo, index_proof=True))
            ok = O['equivalent'](expected, actual, 'index-stat-proven')
            asserted = case in TOUCH_CASES and command[0] == 'diff' and '--cached' not in command
            if asserted:
                ok = ok and den_touched == git_touched
                if case == 'clean':
                    ok = ok and git_index == before and den_index == before and not git_touched['dir_moved']
            name = f'racy-{case}-{"-".join(c.strip("-") for c in command)}'
            touch = (f" touched git {int(git_touched['dir_moved'])}{int(git_touched['index_written'])}"
                     f" den {int(den_touched['dir_moved'])}{int(den_touched['index_written'])}"
                     + (' (asserted)' if asserted else ''))
            print(('PASS ' if ok else 'FAIL ') + name + f" git status {expected['status']} den status {actual['status']}" + touch
                  + ('' if ok else f" git stdout {bytes.fromhex(expected['stdout'])[:120]!r}"
                                    f" den stdout {bytes.fromhex(actual['stdout'])[:120]!r}"
                                    f" den stderr {bytes.fromhex(actual['stderr'])[:160]!r}"), flush=True)
            rows.append(dict(name=name, case=case, command=command, ok=ok, git=expected, den=actual,
                             git_touched=git_touched, den_touched=den_touched, touch_asserted=asserted))
    (ROOT / f'target/diff-racy-{a.tier}.json').write_text(json.dumps({'rows': rows}, indent=2) + '\n')
    failures = [r['name'] for r in rows if not r['ok']]
    print(f'diff-racy: {len(rows)} rows, {len(failures)} failures; zero skips', flush=True)
    return int(bool(failures))


if __name__ == '__main__':
    raise SystemExit(main())
