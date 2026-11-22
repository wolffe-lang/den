#!/usr/bin/env python3
"""Plain `status`'s index lookups, counted: how many path compares the walk
and the rows take to find each worktree path in the index.

The fixture is made with Git alone (it only writes the commit and the index;
the counts depend on nothing but the index's paths and the worktree's): 576
tracked files, 32 in the root and 32 in each of 16 directories, one of which
holds a subdirectory of 32 more, and 24 untracked files spread over the root
and three directories. probes/status-phases scans it (the status scan a
command runs, untracked files included) and prints the scan's counts:
walk_lookups, one for each path the walk visits, and row_lookups, one for each
file the rows ask whether the index tracks; merge_steps, one for each path of
the rows' merge of HEAD's entries with the index's, and merge_compares, its
path compares and change checks; sorted_files, the files the walk sorts into
path order, and sort_compares, the path compares that took.

The rows: the number of lookups is exact (one a visited file), and each
side's compares a lookup are at most its bound: 8 for the walk, 5 for the
rows. A fresh binary search over the whole index takes 10.2 compares a lookup
here on each side (about nine halvings and the equality check), each over the
full path, and fails both. The walk passes by searching only the visited
directory's own entries (five halvings among 32 and the equality check, and
two searches a directory to find its range: 6.8 a lookup); the rows, by
starting where the last file's lookup landed (3.0).

The merge: one step a tracked path (576), and at most 3 compares a step. HEAD's
tree here is the index's own (its cache tree names HEAD's tree), and a tree
merged with itself compared each path and each id with its own copy, looked
for a second stage of every path and found each file with three compares:
7.0 compares a step, which fails.

The sort: every file sorted (600), and at most 1 path compare a file. A merge
sort of the paths takes 6.4 a file here (3,844 in all), each over the path,
and fails.

The scan's files (the probe's `paths` lines) are exactly the fixture's files,
in byte order of their paths.

The counts are exact on every host and tier: they depend neither on the order
a directory is listed in nor on time.
"""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess

WALK_BOUND = 8.0
ROW_BOUND = 5.0
MERGE_BOUND = 3.0
SORT_BOUND = 1.0
TRACKED = 576
UNTRACKED = 24


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tier', choices=('native', 'release'), default='native')
    parser.add_argument('--wolf', required=True, help='the pinned wolf (tools/lib-toolchain.sh\'s $WOLF)')
    a = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = root / 'target' / 'runs' / ('status-lookups-' + a.tier)
    if out.exists():
        shutil.rmtree(out)
    work = out / 'case'
    work.mkdir(parents=True)
    git = os.environ['DEN_GIT']
    wolf = a.wolf

    def run(args, cwd):
        p = subprocess.run([str(x) for x in args], cwd=cwd, capture_output=True)
        assert p.returncode == 0, (args, p.stdout[-300:], p.stderr[-300:])
        return p.stdout

    tracked = ['f%02d.txt' % i for i in range(32)]
    for d in range(16):
        tracked += ['d%02d/f%02d.txt' % (d, i) for i in range(32)]
    tracked += ['d07/sub/f%02d.txt' % i for i in range(32)]
    untracked = ['new%02d.txt' % i for i in range(6)]
    for d in ['d00', 'd07/sub', 'd15']:
        untracked += ['%s/new%02d.txt' % (d, i) for i in range(6)]
    assert len(tracked) == TRACKED and len(untracked) == UNTRACKED
    run([git, 'init', '-q', '-b', 'main', '.'], work)
    for name in tracked:
        (work / name).parent.mkdir(parents=True, exist_ok=True)
        (work / name).write_text(name + '\n')
    run([git, 'add', '-A'], work)
    run([git, '-c', 'commit.gpgsign=false', 'commit', '-q', '-m', 'lookups'], work)
    for name in untracked:
        (work / name).write_text(name + '\n')

    probe = root / 'target' / a.tier / 'status-phases'
    flags = ['--release'] if a.tier == 'release' else []
    run([wolf, 'build', *flags, '--deny-warnings', root / 'probes/status-phases/main.lu', '-o', probe], root)
    text = run([probe, work, 'paths'], work).decode()
    found = re.search(r'^walk_lookups=(\d+) walk_compares=(\d+) row_lookups=(\d+) row_compares=(\d+)$',
                      text, re.M)
    assert found, text
    walk_calls, walk_compares, row_calls, row_compares = (int(x) for x in found.groups())
    merge = re.search(r'^merge_steps=(\d+) merge_compares=(\d+)$', text, re.M)
    assert merge, text
    merge_steps, merge_compares = (int(x) for x in merge.groups())
    sort = re.search(r'^sorted_files=(\d+) sort_compares=(\d+)$', text, re.M)
    assert sort, text
    sorted_files, sort_compares = (int(x) for x in sort.groups())
    listed = re.findall(r'^file=(.*)$', text, re.M)
    files = TRACKED + UNTRACKED
    rows = [
        ('walk-lookups-one-a-file', walk_calls == files, 'walk_lookups=%d (expected %d)' % (walk_calls, files)),
        ('row-lookups-one-a-file', row_calls == files, 'row_lookups=%d (expected %d)' % (row_calls, files)),
        ('walk-compares-a-lookup', walk_calls > 0 and walk_compares <= WALK_BOUND * walk_calls,
         'walk_compares=%d, %.3f a lookup (bound %.1f)' % (walk_compares, walk_compares / max(1, walk_calls), WALK_BOUND)),
        ('row-compares-a-lookup', row_calls > 0 and row_compares <= ROW_BOUND * row_calls,
         'row_compares=%d, %.3f a lookup (bound %.1f)' % (row_compares, row_compares / max(1, row_calls), ROW_BOUND)),
        ('merge-steps-one-a-path', merge_steps == TRACKED, 'merge_steps=%d (expected %d)' % (merge_steps, TRACKED)),
        ('merge-compares-a-step', merge_steps > 0 and merge_compares <= MERGE_BOUND * merge_steps,
         'merge_compares=%d, %.3f a step (bound %.1f)' % (merge_compares, merge_compares / max(1, merge_steps), MERGE_BOUND)),
        ('files-in-path-order', listed == sorted(tracked + untracked, key=lambda x: x.encode()),
         'files=%d, in byte order of their paths: %s' % (len(listed), listed == sorted(listed, key=lambda x: x.encode()))),
        ('sort-files-one-a-file', sorted_files == files, 'sorted_files=%d (expected %d)' % (sorted_files, files)),
        ('sort-compares-a-file', sorted_files > 0 and sort_compares <= SORT_BOUND * sorted_files,
         'sort_compares=%d, %.3f a file (bound %.1f)' % (sort_compares, sort_compares / max(1, sorted_files), SORT_BOUND)),
    ]
    failed = 0
    for name, ok, words in rows:
        print(('PASS' if ok else 'FAIL'), 'status-lookups-%s-%s' % (name, a.tier), words, flush=True)
        failed += not ok
    print('status-lookups %s: %d/%d rows pass' % (a.tier, len(rows) - failed, len(rows)), flush=True)
    raise SystemExit(1 if failed else 0)


if __name__ == '__main__':
    main()
