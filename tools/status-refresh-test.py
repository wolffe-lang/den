#!/usr/bin/env python3
"""status's index refresh, held to the pinned Git: status writes a refreshed
index only when an entry was stat-dirty with its content unchanged, takes no
lock on a clean tree, writes nothing when optional locks are off
(GIT_OPTIONAL_LOCKS=0, or --no-optional-locks before the command), and skips
the write silently when another process holds index.lock.

A checkout of a, b, the symbolic link l (to a) and sub/c, committed. Each row
starts from a fresh copy whose index Git has just refreshed, the index file
dated five seconds after every file, then the case's change:

  clean       nothing changed;
  touch-all   every file's mtime moved twenty seconds back, content kept:
              stat-dirty, unchanged;
  modified    a's bytes replaced by others of another size: changed, and
              nothing stat-only to refresh;
  mixed       touch-all, and a modified as well.

and the mode:

  on          GIT_OPTIONAL_LOCKS unset;
  env-off     GIT_OPTIONAL_LOCKS=0;
  flag-off    --no-optional-locks before the command, the variable unset;
  locked      the variable unset, with .git/index.lock already held (its
              bytes are this test's own and must survive the run).

Git runs `status --porcelain` first. The index's bytes and date, and any held
lock, are then put back, and den runs on the same files. Each must equal Git's
exit status, stdout, stderr and repository bytes. Around each run the test
observes what the tool did to .git: whether a file was created or removed
there (the directory's mtime, dated to a fixed old time just before the run,
moved) and whether the index was written (its inode or mtime moved).

Asserted for den, the rule:
- it writes the index exactly in touch-all and mixed with optional locks on,
  and then its index bytes equal Git's;
- in every other row the index is left unwritten, with its bytes unchanged;
- it takes no lock where it writes nothing: .git's directory is untouched.

Asserted of Git, as measured: it writes in exactly the same rows. On a clean
tree with optional locks on, Git takes the lock and drops it (the directory
moves); den does not. That is the one difference, and it is recorded on each
row, not asserted.
"""
import argparse, json, os, pathlib, runpy, shutil, subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
O = runpy.run_path(str(ROOT / 'tools/oracle.py'))
CASES = ['clean', 'touch-all', 'modified', 'mixed']
MODES = ['on', 'env-off', 'flag-off', 'locked']
WRITES = ('touch-all', 'mixed')
OLD_DIR_TIME = 1_600_000_000_000_000_000
LOCK_BYTES = b'held by status-refresh-test\n'


def observed(repo, run):
    """run()'s result, whether a file was created or removed in .git, whether
    the index was written again, and the index's bytes afterwards."""
    os.utime(repo / '.git', ns=(OLD_DIR_TIME, OLD_DIR_TIME))
    before = os.stat(repo / '.git/index')
    result = run()
    after = os.stat(repo / '.git/index')
    touched = dict(dir_moved=os.stat(repo / '.git').st_mtime_ns != OLD_DIR_TIME,
                   index_written=(before.st_ino, before.st_mtime_ns) != (after.st_ino, after.st_mtime_ns))
    return result, touched, (repo / '.git/index').read_bytes()


def in_mode(mode, run):
    """run() with GIT_OPTIONAL_LOCKS as mode sets it (the oracle's capture
    inherits this process's environment)."""
    saved = os.environ.get('GIT_OPTIONAL_LOCKS')
    os.environ.pop('GIT_OPTIONAL_LOCKS', None)
    if mode == 'env-off':
        os.environ['GIT_OPTIONAL_LOCKS'] = '0'
    try:
        return run()
    finally:
        os.environ.pop('GIT_OPTIONAL_LOCKS', None)
        if saved is not None:
            os.environ['GIT_OPTIONAL_LOCKS'] = saved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tier', choices=('native', 'release'), default='native')
    ap.add_argument('--den', help='another den binary to hold to Git (default: the tier\'s build)')
    a = ap.parse_args()
    git = os.environ['DEN_GIT']
    den = a.den or str(ROOT / f'target/{a.tier}/den')
    base = ROOT / f'target/status-refresh-{a.tier}'
    if base.exists():
        shutil.rmtree(base)
    source = base / 'source'
    (source / 'sub').mkdir(parents=True)

    def g(*args, cwd=source):
        return subprocess.run([git, *args], cwd=cwd, check=True, capture_output=True).stdout

    (source / 'a').write_bytes(b'aaaa\n')
    (source / 'b').write_bytes(b'bbbb\n')
    (source / 'sub' / 'c').write_bytes(b'cccc\n')
    os.symlink('a', source / 'l')
    g('init', '-q')
    g('add', '-A')
    g('commit', '-qm', 'base')

    def prepare(case):
        repo = base / 'repo'
        if repo.exists():
            shutil.rmtree(repo)
        shutil.copytree(source, repo, symlinks=True)
        subprocess.run([git, 'update-index', '-q', '--refresh'], cwd=repo, check=True, capture_output=True)
        newest = max(os.lstat(repo / n).st_mtime_ns for n in ('a', 'b', 'l', 'sub/c'))
        os.utime(repo / '.git/index', ns=(newest + 5_000_000_000, newest + 5_000_000_000))
        if case in ('touch-all', 'mixed'):
            for name in ('a', 'b', 'l', 'sub/c'):
                st = os.lstat(repo / name)
                back = st.st_mtime_ns - 20_000_000_000
                os.utime(repo / name, ns=(back, back), follow_symlinks=False)
        if case in ('modified', 'mixed'):
            st = os.lstat(repo / 'a')
            (repo / 'a').write_bytes(b'a different size\n')
            os.utime(repo / 'a', ns=(st.st_atime_ns, st.st_mtime_ns))
        index = repo / '.git/index'
        return repo, index.read_bytes(), os.stat(index).st_mtime_ns

    def put_back(repo, saved, mtime, mode):
        (repo / '.git/index.lock').unlink(missing_ok=True)
        (repo / '.git/index').write_bytes(saved)
        os.utime(repo / '.git/index', ns=(mtime, mtime))
        if mode == 'locked':
            (repo / '.git/index.lock').write_bytes(LOCK_BYTES)

    rows = []
    for case in CASES:
        for mode in MODES:
            repo, saved, mtime = prepare(case)
            put_back(repo, saved, mtime, mode)
            before = (repo / '.git/index').read_bytes()

            def argv(tool):
                return [tool, *(['--no-optional-locks'] if mode == 'flag-off' else []), 'status', '--porcelain']

            expected, git_touched, git_index = in_mode(mode, lambda: observed(
                repo, lambda: O['capture'](argv(git), repo, index_proof=True)))
            git_lock = (repo / '.git/index.lock').read_bytes() if (repo / '.git/index.lock').exists() else None
            put_back(repo, saved, mtime, mode)
            actual, den_touched, den_index = in_mode(mode, lambda: observed(
                repo, lambda: O['capture'](argv(den), repo, index_proof=True)))
            den_lock = (repo / '.git/index.lock').read_bytes() if (repo / '.git/index.lock').exists() else None
            writes = case in WRITES and mode == 'on'
            same = O['equivalent'](expected, actual, 'index-stat-proven')
            git_rule = git_touched['index_written'] == writes and (writes or git_index == before)
            den_rule = den_touched['index_written'] == writes
            if writes:
                den_rule = den_rule and den_index == git_index
            else:
                den_rule = den_rule and den_index == before and not den_touched['dir_moved']
            if mode == 'locked':
                git_rule = git_rule and git_lock == LOCK_BYTES
                den_rule = den_rule and den_lock == LOCK_BYTES
            ok = same and git_rule and den_rule
            name = f'status-refresh-{case}-{mode}'
            touch = (f" touched git {int(git_touched['dir_moved'])}{int(git_touched['index_written'])}"
                     f" den {int(den_touched['dir_moved'])}{int(den_touched['index_written'])}"
                     f" writes {int(writes)} same {int(same)} git_rule {int(git_rule)} den_rule {int(den_rule)}")
            print(('PASS ' if ok else 'FAIL ') + name + f" git status {expected['status']} den status {actual['status']}"
                  + touch + ('' if ok else f" den stderr {bytes.fromhex(actual['stderr'])[:160]!r}"), flush=True)
            rows.append(dict(name=name, case=case, mode=mode, ok=ok, same=same, writes=writes, git=expected,
                             den=actual, git_touched=git_touched, den_touched=den_touched,
                             index_equal=den_index == git_index))
    (ROOT / f'target/status-refresh-{a.tier}.json').write_text(json.dumps({'rows': rows}, indent=2) + '\n')
    failures = [r['name'] for r in rows if not r['ok']]
    print(f'status-refresh: {len(rows)} rows, {len(failures)} failures; zero skips', flush=True)
    return int(bool(failures))


if __name__ == '__main__':
    raise SystemExit(main())
