#!/usr/bin/env python3
"""A transition's refusals, beside trunk's.

A transition (worktree.transition_held, as a merge's) scans the work tree, checks
and writes it, and builds the next index's cache tree last. The scan runs in a
region of its own, and a scan that fails there is run again outside it, where
its error can leave. Everything up to the cache tree runs in one region, and a
failure there, which may come after files were written, is copied out and raised
once the region is freed: never run again. These rows force a failure in each
place and require the refusal to be what trunk 4f06309 gave on the same input:
the same text, the same exit, and the same work tree and index afterwards. A
half-applied transition must leave what trunk's left.

The fixture is made with Git alone: 32 files in d0..d3/s0..s1, committed on
main, and a second commit, `target`, that changes d0/s0/f0.txt and adds
zz/new.txt. probes/transition-rerun-client moves the work tree toward main's own
tree (the scan and tree rows) or toward target's (the prepare row), as a merge's
transition does:

  transition-rerun-scan   (a) the index value with its last entry dropped, so
                          its cache tree names an entry it lacks, not held
                          validated: the scan refuses it; (b) a tracked file
                          replaced by a named pipe, which the scan cannot read:
                          the scan refuses it by name;
  transition-rerun-prepare  (a) d0/s0/f0.txt changed in the work tree, which
                          target changes too: the checks refuse it before any
                          write, with Git's "would be overwritten by merge"
                          message, built inside the region; (b) an untracked
                          file named zz where target puts zz/new.txt: the
                          checks pass, d0/s0/f0.txt is written, and the write of
                          zz/new.txt fails, after writes have started;
  transition-rerun-trees  the target names added/twice.txt twice: the
                          transition writes it, then the cache tree refuses the
                          doubled entry.

The trunk figures were read with trunk's own build of this probe on this
fixture (the probe calls only what trunk already has).
"""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess

# case: (exit, stdout, digest of the work tree and index afterwards), as trunk 4f06309 gave them.
# Read with --observe at the rows commit, whose den code is trunk's, on native and release alike. The pipe's kind, 4,
# is the runtime's fixed code for a fifo on every host.
TRUNK = {
    'scan-malformed': (1, 'refused=invalid_index\n', '06cfac5b97d538c9'),
    'scan-file': (1, 'refused=Unsupported(tracked worktree file kind 4 at d1/s0/f2.txt)\n', '93a05a24b3c053b6'),
    'prepare-dirty': (1, 'refused=Failure(Your local changes to the following files would be overwritten by merge:\n'
                      '\td0/s0/f0.txt\nPlease commit your changes or stash them before you merge.\nAborting)\n',
                      '867babdf5cb42dff'),
    'prepare-written': (1, 'refused=not_found\n', 'cdee04556f82bcc4'),
    'trees-twice': (1, 'refused=invalid_index\n', '6043f2b44d5f702c'),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tier', choices=('native', 'release'), default='native')
    parser.add_argument('--wolf', required=True, help="the pinned wolf (tools/lib-toolchain.sh's $WOLF)")
    parser.add_argument('--observe', action='store_true', help='print each case as read, for the trunk figures')
    a = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = root / 'target' / 'runs' / ('transition-rerun-' + a.tier)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    git = os.environ['DEN_GIT']

    def run(args, cwd, data=None, ok=True):
        p = subprocess.run([str(x) for x in args], cwd=cwd, input=data, capture_output=True, timeout=120)
        if ok:
            assert p.returncode == 0, (args, p.stdout[-300:], p.stderr[-300:])
        return p

    probe = root / 'target' / a.tier / 'transition-rerun-client'
    probe.parent.mkdir(parents=True, exist_ok=True)
    flags = ['--release'] if a.tier == 'release' else []
    run([a.wolf, 'build', *flags, '--deny-warnings', root / 'probes/transition-rerun-client/main.lu', '-o', probe], root)

    seed = out / 'seed'
    run([git, 'init', '-q', '-b', 'main', seed], out)
    for d in range(4):
        for s in range(2):
            for f in range(4):
                path = seed / f'd{d}' / f's{s}' / f'f{f}.txt'
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f'd{d}/s{s}/f{f}\n')
    run([git, 'add', '-A'], seed)
    run([git, '-c', 'user.name=Den Tester', '-c', 'user.email=den@example.invalid', '-c', 'commit.gpgsign=false',
         'commit', '-q', '-m', 'transition rerun fixture'], seed)
    tree = run([git, 'rev-parse', 'HEAD^{tree}'], seed).stdout.decode().strip()
    # target: d0/s0/f0.txt changed and zz/new.txt added, on a branch; the work tree goes back to main.
    run([git, 'switch', '-q', '-c', 'target'], seed)
    (seed / 'd0/s0/f0.txt').write_text('changed by target\n')
    (seed / 'zz').mkdir()
    (seed / 'zz/new.txt').write_text('added by target\n')
    run([git, 'add', '-A'], seed)
    run([git, '-c', 'user.name=Den Tester', '-c', 'user.email=den@example.invalid', '-c', 'commit.gpgsign=false',
         'commit', '-q', '-m', 'transition rerun target'], seed)
    target_tree = run([git, 'rev-parse', 'HEAD^{tree}'], seed).stdout.decode().strip()
    run([git, 'switch', '-q', 'main'], seed)
    assert not (seed / 'zz').exists()

    def state(work):
        """The work tree's files (kind and content) and the index's entries, as one digest."""
        files = []
        for p in sorted(work.rglob('*')):
            rel = p.relative_to(work).as_posix()
            if rel == '.git' or rel.startswith('.git/'):
                continue
            if p.is_symlink():
                files.append((rel, 'link', os.readlink(p)))
            elif p.is_fifo():
                files.append((rel, 'fifo', ''))
            elif p.is_file():
                files.append((rel, 'file', hashlib.sha256(p.read_bytes()).hexdigest()))
        index = run([git, 'ls-files', '-s'], work).stdout.decode()
        return hashlib.sha256(repr((files, index)).encode()).hexdigest()[:16]

    def case(name):
        work = out / name
        shutil.copytree(seed, work, symlinks=True)
        args = [probe, name, work, tree]
        if name.startswith('prepare-'):
            args = [probe, 'plain', work, target_tree]
        if name == 'prepare-dirty':
            (work / 'd0/s0/f0.txt').write_text('changed in the work tree\n')
        if name == 'prepare-written':
            (work / 'zz').write_text('an untracked file where target puts a directory\n')
        if name == 'scan-file':
            target = work / 'd1/s0/f2.txt'
            target.unlink()
            os.mkfifo(target)
        if name == 'trees-twice':
            blob = run([git, 'hash-object', '-w', '--stdin'], work, b'twice\n').stdout.decode().strip()
            args.append(blob)
        p = run(args, work, ok=False)
        assert p.stderr == b'', (name, p.stderr[-300:])
        if name == 'prepare-written':
            # The fixture's point: the refusal comes after the transition began writing.
            assert (work / 'd0/s0/f0.txt').read_text() == 'changed by target\n', 'prepare-written: no write before it'
        return (p.returncode, p.stdout.decode('utf-8', 'replace'), state(work))

    got = {name: case(name) for name in TRUNK}
    if a.observe:
        for name, value in got.items():
            print(f'OBSERVE {name} {value!r}', flush=True)
    rows = [
        ('scan', got['scan-malformed'] == TRUNK['scan-malformed'] and got['scan-file'] == TRUNK['scan-file'],
         'a malformed value: %r (trunk %r); an unreadable file: %r (trunk %r)' % (
             got['scan-malformed'], TRUNK['scan-malformed'], got['scan-file'], TRUNK['scan-file'])),
        ('prepare', got['prepare-dirty'] == TRUNK['prepare-dirty'] and
         got['prepare-written'] == TRUNK['prepare-written'],
         'a dirty file the target changes: %r (trunk %r); a write that fails after writes began: %r (trunk %r)' % (
             got['prepare-dirty'], TRUNK['prepare-dirty'], got['prepare-written'], TRUNK['prepare-written'])),
        ('trees', got['trees-twice'] == TRUNK['trees-twice'],
         'a doubled target entry: %r (trunk %r)' % (got['trees-twice'], TRUNK['trees-twice'])),
    ]
    failed = 0
    for name, ok, words in rows:
        print(('PASS' if ok else 'FAIL'), 'transition-rerun-%s-%s' % (name, a.tier), words, flush=True)
        failed += not ok
    print('transition-rerun %s: %d/%d rows pass' % (a.tier, len(rows) - failed, len(rows)), flush=True)
    raise SystemExit(1 if failed else 0)


if __name__ == '__main__':
    main()
