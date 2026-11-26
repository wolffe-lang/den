#!/usr/bin/env python3
"""The validation passes a work-tree scan makes over its index value, counted.

A scan checks the index it is given, as index.serialize does: the version, each
entry, the extensions and the cache tree's spans. index.parse makes the same
checks, so a value it has just returned needs no second check, and neither does
a value a scan has checked since it last changed. A merge pull scans the work
tree five times on two index values; each scan checked its value twice.

The fixture is made with Git alone: 240 tracked files in 12 directories of two
subdirectories each, committed, so the index holds a cache tree; then one
tracked file is changed in the work tree and one untracked file is added, so
every scan has rows.
probes/scan-validate-client scans it four ways and prints each scan's
Snapshot.validations and its status rows:

  parsed-held  the value index.parse returned, held validated;
  changed      that value with one entry's stat word rewritten, not held
               validated (den's own value, as a transition makes one);
  plain        the parsed value through worktree.scan_index, not held;
  malformed    the parsed value with its last entry dropped, so its cache tree
               names more entries than it has, not held validated.

Rows:

  scan-validations-parsed     the held scan makes no pass;
  scan-validations-once       the changed value's scan makes exactly one;
  scan-validations-malformed  the dropped entry's value is refused
                              invalid_index (a value nothing has checked is
                              still checked);
  scan-validations-rows       the three scans' status rows are equal (a check
                              changes no row).

The counts are exact on every host and tier.
"""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess

TRACKED = 240
ROWS = '??:d03/new.txt; M:d05/s1/f03.txt;'  # in path order


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tier', choices=('native', 'release'), default='native')
    parser.add_argument('--wolf', required=True, help='the pinned wolf (tools/lib-toolchain.sh\'s $WOLF)')
    a = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = root / 'target' / 'runs' / ('scan-validations-' + a.tier)
    if out.exists():
        shutil.rmtree(out)
    work = out / 'case'
    work.mkdir(parents=True)
    git = os.environ['DEN_GIT']

    def run(args, cwd):
        p = subprocess.run([str(x) for x in args], cwd=cwd, capture_output=True)
        assert p.returncode == 0, (args, p.stdout[-300:], p.stderr[-300:])
        return p.stdout

    tracked = ['d%02d/s%d/f%02d.txt' % (d, s, i) for d in range(12) for s in range(2) for i in range(10)]
    assert len(tracked) == TRACKED
    run([git, 'init', '-q', '-b', 'main', '.'], work)
    for name in tracked:
        (work / name).parent.mkdir(parents=True, exist_ok=True)
        (work / name).write_text(name + '\n')
    run([git, 'add', '-A'], work)
    run([git, '-c', 'commit.gpgsign=false', 'commit', '-q', '-m', 'validations'], work)
    # Rows to compare: one tracked file changed in the work tree, one untracked.
    (work / 'd05/s1/f03.txt').write_text('changed in the work tree\n')
    (work / 'd03/new.txt').write_text('untracked\n')

    probe = root / 'target' / a.tier / 'scan-validate-client'
    probe.parent.mkdir(parents=True, exist_ok=True)
    flags = ['--release'] if a.tier == 'release' else []
    run([a.wolf, 'build', *flags, '--deny-warnings', root / 'probes/scan-validate-client/main.lu', '-o', probe], root)
    text = run([probe, work], work).decode()

    def field(pattern):
        found = re.search(pattern, text, re.M)
        assert found, (pattern, text)
        return found.group(1)

    held = int(field(r'^validations parsed-held=(\d+)$'))
    changed = int(field(r'^validations changed=(\d+)$'))
    plain = int(field(r'^validations plain=(\d+)$'))
    refused = field(r'^malformed refused=(.*)$')
    rows_held = field(r'^rows parsed-held=(.*)$')
    rows_changed = field(r'^rows changed=(.*)$')
    rows_plain = field(r'^rows plain=(.*)$')
    rows = [
        ('parsed', held == 0, 'validations=%d for the value index.parse returned, held validated (expected 0)' % held),
        ('once', changed == 1 and plain == 1,
         'validations=%d for a changed value and %d through scan_index, neither held (expected 1 each)' % (changed, plain)),
        ('malformed', 'invalid_index' in refused, 'a value whose cache tree names a dropped entry: refused %s' % refused),
        ('rows', rows_held == rows_changed == rows_plain == ROWS,
         'status rows of the three scans: %s, %s, %s (expected %s)' % (rows_held, rows_changed, rows_plain, ROWS)),
    ]
    failed = 0
    for name, ok, words in rows:
        print(('PASS' if ok else 'FAIL'), 'scan-validations-%s-%s' % (name, a.tier), words, flush=True)
        failed += not ok
    print('scan-validations %s: %d/%d rows pass' % (a.tier, len(rows) - failed, len(rows)), flush=True)
    raise SystemExit(1 if failed else 0)


if __name__ == '__main__':
    main()
