#!/usr/bin/env python3
"""A transition's refusals inside its scratch regions, beside trunk's.

A transition (worktree.transition_held, as a merge's) scans the work tree first
and builds the next index's cache tree last. Each of those runs in a region of
its own, and a failure inside is run again outside the region, where its error
can leave. These rows force a failure in each place and require the refusal to
be what trunk 4f06309 gave on the same input: the same text, the same exit, and
the same work tree and index afterwards.

The fixture is made with Git alone: 32 files in d0..d3/s0..s1, committed.
probes/transition-rerun-client moves its work tree toward the commit's own tree,
as a merge's transition does:

  transition-rerun-scan   (a) the index value with its last entry dropped, so
                          its cache tree names an entry it lacks, not held
                          validated: the scan refuses it; (b) a tracked file
                          replaced by a named pipe, which the scan cannot read:
                          the scan refuses it by name;
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
        if name == 'scan-file':
            target = work / 'd1/s0/f2.txt'
            target.unlink()
            os.mkfifo(target)
        if name == 'trees-twice':
            blob = run([git, 'hash-object', '-w', '--stdin'], work, b'twice\n').stdout.decode().strip()
            args.append(blob)
        p = run(args, work, ok=False)
        assert p.stderr == b'', (name, p.stderr[-300:])
        return (p.returncode, p.stdout.decode('utf-8', 'replace'), state(work))

    got = {name: case(name) for name in TRUNK}
    if a.observe:
        for name, value in got.items():
            print(f'OBSERVE {name} {value!r}', flush=True)
    rows = [
        ('scan', got['scan-malformed'] == TRUNK['scan-malformed'] and got['scan-file'] == TRUNK['scan-file'],
         'a malformed value: %r (trunk %r); an unreadable file: %r (trunk %r)' % (
             got['scan-malformed'], TRUNK['scan-malformed'], got['scan-file'], TRUNK['scan-file'])),
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
